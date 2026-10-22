"""
scripts/score.py — Opportunity Radar Scoring Engine (Refined Phase 1)

Reads trend signals from docs/data/news.json (or signals.json),
applies 5 core requirements:
1. Content-based scoring strictly aligned with user profile:
   - High priority (Score 3): IoT, hardware, sensors, robotics, device diagnostics, traffic/edge cameras.
   - Low priority (Score 0): Generic LLM frameworks (langchain, dify, wrappers), generic chatbots.
2. Accurate source grouping:
   - Only merge signals into 1 record if their titles PROVE they cover the EXACT SAME story.
   - If not identical / same topic, keep strictly separate (source_count = 1).
   - "AI camera giao thông" and "Joints, Camera, Action! (3D animation paper)" MUST be separate records.
3. Input noise filtering TRƯỚC KHI CHẤM:
   - Drop all gambling / iGaming (regulatory, licensing, sportsbook, casino).
   - Drop all VC funding, IPO, startup valuation, layoffs tracker, equity pieces.
   - Drop all event ads (TechCrunch Disrupt, passes, early bird), podcasts, leadership/self-help.
   - Drop all records with total <= 3 (drop tier) from opportunities.json.
4. Unique deterministic ID generated from URL hash (opp_YYYY_MMDD_{hash8}).
5. Content-based signal_type tagging:
   - pain_repeat: issues, bugs, failures, bottlenecks, crashes, misuse.
   - price_shift: pricing, costs, budget, inflation, fees, tariffs.
   - supply_gap: unmet demand, regulations, compliance, governance, traffic/infrastructure monitoring.
   - tech_cheap: robotics, cameras, sensors, IoT, edge AI, microcontrollers, open-source models/tools.
   - "AI camera giao thông" is NOT pain_repeat (tagged supply_gap / tech_cheap).

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
SENT_OPPORTUNITIES_FILE = os.path.join(DATA_DIR, "sent_opportunities.json")

# Ensure scripts directory is in sys.path to reuse notify.py
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import notify
except ImportError:
    notify = None


# ==================== 1. JUNK FILTER PATTERNS (UPFRONT ELIMINATION) ====================

JUNK_IGAMING_PATTERNS = [
    r"\b(gambling|betting|bookmaker|sportsbook|casino|poker|slot machine|igaming|betgoodwin|flutter|acma|gaming operator|betting sponsor|gaming authority|mgd|wagering|online gambling|sports betting|jackpot|roulette|bingo)\b"
]

JUNK_FUNDING_VC_LAYOFFS_PATTERNS = [
    r"\b(funding (fell|jumps|jumped|drops|dropped|rose|slumps|slumped)|biggest funding rounds|startup funding)\b",
    r"\b(closes? \$\d+[mkb]?\b.*?\bfund\b|venture capital|\bvcs?\b|pre-seed|seed round|series [a-e] (funding|round)?)\b",
    r"\b(raises? \$\d+|raised \$\d+|nabs \$\d+|secures \$\d+|valuation|unicorn|hits \$\d+.*valuation)\b",
    r"\b(ipo|london ipo|public listing|nasdaq listing|equity holders?|employees’ equity|venture winners)\b",
    r"\b(layoffs?|tech layoffs tracker|layoffs tracker|cut (up to )?\d+ jobs|slashing \d+ jobs)\b",
    r"\b(insider-turned-vc|venture pact|investing in a frenzied market|fde bubble|billion-dollar company without venture capital)\b"
]

JUNK_EVENT_PATTERNS = [
    r"\b(techcrunch disrupt|disrupt 202\d|founder summit|ticket|tickets|save up to \$\d+|save \d+%)\b",
    r"\b(booking ends|early bird|registration ends|attend the summit|stage lineup|last day to save)\b",
    r"\b(conference pass|event pass|join the last \d+ days|secure up to \$\d+ ticket|webinar|podcast|episode)\b"
]

JUNK_LEADERSHIP_PATTERNS = [
    r"\b(how ai erodes teamwork|teamwork|aging at work|when you feel envy|jealousy|workplace gossip)\b",
    r"\b(the most consequential move a new ceo|lessons from ups|retirement|how to deal with|emotional intelligence)\b",
    r"\b(hbr\.org|harvard business review|imposter syndrome|team dynamics weaken|build your team with autonomous humans|disciplined chaos)\b",
    r"\b(luxury brand|pricing strategies to deal with persistent inflation|killing digital products)\b"
]


def is_junk_signal(it):
    """
    Filter out noise TRƯỚC KHI CHẤM:
    - Tin gambling/iGaming regulatory, licensing, sportsbook
    - Tin VC funding, IPO, startup valuation, layoffs tracker
    - Quảng cáo sự kiện, podcast, bài leadership chung
    """
    topic = it.get("_topic", "")
    source = it.get("source", "")
    url = (it.get("url") or "").lower()

    # 1. iGaming topic / source / domain
    if topic == "iGaming" or source in ["SBC News", "iGB", "iGaming Business", "sbc", "igb"]:
        return True
    if "sbcnews.co.uk" in url or "igamingbusiness.com" in url:
        return True

    text = f"{it.get('title', '')} {it.get('summary', '')} {url}".lower()

    # 2. Gambling keywords
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_IGAMING_PATTERNS):
        return True

    # 3. Event / Ticket ads & Podcasts
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_EVENT_PATTERNS):
        return True

    # 4. Leadership / Self-help / Emotional advice
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_LEADERSHIP_PATTERNS):
        return True

    # 5. Pure VC funding, IPO, valuation, layoffs
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_FUNDING_VC_LAYOFFS_PATTERNS):
        return True

    return False


# ==================== 2. TITLE COMPARISON (STRICT TOPIC MERGING) ====================

def extract_title_keywords(title):
    """Extract significant keywords from title for semantic matching."""
    # Strip site name suffixes like "- Laodong.vn", " | TechCrunch"
    t = re.sub(r"\s*[-|–—]\s*[\w\s.]+$", "", title)
    t = re.sub(r"https?://\S+", "", t)
    # Extract alpha-numeric words with length >= 3
    words = set(re.findall(r"[a-zA-Z0-9\u00C0-\u1EF9]{3,}", t.lower()))
    stopwords = {
        "with", "from", "that", "this", "have", "more", "about", "will", "what",
        "when", "into", "after", "over", "first", "their", "there", "could",
        "would", "should", "been", "being", "through", "under", "between",
        "vietnam", "laodong", "news", "arxiv", "github", "video", "paper"
    }
    return words - stopwords


def is_same_story(title1, title2):
    """
    Strictly verify if two signals cover the EXACT SAME story/event.
    If not 100% sure, return False -> keeps them as separate records.
    """
    if not title1 or not title2:
        return False

    t1 = title1.strip().lower()
    t2 = title2.strip().lower()
    if t1 == t2:
        return True

    kw1 = extract_title_keywords(title1)
    kw2 = extract_title_keywords(title2)
    if not kw1 or not kw2:
        return False

    intersection = kw1 & kw2
    union = kw1 | kw2
    jaccard = len(intersection) / len(union) if union else 0.0

    # Strict criteria: at least 4 shared meaningful words AND high Jaccard (>= 0.6)
    if len(intersection) >= 4 and jaccard >= 0.6:
        return True

    return False


# ==================== 3. SIGNAL TYPE INFERENCE (CONTENT-BASED) ====================

PAIN_PATTERNS = [
    r"\b(issue|issues|problem|problems|pain|painful|frustrat\w*|struggl\w*|bug|bugs|error|errors|bottleneck|broken|breakdown|downtime|outage|glitch)\b",
    r"\b(terrible|hate|sucks|difficult|slow|annoying|crash\w*|fail\w*|hard to|breach|vulnerability|leak|hazard|danger|threat|fatigue|burnout|misuse)\b",
    r"(khó khăn|vấn đề|bất cập|lỗi|ức chế|than phiền|nghẽn|chậm chạp|rắc rối|chưa đạt|vi phạm|thất bại|nguy hiểm|sự cố|lạm dụng)"
]

PRICE_PATTERNS = [
    r"(\$\d+|\b(price|pricing|cost|costs|expensive|cheap|cheaper|tier|billing|subscription|fee|fees|fine|fines|tax|duty|tariff|tariffs)\b)",
    r"\b(gpu cost|hardware cost|overhead|margin|budget|inflation|token cost|compute cost|cut cost|cost reduction)\b",
    r"(chi phí|giá cả|đắt đỏ|tốn kém|bảng giá|thu phí|lợi nhuận|cắt giảm|tiền phạt|thuế|lạm phát|tiết kiệm)"
]

GAP_PATTERNS = [
    r"\b(alternative to|alternative for|looking for|is there any|why is there no|missing|unmet|gap|unsupported|need a tool|any tool|no good tool|wish there was)\b",
    r"\b(regulation|regulations|regulated|regulate|regulatory|law|laws|compliance|mandate|mandated|must be labelled|must comply|accountability|governance|task force|policy|ban|prohibited|enforcement|standards?)\b",
    r"\b(surveillance|traffic police|control center)\b",
    r"(tìm tool|chưa có|khoảng trống|thay thế cho|giải pháp cho|không có công cụ|thiếu|quy định|bắt buộc|luật|nghị định|tiêu chuẩn|kiểm soát|điều hành|yêu cầu)"
]

TECH_CHEAP_PATTERNS = [
    r"\b(camera|cameras|sensor|sensors|iot|edge ai|tinyml|microcontroller|esp32|arduino|raspberry|firmware|hardware|robot|robots|robotics|embodied|rigs|actuator|motor)\b",
    r"\b(open-source|open source|github\.com|repo|self-host\w*|lightweight|slm|small model|local model|ollama|llama|run locally|efficient|few-step|compact|sdk|framework|library)\b",
    r"\b(observability|diagnostics?|monitoring|spatial intelligence|multi-token|world models?|renderer)\b",
    r"(cảm biến|camera|thiết bị|phần cứng|mã nguồn mở|nhúng|mô hình nhỏ|tối ưu|công nghệ rẻ|chạy local)"
]


def detect_signal_types(title, summary, url):
    """
    Infer signal type strictly from title and content:
    - pain_repeat: than phiền/vấn đề lặp lại/lỗi
    - price_shift: giá/chi phí biến động
    - supply_gap: thiếu giải pháp cho nhu cầu/quy định bắt buộc
    - tech_cheap: công nghệ/cảm biến/phần cứng rẻ đi
    Ví dụ: 'AI camera giao thông' KHÔNG phải pain_repeat.
    """
    text = f"{title} {summary or ''} {url or ''}".lower()
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

    # If no pattern matched, infer from dominant technical context (NEVER blind pain_repeat)
    if not types:
        if any(k in text for k in ["model", "video", "agent", "app", "tool", "ai", "learning", "renderer", "code", "workflow"]):
            types.append("tech_cheap")
        else:
            types.append("supply_gap")

    return sorted(list(set(types)))


# ==================== 4. USER PROFILE ALIGNMENT & 3-LAYER SCORING ====================

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
    r"\b(pipeline|automation|scraper|proxy|queue|backend|database|security|auth|devtool|compliance|regulation|regulatory|governance|audit|law|luật)\b"
]


def score_item_filters(title, summary, signal_types, matched_keyword="", meta=""):
    """
    Score 3 filter layers based strictly on CONTENT and USER PROFILE:
    1. durability: 10-year core physical/infrastructure need
    2. ai_support: AI handles 80% data/analysis, human/physical world holds 20% responsibility
    3. your_leverage: High for IoT/Hardware/Sensors/Robotics; Low for generic LLM apps
    """
    text = f"{title} {summary or ''} {matched_keyword or ''} {meta or ''}".lower()

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

    # 2. durability (0–3): 10-year perennial need
    # Physical infrastructure, traffic, water, energy, industrial maintenance, diagnostics
    if bool(re.search(r"\b(water|traffic|energy|solar|grid|soil|health|safety|food|logistics|manufacturing|fleet)\b", text, re.IGNORECASE)):
        durability = 3
    elif is_hardware_iot or bool(re.search(r"\b(infrastructure|database|security|pipeline|compliance|law|regulation|diagnostics?)\b", text, re.IGNORECASE)):
        durability = 3 if any(k in text for k in ["water", "traffic", "factory", "industrial", "diagnost", "robot"]) else 2
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

    # ==================== STEP 1: UPFRONT JUNK FILTERING ====================
    # Lỗi 2: Lọc rác TRƯỚC khi chấm (không phải chấm rồi để đó)
    # Loại hẳn: gambling/iGaming, VC funding, IPO, startup valuation, layoffs, event ads, leadership
    filtered_items = []
    filtered_junk_count = 0
    seen_urls = set()

    for it in raw_items:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        if not title:
            continue

        dedup_url_key = url.lower() if url else title.lower()
        if dedup_url_key in seen_urls:
            continue
        seen_urls.add(dedup_url_key)

        if is_junk_signal(it):
            filtered_junk_count += 1
            continue

        filtered_items.append(it)

    print(f"[score] Upfront filtering: dropped {filtered_junk_count} noise items. Retained {len(filtered_items)} valid signals.")

    # ==================== STEP 2: SOURCE GROUPING (STRICT TOPIC MATCHING) ====================
    # Lỗi 1: Chỉ gộp 2 tín hiệu thành 1 khi chúng NÓI VỀ CÙNG MỘT CHỦ ĐỀ.
    # Nếu không chắc 2 tín hiệu cùng chủ đề -> để riêng, source_count = 1.
    merged_groups = []
    used_indices = set()

    for i in range(len(filtered_items)):
        if i in used_indices:
            continue
        group = [filtered_items[i]]
        used_indices.add(i)

        for j in range(i + 1, len(filtered_items)):
            if j in used_indices:
                continue
            # Strictly verify if titles talk about the exact same story
            if is_same_story(filtered_items[i].get("title", ""), filtered_items[j].get("title", "")):
                group.append(filtered_items[j])
                used_indices.add(j)

        merged_groups.append(group)

    # ==================== STEP 3: SCORING & OUTPUT FILTERING ====================
    opportunities = []

    for group in merged_groups:
        primary = group[0]
        title = primary.get("title", "").strip()
        summary = primary.get("summary") or ""
        matched_kw = primary.get("matched_keyword") or ""
        meta_str = primary.get("meta") or ""
        primary_url = (primary.get("url") or "").strip()

        # Build unique sources list across the group
        formatted_sources = []
        seen_source_urls = set()

        for it in group:
            it_url = (it.get("url") or "").strip()
            if it_url and it_url in seen_source_urls:
                continue
            if it_url:
                seen_source_urls.add(it_url)

            srcs = it.get("sources") or []
            if isinstance(srcs, str):
                srcs = [srcs]
            elif not srcs and it.get("source"):
                srcs = [it.get("source")]
            if not srcs:
                srcs = ["web"]

            src_name = normalize_source_name(srcs[0])
            formatted_sources.append({
                "name": src_name,
                "url": it_url,
                "date": today_str
            })

        # Calculate strict source_count based on distinct URLs
        unique_urls = set(s["url"] for s in formatted_sources if s.get("url"))
        source_count = max(1, len(unique_urls))

        # Multiplier: source_count < 2 -> 0.85; >= 2 (distinct validated sources) -> 1.0
        multiplier = 1.0 if source_count >= 2 else 0.85

        # Tag signal types based on content
        signal_types = detect_signal_types(title, summary, primary_url)

        # Score 3 filter layers based on content and user profile
        scores = score_item_filters(title, summary, signal_types, matched_kw, meta_str)

        # Calculate total score
        raw_sum = scores["durability"] + scores["ai_support"] + scores["your_leverage"]
        total = int(round(raw_sum * multiplier))
        total = max(0, min(9, total))

        # Lỗi 2: Loại các item total <= 3 (drop tier) khỏi output
        if total <= 3:
            continue

        stage = compute_stage(total)

        # Preserve first_seen date and ID from history if seen before
        prev_opp = existing_map.get(primary_url.lower()) or existing_map.get(title.lower())
        first_seen = prev_opp.get("first_seen") if prev_opp else today_str
        
        # Preserve idempotent ID if previously assigned
        if prev_opp and prev_opp.get("id"):
            opp_id = prev_opp["id"]
        else:
            raw_hash_key = (primary_url or title).strip().lower()
            url_hash = hashlib.md5(raw_hash_key.encode("utf-8")).hexdigest()[:8]
            opp_id = f"opp_{now_utc.strftime('%Y_%m%d')}_{url_hash}"

        # Phase 6: Appearance history tracking
        prev_history = prev_opp.get("history_dates", []) if prev_opp else []
        if today_str not in prev_history:
            history_dates = prev_history + [today_str]
        else:
            history_dates = prev_history

        appearance_count = len(history_dates)

        # Automatic Velocity Calculation (Phase 6)
        velocity = compute_velocity(
            first_seen_str=first_seen,
            last_seen_str=today_str,
            history_dates=history_dates,
            source_count=source_count,
            pipeline_velocity=primary.get("velocity")
        )

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
            "appearance_count": appearance_count,
            "history_dates": history_dates[-14:],  # Keep recent 14 active appearances
            "velocity": velocity
        }
        opportunities.append(opp_record)

    # ==================== PHASE 6: HISTORICAL OPPORTUNITY RETENTION & AGING ====================
    # Retain opportunities from previous runs that were not captured in today's fresh batch.
    # - If inactive > 7 days -> automatically mark as 'fading' (xu hướng đang tắt)
    # - If inactive > 30 days -> drop (retire old signals)
    seen_in_current_batch = set()
    for opp in opportunities:
        for s in opp.get("sources", []):
            if s.get("url"):
                seen_in_current_batch.add(s["url"].strip().lower())
        if opp.get("title"):
            seen_in_current_batch.add(opp["title"].strip().lower())
        if opp.get("id"):
            seen_in_current_batch.add(opp["id"])

    retained_count = 0
    faded_count = 0
    for prev_key, prev_opp in existing_map.items():
        if prev_key in seen_in_current_batch:
            continue
        prev_id = prev_opp.get("id")
        if prev_id and prev_id in seen_in_current_batch:
            continue

        prev_last_seen = prev_opp.get("last_seen") or prev_opp.get("first_seen") or today_str
        try:
            prev_last_date = datetime.strptime(prev_last_seen, "%Y-%m-%d").date()
            days_inactive = (now_utc.date() - prev_last_date).days
        except Exception:
            days_inactive = 0

        # Drop old opportunities inactive for more than 30 days
        if days_inactive > 30:
            continue

        # Clone and update aging velocity
        aged_opp = dict(prev_opp)
        if days_inactive >= 7:
            aged_opp["velocity"] = "fading"
            faded_count += 1
        else:
            aged_opp["velocity"] = prev_opp.get("velocity", "steady")

        # Mark seen to prevent duplicate entries from multiple map keys
        seen_in_current_batch.add(prev_key)
        if prev_id:
            seen_in_current_batch.add(prev_id)
        opportunities.append(aged_opp)
        retained_count += 1

    if retained_count > 0:
        print(f"[score] [Phase 6] Retained {retained_count} active historical opportunities ({faded_count} marked fading).")

    # ==================== PHASE 6: VELOCITY-WEIGHTED SORTING ====================
    # Rule: 'fading' items are demoted below active opportunities even if score is high.
    # 'rising' gets top priority, followed by 'steady', with 'fading' at the bottom.
    VELOCITY_WEIGHT = {
        "rising": 2,
        "steady": 1,
        "stable": 1,
        "fading": 0,
        "cooling": 0
    }

    opportunities.sort(
        key=lambda x: (
            VELOCITY_WEIGHT.get(x.get("velocity", "steady"), 1),
            x["total"],
            x["scores"]["your_leverage"],
            x["scores"]["durability"],
            x["source_count"]
        ),
        reverse=True
    )

    # Save to opportunities.json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(opportunities, f, ensure_ascii=False, indent=2)

    # Print summary report
    print(f"\n[score] Successfully saved {len(opportunities)} qualified opportunities into {OUTPUT_FILE}")

    stage_counts = {}
    velocity_counts = {}
    for opp in opportunities:
        s = opp["stage"]
        stage_counts[s] = stage_counts.get(s, 0) + 1
        v = opp.get("velocity", "steady")
        velocity_counts[v] = velocity_counts.get(v, 0) + 1

    print("\n--- OPPORTUNITY RADAR BREAKDOWN (PHASE 6) ---")
    print(f"  • Build Ready (9/9) : {stage_counts.get('build_ready', 0)}")
    print(f"  • Research (7-8/9)  : {stage_counts.get('research', 0)}")
    print(f"  • Watch (4-6/9)     : {stage_counts.get('watch', 0)}")
    print(f"  • Drop (0-3/9)      : 0 (Excluded from output)")
    print(f"  • Velocity Trends   : 🚀 {velocity_counts.get('rising', 0)} rising | ➡️ {velocity_counts.get('steady', 0)} steady | 📉 {velocity_counts.get('fading', 0)} fading")
    print("---------------------------------------------\n")

    print("[score] TOP 10 OPPORTUNITIES PREVIEW:")
    for i, o in enumerate(opportunities[:10], 1):
        print(f"  #{i} [{o['stage'].upper()}] (Score: {o['total']}/9 | mult: {o['multiplier']} | sources: {o['source_count']})")
        print(f"      ID: {o['id']}")
        print(f"      Title: {o['title']}")
        print(f"      Types: {', '.join(o['signal_type'])} | Scores: {o['scores']}")
        print(f"      Sources: {[s['name'] for s in o['sources']]}")

    # ==================== PHASE 5: TELEGRAM ALERTS (ACT NOW / SCORE 9 ONLY) ====================
    is_dry_run = "--dry-run" in sys.argv or "--dry-run-telegram" in sys.argv
    is_test_mode = "--test-telegram" in sys.argv

    if is_test_mode:
        print("\n[score] Running in --test-telegram mode...")
        # Demo score 9 opportunity to verify Phase 5 formatting and delivery
        test_opp = {
            "id": "opp_test_actnow_sample",
            "title": "Hệ thống AI Camera & Cảm biến LiDAR giám sát giao thông đô thị và chẩn đoán hạ tầng vật lý",
            "summary": "Tín hiệu tổng hợp từ 2 nguồn độc lập đạt điểm tuyệt đối 9/9. Nhu cầu vật lý trường tồn, thay thế 80% thời gian giám sát thủ công.",
            "total": 9,
            "stage": "build_ready",
            "signal_type": ["supply_gap", "tech_cheap"],
            "sources": [
                {"name": "Báo Giao Thông", "url": "https://baogiaothong.vn", "date": today_str},
                {"name": "IEEE Sensors", "url": "https://ieeexplore.ieee.org", "date": today_str}
            ],
            "source_count": 2
        }
        send_actnow_alerts([test_opp], dry_run=is_dry_run)
    else:
        send_actnow_alerts(opportunities, dry_run=is_dry_run)


# ==================== PHASE 6 HELPER FUNCTIONS (AUTOMATIC VELOCITY) ====================

def compute_velocity(first_seen_str, last_seen_str, history_dates, source_count, pipeline_velocity=None):
    """
    Phase 6: Automatic velocity calculation based on appearance history:
    - 'rising': Xuất hiện ngày càng nhiều trong 2 tuần gần nhất (hoặc source_count >= 2)
    - 'steady': Đều đặn, xuất hiện gần đây (<= 5 ngày), không tăng không giảm
    - 'fading': Thưa dần, lâu không thấy lại (> 7 ngày kể từ lần cuối xuất hiện)
    """
    try:
        last_date = datetime.strptime(last_seen_str, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        days_since_last = (today - last_date).days
    except Exception:
        days_since_last = 0

    # Inactive for more than 7 days -> fading (thưa dần, lâu không thấy lại)
    if days_since_last > 7:
        return "fading"

    # Count appearances in last 14 days
    recent_14d_appearances = 0
    if history_dates:
        for d_str in history_dates:
            try:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
                if (today - d).days <= 14:
                    recent_14d_appearances += 1
            except Exception:
                pass
    else:
        recent_14d_appearances = 1

    # Rising: Xuất hiện ngày càng nhiều trong 2 tuần gần nhất, hoặc >= 2 nguồn xác nhận, hoặc pipeline tag 'rising'
    if pipeline_velocity == "rising":
        return "rising"
    if source_count >= 2 or recent_14d_appearances >= 3:
        return "rising"

    # Steady: Đều đặn, không tăng không giảm
    return "steady"


# ==================== PHASE 5 HELPER FUNCTIONS ====================

SIGNAL_TYPE_LABELS = {
    "pain_repeat": "Than phiền lặp lại",
    "price_shift": "Biến động giá",
    "supply_gap": "Thiếu hụt cung / Luật",
    "tech_cheap": "Công nghệ / IoT rẻ"
}


def load_sent_opportunities():
    """Load set of opportunity IDs that have already been alerted to Telegram."""
    if os.path.exists(SENT_OPPORTUNITIES_FILE):
        try:
            with open(SENT_OPPORTUNITIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict) and "sent_ids" in data:
                    return set(data["sent_ids"])
        except Exception as e:
            print(f"[score] Note: could not load sent opportunities history: {e}")
    return set()


def save_sent_opportunities(sent_ids):
    """Save set of alerted opportunity IDs to avoid duplicate Telegram notifications."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SENT_OPPORTUNITIES_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "sent_ids": sorted(list(sent_ids)),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[score] Warning: could not save sent opportunities: {e}")


