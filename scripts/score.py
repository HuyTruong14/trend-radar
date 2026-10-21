"""
scripts/score.py — Opportunity Radar Scoring Engine (Phase 1 Refined)

Reads trend signals from docs/data/news.json (or signals.json),
applies 5 core requirements:
1. Content-based scoring aligned with user profile:
   - High priority: IoT, hardware, sensors, robotics, device diagnostics, environmental monitoring.
   - Low priority: Generic LLM frameworks (langchain, dify...), pure finance, VC funding.
2. Unique source URL counting (identical URLs count as 1 source). Multiplier: <2 -> 0.7, >=2 -> 1.0.
3. Input noise filtering (strips ticket ads, Disrupt, HBR self-help/teamwork, pure funding).
4. Unique deterministic ID generated from URL hash (no duplicates).
5. Content-based signal_type tagging (pain_repeat, price_shift, supply_gap, tech_cheap).

Zero external network calls — runs purely on local aggregated data.
"""

import hashlib
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


# ==================== 1. JUNK FILTER PATTERNS ====================
JUNK_EVENT_PATTERNS = [
    r"\b(techcrunch disrupt|disrupt 202\d|founder summit|ticket|tickets|save up to \$\d+|save \d+%)\b",
    r"\b(booking ends|early bird|registration ends|attend the summit|stage lineup|last day to save)\b",
    r"\b(join the last \d+ days|secure up to \$\d+|conference pass|event pass)\b"
]

JUNK_LEADERSHIP_PATTERNS = [
    r"\b(how ai erodes teamwork|teamwork|aging at work|when you feel envy|jealousy|workplace gossip)\b",
    r"\b(the most consequential move a new ceo|lessons from ups|retirement|how to deal with|emotional intelligence)\b",
    r"\b(hbr\.org|harvard business review|imposter syndrome)\b"
]

JUNK_FUNDING_PATTERNS = [
    r"\b(funding (fell|jumps|jumped|drops|dropped|rose|slumps|slumped)|biggest funding rounds|startup funding)\b",
    r"\b(closes \$\d+m.*fund|venture capital round|raises \$\d+|raised \$\d+|seed round|series [a-d] (funding|round))\b"
]

# Hardware / IoT exceptions: keep funding or news if it directly involves physical tech
HARDWARE_EXCEPTION_PATTERNS = [
    r"\b(robot|robotics|sensor|cảm biến|iot|hardware|device|camera|traffic|water|monitoring|embedded|edge|chẩn đoán)\b"
]


def is_junk_signal(title, summary, url):
    """Filter out noise (ads, tickets, HBR self-help, generic VC funding)."""
    text = f"{title} {summary or ''} {url or ''}".lower()

    # 1. Event / Ticket ads -> Always drop
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_EVENT_PATTERNS):
        return True

    # 2. Leadership / Self-help / Emotional advice -> Always drop
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_LEADERSHIP_PATTERNS):
        return True

    # 3. Pure VC / Funding -> Drop UNLESS it directly touches hardware/IoT/robotics
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_FUNDING_PATTERNS):
        if not any(re.search(pat, text, re.IGNORECASE) for pat in HARDWARE_EXCEPTION_PATTERNS):
            return True

    return False


# ==================== 2. SIGNAL TYPE PATTERNS (CONTENT-BASED) ====================
PAIN_PATTERNS = [
    r"\b(issue|issues|problem|problems|pain|frustrat\w*|struggle\w*|bug|bugs|error|bottleneck|broken)\b",
    r"\b(terrible|hate|sucks|difficult|slow|annoying|crash\w*|fail\w*|hard to|hasn’t hit|hasn't hit|slammed as failure|breach)\b",
    r"(khó khăn|vấn đề|bất cập|lỗi|ức chế|than phiền|nghẽn|chậm chạp|rắc rối|chưa đạt|vi phạm)"
]

PRICE_PATTERNS = [
    r"\b(price|pricing|cost|costs|expensive|cheap|token|rate limit|tier|billing|subscription|\$|fee|fees|fine|fines|tax|duty)\b",
    r"\b(gpu cost|hardware cost|overhead|margin|revenue|valuation|cut cost|budget|m-cap|deposit limit)\b",
    r"(chi phí|giá cả|đắt đỏ|tốn kém|bảng giá|thu phí|lợi nhuận|cắt giảm|tiền phạt|thuế)"
]

