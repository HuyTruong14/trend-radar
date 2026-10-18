"""
fetchers/reddit.py — Fetches hot posts from subreddits via public JSON endpoints.

Endpoints:
  https://www.reddit.com/r/{subreddit}/hot.json?limit=15

Filters:
  - Posts within the last 24 hours
  - Minimum 50 upvotes

Output schema:
  List of dicts:
  {
    "title": "...",
    "url": "...",
    "source": "reddit",
    "topic": "...",
    "timestamp": "ISO-8601",
    "score": 120,
    "summary": "..."
  }
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
import urllib.request
import urllib.error

# Subreddits mapped per topic
TOPIC_SUBREDDITS = {
    "AI/Tech": ["MachineLearning", "LocalLLaMA", "programming"],
    "iGaming": ["igaming", "gambling", "sportsbook"],
    "Business": ["startups", "Entrepreneur", "business"],
    "News": ["technology", "worldnews", "futurology"]
}

HEADERS = {
    "User-Agent": "TrendRadar/1.0 (personal research tool; contact: admin@trendradar.local)"
}
REQUEST_TIMEOUT = 10  # seconds


def fetch_subreddit_posts(subreddit, topic="News", min_score=50, max_age_hours=24):
    """
    Fetch up to 15 hot posts from a given subreddit.
    Filters by minimum score and age threshold (default: 24h, 50 score).
    """
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
    now_ts = time.time()
    cutoff_ts = now_ts - (max_age_hours * 3600)
    items = []

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                print(f"[reddit] HTTP {response.status} fetching r/{subreddit}", file=sys.stderr)
                return []
            raw_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[reddit] Error fetching r/{subreddit}: {e}", file=sys.stderr)
        return []

    data_children = raw_data.get("data", {}).get("children", [])
    for child in data_children:
        post = child.get("data", {})
        
        # Check pinned / stickied posts
        if post.get("stickied"):
            continue

        score = post.get("score", 0)
        created_utc = post.get("created_utc", 0)

        # Filters: score >= 50 and within last 24h
        if score < min_score:
            continue
        if created_utc < cutoff_ts:
            continue

        title = (post.get("title") or "").strip()
        if not title:
            continue

        permalink = post.get("permalink") or ""
        post_url = post.get("url") or ""
        
        # Use external link if not a self-post/internal reddit link, otherwise permalink
        if not post_url or post_url.startswith("/r/") or "reddit.com" in post_url:
            resolved_url = f"https://reddit.com{permalink}" if permalink else post_url
        else:
            resolved_url = post_url

        iso_timestamp = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
        selftext = (post.get("selftext") or "").strip()
        summary = selftext[:300] if selftext else title

        items.append({
            "title": title,
            "url": resolved_url,
            "source": "reddit",
            "topic": topic,
            "timestamp": iso_timestamp,
            "published": iso_timestamp,
            "score": score,
            "summary": summary
        })

    return items


def fetch_topic_reddit(topic, subreddits=None, min_score=50, max_age_hours=24):
    """Fetch and aggregate reddit posts for a specific topic."""
    subs = subreddits or TOPIC_SUBREDDITS.get(topic, [])
    topic_items = []
    for sub in subs:
        posts = fetch_subreddit_posts(sub, topic=topic, min_score=min_score, max_age_hours=max_age_hours)
        topic_items.extend(posts)
        # Gentle rate-limit between subreddit requests
        time.sleep(0.5)
    return topic_items


def fetch_all_reddit(min_score=50, max_age_hours=24):
    """
    Fetch reddit items for all configured topics.
    Returns a dictionary mapping topic name -> list of items.
    """
    results_by_topic = {}
    for topic, subs in TOPIC_SUBREDDITS.items():
        results_by_topic[topic] = fetch_topic_reddit(topic, subs, min_score=min_score, max_age_hours=max_age_hours)
    return results_by_topic


def main():
    """CLI entry point for standalone testing."""
    all_items = []
    for topic, subs in TOPIC_SUBREDDITS.items():
        for sub in subs:
            posts = fetch_subreddit_posts(sub, topic=topic)
            all_items.extend(posts)
            time.sleep(0.3)

    print(json.dumps(all_items, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
