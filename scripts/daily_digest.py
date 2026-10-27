#!/usr/bin/env python3
"""
scripts/daily_digest.py — Daily Digest Engine (Phase 10)

Synthesizes all events from yesterday across 4 core pillars:
1. 🎯 Cơ hội nổi bật (Top max 3, stage >= research; tag '(đã gửi alert)' if already notified)
2. 💰 Dòng tiền hôm qua (Deals Gọi vốn / M&A, max 3)
3. 🔥 Chủ đề nóng (Top 3 hot topics across Reddit, Twitter, Google Trends with summary_vi)
4. 📊 Số liệu nhanh (Total signals, new opportunities, build_ready, research, watch, triple signal, velocity)

If yesterday was quiet (no build_ready/research items) -> sends short 'Hôm qua yên ắng' message.
Produces:
- docs/data/digest_YYYYMMDD.json
- docs/data/digest_latest.json
Sends via Telegram Bot API when configured or --send-telegram flag is passed.
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone, timedelta

# Import notify helper
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import notify

try:
    from summary_vi import translate_title_vi
except ImportError:
    try:
        from scripts.summary_vi import translate_title_vi
    except ImportError:
        translate_title_vi = None

BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "docs", "data")
DEFAULT_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://huytruong14.github.io/trend-radar/")

SECTOR_MAP_VI = {
    "igaming": "iGaming & Betting",
    "aquatech": "Thủy sản & Nước",
    "agtech": "Nông nghiệp",
    "hardware": "Phần cứng & IoT",
    "robotics": "Robotics",
    "ai_infra": "Hạ tầng AI",
    "energy": "Năng lượng",
    "fintech": "Fintech",
    "healthtech": "Y tế",
    "other": "Công nghệ & Startup"
}


def load_json(filepath, default=None):
    if not os.path.exists(filepath):
        return default if default is not None else {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[daily_digest] Warning: failed to load {filepath}: {e}")
        return default if default is not None else {}


def get_target_date(specified_date=None, opps=None):
    """
    Determine target date string (YYYY-MM-DD).
    Default logic: Yesterday in VN timezone (UTC+7).
    Fallback: If yesterday has 0 opportunities and today/latest date has items,
    fallback to the latest available date in opportunities.json.
    """
    if specified_date:
        return specified_date

    # Vietnam time: UTC+7
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    yesterday = (vn_now - timedelta(days=1)).strftime("%Y-%m-%d")

    if opps:
        available_dates = set(o.get("last_seen") for o in opps if o.get("last_seen"))
        if yesterday in available_dates:
            return yesterday
        # If running today on fresh fetch or test, find latest available date
        if available_dates:
            latest = sorted(list(available_dates))[-1]
            return latest

    return yesterday


def format_funding_deal_line(deal):
    """
    Format deal according to prompt template:
    • [Ai] gọi [bao nhiêu] — [ngành gì]
    • [Ai] mua [công ty nào] — [ngành gì]
    """
    title = (deal.get("title") or "").strip()
    sector = deal.get("sector") or deal.get("funding_sector") or "other"
    sector_name = SECTOR_MAP_VI.get(sector, "Công nghệ")
    deal_type = deal.get("deal_type") or "Xu hướng"
    amount = deal.get("funding_amount") or deal.get("amount") or "N/A"

    # M&A detection
    m_acq = re.search(r"^(.*?)\s+(?:acquires|to acquire|buys)\s+(.*?)(?:\s+to\b|\s+for\b|\s+in\b|$)", title, re.IGNORECASE)
    if m_acq:
        buyer = m_acq.group(1).strip()
        target = m_acq.group(2).strip()
        return f"• {buyer} mua {target} — {sector_name}"

    m_stake = re.search(r"^(.*?)\s+(?:takes majority stake in|invests in)\s+(.*?)(?:\s+to\b|\s+for\b|$)", title, re.IGNORECASE)
    if m_stake:
        buyer = m_stake.group(1).strip()
        target = m_stake.group(2).strip()
        return f"• {buyer} mua cổ phần chi phối {target} — {sector_name}"

    # Funding detection
    m_raise = re.search(r"^(.*?)\s+(?:raises|raised|secures|lands|nabs|closes)\s+(.*?)(?:from\b|led\b|at\b|for\b|$)", title, re.IGNORECASE)
    if m_raise:
        who = m_raise.group(1).strip()
        detail = m_raise.group(2).strip()
        amt = amount if amount != "N/A" else detail
        return f"• {who} gọi {amt} — {sector_name}"

    if deal_type == "Gọi vốn" and amount != "N/A":
        return f"• {title[:60]} — gọi {amount} ({sector_name})"

    if len(title) > 70:
        title = title[:67].rstrip() + "..."
    return f"• {title} — {sector_name}"


def compile_daily_digest(target_date=None, dashboard_url=DEFAULT_DASHBOARD_URL):
    """
    Extract and structure digest data across the 4 pillars.
    """
    # 1. Load source files
    opps_file = os.path.join(DATA_DIR, "opportunities.json")
    signals_file = os.path.join(DATA_DIR, "signals.json")
    history_file = os.path.join(DATA_DIR, "sent_history.json")
    funding_file = os.path.join(DATA_DIR, "funding.json")
    social_file = os.path.join(DATA_DIR, "social_buzz.json")

    opps_all = load_json(opps_file, default=[])
    signals_all = load_json(signals_file, default=[])
    sent_history = load_json(history_file, default={})
    funding_data = load_json(funding_file, default={})
    social_data = load_json(social_file, default={})

    # 2. Determine target date
    date_str = get_target_date(target_date, opps_all)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_formatted = date_obj.strftime("%d/%m/%Y")

    # 3. Filter yesterday's opportunities
    target_opps = [o for o in opps_all if o.get("last_seen") == date_str]
    # If no opps found for date_str and no specific date requested, fallback to all opps
    if not target_opps and not target_date:
        target_opps = opps_all

    # Sort by total descending
    target_opps_sorted = sorted(target_opps, key=lambda x: (x.get("total", 0), x.get("stage") == "build_ready"), reverse=True)

    # 4. Pillar 1: Cơ hội nổi bật (top 3, stage >= research)
    high_tier_opps = [o for o in target_opps_sorted if o.get("stage") in ["build_ready", "research"]]
    top_opportunities = []
    for opp in high_tier_opps[:3]:
        oid = opp.get("id")
        # Check if already sent in Telegram alerts
        alert_sent = False
        if oid in sent_history:
            entry = sent_history[oid]
            if isinstance(entry, dict) and entry.get("times_sent", 0) > 0:
                alert_sent = True

        top_opportunities.append({
            "id": oid,
            "title": opp.get("title", "").strip(),
            "title_vi": opp.get("title_vi") or (translate_title_vi(opp.get("title", ""), opp.get("summary", "")) if translate_title_vi else opp.get("title", "").strip()),
            "total": opp.get("total", 0),
            "stage": opp.get("stage", "watch"),
            "summary_vi": (opp.get("summary_vi") or opp.get("summary") or "").strip(),
            "alert_sent": alert_sent,
            "url": opp.get("url") or (opp.get("sources", [{}])[0].get("url") if opp.get("sources") else ""),
            "signal_type": opp.get("signal_type", []),
            "velocity": opp.get("velocity", "steady")
        })

    quiet_day = len(high_tier_opps) == 0

    # 5. Pillar 2: Dòng tiền hôm qua (Deals Gọi vốn / M&A, max 3)
    deals_candidates = []
    # From opportunities with price_shift / funding amount / deal_type
    for o in target_opps:
        dt = o.get("deal_type")
        amt = o.get("funding_amount", "N/A")
        sig = o.get("signal_type", [])
        if "price_shift" in sig or dt in ["Gọi vốn", "M&A"] or amt != "N/A":
            deals_candidates.append({
                "title": o.get("title", ""),
                "deal_type": dt or "Xu hướng",
                "amount": amt,
                "funding_amount": amt,
                "sector": o.get("funding_sector", "other"),
                "url": o.get("url") or (o.get("sources", [{}])[0].get("url") if o.get("sources") else "")
            })

    # Also check items in funding.json
    funding_items = funding_data.get("items", []) if isinstance(funding_data, dict) else (funding_data if isinstance(funding_data, list) else [])
    for fit in funding_items:
        t = fit.get("title", "")
        s = fit.get("summary", "")
        combined = f"{t} {s}".lower()
        if any(k in combined for k in ["raises", "raised", "secures", "lands", "seed round", "series a", "series b", "acquires", "acquisition", "merger"]):
            # Avoid duplicate title
            if not any(d["title"].lower() == t.lower() for d in deals_candidates):
                deals_candidates.append({
                    "title": t,
                    "deal_type": "M&A" if ("acquires" in combined or "acquisition" in combined) else "Gọi vốn",
                    "amount": "N/A",
                    "funding_amount": "N/A",
                    "sector": "agtech" if any(k in combined for k in ["agtech", "farm", "crop", "livestock", "food"]) else "other",
                    "url": fit.get("url", "")
                })

    # Prioritize items with actual amounts or M&A
    def deal_priority(d):
        p = 0
        if d.get("amount") and d["amount"] != "N/A":
            p += 10
        if d.get("deal_type") in ["M&A", "Gọi vốn"]:
            p += 5
        return p

    deals_candidates = sorted(deals_candidates, key=deal_priority, reverse=True)
    funding_deals = []
    for d in deals_candidates[:3]:
        line = format_funding_deal_line(d)
        d_copy = dict(d)
        d_copy["formatted_text"] = line
        d_copy["sector_vi"] = SECTOR_MAP_VI.get(d.get("sector"), "Công nghệ")
        d_copy["title_vi"] = translate_title_vi(d.get("title", ""), "") if translate_title_vi else d.get("title", "")
        funding_deals.append(d_copy)

    # 6. Pillar 3: Chủ đề nóng (Top 3 across Reddit, Twitter, Google Trends)
    hot_topics = []
    reddit_posts = social_data.get("reddit_posts", [])
    twitter_trends = social_data.get("twitter_trends", [])
    g_keywords = social_data.get("google_trends_keywords", [])
    g_rss = social_data.get("google_trends_rss", [])

    # Pick 1 top Reddit post
    if reddit_posts:
        r_sorted = sorted(reddit_posts, key=lambda x: x.get("upvotes", 0) or x.get("engagement", 0), reverse=True)
        r_top = r_sorted[0]
        hot_topics.append({
            "topic": r_top.get("title", "").strip(),
            "source": f"Reddit {r_top.get('subreddit', 'r/technology')}",
            "summary_vi": r_top.get("summary_vi") or "Thảo luận công nghệ và cộng đồng sôi nổi",
            "engagement": f"{r_top.get('upvotes', 0)} upvotes",
            "url": r_top.get("url", "")
        })

    # Pick 1 top Twitter trend
    if twitter_trends:
        tw_sorted = sorted(twitter_trends, key=lambda x: x.get("engagement", 0), reverse=True)
        tw_top = tw_sorted[0]
        hot_topics.append({
            "topic": tw_top.get("keyword", "").strip(),
            "source": "Twitter/X",
            "summary_vi": tw_top.get("summary_vi") or "Chủ đề tâm điểm thảo luận lan truyền nhanh trên X",
            "engagement": f"{tw_top.get('tweets', '')} tweets",
            "url": tw_top.get("url", "")
        })

    # Pick 1 top Google Trends
    if g_keywords:
        gk_sorted = sorted(g_keywords, key=lambda x: x.get("volume", 0), reverse=True)
        gk_top = gk_sorted[0]
        hot_topics.append({
            "topic": gk_top.get("keyword", "").strip(),
            "source": "Google Trends",
            "summary_vi": gk_top.get("summary_vi") or "Lượng tìm kiếm người dùng đang gia tăng mạnh",
            "engagement": f"{gk_top.get('change', 'Tăng')}",
            "url": gk_top.get("link", "")
        })
    elif g_rss:
        gr_top = g_rss[0]
        hot_topics.append({
            "topic": gr_top.get("title", "").strip(),
            "source": "Google Trends VN",
            "summary_vi": gr_top.get("summary_vi") or "Xu hướng tìm kiếm đột biến",
            "engagement": f"{gr_top.get('traffic', '1000+')}",
            "url": gr_top.get("url", "")
        })

    # If < 3 items, fill from remaining reddit or twitter
    if len(hot_topics) < 3 and len(reddit_posts) > 1:
        for r_extra in r_sorted[1:]:
            if len(hot_topics) >= 3:
                break
            hot_topics.append({
                "topic": r_extra.get("title", "").strip(),
                "source": f"Reddit {r_extra.get('subreddit', 'r/technology')}",
                "summary_vi": r_extra.get("summary_vi") or "Thảo luận cộng đồng sôi nổi",
                "engagement": f"{r_extra.get('upvotes', 0)} upvotes",
                "url": r_extra.get("url", "")
            })

    # 7. Pillar 4: Số liệu nhanh (Stats)
    total_signals_count = len(signals_all)
    new_opps_count = len(target_opps)
    build_ready_count = sum(1 for o in target_opps if o.get("stage") == "build_ready")
    research_count = sum(1 for o in target_opps if o.get("stage") == "research")
    watch_count = sum(1 for o in target_opps if o.get("stage") == "watch")

    triple_signals_data = social_data.get("triple_signals", [])
    triple_count = len(triple_signals_data)
    triple_theme = triple_signals_data[0].get("theme", "") if triple_count > 0 else ""

    rising_count = sum(1 for o in target_opps if o.get("velocity") == "rising")
    fading_count = sum(1 for o in target_opps if o.get("velocity") == "fading")

    stats = {
        "total_signals": total_signals_count,
        "new_opportunities": new_opps_count,
        "build_ready": build_ready_count,
        "research": research_count,
        "watch": watch_count,
        "triple_signals": triple_count,
        "triple_signal_theme": triple_theme,
        "rising": rising_count,
        "fading": fading_count,
        "labels_vi": {
            "total_signals": "Tổng tín hiệu mới",
            "new_opportunities": "Cơ hội mới",
            "build_ready": "Sẵn sàng triển khai",
            "research": "Cần nghiên cứu",
            "watch": "Theo dõi",
            "triple_signals": "Tín hiệu 3 chiều",
            "rising": "Tăng trưởng nhanh",
            "fading": "Hạ nhiệt"
        }
    }

    # 8. Render Telegram Text strictly according to specification
    lines = [
        f"📰 TREND RADAR — BẢN TIN NGÀY {date_formatted}\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    if quiet_day:
        # Quiet Day Template
        lines = [
            f"📰 TREND RADAR — BẢN TIN NGÀY {date_formatted}\n",
            "😴 Hôm qua yên ắng — không có cơ hội mới đáng chú ý.\n",
            f"📊 Tín hiệu mới: {total_signals_count} | Tất cả ở mức watch hoặc thấp hơn.\n",
            f"🔗 Dashboard: {dashboard_url}"
        ]
        telegram_text = "\n".join(lines).strip()
    else:
        # Full 4-pillar Template
        # 1. Cơ hội nổi bật
        lines.append("\n🎯 CƠ HỘI NỔI BẬT")
        for opp in top_opportunities:
            emoji = "🔴" if opp["stage"] == "build_ready" else "⚡"
            alert_tag = " (đã gửi alert)" if opp["alert_sent"] else ""
            lines.append(f"\n{emoji} {opp['total']}/9 · {opp['title']}{alert_tag}")
            lines.append(f"→ {opp['summary_vi']}")

        remaining_high = len(high_tier_opps) - len(top_opportunities)
        if remaining_high > 0:
            lines.append(f"\n(và {remaining_high} cơ hội khác trên dashboard)")

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")

        # 2. Dòng tiền hôm qua (nếu có deals)
        if funding_deals:
            lines.append("\n💰 DÒNG TIỀN HÔM QUA")
            for fd in funding_deals:
                lines.append(fd["formatted_text"])
            lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")

        # 3. Chủ đề nóng (Top 3)
        if hot_topics:
            lines.append("\n🔥 CHỦ ĐỀ NÓNG")
            for idx, ht in enumerate(hot_topics[:3], 1):
                lines.append(f"\n{idx}. {ht['topic']} — {ht['source']}")
                lines.append(f"   → {ht['summary_vi']}")
            lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")

        # 4. Số liệu nhanh
        lines.append("\n📊 SỐ LIỆU NHANH")
        lines.append(f"• Tổng tín hiệu mới: {total_signals_count} | Cơ hội mới: {new_opps_count}")
        lines.append(f"• Build-ready: {build_ready_count} | Research: {research_count} | Watch: {watch_count}")
        if triple_count > 0:
            lines.append(f"• Triple Signal: Có ({triple_count}) → {triple_theme}")
        else:
            lines.append("• Triple Signal: Không")
        lines.append(f"• Velocity: {rising_count} rising ↑ | {fading_count} fading ↓")

        # Phase 13: Tech Glossary Highlight
        tech_glossary_file = os.path.join(DATA_DIR, "tech_glossary.json")
        if os.path.exists(tech_glossary_file):
            try:
                with open(tech_glossary_file, "r", encoding="utf-8") as f:
                    glossary_data = json.load(f)
                rising_techs = [(k, v) for k, v in glossary_data.items() if v.get("trend") == "rising"]
                if rising_techs:
                    rising_techs.sort(key=lambda x: (x[1].get("mentions_this_week", 0) >= 5, x[1].get("change_pct", 0), x[1].get("mentions_this_week", 0)), reverse=True)
                    top_t, top_info = rising_techs[0]
                    pct = top_info.get("change_pct", 0)
                    lines.append(f"• Công nghệ nổi bật: {top_t} (↑+{pct}%)")
            except Exception:
                pass

        # Phase 16: AI Disruption Highlight
        disruption_file = os.path.join(DATA_DIR, "disruption_current.json")
        if os.path.exists(disruption_file):
            try:
                with open(disruption_file, "r", encoding="utf-8") as f:
                    disruption_data = json.load(f)
                sorted_disrupt = sorted(
                    [(k, v) for k, v in disruption_data.items() if isinstance(v, dict)],
                    key=lambda x: (x[1].get("ai_pct", 0), x[1].get("mentions_this_week", 0)),
                    reverse=True
                )
                if sorted_disrupt:
                    top_k, top_v = sorted_disrupt[0]
                    lines.append(f"• Skill bị can thiệp mạnh nhất: {top_v.get('name_vi', top_k)} ({top_v.get('ai_pct')}%)")
            except Exception:
                pass

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"\n🔗 Xem chi tiết: {dashboard_url}")

        telegram_text = "\n".join(lines).strip()

    digest_payload = {
        "date": date_str,
        "date_formatted": date_formatted,
        "generated_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "quiet_day": quiet_day,
        "top_opportunities": top_opportunities,
        "remaining_high_tier_count": max(0, len(high_tier_opps) - len(top_opportunities)),
        "funding_deals": funding_deals,
        "hot_topics": hot_topics[:3],
        "stats": stats,
        "dashboard_url": dashboard_url,
        "telegram_text": telegram_text
    }

    return digest_payload


def save_digest_files(digest_payload):
    """Save date-stamped file and digest_latest.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    date_clean = digest_payload["date"].replace("-", "")
    dated_filename = f"digest_{date_clean}.json"
    dated_filepath = os.path.join(DATA_DIR, dated_filename)
    latest_filepath = os.path.join(DATA_DIR, "digest_latest.json")

    with open(dated_filepath, "w", encoding="utf-8") as f:
        json.dump(digest_payload, f, ensure_ascii=False, indent=2)
    print(f"[daily_digest] Wrote dated digest to {dated_filepath}")

    with open(latest_filepath, "w", encoding="utf-8") as f:
        json.dump(digest_payload, f, ensure_ascii=False, indent=2)
    print(f"[daily_digest] Wrote latest digest to {latest_filepath}")

    # Also save to docs/data/news/digest_latest.json (Phase 17 - Nhóm D2)
    news_dir = os.path.join(DATA_DIR, "news")
    os.makedirs(news_dir, exist_ok=True)
    with open(os.path.join(news_dir, "digest_latest.json"), "w", encoding="utf-8") as f:
        json.dump(digest_payload, f, ensure_ascii=False, indent=2)

    return dated_filepath, latest_filepath


