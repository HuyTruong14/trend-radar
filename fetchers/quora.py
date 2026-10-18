"""
fetchers/quora.py — Fetches trending Quora questions and discussions via Google Custom Search API.

Endpoints:
  https://www.googleapis.com/customsearch/v1?key={KEY}&cx={CX_ID}&q={query}&dateRestrict=d1&num=5

Configuration:
  - GOOGLE_CSE_KEY: Google Custom Search JSON API Key
  - GOOGLE_CSE_ID: Programmable Search Engine ID (CX)

Topics:
  - AI/Tech: "AI artificial intelligence LLM site:quora.com"
  - iGaming: "online gambling igaming regulation site:quora.com"
  - Business: "startup SaaS business strategy site:quora.com"
  - News: "technology trend 2026 site:quora.com"

Output schema:
  List of dicts:
  {
    "title": "...",
    "url": "https://www.quora.com/...",
    "source": "quora",
    "topic": "...",
    "timestamp": "ISO-8601",
    "published": "ISO-8601",
    "score": 50,
    "summary": "..."
  }
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

TOPIC_QUERIES = {
    "AI/Tech": "AI artificial intelligence LLM site:quora.com",
    "iGaming": "online gambling igaming regulation site:quora.com",
    "Business": "startup SaaS business strategy site:quora.com",
    "News": "technology trend 2026 site:quora.com"
}

REQUEST_TIMEOUT = 10  # seconds


def get_api_credentials():
    """Retrieve Google Custom Search API credentials from environment."""
    key = os.environ.get("GOOGLE_CSE_KEY") or os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CSE_CX")
    return key, cx


def clean_quora_title(raw_title):
    """Clean up Quora titles by stripping trailing branding."""
    if not raw_title:
        return "Untitled Quora Discussion"
    # Remove trailing ' - Quora'
    cleaned = re.sub(r"\s*-\s*Quora\s*$", "", raw_title.strip(), flags=re.IGNORECASE)
    return cleaned.strip()


def fetch_topic_quora(topic, query=None, max_results=5):
    """
    Fetch trending Quora discussions for a specific topic using Google Custom Search API.
    Uses dateRestrict=d1 (past 24 hours).
    """
    key, cx = get_api_credentials()
    if not key or not cx:
        # Fallback gracefully if credentials are not configured yet
        return []

    q = query or TOPIC_QUERIES.get(topic, f"{topic} site:quora.com")
    params = {
        "key": key,
        "cx": cx,
        "q": q,
        "dateRestrict": "d1",
        "num": max(1, min(10, max_results))
    }
    encoded_url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"
    now_iso = datetime.now(timezone.utc).isoformat()
    items = []

    req = urllib.request.Request(
        encoded_url,
        headers={"User-Agent": "TrendRadar/1.0 (personal research tool)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                print(f"[quora] HTTP {response.status} searching for {topic}", file=sys.stderr)
                return []
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[quora] Error querying Google CSE for {topic}: {e}", file=sys.stderr)
        return []

    for item in payload.get("items", []):
        raw_title = item.get("title") or ""
        link = item.get("link") or ""
        snippet = item.get("snippet") or ""

        if not link or not raw_title:
            continue

        title = clean_quora_title(raw_title)

        # Try extracting published date from metadata if available
        published_iso = now_iso
        pagemap = item.get("pagemap", {})
        metatags = pagemap.get("metatags", [{}])
        if metatags and isinstance(metatags, list):
            meta = metatags[0]
            candidate_dt = meta.get("article:published_time") or meta.get("datePublished")
            if candidate_dt:
                published_iso = candidate_dt

        items.append({
            "title": title,
            "url": link,
            "source": "quora",
            "topic": topic,
            "timestamp": published_iso,
            "published": published_iso,
            "score": 50,
            "summary": snippet
        })

    return items


def fetch_all_quora(max_results=5):
    """
    Fetch Quora discussions across all configured topics.
    Total: 4 queries x 1 call = 4 queries/day (within 100 free query quota).
    """
    key, cx = get_api_credentials()
    if not key or not cx:
        print("[quora] GOOGLE_CSE_KEY or GOOGLE_CSE_ID not set in environment. Skipping Quora search.")
        return {}

    results_by_topic = {}
    for topic, query in TOPIC_QUERIES.items():
        results_by_topic[topic] = fetch_topic_quora(topic, query=query, max_results=max_results)
        time.sleep(0.2)
    return results_by_topic


def main():
    """Standalone CLI test runner."""
    key, cx = get_api_credentials()
    if not key or not cx:
        print("[quora] Note: GOOGLE_CSE_KEY and GOOGLE_CSE_ID are not set in environment or .env.", file=sys.stderr)
        print("[]")
        return

    all_quora_items = []
    for topic, query in TOPIC_QUERIES.items():
        items = fetch_topic_quora(topic, query=query)
        all_quora_items.extend(items)
        time.sleep(0.2)

    print(json.dumps(all_quora_items, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
