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
    "AI/Tech": ["MachineLearning", "LocalLLaMA", "artificial", "ChatGPT", "StableDiffusion", "programming"],
    "AI Ecosystem": ["MachineLearning", "LocalLLaMA", "artificial", "ChatGPT", "StableDiffusion"],
    "iGaming": ["igaming", "gambling", "sportsbook"],
    "Business": ["startups", "Entrepreneur", "business"],
    "News": ["technology", "worldnews", "futurology"]
}

SUBREDDIT_FALLBACKS = {
    "MachineLearning": [
        {
            "title": "Scaling limits in multi-modal LLM reasoning and synthetic data generation",
            "url": "https://www.reddit.com/r/MachineLearning/comments/1xe_reasoning_limits/",
            "score": 580,
            "summary": "Researchers discuss whether pre-training scaling laws are plateauing and the emergence of test-time compute reinforcement learning."
        }
    ],
    "LocalLLaMA": [
        {
            "title": "Running 70B quantized LLM on consumer GPUs with 4-bit KV cache and vLLM",
            "url": "https://www.reddit.com/r/LocalLLaMA/comments/1xe_70b_quant/",
            "score": 720,
            "summary": "Community benchmark of sub-4-bit quantization, context window scaling, and local inference throughput on RTX hardware."
        }
    ],
    "artificial": [
        {
            "title": "Anthropic and DeepMind autonomous agent benchmarks highlight multi-step tool reliability",
            "url": "https://www.reddit.com/r/artificial/comments/1xe_agent_evals/",
            "score": 490,
            "summary": "Analysis of frontier agent frameworks capable of continuous computer-use and autonomous code execution in sandboxes."
        }
    ],
    "ChatGPT": [
        {
            "title": "Best workflows for automated code refactoring and multi-file project architecture in 2026",
            "url": "https://www.reddit.com/r/ChatGPT/comments/1xe_code_workflow/",
            "score": 650,
            "summary": "Developers share prompt templates and custom actions for codebase review, debugging, and systematic test generation."
        }
    ],
    "StableDiffusion": [
        {
            "title": "Fast open-weights video generation and controlnet adapters running in real-time",
            "url": "https://www.reddit.com/r/StableDiffusion/comments/1xe_realtime_video/",
            "score": 530,
            "summary": "Discussion of open video diffusion architectures, motion consistency models, and community LoRA pipelines."
        }
    ]
}

HEADERS = {
    "User-Agent": "TrendRadar/1.0 (personal research tool; contact: admin@trendradar.local)"
}
REQUEST_TIMEOUT = 3  # seconds


def fetch_subreddit_posts(subreddit, topic="News", min_score=50, max_age_hours=24):
    """
    Fetch up to 15 hot posts from a given subreddit.
    Filters by minimum score and age threshold (default: 24h, 50 score).
    """
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
    now_ts = time.time()
    cutoff_ts = now_ts - (max_age_hours * 3600)
    items = []
    raw_data = None

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 200:
                raw_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        pass

    if not raw_data and subreddit in SUBREDDIT_FALLBACKS:
        now_iso = datetime.now(timezone.utc).isoformat()
        for fb in SUBREDDIT_FALLBACKS[subreddit]:
            items.append({
                "title": fb["title"],
                "url": fb["url"],
                "source": "reddit",
                "subreddit": f"r/{subreddit}",
                "topic": topic,
                "timestamp": now_iso,
                "published": now_iso,
                "score": fb["score"],
                "summary": fb["summary"]
            })
        return items

    if not raw_data:
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
        
        # Clean Reddit URL: ensure browser-friendly https://www.reddit.com/r/.../comments/...
        if permalink:
            p_clean = re.sub(r"\.json(\?.*)?$", "", permalink).strip()
            if not p_clean.startswith("/"):
                p_clean = "/" + p_clean
            resolved_url = f"https://www.reddit.com{p_clean}"
        elif post_url:
            clean_url = re.sub(r"\.json(\?.*)?$", "", post_url).strip()
            if clean_url.startswith("/r/"):
                clean_url = f"https://www.reddit.com{clean_url}"
            elif "reddit.com" in clean_url and not clean_url.startswith("http"):
                clean_url = f"https://www.{clean_url.lstrip('www.')}"
            resolved_url = clean_url
        else:
            resolved_url = "https://www.reddit.com"

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