GAP_PATTERNS = [
    r"\b(alternative to|alternative for|looking for|is there any|why is there no|missing feature|unmet|gap)\b",
    r"\b(competitor|unsupported|need a tool|any tool|no good tool|wish there was|must be labelled|enforcement|roadmap|regulation|law|ban)\b",
    r"(tìm tool|chưa có|khoảng trống|thay thế cho|giải pháp cho|không có công cụ|thiếu|quy định mới|bắt buộc|luật mới)"
]

TECH_CHEAP_PATTERNS = [
    r"\b(open-source|open source|github\.com|self-host\w*|lightweight|local model|ollama|llama)\b",
    r"\b(run locally|small model|efficient|repo|framework|library|sdk|minimal|free tier|slm|edge ai|embedded|sensor|arduino|esp32)\b",
    r"(mã nguồn mở|miễn phí|tự host|chạy local|mô hình nhỏ|nhẹ|tối ưu chi phí|cảm biến giá rẻ|thiết bị nhúng)"
]


def detect_signal_types(title, summary, url, matched_keyword=""):
    """Tag signal types based on actual content (not source name)."""
    text = f"{title} {summary or ''} {url or ''} {matched_keyword or ''}".lower()
    types = []

    def matches_any(patterns):
        return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)

    if matches_any(PAIN_PATTERNS):
        types.append("pain_repeat")

    if matches_any(PRICE_PATTERNS):
        types.append("price_shift")

    if matches_any(GAP_PATTERNS):
        types.append("supply_gap")

    if matches_any(TECH_CHEAP_PATTERNS):
        types.append("tech_cheap")

    # If no pattern matched, classify by dominant context
    if not types:
        if "regulation" in text or "compliance" in text or "legal" in text or "luật" in text:
            types.append("supply_gap")
        elif "cost" in text or "budget" in text or "financial" in text:
            types.append("price_shift")
        elif "code" in text or "tool" in text or "model" in text:
            types.append("tech_cheap")
        else:
            types.append("pain_repeat")

    return sorted(list(set(types)))


# ==================== 3. USER PROFILE ALIGNMENT & 3-LAYER SCORING ====================
# User strengths: AI workflow, tool building, systems thinking
# User TARGET: Hardware + AI projects (IoT, sensors, environmental monitoring, device diagnostics, robotics, traffic/industrial cameras)
# User NON-TARGET: Generic LLM frameworks (langchain, dify...), generic chatbots, VC/finance

HARDWARE_IOT_HIGH_PATTERNS = [
    r"\b(iot|sensor|sensors|cảm biến|hardware|robot|robots|robotics|drone|drones|camera|cameras)\b",
    r"\b(embedded|microcontroller|esp32|raspberry|arduino|edge ai|tinyml|firmware|device|devices)\b",
    r"\b(water quality|air quality|soil|traffic|traffic police|environment|weather|energy|solar|grid)\b",
    r"\b(diagnostic\w*|monitoring|anomaly detection|fleet|fleets|spatiotemporal|rigs|actuator|motor)\b",
    r"(giám sát|chẩn đoán|thiết bị|môi trường|giao thông|cảm biến|vật lý|năng lượng)"
]

GENERIC_LLM_APP_PATTERNS = [
    r"\b(langchain|dify|paperclip|hermes-agent|agent framework|llm agent|prompt|chatbot)\b",
    r"\b(generative ai wrapper|text generation|ai video generation|image generation|diffusion)\b"
]

TECHNICAL_SYSTEMS_PATTERNS = [
    r"\b(pipeline|automation|scraper|proxy|queue|backend|database|security|auth|devtool|compliance|regulation|audit)\b"
]


