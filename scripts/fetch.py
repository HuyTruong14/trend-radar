"""
Trend Radar — fetches weak-signal + mainstream data points from free sources
(Hacker News, arXiv, GitHub, RSS feeds) and writes JSON files that the
docs/index.html dashboard reads.

Run locally:  python scripts/fetch.py
Run in CI:    triggered by .github/workflows/fetch-trends.yml
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import requests
import yaml
from rapidfuzz import fuzz

import notify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
OUT_DIR = os.path.join(ROOT, "docs", "data")
HISTORY_DIR = os.path.join(OUT_DIR, "history")
HEADERS = {"User-Agent": "trend-radar-bot/1.0 (personal research tool)"}
TIMEOUT = 20

DUP_THRESHOLD = 85  # rapidfuzz token_sort_ratio: >= this on title -> same story
CORRELATION_WINDOW_HOURS = 48
ALERT_SCORE_THRESHOLD = 4
AI_MODEL = "claude-sonnet-5"
AI_BATCH_LIMIT = 40


def log(msg):
    print(f"[trend-radar] {msg}", flush=True)


def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except Exception as e:
        log(f"  ! request failed: {url} -> {e}")
        return None


def parse_dt(value):
    """Best-effort parse of various date formats into a UTC datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    return None


def within_freshness(dt, days):
    if dt is None:
        return True  # keep items we couldn't date rather than silently dropping them
    return dt >= datetime.now(timezone.utc) - timedelta(days=days)


# ---------------------------------------------------------------- Hacker News
def fetch_hackernews(keywords, max_items):
    items = []
    for kw in keywords:
        r = safe_get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": kw, "tags": "story", "hitsPerPage": max_items},
        )
        if not r:
            continue
        for hit in r.json().get("hits", []):
            items.append(
                {
                    "source": "Hacker News",
                    "title": hit.get("title") or hit.get("story_title") or "(no title)",
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "matched_keyword": kw,
                    "score": hit.get("points", 0),
                    "meta": f"{hit.get('points', 0)} pts · {hit.get('num_comments', 0)} comments",
                    "published": hit.get("created_at"),
                }
            )
        time.sleep(0.3)
    return items


# ------------------------------------------------------------------- arXiv
def fetch_arxiv(categories, keywords, max_items):
    items = []
    clauses = []
    for cat in categories:
        clauses.append(f"cat:{cat}")
    for kw in keywords:
        clauses.append(f'abs:"{kw}"')
    if not clauses:
        return items
    search_query = "+OR+".join(quote(c) for c in clauses)
    url = (
        "http://export.arxiv.org/api/query"
        f"?search_query={search_query}&sortBy=submittedDate&sortOrder=descending&max_results={max_items}"
    )
    r = safe_get(url)
    if not r:
        return items
    feed = feedparser.parse(r.text)
    for entry in feed.entries:
        items.append(
            {
                "source": "arXiv",
                "title": re.sub(r"\s+", " ", entry.get("title", "(no title)")).strip(),
                "url": entry.get("link"),
                "matched_keyword": ", ".join(categories) if categories else "",
                "score": None,
                "meta": entry.get("published", "")[:10],
                "published": entry.get("published"),
            }
        )
    return items


# --------------------------------------------------------------- GitHub search
def fetch_github(queries, max_items):
    items = []
    token = os.environ.get("GITHUB_TOKEN")
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Accept"] = "application/vnd.github+json"
    since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    for q in queries:
        r = None
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": f"{q} pushed:>{since}", "sort": "stars", "order": "desc", "per_page": max_items},
                headers=headers,
                timeout=TIMEOUT,
            )
            r.raise_for_status()
        except Exception as e:
            log(f"  ! github search failed for '{q}': {e}")
            continue
        for repo in r.json().get("items", []):
            items.append(
                {
                    "source": "GitHub",
                    "title": repo.get("full_name"),
                    "url": repo.get("html_url"),
                    "matched_keyword": q,
                    "score": repo.get("stargazers_count", 0),
                    "meta": f"{repo.get('stargazers_count', 0)} stars · {repo.get('description') or ''}"[:140],
                    "published": repo.get("pushed_at"),
                }
            )
        time.sleep(0.3)
    return items


