"""
aggregate.py — Consolidates, deduplicates, scores, classifies, and groups news items
into the new docs/data/news.json schema.

Schema:
{
  "updated": "2026-10-18T09:00:00Z",
  "topics": {
    "AI/Tech": {
      "briefing": "",
      "clusters": [
        { "label": "Anthropic", "items": [0, 2] }
      ],
      "items": [
        {
          "title": "...",
          "summary": "...",
          "url": "...",
          "sources": ["hn", "reddit"],
          "time": "2h",
          "score": 85,
          "velocity": "rising",
          "tag": "market"
        }
      ]
    }
  }
}
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def _load_env():
    """Load variables from local .env if present and not already in os.environ."""
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


_load_env()

DATA_DIR = os.path.join(ROOT, "docs", "data")
OUTPUT_NEWS_JSON = os.path.join(DATA_DIR, "news.json")

# Import Telegram notifier
try:
    import notify
except Exception:
    notify = None

# Import reddit, twitter & quora fetchers
try:
    from fetchers import reddit
except Exception:
    reddit = None

try:
    from fetchers import twitter
except Exception:
    twitter = None

try:
    from fetchers import quora
except Exception:
    quora = None

# Topic key mapping to standard UI tab labels
TOPIC_LABEL_MAP = {
    "ai-tech": "AI/Tech",
    "ai_tech": "AI/Tech",
    "igaming": "iGaming",
    "business": "Business",
    "news": "News",
    "funding": "Funding",
    "aquaculture-iot": "Aquaculture & IoT",
    "aquaculture_iot": "Aquaculture & IoT",
    "industry-news": "Industry News",
    "industry_news": "Industry News",
}


def are_similar_titles(t1, t2, threshold=0.80):
    """Check if two titles refer to the same story."""
    if not t1 or not t2:
        return False
    # Strip twitter account tag prefix like [@AnthropicAI]
    s1 = re.sub(r"^\[@[^\]]+\]\s*", "", str(t1))
    s2 = re.sub(r"^\[@[^\]]+\]\s*", "", str(t2))
    t1_clean = re.sub(r"[^\w\s]", "", s1.lower()).strip()
    t2_clean = re.sub(r"[^\w\s]", "", s2.lower()).strip()
    if not t1_clean or not t2_clean:
        return False
    if t1_clean == t2_clean:
        return True
    try:
        from rapidfuzz import fuzz
        return fuzz.token_sort_ratio(t1_clean, t2_clean) >= (threshold * 100)
    except Exception:
        import difflib
        return difflib.SequenceMatcher(None, t1_clean, t2_clean).ratio() >= threshold


def dedupe_and_merge_items(items):
    """
    Deduplicates items by exact URL or fuzzy title matching.
    Merges sources (e.g. ['hn'] + ['reddit'] -> ['hn', 'reddit']) so items
    participate in multi-source scoring and velocity calculation.
    """
    kept = []
    for it in items:
        url = (it.get("url") or "").strip().lower()
        title = (it.get("title") or "").strip()
        match_idx = None

        for idx, existing in enumerate(kept):
            e_url = (existing.get("url") or "").strip().lower()
            if url and e_url and url == e_url:
                match_idx = idx
                break
            e_title = (existing.get("title") or "").strip()
            if title and e_title and are_similar_titles(title, e_title):
                match_idx = idx
                break

        if match_idx is None:
            cloned = dict(it)
            cloned["sources"] = list(extract_item_sources(it))
            cloned.setdefault("source_timestamps", [])
            ts = it.get("timestamp") or it.get("published")
            if ts:
                cloned["source_timestamps"].append(ts)
            kept.append(cloned)
        else:
            target = kept[match_idx]
            # Merge sources
            merged_sources = set(target.get("sources") or [])
            merged_sources.update(extract_item_sources(it))
            target["sources"] = sorted(list(merged_sources))

            # Merge source timestamps
            ts = it.get("timestamp") or it.get("published")
            target_ts_list = target.setdefault("source_timestamps", [])
            if ts and ts not in target_ts_list:
                target_ts_list.append(ts)

            # Preserve highest score
            it_score = it.get("score")
            target_score = target.get("score")
            if isinstance(it_score, (int, float)):
                if not isinstance(target_score, (int, float)) or it_score > target_score:
                    target["score"] = it_score

            # Keep more detailed summary
            if len(it.get("summary") or "") > len(target.get("summary") or ""):
                target["summary"] = it["summary"]

    return kept

# 1. IMPACT TAG CLASSIFICATION PATTERNS
TAG_PATTERNS = {
    "tool": [
        r"\breleases?\b", r"\breleased\b", r"\blaunch(es|ed)?\b", r"\bopen-source\b",
        r"\bframeworks?\b", r"\blibrar(y|ies)\b", r"\bsdks?\b", r"\bapis?\b",
        r"\bbuilt\b", r"\bships?\b", r"\bshipped\b"
    ],
    "market": [
        r"\brevenue\b", r"\bgrowth\b", r"\bvaluations?\b", r"\bacquisitions?\b",
        r"\bacquires?\b", r"\bfundings?\b", r"\bmarkets?\b", r"\bipos?\b",
        r"\bpartnerships?\b", r"\bbillions?\b", r"\bmillions?\b", r"\braises?\b",
        r"\braised\b", r"\barr\b"
    ],
    "risk": [
        r"\bregulations?\b", r"\bcompliance\b", r"\bbans?\b", r"\bbanned\b",
        r"\brestricts?\b", r"\brestricted\b", r"\bsecurit(y|ies)\b",
        r"\bvulnerabilit(y|ies)\b", r"\bbreach(es)?\b", r"\bfines?\b",
        r"\bpenalt(y|ies)\b", r"\btightens?\b", r"\btightened\b", r"\baudits?\b"
    ]
}

# 2. KNOWN ENTITIES FOR CLUSTERING
KNOWN_ENTITIES = [
    "Anthropic", "OpenAI", "DeepMind", "Google", "Meta", "Microsoft", "Apple",
    "SpaceX", "Claude", "Gemini", "GPT-5", "GPT-4", "GPT", "Llama", "Starship",
    "Evolution Gaming", "UK Gambling Commission", "Gambling Commission", "BetMGM",
    "MGM Resorts", "Flutter", "FanDuel", "Pragmatic Play", "Notion", "Linear",
    "Stripe", "Cursor", "FastAPI", "TypeScript", "Stanford", "UC Berkeley",
    "Brazil", "Vietnam", "Singapore", "EU AI Act", "AI Act", "US Commerce",
    "Y Combinator", "YC", "Artemis", "NVIDIA", "Agent", "Coding Agent", "RAG",
    "Diffusion", "LLM", "Video Generation", "Benchmark"
]

STOP_WORDS = {
    "The", "A", "An", "How", "Why", "What", "When", "Where", "Who", "Is", "Are",
    "Was", "Were", "In", "On", "At", "To", "For", "With", "By", "From", "About",
    "Against", "Between", "Into", "Through", "During", "Before", "After", "Above",
    "Below", "Of", "And", "Or", "But", "Not", "No", "New", "Latest", "Top",
    "Major", "Global", "First", "Over", "Under", "More", "Most", "Some", "Many",
    "All", "Both", "Each", "Few", "Other", "Shows", "Beats", "Hits", "Adds",
    "Warns", "Calls", "Could", "Should", "Would", "May", "Might", "Must", "Can",
    "Will", "Just", "Now", "Today", "Rules", "Report", "Update"
}


def parse_datetime(val):
    """Safely parse various datetime formats into UTC datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc)
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)

    val_str = str(val).strip()
    try:
        return datetime.fromisoformat(val_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        pass

    try:
        dt = parsedate_to_datetime(val_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return None


def normalize_source_name(source):
    """Normalize source strings or feed names to standard tokens."""
    if not source:
        return "rss"
    s = str(source).lower().strip()
    if "hacker news" in s or "ycombinator" in s or s == "hn":
        return "hn"
    if "github" in s or s == "gh":
        return "gh"
    if "arxiv" in s:
        return "arxiv"
    if "reddit" in s:
        return "reddit"
    if "twitter" in s or s == "x" or "/x.com" in s:
        return "x"
    if "quora" in s:
        return "quora"
    return "rss"


def extract_item_sources(item):
    """Extract and deduplicate list of normalized sources for an item."""
    sources_set = set()

    # Direct sources list
    if isinstance(item.get("sources"), list):
        for s in item["sources"]:
            sources_set.add(normalize_source_name(s))

    # Single source
    if item.get("source"):
        sources_set.add(normalize_source_name(item["source"]))

    # Correlated sources from cross-source correlation
    if isinstance(item.get("correlated_with"), list):
        for s in item["correlated_with"]:
            sources_set.add(normalize_source_name(s))

    return sorted(list(sources_set)) if sources_set else ["rss"]


def calculate_velocity(item, now_dt):
    """
    Velocity calculation based on appearance times and source count:
    - If item appeared in 2+ sources within 3 hours -> 'rising'
    - If appeared in 1 source OR sources spread over 3-12 hours -> 'stable'
    - If only 1 source and older than 12 hours -> 'cooling'
    """
    sources = item.get("sources") or []
    pub_dt = parse_datetime(item.get("published") or item.get("meta") or item.get("_dt"))
    if not pub_dt:
        pub_dt = now_dt

    age_hours = max(0.0, (now_dt - pub_dt).total_seconds() / 3600.0)

    # Check for timestamps across multiple source appearances if available
    source_timestamps = item.get("source_timestamps") or []
    if len(source_timestamps) >= 2:
        parsed_ts = [parse_datetime(ts) for ts in source_timestamps if parse_datetime(ts)]
        if len(parsed_ts) >= 2:
            time_span_hours = (max(parsed_ts) - min(parsed_ts)).total_seconds() / 3600.0
            if time_span_hours <= 3.0:
                return "rising"
            if time_span_hours <= 12.0:
                return "stable"
            return "cooling" if age_hours > 12.0 else "stable"

    # Multi-source without separate timestamps: use publication age
    if len(sources) >= 2:
        if age_hours <= 3.0:
            return "rising"
        if age_hours <= 12.0:
            return "stable"
        return "cooling"

    # Single source
    if age_hours > 12.0:
        return "cooling"
    return "stable"


def classify_impact_tag(title, summary):
    """Classify item into 'tool', 'market', 'risk', or 'signal'."""
    text = f"{title or ''} {summary or ''}".lower()

    scores = {}
    for tag, patterns in TAG_PATTERNS.items():
        hits = 0
        for pattern in patterns:
            hits += len(re.findall(pattern, text, re.IGNORECASE))
        scores[tag] = hits

    # Check highest hit count
    best_tag = "signal"
    best_hits = 0
    # Tie-break priority: risk > market > tool
    for tag in ["risk", "market", "tool"]:
        if scores.get(tag, 0) > best_hits:
            best_hits = scores[tag]
            best_tag = tag

    return best_tag if best_hits > 0 else "signal"


def extract_clusters(items):
    """
    Group related items by entity overlap:
    - Extracts known entities and capitalized entities from titles
    - If 2+ items share an entity -> group them as a cluster
    - Returns: [{ 'label': entity_name, 'items': [index1, index2] }]
    """
    entity_to_indices = {}

    for idx, item in enumerate(items):
        title = item.get("title") or ""
        found_in_title = set()

        # 1. Match known entities
        for entity in KNOWN_ENTITIES:
            # Word boundary check for entity
            pattern = r"\b" + re.escape(entity) + r"\b"
            if re.search(pattern, title, re.IGNORECASE):
                found_in_title.add(entity)

        # 2. Extract capitalized phrases (NER heuristic)
        cap_candidates = re.findall(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*\b", title)
        for cand in cap_candidates:
            words = cand.split()
            # Skip if only stop words
            if all(w in STOP_WORDS for w in words):
                continue
            if len(cand) >= 3 and cand not in STOP_WORDS:
                found_in_title.add(cand)

        for ent in found_in_title:
            entity_to_indices.setdefault(ent, []).append(idx)

    # Filter entities that appear in 2+ items
    clusters = []
    seen_index_signatures = set()

    # Sort candidates by frequency of items descending
    sorted_entities = sorted(entity_to_indices.items(), key=lambda x: len(x[1]), reverse=True)

    for entity, indices in sorted_entities:
        if len(indices) < 2:
            continue

        # Deduplicate clusters with identical matching items
        sig = tuple(sorted(indices))
        if sig in seen_index_signatures:
            continue
        seen_index_signatures.add(sig)

        clusters.append({
            "label": entity,
            "items": sorted(indices)
        })

        if len(clusters) >= 5:
            break

    return clusters


def calculate_item_score(item, velocity):
    """
    Calculate 0-100 score:
    - Preserves existing score or converts relevance_score (1-5)
    - Multi-source = higher score
    - Velocity boost
    """
    raw_score = item.get("score")
    if isinstance(raw_score, (int, float)) and 10 <= raw_score <= 100:
        base_score = int(raw_score)
    else:
        rel = item.get("relevance_score")
        if isinstance(rel, (int, float)):
            base_score = int(rel * 16)  # 5 -> 80, 4 -> 64, 3 -> 48, etc.
        else:
            base_score = 45

    sources = item.get("sources") or []
    # Multi-source boost
    if len(sources) >= 3:
        base_score += 18
    elif len(sources) == 2:
        base_score += 10
    elif item.get("cross_source"):
        base_score += 10

    # Velocity boost
    if velocity == "rising":
        base_score += 6
    elif velocity == "cooling":
        base_score -= 4

    return max(15, min(98, base_score))


def format_relative_time(pub_dt, now_dt, fallback_time):
    """Format published datetime into relative string like '2h', '4h', '1d'."""
    if not pub_dt:
        return fallback_time or "today"

    delta = now_dt - pub_dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "just now"
    if total_seconds < 3600:
        minutes = max(1, total_seconds // 60)
        return f"{minutes}m"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h"
    days = delta.days
    return f"{days}d" if days > 0 else "today"


def process_topic_items(raw_items, now_dt):
    """Process a list of raw topic items into the new schema structure."""
    processed = []

    for item in raw_items:
        title = item.get("title") or "Untitled"
        summary = item.get("summary") or ""
        url = item.get("url") or "#"
        sources = extract_item_sources(item)

        pub_dt = parse_datetime(item.get("published") or item.get("meta") or item.get("_dt"))
        time_str = format_relative_time(pub_dt, now_dt, item.get("time") or item.get("meta"))

        temp_item = dict(item)
        temp_item["sources"] = sources
        velocity = calculate_velocity(temp_item, now_dt)
        tag = classify_impact_tag(title, summary)
        score = calculate_item_score(temp_item, velocity)

        entry = {
            "title": title,
            "summary": summary,
            "url": url,
            "sources": sources,
            "time": time_str,
            "score": score,
            "velocity": velocity,
            "tag": tag,
            "_raw_pub": pub_dt.isoformat() if pub_dt else None
        }
        for extra_field in ("source", "date", "engagement", "upvotes", "comments", "subreddit", "geo", "traffic"):
            if extra_field in item and item[extra_field] is not None:
                entry[extra_field] = item[extra_field]

        processed.append(entry)

    # Sort items by score descending
    processed.sort(key=lambda x: x["score"], reverse=True)

    # Extract clusters based on the sorted items list
    clusters = extract_clusters(processed)

    # Clean up internal temporary fields
    for p in processed:
        p.pop("_raw_pub", None)

    return processed, clusters


def build_aggregated_news(topics_data=None, out_dir=DATA_DIR):
    """
    Aggregate topic items into the new data/news.json format:
    {
      "updated": "ISO timestamp",
      "topics": {
        "AI/Tech": {
          "briefing": "",
          "clusters": [...],
          "items": [...]
        }
      }
    }
    """
    now_dt = datetime.now(timezone.utc)
    updated_iso = now_dt.isoformat()

    output_data = {
      "updated": updated_iso,
      "topics": {}
    }

    # Fetch Reddit items if reddit fetcher is available
    # Fetch Reddit & Twitter items if available
    reddit_items_by_topic = {}
    if reddit:
        try:
            print("[aggregate] Fetching Reddit posts for topics...")
            reddit_items_by_topic = reddit.fetch_all_reddit()
            for t_name, r_items in reddit_items_by_topic.items():
                if r_items:
                    print(f"  -> Fetched {len(r_items)} Reddit items for {t_name}")
        except Exception as e:
            print(f"[aggregate] Reddit fetching failed: {e}")

    twitter_items_by_topic = {}
    if twitter:
        try:
            print("[aggregate] Fetching X / Twitter posts for topics...")
            twitter_items_by_topic = twitter.fetch_all_twitter()
            for t_name, x_items in twitter_items_by_topic.items():
                if x_items:
                    print(f"  -> Fetched {len(x_items)} X items for {t_name}")
        except Exception as e:
            print(f"[aggregate] Twitter fetching failed: {e}")

    quora_items_by_topic = {}
    if quora:
        try:
            print("[aggregate] Fetching Quora discussions for topics...")
            quora_items_by_topic = quora.fetch_all_quora()
            for t_name, q_items in quora_items_by_topic.items():
                if q_items:
                    print(f"  -> Fetched {len(q_items)} Quora items for {t_name}")
        except Exception as e:
            print(f"[aggregate] Quora fetching failed: {e}")

    # 1. If topics_data is provided directly (from fetch.py)
    # Format expected: list of (topic_key, label, items) or dict
    collected_topics = {}

    if topics_data:
        if isinstance(topics_data, list):
            for entry in topics_data:
                if len(entry) >= 3:
                    topic_key, label, items = entry[0], entry[1], entry[2]
                else:
                    topic_key, items = entry[0], entry[1]
                    label = topic_key
                topic_name = TOPIC_LABEL_MAP.get(topic_key, label)
                collected_topics.setdefault(topic_name, []).extend(items)
        elif isinstance(topics_data, dict):
            for topic_key, val in topics_data.items():
                items = val.get("items", []) if isinstance(val, dict) else val
                label = val.get("label", topic_key) if isinstance(val, dict) else topic_key
                topic_name = TOPIC_LABEL_MAP.get(topic_key, label)
                collected_topics.setdefault(topic_name, []).extend(items)

    # 2. If topics_data is not provided or incomplete, load from existing JSON files in DATA_DIR
    if not collected_topics:
        candidate_files = [
            ("ai-tech.json", "AI/Tech"),
            ("funding.json", "Funding"),
            ("aquaculture-iot.json", "Aquaculture & IoT"),
            ("social-buzz.json", "Social Buzz"),
            ("business.json", "Business"),
            ("news.json", "News"),
            ("igaming.json", "iGaming"),
            ("industry-news.json", "Industry News")
        ]
        for filename, topic_name in candidate_files:
            file_path = os.path.join(out_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    if "topics" in content:
                        raw_items = content["topics"].get(topic_name, {}).get("items", [])
                    else:
                        raw_items = content.get("items", [])
                    if raw_items:
                        collected_topics.setdefault(topic_name, []).extend(raw_items)
                except Exception as e:
                    print(f"Warning: could not read {file_path}: {e}")

    # 3. Merge Reddit, Twitter, and Quora items, deduplicate, score, and group
    all_topic_names = set(collected_topics.keys())
    all_topic_names.update(reddit_items_by_topic.keys())
    all_topic_names.update(twitter_items_by_topic.keys())
    all_topic_names.update(quora_items_by_topic.keys())
    # Ensure canonical topic order: AI/Tech, Funding, Aquaculture & IoT, Social Buzz, Business, News, iGaming
    ordered_topics = ["AI/Tech", "Funding", "Aquaculture & IoT", "Social Buzz", "Business", "News", "iGaming"]
    for extra in sorted(all_topic_names):
        if extra not in ordered_topics:
            ordered_topics.append(extra)

    for topic_name in ordered_topics:
        base_items = collected_topics.get(topic_name, [])
        reddit_items = reddit_items_by_topic.get(topic_name, [])
        twitter_items = twitter_items_by_topic.get(topic_name, [])
        quora_items = quora_items_by_topic.get(topic_name, [])
        combined = base_items + reddit_items + twitter_items + quora_items
        if not combined:
            continue

        # Deduplicate & merge cross-source items
        deduped = dedupe_and_merge_items(combined)
        processed_items, clusters = process_topic_items(deduped, now_dt)

        # Generate topic briefing (AI if key available, otherwise template)
        briefing = generate_briefing(topic_name, processed_items)

        output_data["topics"][topic_name] = {
            "briefing": briefing,
            "clusters": clusters,
            "items": processed_items
        }

    # 4. Check watchlist keywords against items with score >= threshold & send Telegram alerts
    check_watchlist_and_alert(output_data, out_dir)

    # Write output to docs/data/news.json
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "news.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Write flat list to docs/data/signals.json for Opportunity Radar / downstream consumers
    all_signals = []
    for topic_name, topic_data in output_data.get("topics", {}).items():
        for item in topic_data.get("items", []):
            item_copy = dict(item)
            item_copy["topic"] = topic_name
            all_signals.append(item_copy)
    signals_file = os.path.join(out_dir, "signals.json")
    with open(signals_file, "w", encoding="utf-8") as f:
        json.dump(all_signals, f, indent=2, ensure_ascii=False)

    print(f"Aggregated {len(output_data['topics'])} topics into {out_file} and exported {len(all_signals)} signals to {signals_file}")
    return output_data


# --- BRIEFING GENERATION & WATCHLIST TELEGRAM ALERTS ---

def generate_ai_briefing(topic_name, top_items, api_key=None):
    """Use Gemini Flash (primary) or Claude Haiku (secondary) to generate an executive daily briefing."""
    import requests
    # 1. Primary: Use Gemini if GEMINI_API_KEY is present
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        models = ["gemini-2.0-flash", "gemini-1.5-flash"]
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                prompt = (
                    f"Bạn là chuyên gia phân tích công nghệ của Trend Radar. Hãy viết một bản tin điều hành (Executive Daily Briefing) "
                    f"khoảng 3-4 câu sắc sảo, tự nhiên bằng tiếng Việt cho chủ đề {topic_name}.\n\n"
                    f"Dựa trên các bài viết/dự án nổi bật nhất hôm nay:\n"
                )
                for idx, it in enumerate(top_items[:5], 1):
                    prompt += f"{idx}. {it.get('title')}: {it.get('summary')}\n"
                prompt += (
                    "\nYêu cầu:\n"
                    "- Nêu rõ dự án/chủ đề dẫn đầu và lý do quan trọng.\n"
                    "- Tóm tắt xu hướng công nghệ nổi bật và tác động thực tế.\n"
                    "- Trả lời bằng đoạn văn sạch, tự nhiên, súc tích, không dùng gạch đầu dòng hay lời chào/kết."
                )

                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}
                }
                resp = requests.post(url, headers={"x-goog-api-key": gemini_key}, json=payload, timeout=15)
                if resp.ok:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        if text:
                            print(f"[aggregate] Generated Gemini briefing ({model}) for {topic_name}")
                            return text
            except Exception as e:
                print(f"[aggregate] Warning: Gemini {model} briefing failed for {topic_name}: {e}")

    # 2. Secondary fallback: Try Claude Haiku if ANTHROPIC_API_KEY is present
    anthropic_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            prompt = (
                f"Hãy viết một bản tóm tắt điều hành (Executive Daily Briefing) khoảng 3-4 câu tự nhiên bằng tiếng Việt cho chủ đề {topic_name}:\n"
            )
            for idx, it in enumerate(top_items[:5], 1):
                prompt += f"{idx}. {it.get('title')}: {it.get('summary')}\n"
            prompt += "\nNêu rõ giải pháp dẫn đầu, xu hướng nổi bật và tác động chính. Không dùng gạch đầu dòng."

            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.ok:
                data = resp.json()
                content = data.get("content", [{}])[0].get("text", "").strip()
                if content:
                    return content
        except Exception as e:
            print(f"[aggregate] Warning: Claude Haiku briefing generation failed for {topic_name}: {e}")
    return None


def generate_briefing(topic_name, items):
    """
    Generate daily briefing for each topic:
    - If GEMINI_API_KEY or ANTHROPIC_API_KEY exists, try AI-generated natural briefing.
    - Fallback: Rich Executive Template containing top story summaries and market velocity pulse.
    """
    if not items:
        return f"Chưa có tín hiệu công nghệ mới nào được ghi nhận cho {topic_name} hôm nay."

    top_items = sorted(items, key=lambda x: x.get("score") or 0, reverse=True)
    rising_count = sum(1 for it in items if (it.get("velocity") or "").lower() == "rising")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if api_key or gemini_key:
        ai_briefing = generate_ai_briefing(topic_name, top_items, api_key)
        if ai_briefing:
            return ai_briefing

    # Rich Executive Template fallback
    it1 = top_items[0]
    score1 = it1.get("score", 0)
    title1 = it1.get("title", "")
    summary1 = (it1.get("summary") or "").strip()
    if summary1 and len(summary1) > 160:
        summary1 = summary1[:157] + "..."

    lines = []
    lines.append(
        f"🌟 <strong>Tiêu điểm dẫn đầu:</strong> <strong>{title1}</strong> (Score {score1})"
        + (f" — <em>{summary1}</em>" if summary1 else "")
        + "."
    )

    if len(top_items) >= 2:
        it2 = top_items[1]
        score2 = it2.get("score", 0)
        title2 = it2.get("title", "")
        summary2 = (it2.get("summary") or "").strip()
        if summary2 and len(summary2) > 120:
            summary2 = summary2[:117] + "..."

        trending_parts = [f"<strong>{title2}</strong> (Score {score2})" + (f": {summary2}" if summary2 else "")]

        if len(top_items) >= 3:
            it3 = top_items[2]
            title3 = it3.get("title", "")
            trending_parts.append(f"<strong>{title3}</strong>")

        lines.append(f"🔥 <strong>Xu hướng nổi bật:</strong> " + " và ".join(trending_parts) + ".")

    pulse_info = f"📊 <strong>Nhịp đập hôm nay:</strong> Ghi nhận tổng cộng {len(top_items)} tín hiệu theo dõi."
    if rising_count > 0:
        pulse_info += f" Trong đó có <strong>{rising_count} tín hiệu đang bứt phá mạnh (Rising Velocity)</strong>."
    else:
        pulse_info += " Các tín hiệu duy trì mức lan tỏa và quan tâm ổn định trên các nền tảng."
    lines.append(pulse_info)

    return "<br><br>".join(lines)


def load_watchlist_config(out_dir):
    """Load keywords and threshold from data/watchlist.json."""
    candidate_paths = [
        os.path.join(out_dir, "watchlist.json"),
        os.path.join(ROOT, "docs", "data", "watchlist.json"),
        os.path.join(ROOT, "data", "watchlist.json")
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {
        "keywords": ["iGaming regulation", "Claude", "Vietnam tech", "Anthropic"],
        "threshold": 50
    }


def check_watchlist_and_alert(output_data, out_dir):
    """
    Check all items against data/watchlist.json keywords with score >= threshold.
    Flag matched items and send Telegram alerts if enabled.
    """
    watchlist_config = load_watchlist_config(out_dir)
    keywords = watchlist_config.get("keywords", [])
    threshold = watchlist_config.get("threshold", 35)
    lower_keywords = [k.lower().strip() for k in keywords if k]

    matched_alerts = []

    for topic_name, topic_data in output_data.get("topics", {}).items():
        for item in topic_data.get("items", []):
            score = item.get("score") or 0

            search_text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            for kw in lower_keywords:
                if kw in search_text:
                    item["watchlist_matched"] = kw
                    effective_score = max(score, threshold)
                    item["score"] = effective_score
                    matched_alerts.append({
                        "keyword": kw,
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "score": effective_score,
                        "topic": topic_name
                    })
                    break

    # Send Telegram alert only if explicitly enabled (default false to prevent spamming;
    # Opportunity Radar Phase 5B/5C handles intelligent alerting with 3 dedicated templates).
    alert_enabled = os.environ.get("WATCHLIST_TELEGRAM_ALERT", "false").lower() in ("true", "1", "yes")
    if alert_enabled and notify and matched_alerts:
        print(f"[aggregate] Found {len(matched_alerts)} watchlist matches with score >= {threshold}")
        # Group into a single digest message instead of spamming 1 message per match
        lines = [f"🔔 TỔNG HỢP WATCHLIST ({len(matched_alerts)} mục khớp)"]
        for m in matched_alerts[:8]:
            lines.append(f"• [{m['keyword']}] {m['title']} ({m['score']}đ)\n  {m['url']}")
        if len(matched_alerts) > 8:
            lines.append(f"... và {len(matched_alerts) - 8} mục khác.")
        notify.send_message("\n".join(lines))



if __name__ == "__main__":
    build_aggregated_news()