def format_telegram_actnow_message(opp):
    """
    Format Telegram alert message according to Phase 5 spec:
    🔴 CƠ HỘI MỚI (9/9) — Act now
    [title]
    [summary]
    Loại: [signal_type]
    Nguồn: [source_count] nguồn xác nhận
    → Tuần này: đi hỏi 3 người thật
    """
    title = (opp.get("title") or "").strip()
    summary = (opp.get("summary") or "").strip()
    signal_types = opp.get("signal_type") or []
    type_str = ", ".join([SIGNAL_TYPE_LABELS.get(st, st) for st in signal_types]) or "Đa nguồn"
    source_count = opp.get("source_count", 1)

    sources = opp.get("sources") or []
    primary_url = sources[0].get("url") if sources else opp.get("url", "")
    url_line = f"\n🔗 {primary_url}" if primary_url else ""

    msg = (
        f"🔴 CƠ HỘI MỚI (9/9) — Act now\n"
        f"{title}\n"
        f"{summary}\n"
        f"Loại: {type_str}\n"
        f"Nguồn: {source_count} nguồn xác nhận\n"
        f"→ Tuần này: đi hỏi 3 người thật{url_line}"
    )
    return msg


def send_actnow_alerts(opportunities, dry_run=False):
    """
    Phase 5: Filter Telegram alerts.
    - Only send opportunities with total == 9 (build_ready).
    - Send each opportunity ID exactly once.
    - Never send research (7-8) or watch (4-6).
    """
    # 1. Filter: total == 9 or stage == 'build_ready'
    act_now_candidates = [
        opp for opp in opportunities
        if (opp.get("total") or 0) >= 9 or opp.get("stage") == "build_ready"
    ]

    if not act_now_candidates:
        print("\n[score] [Phase 5] No score 9/9 (build_ready) opportunities to alert via Telegram this run.")
        print("[score] [Phase 5] Research (7-8) and Watch (4-6) are kept in dashboard only (no Telegram spam).")
        return 0

    sent_ids = load_sent_opportunities()
    new_sent_count = 0

    for opp in act_now_candidates:
        opp_id = opp.get("id")
        if not opp_id:
            continue

        if opp_id in sent_ids:
            print(f"[score] [Phase 5] Skipping already alerted opportunity ID: {opp_id} ({opp.get('title')[:40]}...)")
            continue

        msg = format_telegram_actnow_message(opp)
        print(f"\n[score] [Phase 5] Preparing Telegram alert for Act Now opportunity: {opp.get('title')}")

        if dry_run:
            print("[score] [Phase 5] [DRY RUN] Would send Telegram message:\n---")
            print(msg)
            print("---\n")
            sent_ids.add(opp_id)
            new_sent_count += 1
        elif notify:
            success = notify.send_message(msg)
            if success:
                print(f"[score] [Phase 5] Successfully sent Telegram alert for: {opp_id}")
                sent_ids.add(opp_id)
                new_sent_count += 1
            else:
                print(f"[score] [Phase 5] Telegram send returned False or skipped (check credentials).")
        else:
            print("[score] [Phase 5] notify module not available.")

    if new_sent_count > 0:
        save_sent_opportunities(sent_ids)
        print(f"[score] [Phase 5] Saved {len(sent_ids)} sent opportunity IDs to {SENT_OPPORTUNITIES_FILE}")

    return new_sent_count


if __name__ == "__main__":
    main()
