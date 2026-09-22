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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
OUT_DIR = os.path.join(ROOT, "docs", "data")
HEADERS = {"User-Agent": "trend-radar-bot/1.0 (personal research tool)"}
TIMEOUT = 20


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
    seen = set()
    out = []
    for it in items:
        key = (it.get("url") or it.get("title", "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


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

    items = dedupe(items)

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

    log(f"  -> {len(fresh)} fresh items (from {len(items)} fetched)")
    return fresh


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    os.makedirs(OUT_DIR, exist_ok=True)
    max_items = config.get("max_items_per_source", 15)
    freshness_days = config.get("freshness_days", 14)

    manifest = {"updated": datetime.now(timezone.utc).isoformat(), "topics": []}

    for topic_key, cfg in config["topics"].items():
        results = build_topic(topic_key, cfg, max_items, freshness_days)
        out_path = os.path.join(OUT_DIR, f"{topic_key}.json")
        with open(out_path, "w") as f:
            json.dump({"label": cfg.get("label", topic_key), "items": results}, f, indent=2)
        manifest["topics"].append({"key": topic_key, "label": cfg.get("label", topic_key), "count": len(results)})

    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    log("Done.")


if __name__ == "__main__":
    main()