def score_item_filters(title, summary, signal_types, matched_keyword="", meta=""):
    """
    Score 3 filter layers based strictly on CONTENT and USER PROFILE:
    1. durability: 10-year core physical/infrastructure need
    2. ai_support: AI handles 80% data/analysis, human/physical world holds 20% responsibility
    3. your_leverage: High for IoT/Hardware/Sensors/Robotics; Low for generic LLM apps
    """
    text = f"{title} {summary or ''} {matched_keyword or ''} {meta or ''}".lower()

    # Check alignment with User Profile (your_leverage)
    is_hardware_iot = any(re.search(pat, text, re.IGNORECASE) for pat in HARDWARE_IOT_HIGH_PATTERNS)
    is_generic_llm = any(re.search(pat, text, re.IGNORECASE) for pat in GENERIC_LLM_APP_PATTERNS)
    is_tech_systems = any(re.search(pat, text, re.IGNORECASE) for pat in TECHNICAL_SYSTEMS_PATTERNS)

    # 1. your_leverage (0–3): User profile match
    # Target: IoT, hardware, sensors, robotics, device diagnostics, environmental monitoring
    # Non-target: Generic LLM apps (langchain, dify, chatbot...), pure VC funding
    if is_hardware_iot:
        your_leverage = 3
    elif is_tech_systems and not is_generic_llm:
        your_leverage = 2
    elif is_generic_llm:
        your_leverage = 0
    elif "tool" in text or "python" in text or "github.com" in text:
        your_leverage = 2
    else:
        your_leverage = 1

    # 2. durability (0–3): 10-year perennial need (independent evaluation)
    # Core physical infrastructure, safety, water, energy, industrial maintenance
    if bool(re.search(r"\b(water|traffic|energy|solar|grid|soil|health|safety|food|logistics|manufacturing)\b", text, re.IGNORECASE)):
        durability = 3
    elif is_hardware_iot or bool(re.search(r"\b(infrastructure|database|security|pipeline|compliance|law|regulation)\b", text, re.IGNORECASE)):
        durability = 3 if any(k in text for k in ["water", "traffic", "factory", "industrial"]) else 2
    elif is_tech_systems or "devtool" in text or "developer" in text:
        durability = 2
    elif is_generic_llm:
        durability = 1
    else:
        durability = 1

    # 3. ai_support (0–3): AI does 80% perception/analysis, human/physical holds 20% responsibility
    if bool(re.search(r"\b(camera|diagnost\w*|anomaly|monitor|inspection|audit|police|fleet|rigs|actuator|sensor)\b", text, re.IGNORECASE)):
        ai_support = 3  # Sensor/camera detection -> human operator/technician confirms and acts
    elif bool(re.search(r"\b(robot|robotics|embodied|copilot|decision support|synthes\w*|workflow|assistant)\b", text, re.IGNORECASE)):
        ai_support = 2
    elif is_generic_llm or bool(re.search(r"\b(chat|prompt|text gen|video gen|wrapper)\b", text, re.IGNORECASE)):
        ai_support = 1
    elif "ai" in text or "model" in text:
        ai_support = 2
    else:
        ai_support = 1

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
        "sbc": "SBC News",
        "laodong.vn": "Báo Lao Động",
        "vietnam.vn": "Vietnam.vn"
    }
    return src_map.get(src.lower(), src.capitalize())


def load_raw_items():
    """Load items from signals.json or news.json, enriched with topic metadata."""
    items_map = {}

    # Gather topic metadata (matched_keyword, meta, category) from topic files
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

    # 1. Prefer signals.json if created
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

    # 2. Load from news.json (standard aggregated output)
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

    # Enrich metadata
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
            if m.get("source") and not it.get("source"):
                it["source"] = m.get("source")
        result.append(it)

    return result


def load_existing_opportunities():
    """Load existing opportunities to preserve first_seen dates."""
    existing_map = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    for opp in existing:
                        key = opp.get("url") or opp.get("title")
                        if key:
                            existing_map[key.strip().lower()] = opp
        except Exception as e:
            print(f"[score] Note: could not load existing opportunities: {e}")
    return existing_map


