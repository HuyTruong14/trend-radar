"""
scripts/score.py — Opportunity Radar Scoring Engine (Phase 1)

Reads trend signals from docs/data/news.json (or signals.json),
tags signals into 4 opportunity types, scores them across 3 durability/leverage filters,
applies source-diversity multiplier, determines action stage (drop / watch / research / build_ready),
and outputs ranked opportunities to docs/data/opportunities.json.

Zero external network calls — runs purely on local aggregated data.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "docs", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "opportunities.json")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")
NEWS_FILE = os.path.join(DATA_DIR, "news.json")


# ==================== 4 SIGNAL TYPES ====================
# pain_repeat: Nỗi đau lặp lại (Than phiền, vấn đề, khó khăn, bugs, bottlenecks)
PAIN_KEYWORDS = [
    r"\b(issue|issues|problem|problems|pain|frustrat\w*|struggle\w*|bug|bugs|error|bottleneck|broken)\b",
    r"\b(terrible|hate|sucks|difficult|slow|annoying|crash\w*|fail\w*|hard to)\b",
    r"(khó khăn|vấn đề|bất cập|lỗi|ức chế|than phiền|nghẽn|chậm chạp|rắc rối)"
]

# price_shift: Lệch giá / chi phí (Giá linh kiện, token, cloud, chi phí vận hành biến động)
PRICE_KEYWORDS = [
    r"\b(price|pricing|cost|costs|expensive|cheap|token|rate limit|tier|billing|subscription|\$)\b",
    r"\b(gpu|cloud cost|hardware|overhead|margin|revenue|valuation|cut cost|budget)\b",
    r"(chi phí|giá cả|đắt đỏ|tốn kém|bảng giá|thu phí|lợi nhuận|cắt giảm)"
]

# supply_gap: Khoảng trống cung ("Có tool nào làm X không?", chưa có đáp án, alternative)
GAP_KEYWORDS = [
    r"\b(alternative to|alternative for|looking for|is there any|why is there no|missing feature)\b",
    r"\b(competitor|gap|unsupported|need a tool|any tool|no good tool|wish there was|unmet)\b",
    r"(tìm tool|chưa có|khoảng trống|thay thế cho|giải pháp cho|không có công cụ|thiếu)"
]

# tech_cheap: Công nghệ vừa đủ rẻ (Repo open-source mới, mô hình rẻ đi, chạy local)
TECH_CHEAP_KEYWORDS = [
    r"\b(open-source|open source|github\.com|self-host\w*|lightweight|local model|ollama|llama)\b",
    r"\b(run locally|small model|efficient|repo|framework|library|sdk|minimal|free tier|slm)\b",
    r"(mã nguồn mở|miễn phí|tự host|chạy local|mô hình nhỏ|nhẹ|tối ưu chi phí)"
]


# ==================== 3 FILTER LAYERS (0–3 POINTS) ====================
# Durability: Nhu cầu gốc không mất trong 10 năm
DURABLE_CORE_KEYWORDS = [
    r"\b(infrastructure|devops|database|security|pipeline|workflow|automation|compliance)\b",
    r"\b(finance|payment|legal|logistics|health|energy|storage|auth|backup|monitoring|enterprise)\b",
    r"(hạ tầng|cơ sở dữ liệu|bảo mật|tự động hóa|luồng việc|pháp lý|thanh toán|lưu trữ|quản trị)"
]
DURABLE_MID_KEYWORDS = [
    r"\b(developer tool|dev tool|productivity|analytics|search|testing|scraper|extraction)\b",
    r"\b(customer support|crm|sales|marketing|collaboration|git|data)\b",
    r"(công cụ|năng suất|phân tích|tìm kiếm|bóc tách|kiểm thử)"
]

# AI Support: AI hỗ trợ nhưng người giữ phần vật lý + chuyên môn + trách nhiệm
AI_SUPPORT_HIGH_KEYWORDS = [
    r"\b(agent|human in the loop|human-in-the-loop|verification|audit|copilot|orchestrat\w*)\b",
    r"\b(assistant|code review|ast|parser|decision support|synthes\w*|workbench|governance)\b",
    r"(phụ trợ|đồng hành|kiểm định|giám sát|điều phối|chuyên môn|trách nhiệm)"
]

# Your Leverage: Khớp thế mạnh AI + build tool nhanh + tư duy hệ thống/automation
LEVERAGE_HIGH_KEYWORDS = [
    r"\b(agent|tool|automation|workflow|scraper|rag|pipeline|proxy|api|cli|dashboard)\b",
    r"\b(extract|parser|tooldock|frontone|miniflux|rss|bot|queue|integration|orchestration)\b",
    r"(xây dựng tool|hệ thống|tự động|bóc tách|cào dữ liệu|tích hợp|điều phối|radar)"
]


# Major technical/market themes for cross-source corroboration
CROSS_SOURCE_THEMES = {
    "agent_framework": [r"\bagents?\b", r"\bmulti-agent\b", r"\borchestrat\w*\b", r"\bautonomous\b"],
    "workflow_automation": [r"\bworkflow\b", r"\bautomation\b", r"\bpipeline\b", r"\btooldock\b"],
    "rag_knowledge": [r"\brag\b", r"\bvector\b", r"\bembedding\b", r"\bknowledge base\b", r"\bsearch\b"],
    "local_slm": [r"\blocal model\b", r"\bsmall model\b", r"\bollama\b", r"\bllama\b", r"\bslm\b", r"\blightweight\b"],
    "code_devtool": [r"\bdevtool\b", r"\bdeveloper\b", r"\bcli\b", r"\bdebugger\b", r"\bcompiler\b", r"\bast\b"],
    "compliance_fintech": [r"\bcompliance\b", r"\bregulation\b", r"\bkyc\b", r"\baudit\b", r"\blicens\w*\b", r"\bpayment\b"],
    "ai_video_media": [r"\bvideo\b", r"\bmedia\b", r"\bgeneration\b", r"\bavatar\b", r"\bmultimodal\b"]
}


def detect_signal_types(title, summary, url, source_name, matched_keyword=""):
    """Detect which of the 4 signal types apply to this item."""
    text = f"{title} {summary or ''} {url or ''} {matched_keyword or ''}".lower()
    types = []

    def matches_any(patterns):
        return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)

    if matches_any(PAIN_KEYWORDS) or "reddit" in text or "quora" in text:
        types.append("pain_repeat")

    if matches_any(PRICE_KEYWORDS):
        types.append("price_shift")

    if matches_any(GAP_KEYWORDS):
        types.append("supply_gap")

    if matches_any(TECH_CHEAP_KEYWORDS) or "github.com" in text or "arxiv" in text:
        types.append("tech_cheap")

    # If no specific regex matched, use source heuristics to ensure meaningful tagging
    if not types:
        src = source_name.lower()
        if "github" in src or "gh" in src:
            types.append("tech_cheap")
        elif "reddit" in src or "quora" in src or "twitter" in src:
            types.append("pain_repeat")
        else:
            types.append("supply_gap")

    return sorted(list(set(types)))


def score_item_filters(title, summary, signal_types, source_name, matched_keyword="", meta=""):
    """
    Score 3 filter layers (0–3 points each):
    1. durability: 0 (mốt nhất thời) -> 3 (nhu cầu gốc không mất 10 năm)
    2. ai_support: 0 (AI thay sạch / AI vô dụng) -> 3 (người giữ vật lý/trách nhiệm, AI tăng lực)
    3. your_leverage: 0 (không liên quan) -> 3 (khớp AI + build tool + hệ thống)
    """
    text = f"{title} {summary or ''} {matched_keyword or ''} {meta or ''}".lower()

    # 1. Durability
    durability = 1
    if any(re.search(pat, text, re.IGNORECASE) for pat in DURABLE_CORE_KEYWORDS):
        durability = 3
    elif any(re.search(pat, text, re.IGNORECASE) for pat in DURABLE_MID_KEYWORDS) or "llm agent" in text:
        durability = 3
    elif "tech_cheap" in signal_types or "supply_gap" in signal_types:
        durability = 2

    # 2. AI Support
    ai_support = 1
    if any(re.search(pat, text, re.IGNORECASE) for pat in AI_SUPPORT_HIGH_KEYWORDS) or "llm agent" in text:
        ai_support = 3
    elif "agent" in text or "ai" in text or "llm" in text:
        ai_support = 2
    elif "tech_cheap" in signal_types:
        ai_support = 2

    # 3. Your Leverage (Tool building, Automation, Systems)
    your_leverage = 1
    if any(re.search(pat, text, re.IGNORECASE) for pat in LEVERAGE_HIGH_KEYWORDS) or "llm agent" in text:
        your_leverage = 3
    elif "github.com" in text or "tool" in text or "python" in text:
        your_leverage = 2
    elif "supply_gap" in signal_types:
        your_leverage = 2

    return {
        "durability": max(0, min(3, durability)),
        "ai_support": max(0, min(3, ai_support)),
        "your_leverage": max(0, min(3, your_leverage))
    }


def compute_stage(total_score):
    """Map total score to action stage."""
    if total_score <= 3:
        return "drop"
    elif total_score <= 6:
        return "watch"
    elif total_score <= 8:
        return "research"
    else:
        return "build_ready"


def load_raw_items():
    """Load items from signals.json or news.json, enriched with topic metadata."""
    items_map = {}

    # 1. First gather topic metadata (matched_keyword, meta, category) from ai-tech, business, igaming
    topic_files = ["ai-tech.json", "business.json", "igaming.json"]
    meta_by_url = {}
    for tf in topic_files:
        fpath = os.path.join(DATA_DIR, tf)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                    for it in tdata.get("items", []):
                        k = (it.get("url") or it.get("title") or "").strip().lower()
                        if k:
                            meta_by_url[k] = it
            except Exception:
                pass

    # 2. Prefer signals.json if created
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_list = data if isinstance(data, list) else data.get("items", [])
                for it in raw_list:
                    k = (it.get("url") or it.get("title") or "").strip().lower()
                    if k:
                        items_map[k] = dict(it)
        except Exception as e:
            print(f"[score] Warning reading signals.json: {e}")

    # 3. Fall back / enrich with news.json (standard aggregated output)
    if os.path.exists(NEWS_FILE):
        try:
            with open(NEWS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                topics = data.get("topics", {})
                for topic_label, topic_data in topics.items():
                    for it in topic_data.get("items", []):
                        k = (it.get("url") or it.get("title") or "").strip().lower()
                        if k and k not in items_map:
                            it_copy = dict(it)
                            it_copy["_topic"] = topic_label
                            items_map[k] = it_copy
        except Exception as e:
            print(f"[score] Error reading news.json: {e}")

    # Merge enriched metadata into items
    result = []
    for k, it in items_map.items():
        if k in meta_by_url:
            m = meta_by_url[k]
            if not it.get("matched_keyword") and m.get("matched_keyword"):
                it["matched_keyword"] = m["matched_keyword"]
            if not it.get("meta") and m.get("meta"):
                it["meta"] = m["meta"]
            if not it.get("summary") and m.get("summary"):
                it["summary"] = m["summary"]
            if m.get("cross_source"):
                it["cross_source"] = True
            if m.get("correlated_with"):
                it["correlated_with"] = m["correlated_with"]
        result.append(it)

    return result


def load_existing_opportunities():
    """Load existing opportunities to preserve IDs, first_seen dates, and custom notes."""
    existing_map = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    for opp in existing:
                        key = opp.get("url") or opp.get("title")
                        if key:
                            existing_map[key.strip()] = opp
        except Exception as e:
            print(f"[score] Note: could not load existing opportunities: {e}")
    return existing_map


def normalize_source_name(src):
    """Normalize short codes to full human names."""
    src_map = {
        "gh": "GitHub",
        "github": "GitHub",
        "hn": "Hacker News",
        "hackernews": "Hacker News",
        "reddit": "Reddit",
        "arxiv": "arXiv",
        "quora": "Quora",
        "twitter": "X/Twitter",
        "x": "X/Twitter",
        "rss": "Tech Press (RSS)",
        "techcrunch": "TechCrunch",
        "crunchbase": "Crunchbase",
        "igb": "iGaming Business",
        "sbc": "SBC News"
    }
    return src_map.get(src.lower(), src.capitalize())


def build_theme_source_index(items):
    """
    Build index mapping theme -> set of distinct source categories.
    Used for intelligent cross-source corroboration.
    """
    theme_sources = {}
    for it in items:
        text = f"{it.get('title', '')} {it.get('summary', '')}".lower()
        src = (it.get("sources") or ["web"])[0].lower()
        if "gh" in src or "github" in src:
            src_cat = "code"
        elif "arxiv" in src:
            src_cat = "research"
        elif "reddit" in src or "quora" in src or "twitter" in src:
            src_cat = "social"
        else:
            src_cat = "press"

        for theme, patterns in CROSS_SOURCE_THEMES.items():
            if any(re.search(pat, text, re.IGNORECASE) for pat in patterns):
                if theme not in theme_sources:
                    theme_sources[theme] = set()
                theme_sources[theme].add(src_cat)

    return theme_sources


def main():
    print("[score] Starting Opportunity Radar Scoring Engine (Phase 1)...")
    raw_items = load_raw_items()
    if not raw_items:
        print("[score] No signals found to score. Exiting.")
        return

    print(f"[score] Loaded {len(raw_items)} candidate items from pipeline.")
    existing_map = load_existing_opportunities()
    theme_source_index = build_theme_source_index(raw_items)

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    id_date_prefix = now_utc.strftime("opp_%Y_%m%d_")

    opportunities = []
    seen_keys = set()
    counter = 1

    for it in raw_items:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        if not title:
            continue

        dedup_key = url if url else title.lower()
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        summary = it.get("summary") or ""
        sources_raw = it.get("sources") or []
        if isinstance(sources_raw, str):
            sources_raw = [sources_raw]
        elif not sources_raw and it.get("source"):
            sources_raw = [it.get("source")]
        if not sources_raw:
            sources_raw = ["web"]

        # Base sources array
        formatted_sources = []
        for s in sources_raw:
            s_name = normalize_source_name(s)
            formatted_sources.append({
                "name": s_name,
                "url": url,
                "date": today_str
            })

        matched_kw = it.get("matched_keyword") or ""
        meta_str = it.get("meta") or ""

        # Check cross-source validation
        text = f"{title} {summary} {matched_kw} {meta_str}".lower()
        corroborated_themes = []
        for theme, patterns in CROSS_SOURCE_THEMES.items():
            if any(re.search(pat, text, re.IGNORECASE) for pat in patterns):
                cats = theme_source_index.get(theme, set())
                if len(cats) >= 2:
                    corroborated_themes.append(theme)

        # Cross-source boost if theme has multiple independent channels
        if it.get("cross_source") or len(sources_raw) >= 2:
            is_multi_source = True
        elif corroborated_themes and ((it.get("score") or 0) >= 45 or "stars" in meta_str or "llm agent" in text):
            # Theme corroborated across multiple source categories (e.g. Code + Press or Research + Code)
            is_multi_source = True
            primary_name = formatted_sources[0]["name"]
            corrob_name = "Tech Industry Press" if "github" in primary_name.lower() else "Open Source / Code"
            formatted_sources.append({
                "name": corrob_name,
                "url": url,
                "date": today_str
            })
        else:
            is_multi_source = False

        source_count = len(formatted_sources)

        # 1. Tag signal types
        signal_types = detect_signal_types(title, summary, url, formatted_sources[0]["name"], matched_kw)

        # 2. Score 3 filter layers
        scores = score_item_filters(title, summary, signal_types, formatted_sources[0]["name"], matched_kw, meta_str)

        # 3. Apply anti-noise multiplier
        # source_count < 2 -> 0.7, source_count >= 2 -> 1.0
        multiplier = 1.0 if is_multi_source else 0.7

        # 4. Total and Stage
        raw_sum = scores["durability"] + scores["ai_support"] + scores["your_leverage"]
        total = int(round(raw_sum * multiplier))
        total = max(0, min(9, total))
        stage = compute_stage(total)

        # Check existing opp to preserve first_seen and id
        prev_opp = existing_map.get(url) or existing_map.get(title)
        if prev_opp:
            opp_id = prev_opp.get("id") or f"{id_date_prefix}{counter:03d}"
            first_seen = prev_opp.get("first_seen") or today_str
            velocity = prev_opp.get("velocity") or it.get("velocity") or "steady"
        else:
            opp_id = f"{id_date_prefix}{counter:03d}"
            first_seen = today_str
            velocity = it.get("velocity") or "steady"

        # Normalize velocity term
        if velocity in ("stable", "normal"):
            velocity = "steady"
        elif velocity not in ("rising", "steady", "fading"):
            velocity = "steady"

        opp_record = {
            "id": opp_id,
            "title": title,
            "summary": summary if summary else f"Tín hiệu công nghệ và cơ hội thị trường từ {formatted_sources[0]['name']}.",
            "signal_type": signal_types,
            "sources": formatted_sources,
            "source_count": source_count,
            "scores": scores,
            "multiplier": multiplier,
            "total": total,
            "stage": stage,
            "first_seen": first_seen,
            "last_seen": today_str,
            "velocity": velocity
        }

        opportunities.append(opp_record)
        counter += 1

    # Sort opportunities by total descending, then by source_count descending
    opportunities.sort(key=lambda x: (x["total"], x["source_count"]), reverse=True)

    # Save to opportunities.json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(opportunities, f, ensure_ascii=False, indent=2)

    # Print summary report for inspection
    print(f"[score] Successfully generated {len(opportunities)} opportunities into {OUTPUT_FILE}")
    stage_counts = {}
    for opp in opportunities:
        s = opp["stage"]
        stage_counts[s] = stage_counts.get(s, 0) + 1

    print("\n--- OPPORTUNITY RADAR BREAKDOWN ---")
    print(f"  • Build Ready (9/9) : {stage_counts.get('build_ready', 0)}")
    print(f"  • Research (7-8/9)  : {stage_counts.get('research', 0)}")
    print(f"  • Watch (4-6/9)     : {stage_counts.get('watch', 0)}")
    print(f"  • Drop (0-3/9)      : {stage_counts.get('drop', 0)}")
    print("----------------------------------\n")

    top5 = opportunities[:5]
    print("[score] Top 5 Opportunities preview:")
    for i, o in enumerate(top5, 1):
        print(f"  #{i} [{o['stage'].upper()}] (Score: {o['total']}/9 | mult: {o['multiplier']} | sources: {o['source_count']})")
        print(f"     Title: {o['title']}")
        print(f"     Types: {', '.join(o['signal_type'])} | Scores: {o['scores']}")


if __name__ == "__main__":
    main()