# ------------------------------------------------------------------- RSS
def fetch_rss(feed_urls, max_items):
    items = []
    for feed_url in feed_urls:
        r = safe_get(feed_url)
        if not r:
            continue
        parsed = feedparser.parse(r.content)
        for entry in parsed.entries[:max_items]:
            items.append(
                {
                    "source": parsed.feed.get("title", feed_url),
                    "title": entry.get("title", "(no title)"),
                    "url": entry.get("link"),
                    "matched_keyword": "",
                    "score": None,
                    "meta": entry.get("published", "")[:16],
                    "published": entry.get("published"),
                }
            )
    return items


def dedupe(items):
    """Merge near-duplicate items (same story, different title wording/URL).

    Exact URL match is treated as an automatic duplicate. Otherwise, titles
    are compared with rapidfuzz token_sort_ratio; a score >= DUP_THRESHOLD is
    considered the same story. Between duplicates, keep the one with the
    higher `score` (GitHub stars, HN points); if scores aren't comparable,
    keep whichever came first.
    """
    kept = []
    for it in items:
        title = (it.get("title") or "").strip().lower()
        url = (it.get("url") or "").strip().lower()
        match_idx = None
        for i, k in enumerate(kept):
            k_url = (k.get("url") or "").strip().lower()
            if url and k_url and url == k_url:
                match_idx = i
                break
            k_title = (k.get("title") or "").strip().lower()
            if title and k_title and fuzz.token_sort_ratio(title, k_title) >= DUP_THRESHOLD:
                match_idx = i
                break
        if match_idx is None:
            kept.append(it)
            continue
        existing = kept[match_idx]
        new_score, old_score = it.get("score"), existing.get("score")
        if new_score is not None and old_score is not None:
            if new_score > old_score:
                kept[match_idx] = it
        elif new_score is not None and old_score is None:
            kept[match_idx] = it
        # else: keep the existing (earlier) item
    return kept


def _extract_json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def score_items_with_ai(items, topic_label):
    """Batch-score a topic's items with one Claude API call.

    Adds `summary` (1-sentence Vietnamese) and `relevance_score` (1-5 int)
    to each item in place. On any failure (missing key, network, bad JSON),
    logs and leaves summary/relevance_score as None rather than crashing —
    a scoring failure for one topic must not stop the other topics.
    """
    if not items:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log("  ! ANTHROPIC_API_KEY not set — skipping AI scoring")
        for it in items:
            it["summary"] = None
            it["relevance_score"] = None
        return

    to_score = items[:AI_BATCH_LIMIT]
    skipped = len(items) - len(to_score)
    if skipped > 0:
        log(f"  ! {skipped} item(s) skipped for AI scoring (batch limit {AI_BATCH_LIMIT}, kept newest)")

    results = None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        payload = [{"title": it.get("title") or "", "meta": it.get("meta") or ""} for it in to_score]
        system_prompt = (
            "Bạn là trợ lý phân tích trend. Với danh sách item JSON đầu vào (mỗi item có "
            "title, meta), trả về DUY NHẤT một JSON array cùng thứ tự, cùng số lượng phần tử "
            "với đầu vào. Mỗi phần tử có 2 field: \"summary\" (tóm tắt 1 câu tiếng Việt) và "
            "\"relevance_score\" (số nguyên 1-5, 5 = rất đáng chú ý với người theo dõi trend "
            "AI/iGaming/business sớm). Không kèm text nào khác ngoài JSON array."
        )
        message = client.messages.create(
            model=AI_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Chu de: {topic_label}\n\nItems:\n{json.dumps(payload, ensure_ascii=False)}",
                }
            ],
        )
        raw_text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        results = json.loads(_extract_json_text(raw_text))
        if not isinstance(results, list) or len(results) != len(to_score):
            raise ValueError(f"expected {len(to_score)} scored items, got {results!r}"[:200])
    except Exception as e:
        log(f"  ! AI scoring failed for topic '{topic_label}': {e}")
        results = None

    for idx, it in enumerate(to_score):
        res = results[idx] if results else None
        if isinstance(res, dict):
            it["summary"] = res.get("summary")
            score = res.get("relevance_score")
            try:
                it["relevance_score"] = int(score) if score is not None else None
            except (TypeError, ValueError):
                it["relevance_score"] = None
        else:
            it["summary"] = None
            it["relevance_score"] = None

    for it in items[len(to_score):]:
        it["summary"] = None
        it["relevance_score"] = None