def main():
    parser = argparse.ArgumentParser(description="Trend Radar — Daily Digest Engine (Phase 10)")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (defaults to yesterday UTC+7)")
    parser.add_argument("--send-telegram", action="store_true", help="Send formatted digest to Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Print digest without sending")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL, help="Custom dashboard URL")
    args = parser.parse_args()

    print("==================================================")
    print("📰 TREND RADAR — DAILY DIGEST GENERATION (PHASE 10)")
    print("==================================================")

    digest = compile_daily_digest(target_date=args.date, dashboard_url=args.dashboard_url)
    dated_file, latest_file = save_digest_files(digest)

    print("\n--- TELEGRAM MESSAGE PREVIEW ---")
    print(digest["telegram_text"])
    print("--------------------------------\n")

    if args.send_telegram and not args.dry_run:
        print("[daily_digest] Sending Daily Digest to Telegram...")
        success = notify.send_message(digest["telegram_text"])
        if success:
            print("[daily_digest] ✅ Daily Digest sent to Telegram successfully!")
        else:
            print("[daily_digest] ⚠️ Telegram send failed or skipped (check tokens/logs)")
    else:
        print("[daily_digest] Telegram sending skipped (use --send-telegram to send)")

    print("[daily_digest] Daily Digest completed successfully.")


if __name__ == "__main__":
    main()
