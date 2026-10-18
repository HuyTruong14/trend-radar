"""
fetchers/twitter.py — Fetches recent tweets via public Nitter RSS bridges.

Instances:
  - nitter.privacydev.net
  - nitter.poast.org
  - nitter.lucabrunox.com

Account tracking per topic:
  - AI/Tech: @AnthropicAI, @OpenAI, @GoogleDeepMind, @kaborozu
  - iGaming: @CalvinAyre, @GamblingComp, @iaborusz
  - Business: @ycombinator, @paulg, @naval
  - News: @Reuters, @BBCBreaking, @TechCrunch

Output schema:
  List of dicts:
  {
    "title": "...",
    "url": "https://x.com/...",
    "source": "x",
    "topic": "...",
    "timestamp": "ISO-8601",
    "published": "ISO-8601",
    "score": 60,
    "summary": "..."
  }
"""

import html
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Nitter instances to try in order
NITTER_INSTANCES = [
    "nitter.privacydev.net",
    "nitter.poast.org",
    "nitter.lucabrunox.com"
]

TOPIC_ACCOUNTS = {
    "AI/Tech": ["@AnthropicAI", "@OpenAI", "@GoogleDeepMind", "@kaborozu"],
    "iGaming": ["@CalvinAyre", "@GamblingComp", "@iaborusz"],
    "Business": ["@ycombinator", "@paulg", "@naval"],
    "News": ["@Reuters", "@BBCBreaking", "@TechCrunch"]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TrendRadar/1.0; +https://github.com/HuyTruong14/trend-radar)"
}
REQUEST_TIMEOUT = 8  # seconds per attempt


def clean_text(raw_html):
    """Strip HTML tags and unescape HTML entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_html)
    return html.unescape(text).strip()


def parse_pubdate(pubdate_str):
    """Parse RSS pubDate string into UTC datetime."""
    if not pubdate_str:
        return None
    try:
        dt = parsedate_to_datetime(pubdate_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_user_rss(username, topic="News", max_age_hours=24):
    """
    Fetch RSS for a given user trying multiple Nitter instances.
    Returns list of items filtered to the last max_age_hours (default 24h).
    """
    clean_username = username.lstrip("@").strip()
    now_dt = datetime.now(timezone.utc)
    cutoff_ts = now_dt.timestamp() - (max_age_hours * 3600)
    items = []

    for instance in NITTER_INSTANCES:
        url = f"https://{instance}/{clean_username}/rss"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                if response.status != 200:
                    continue
                xml_content = response.read()

            root = ET.fromstring(xml_content)
            channel = root.find("channel")
            if channel is None:
                continue

            for entry in channel.findall("item"):
                pub_elem = entry.find("pubDate")
                pub_str = pub_elem.text if pub_elem is not None else ""
                pub_dt = parse_pubdate(pub_str)
                if not pub_dt or pub_dt.timestamp() < cutoff_ts:
                    continue

                title_elem = entry.find("title")
                desc_elem = entry.find("description")
                link_elem = entry.find("link")

                raw_title = title_elem.text if title_elem is not None else ""
                raw_desc = desc_elem.text if desc_elem is not None else ""
                raw_link = link_elem.text if link_elem is not None else ""

                text = clean_text(raw_desc or raw_title)
                if not text:
                    continue

                # Title truncated to 120 chars
                title = text[:120].strip()
                if len(text) > 120:
                    title += "..."

                # Format URL as clean x.com link
                clean_link = raw_link
                for inst in NITTER_INSTANCES:
                    if inst in clean_link:
                        clean_link = clean_link.replace(f"https://{inst}/", "https://x.com/").replace(f"http://{inst}/", "https://x.com/")

                iso_time = pub_dt.isoformat()

                items.append({
                    "title": f"[{username}] {title}",
                    "url": clean_link,
                    "source": "x",
                    "topic": topic,
                    "timestamp": iso_time,
                    "published": iso_time,
                    "score": 60,
                    "summary": text
                })

            # If successfully fetched from this instance, exit instance loop
            return items

        except Exception:
            # Try next instance
            continue

    return []


def fetch_topic_twitter(topic, accounts=None, max_age_hours=24):
    """Fetch tweets for all accounts in a given topic."""
    accts = accounts or TOPIC_ACCOUNTS.get(topic, [])
    topic_items = []
    for acct in accts:
        tweets = fetch_user_rss(acct, topic=topic, max_age_hours=max_age_hours)
        topic_items.extend(tweets)
        time.sleep(0.3)
    return topic_items


def fetch_all_twitter(max_age_hours=24):
    """
    Fetch tweets across all configured topics.
    Returns dict mapping topic_name -> list of tweet items.
    """
    results_by_topic = {}
    for topic, accts in TOPIC_ACCOUNTS.items():
        results_by_topic[topic] = fetch_topic_twitter(topic, accts, max_age_hours=max_age_hours)
    return results_by_topic


def main():
    """Standalone CLI test runner."""
    all_tweets = []
    for topic, accts in TOPIC_ACCOUNTS.items():
        for acct in accts:
            tweets = fetch_user_rss(acct, topic=topic)
            all_tweets.extend(tweets)
            time.sleep(0.3)

    print(json.dumps(all_tweets, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