def correlate_cross_source(items):
    """Flag items covering the same story across >=2 independent sources.

    Two items are "the same story" if their titles are fuzzy-similar
    (>= DUP_THRESHOLD), they come from different sources, and their
    published dates are within CORRELATION_WINDOW_HOURS of each other.
    Runs after dedupe() so it never confuses two copies of one article
    for cross-source coverage.
    """
    n = len(items)
    matches = [set() for _ in range(n)]
    parsed_dates = [parse_dt(it.get("published")) for it in items]

    for i in range(n):
        title_i = (items[i].get("title") or "").strip().lower()
        source_i = items[i].get("source")
        if not title_i or parsed_dates[i] is None:
            continue
        for j in range(i + 1, n):
            source_j = items[j].get("source")
            if not source_j or source_i == source_j:
                continue
            title_j = (items[j].get("title") or "").strip().lower()
            if not title_j or parsed_dates[j] is None:
                continue
            delta_hours = abs((parsed_dates[i] - parsed_dates[j]).total_seconds()) / 3600
            if delta_hours > CORRELATION_WINDOW_HOURS:
                continue
            if fuzz.token_sort_ratio(title_i, title_j) >= DUP_THRESHOLD:
                matches[i].add(source_j)
                matches[j].add(source_i)

    for idx, it in enumerate(items):
        correlated = sorted(matches[idx])
        it["cross_source"] = bool(correlated)
        it["correlated_with"] = correlated


def _format_alert_line(idx, it):
    tags = []
    score = it.get("relevance_score")
    if isinstance(score, int) and score >= ALERT_SCORE_THRESHOLD:
        tags.append(f"score {score}")
    if it.get("cross_source"):
        sources = it.get("correlated_with") or []
        tags.append("🔥 cross-source: " + (" + ".join(sources) if sources else "?"))
    title = it.get("title") or "(no title)"
    url = it.get("url") or ""
    return f"{idx}. [{', '.join(tags)}] {title} — {url}"


def build_alert_message(topic_label, items):
    """Return a Telegram message for a topic's standout items, or None.

    Standout = relevance_score >= ALERT_SCORE_THRESHOLD or cross_source.
    Returns None (send nothing) when no item in this topic qualifies —
    silence is the normal case, not an error.
    """
    qualifying = [
        it
        for it in items
        if (isinstance(it.get("relevance_score"), int) and it["relevance_score"] >= ALERT_SCORE_THRESHOLD)
        or it.get("cross_source")
    ]
    if not qualifying:
        return None

    lines = [f"🔥 Trend Radar — {topic_label} ({len(qualifying)} tín hiệu đáng chú ý)"]
    lines += [_format_alert_line(i, it) for i, it in enumerate(qualifying, 1)]
    return "\n".join(lines)