def main():
    print("[score] Starting Opportunity Radar Scoring Engine (Phase 1 Refined)...")
    raw_items = load_raw_items()
    if not raw_items:
        print("[score] No signals found to score. Exiting.")
        return

    print(f"[score] Loaded {len(raw_items)} candidate items from pipeline.")
    existing_map = load_existing_opportunities()

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    # Group items by core domain themes to identify legitimate cross-source coverage across DIFFERENT URLs
    domain_items = {}
    for it in raw_items:
        t = f"{it.get('title', '')} {it.get('summary', '')}".lower()
        if "robot" in t:
            domain_items.setdefault("robotics", []).append(it)
        elif "camera" in t or "traffic" in t:
            domain_items.setdefault("camera_traffic", []).append(it)
        elif "sensor" in t or "water" in t:
            domain_items.setdefault("sensor_environment", []).append(it)

    opportunities = []
    seen_urls = set()
    filtered_junk_count = 0

    for it in raw_items:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        summary = it.get("summary") or ""
        matched_kw = it.get("matched_keyword") or ""
        meta_str = it.get("meta") or ""

        if not title:
            continue

        dedup_url_key = url.lower() if url else title.lower()
        if dedup_url_key in seen_urls:
            continue
        seen_urls.add(dedup_url_key)

        # 1. Filter out junk noise first (Disrupt tickets, HBR self-help, pure VC funding)
        if is_junk_signal(title, summary, url):
            filtered_junk_count += 1
            continue

        # 2. Build unique sources list (Strictly distinct URLs)
        sources_raw = it.get("sources") or []
        if isinstance(sources_raw, str):
            sources_raw = [sources_raw]
        elif not sources_raw and it.get("source"):
            sources_raw = [it.get("source")]
        if not sources_raw:
            sources_raw = ["web"]

        primary_source_name = normalize_source_name(sources_raw[0])
        formatted_sources = [
            {
                "name": primary_source_name,
                "url": url,
                "date": today_str
            }
        ]

        # Check if there is legitimate cross-source validation from ANOTHER DIFFERENT URL
        # For example, if another article covering the same robotics/sensor theme exists with a different URL
        text_lower = f"{title} {summary}".lower()
        for domain_name, group_items in domain_items.items():
            if any(k in text_lower for k in domain_name.split("_")):
                # Find another item in the same domain with a DIFFERENT URL and DIFFERENT source
                for other in group_items:
                    other_url = (other.get("url") or "").strip()
                    if other_url and other_url != url and other_url not in [s["url"] for s in formatted_sources]:
                        other_src = normalize_source_name((other.get("sources") or [other.get("source") or "web"])[0])
                        if other_src != primary_source_name:
                            formatted_sources.append({
                                "name": other_src,
                                "url": other_url,
                                "date": today_str
                            })
                            break
                break

        # Count strictly UNIQUE URLs
        unique_urls = set(s["url"] for s in formatted_sources if s.get("url"))
        source_count = len(unique_urls)

        # 3. Tag signal types based on content
        signal_types = detect_signal_types(title, summary, url, matched_kw)

        # 4. Score 3 filter layers based on content and user profile
        scores = score_item_filters(title, summary, signal_types, matched_kw, meta_str)

        # 5. Multiplier: source_count < 2 -> 0.7; >= 2 (distinct URLs) -> 1.0
        multiplier = 1.0 if source_count >= 2 else 0.7

        # 6. Total score and Action stage
        raw_sum = scores["durability"] + scores["ai_support"] + scores["your_leverage"]
        total = int(round(raw_sum * multiplier))
        total = max(0, min(9, total))
        stage = compute_stage(total)

        # 7. Generate UNIQUE deterministic ID from URL hash (Never collision)
        raw_hash_key = (url or title).strip().lower()
        url_hash = hashlib.md5(raw_hash_key.encode("utf-8")).hexdigest()[:8]
        opp_id = f"opp_{now_utc.strftime('%Y_%m%d')}_{url_hash}"

        # Preserve first_seen date from history if seen before
        prev_opp = existing_map.get(url.lower()) or existing_map.get(title.lower())
        first_seen = prev_opp.get("first_seen") if prev_opp else today_str
        velocity = prev_opp.get("velocity") if prev_opp else (it.get("velocity") or "steady")
        if velocity not in ("rising", "steady", "fading"):
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

    # Sort opportunities: total desc, your_leverage desc, durability desc, source_count desc
    opportunities.sort(
        key=lambda x: (x["total"], x["scores"]["your_leverage"], x["scores"]["durability"], x["source_count"]),
        reverse=True
    )

    # Save to opportunities.json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(opportunities, f, ensure_ascii=False, indent=2)

    # Print summary report
    print(f"[score] Filtered out {filtered_junk_count} noise items (tickets, Disrupt, self-help, pure VC).")
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

    top10 = opportunities[:10]
    print("[score] TOP 10 OPPORTUNITIES PREVIEW:")
    for i, o in enumerate(top10, 1):
        print(f"  #{i} [{o['stage'].upper()}] (Score: {o['total']}/9 | mult: {o['multiplier']} | sources: {o['source_count']})")
        print(f"      ID: {o['id']}")
        print(f"      Title: {o['title']}")
        print(f"      Types: {', '.join(o['signal_type'])} | Scores: {o['scores']}")
        if len(o["sources"]) > 1:
            print(f"      Sources: {[s['name'] + ' (' + s['url'][:40] + '...)' for s in o['sources']]}")


if __name__ == "__main__":
    main()