def update_history(topic_key, items, history_days):
    """Append/replace today's rolling summary entry for a topic's history.

    Stores aggregate counts only (never full item content), so the file
    stays small no matter how long the workflow runs daily. One entry per
    calendar date: re-running the same day replaces that day's entry
    instead of appending a duplicate. Entries older than history_days are
    dropped on every write.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{topic_key}.json")

    history = []
    if os.path.exists(path):
        try:
            with open(path) as f:
                loaded = json.load(f)
            if not isinstance(loaded, list):
                raise ValueError("expected a JSON array")
            history = loaded
        except Exception as e:
            log(f"  ! history file for '{topic_key}' unreadable ({e}) — recreating from empty")
            history = []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    scores = [it.get("relevance_score") for it in items if isinstance(it.get("relevance_score"), int)]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    by_source, by_keyword = {}, {}
    cross_source_count = 0
    for it in items:
        src = it.get("source") or ""
        by_source[src] = by_source.get(src, 0) + 1
        kw = it.get("matched_keyword") or ""
        by_keyword[kw] = by_keyword.get(kw, 0) + 1
        if it.get("cross_source"):
            cross_source_count += 1

    entry = {
        "date": today,
        "total_items": len(items),
        "avg_relevance_score": avg_score,
        "cross_source_count": cross_source_count,
        "by_source": by_source,
        "by_keyword": by_keyword,
    }

    history = [h for h in history if isinstance(h, dict) and h.get("date") != today]
    history.append(entry)

    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=history_days - 1)).isoformat()
    history = [h for h in history if isinstance(h.get("date"), str) and h["date"] >= cutoff]
    history.sort(key=lambda h: h.get("date", ""))

    with open(path, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return entry


def build_topic(topic_key, cfg, max_items, freshness_days):
    log(f"Fetching topic: {topic_key}")
    items = []

    if cfg.get("hackernews"):
        items += fetch_hackernews(cfg.get("keywords", []), max_items)

    arxiv_cfg = cfg.get("arxiv") or {}
    if arxiv_cfg.get("categories") or arxiv_cfg.get("keywords"):
        items += fetch_arxiv(arxiv_cfg.get("categories", []), arxiv_cfg.get("keywords", []), max_items)

    gh_queries = cfg.get("github_search") or []
    if gh_queries:
        items += fetch_github(gh_queries, max_items)

    rss_feeds = cfg.get("rss") or []
    if rss_feeds:
        items += fetch_rss(rss_feeds, max_items)

    raw_count = len(items)
    items = dedupe(items)
    dup_count = raw_count - len(items)
    if dup_count:
        log(f"  -> {dup_count} near-duplicate(s) merged by dedupe ({raw_count} -> {len(items)})")

    # attach parsed datetime for sorting/filtering, then drop stale items
    fresh = []
    for it in items:
        dt = parse_dt(it.get("published"))
        it["_dt"] = dt.isoformat() if dt else None
        if within_freshness(dt, freshness_days):
            fresh.append(it)

    fresh.sort(key=lambda x: x["_dt"] or "", reverse=True)
    for it in fresh:
        it.pop("_dt", None)

    log(f"  -> {len(fresh)} fresh items (from {raw_count} fetched)")

    score_items_with_ai(fresh, cfg.get("label", topic_key))
    correlate_cross_source(fresh)
    cross_source_count = sum(1 for it in fresh if it.get("cross_source"))
    if cross_source_count:
        log(f"  -> {cross_source_count} item(s) flagged cross-source")

    return fresh


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    os.makedirs(OUT_DIR, exist_ok=True)
    max_items = config.get("max_items_per_source", 15)
    freshness_days = config.get("freshness_days", 14)
    history_days = config.get("history_days", 60)

    manifest = {"updated": datetime.now(timezone.utc).isoformat(), "topics": []}

    for topic_key, cfg in config["topics"].items():
        try:
            results = build_topic(topic_key, cfg, max_items, freshness_days)
        except Exception as e:
            log(f"  ! topic '{topic_key}' failed entirely: {e} — skipping, other topics continue")
            continue
        out_path = os.path.join(OUT_DIR, f"{topic_key}.json")
        with open(out_path, "w") as f:
            json.dump({"label": cfg.get("label", topic_key), "items": results}, f, indent=2)
        manifest["topics"].append({"key": topic_key, "label": cfg.get("label", topic_key), "count": len(results)})

        try:
            update_history(topic_key, results, history_days)
        except Exception as e:
            log(f"  ! history update failed for '{topic_key}': {e} — skipping history for this topic")

        try:
            alert_msg = build_alert_message(cfg.get("label", topic_key), results)
            if alert_msg:
                if notify.send_message(alert_msg):
                    log(f"  -> Telegram alert sent for '{topic_key}'")
                else:
                    log(f"  ! Telegram alert not sent for '{topic_key}' (see notify log above)")
        except Exception as e:
            log(f"  ! alert failed for '{topic_key}': {e} — continuing")

    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    log("Done.")


if __name__ == "__main__":
    main()
