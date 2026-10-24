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
SENT_HISTORY_FILE = os.path.join(DATA_DIR, "sent_history.json")



# Ensure scripts directory is in sys.path to reuse notify.py
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import notify
except ImportError:
    notify = None

try:
    from summary_vi import generate_summary_vi
except ImportError:
    try:
        from scripts.summary_vi import generate_summary_vi
    except ImportError:
        generate_summary_vi = None


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


NICHE_PATTERNS = [
    r"\b(aquaculture|fish farm\w*|shrimp\w*|fishery|fisheries|seafood|ocean|marine|algae|water quality|water sensor|dissolved oxygen|salinity|turbidity|ph sensor|water treatment|aquaponics|submetering|leak detection|waterwatch|purifyx|aquawatch)\b",
    r"\b(iot|sensor|sensors|hardware|robot\w*|camera\w*|edge ai|embedded|microcontroller|tinyml|monitoring|telemetry|actuator|drone|drones|esp32|arduino|raspberry)\b",
    r"\b(agtech|agritech|agriculture|farm\w*|crop\w*|soil|irrigation|weeder\w*|roboweeder|forestry|microgrid|solar|storage)\b",
    r"(thủy sản|nuôi tôm|nuôi cá|nông nghiệp|cảm biến|nguồn nước|môi trường nước|quan trắc|chất lượng nước)"
]

FUNDING_FLOW_PATTERNS = [
    r"\b(raises?|raised|funding|seed|series [a-e]|venture|invest\w*|capital|grant|round|valuation|backs|backed|financing|cash injection|funded|dealflow|vc dollars?)\b",
    r"(\$\d+|\b\d+\s*million|\b\d+\s*m\b|triệu usd)"
]


def is_target_niche(text):
    """Check if text is related to hardware, IoT, sensors, aquaculture, or environmental monitoring."""
    if not text:
        return False
    return any(re.search(pat, text, re.IGNORECASE) for pat in NICHE_PATTERNS)


def is_junk_signal(it):
    """
    Filter out noise TRƯỚC KHI CHẤM:
    - Tin gambling/iGaming regulatory, licensing, sportsbook
    - Tin VC funding, IPO, startup valuation, layoffs tracker
      (NGOẠI TRỪ các thương vụ/dòng tiền đầu tư vào đúng ngách IoT/Aquaculture/Hardware/Sensors)
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
    # Chỉ loại nếu KHÔNG thuộc ngách mục tiêu (IoT, aquaculture, sensors, hardware, water)
    if any(re.search(pat, text, re.IGNORECASE) for pat in JUNK_FUNDING_VC_LAYOFFS_PATTERNS):
        if not is_target_niche(text):
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


def detect_signal_types(title, summary, url, topic="", source=""):
    """
    Infer signal type strictly from title and content:
    - pain_repeat: than phiền/vấn đề lặp lại/lỗi
    - price_shift: giá/chi phí biến động, HOẶC dòng tiền đầu tư (Funding flow) đổ vào ngách IoT/Aquaculture/Hardware
    - supply_gap: thiếu giải pháp cho nhu cầu/quy định bắt buộc
    - tech_cheap: công nghệ/cảm biến/phần cứng rẻ đi
    Ví dụ: 'AI camera giao thông' KHÔNG phải pain_repeat.
    """
    text = f"{title} {summary or ''} {url or ''} {topic or ''} {source or ''}".lower()
    types = []

    def matches_any(patterns):
        return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)

    if matches_any(PAIN_PATTERNS):
        types.append("pain_repeat")

    # Phase 7: Strict 4-type Funding Classification
    is_funding_source_or_topic = (
        topic == "Funding"
        or any(s in str(source).lower() for s in ["funding", "venture", "agfunder", "crunchbase", "igrow"])
        or any(d in url.lower() for d in ["techcrunch.com/category/venture", "crunchbase.com", "agfundernews.com", "igrownews.com", "aquageek.substack.com"])
        or any(re.search(pat, text, re.IGNORECASE) for pat in FUNDING_FLOW_PATTERNS)
    )

    if is_funding_source_or_topic:
        # Type 3: M&A -> price_shift, supply_gap
        if re.search(r"\b(acquires?|acquisition|merger|takeover|takes majority stake|buys|bought|letter of intent to acquire)\b", text, re.IGNORECASE):
            types.extend(["price_shift", "supply_gap"])
        # Type 4: Rút vốn / giảm -> price_shift
        elif re.search(r"\b(funding (fell|falls|drops|dropped|slumps|slumped|down)|decline|cuts|slashed|funding gap|struggl\w* to raise|down by \d+%)\b", text, re.IGNORECASE):
            types.append("price_shift")
        # Type 1: Gọi vốn trong ngách -> price_shift, tech_cheap
        elif is_target_niche(text) and re.search(r"\b(raises?|raised|series [a-e]|seed|\$\d+[mkb]?\b|triệu usd|venture round|backed|lands \$\d+)\b", text, re.IGNORECASE):
            types.extend(["price_shift", "tech_cheap"])
        # Type 2: Xu hướng đầu tư -> price_shift
        else:
            types.append("price_shift")

    if matches_any(PRICE_PATTERNS) and "price_shift" not in types:
        types.append("price_shift")

    if matches_any(GAP_PATTERNS) and "supply_gap" not in types:
        types.append("supply_gap")

    if matches_any(TECH_CHEAP_PATTERNS) and "tech_cheap" not in types:
        types.append("tech_cheap")

    # If no pattern matched, infer from dominant technical context (NEVER blind pain_repeat)
    if not types:
        if any(k in text for k in ["model", "video", "agent", "app", "tool", "ai", "learning", "renderer", "code", "workflow", "sensor", "hardware", "iot"]):
            types.append("tech_cheap")
        else:
            types.append("supply_gap")

    return sorted(list(set(types)))


# ==================== 4. USER PROFILE ALIGNMENT & 3-LAYER SCORING ====================

HARDWARE_IOT_HIGH_PATTERNS = [
    r"\b(iot|sensor|sensors|cảm biến|hardware|robot|robots|robotics|drone|drones|camera|cameras)\b",
    r"\b(embedded (?:system|device|software|linux|hardware|firmware|board|sensor)|microcontroller|esp32|raspberry|arduino|edge ai|tinyml|firmware|physical device)\b",
    r"\b(water quality|air quality|soil|traffic|traffic police|environment|weather|energy|solar|grid)\b",
    r"\b(aquaculture|fish farm\w*|shrimp\w*|fishery|fisheries|water sensor|dissolved oxygen|salinity|turbidity|aerator|pond monitoring|aquaponics|water treatment|submetering|leak detection)\b",
    r"\b(autonomous|autonomous systems?|diagnostics?|fault diagnosis|sensor monitoring|machine monitoring|fleet|fleets|spatiotemporal memory|actuator|motor)\b",
    r"(giám sát|chẩn đoán|thiết bị|môi trường|giao thông|cảm biến|vật lý|năng lượng|thủy sản|nuôi tôm|nuôi cá|nguồn nước|ao nuôi|chất lượng nước)"
]

FINTECH_GENERIC_PATTERNS = [
    r"\b(insurance|insurer|insuretech|fintech|insurtech|banking|payments?|checkout|crypto|cryptocurrency|blockchain|defi|web3|payroll|accounting|mortgage|wealth|lending|e-commerce|ecommerce|marketing tech|hr tech)\b"
]

GENERIC_LLM_APP_PATTERNS = [
    r"\b(langchain|dify|paperclip|hermes-agent|agent framework|llm agent|prompt|chatbot)\b",
    r"\b(generative ai wrapper|text generation|ai video generation|image generation|diffusion)\b",
    r"\b(recommendation|recommender|recsys|sequential recommendation|click-through|ctr|collaborative filtering)\b",
    r"\b(3d motion|animation|video co-generating|video generation|arbitrary rigs|character rig|rigging|motion generation)\b",
    r"\b(3d reconstruction|monocular 3d|ray field|composite ray|gaussian splat\w*|nerf|novel view synthesis)\b",
    r"\b(perspective from computer-use|co-evolution|survey paper)\b"
]

TECHNICAL_SYSTEMS_PATTERNS = [
    r"\b(pipeline|automation|scraper|proxy|queue|backend|database|security|auth|devtool|compliance|regulation|regulatory|governance|audit|law|luật)\b"
]


def score_item_filters(title, summary, signal_types, matched_keyword="", meta="", engagement=0):
    """
    Score 3 filter layers based strictly on CONTENT and USER PROFILE:
    1. durability: 10-year core physical/infrastructure need
    2. ai_support: AI handles 80% data/analysis, human/physical world holds 20% responsibility
    3. your_leverage: High for IoT/Hardware/Sensors/Robotics; Low for generic LLM/pure ML papers
    
    Phase 9: High engagement (>100 upvotes on Reddit or >=100K traffic on Google Trends)
    boosts durability by 1 level (capped at 3).
    """
    text = f"{title} {summary or ''} {matched_keyword or ''} {meta or ''}".lower()

    is_fintech_generic = any(re.search(pat, text, re.IGNORECASE) for pat in FINTECH_GENERIC_PATTERNS)
    is_generic_llm = any(re.search(pat, text, re.IGNORECASE) for pat in GENERIC_LLM_APP_PATTERNS)
    is_hardware_iot = any(re.search(pat, text, re.IGNORECASE) for pat in HARDWARE_IOT_HIGH_PATTERNS) and not is_generic_llm and not is_fintech_generic
    is_tech_systems = any(re.search(pat, text, re.IGNORECASE) for pat in TECHNICAL_SYSTEMS_PATTERNS) and not is_generic_llm and not is_fintech_generic

    # Phase 7: Detect if this item is a funding flow signal
    is_funding = (
        any(re.search(pat, text, re.IGNORECASE) for pat in FUNDING_FLOW_PATTERNS)
        or any(k in text for k in ["agfunder", "crunchbase", "igrow", "techcrunch.com/category/venture", "aquageek.substack.com"])
        or ("price_shift" in signal_types and "github.com" not in text and "arxiv.org" not in text)
    )

    # 1. your_leverage (0–3): User profile match
    # Target: IoT, hardware, sensors, robotics, device diagnostics, environmental monitoring, aquaculture
    # Non-target: Generic LLM apps, pure recommendation/animation ML papers, generic fintech/VC
    if is_funding:
        if is_fintech_generic:
            your_leverage = 0  # Funding vào fintech/SaaS chung -> your_leverage 0 -> drop
        elif is_target_niche(text) or is_hardware_iot:
            your_leverage = 3
        else:
            your_leverage = 0  # Funding vào fintech/SaaS chung -> your_leverage 0 -> drop
    elif is_hardware_iot:
        your_leverage = 3
    elif is_tech_systems:
        your_leverage = 2
    elif is_generic_llm or is_fintech_generic:
        your_leverage = 0
    elif "tool" in text or "python" in text or "github.com" in text:
        your_leverage = 2
    else:
        your_leverage = 1

    # 2. durability (0–3): 10-year perennial need
    # Physical infrastructure, traffic, water, energy, industrial maintenance, diagnostics, food, aquaculture
    if is_funding:
        if is_fintech_generic:
            durability = 1
        elif is_target_niche(text) or is_hardware_iot:
            durability = 3
        else:
            durability = 1
    elif is_generic_llm:
        durability = 1
    elif bool(re.search(r"\b(water|traffic|energy|solar|grid|soil|health|safety|food|logistics|manufacturing|fleet|aquaculture|fish farm\w*|shrimp|agriculture|agtech)\b", text, re.IGNORECASE)):
        durability = 3
    elif is_hardware_iot or bool(re.search(r"\b(infrastructure|database|security|pipeline|compliance|law|regulation|diagnostics?)\b", text, re.IGNORECASE)):
        durability = 3 if any(k in text for k in ["water", "traffic", "factory", "industrial", "diagnost", "robot"]) else 2
    elif is_tech_systems or "devtool" in text or "developer" in text:
        durability = 2
    else:
        durability = 1

    # Phase 9: High engagement boost for durability (>100 upvotes or traffic 100K+)
    is_high_engagement = False
    if isinstance(engagement, (int, float)) and engagement >= 100:
        is_high_engagement = True
    elif isinstance(engagement, str) and any(k in engagement.lower() for k in ["100k", "200k", "500k", "1m"]):
        is_high_engagement = True

    if is_high_engagement and durability < 3:
        durability = min(3, durability + 1)

    # 3. ai_support (0–3): AI does 80% perception/analysis, human/physical holds 20% responsibility
    if is_funding:
        if is_target_niche(text) or is_hardware_iot:
            ai_support = 3
        else:
            ai_support = 1
    elif is_generic_llm:
        ai_support = 1
    elif bool(re.search(r"\b(camera|diagnost\w*|anomaly|monitor|inspection|audit|police|fleet|actuator|sensor)\b", text, re.IGNORECASE)):
        ai_support = 3  # Sensor/camera detection -> human operator/technician confirms and acts
    elif bool(re.search(r"\b(robot|robotics|embodied|copilot|decision support|synthes\w*|workflow|assistant)\b", text, re.IGNORECASE)):
        ai_support = 2
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


def normalize_source_name(src, url=""):
    """Normalize short codes or URLs to full human names."""
    u = (url or "").lower()
    if "techcrunch.com" in u:
        return "TechCrunch Funding"
    if "crunchbase.com" in u:
        return "Crunchbase News"
    if "agfundernews.com" in u:
        return "AgFunder News"
    if "igrownews.com" in u:
        return "iGrow News"
    if "fishfarmer" in u:
        return "Fish Farmer Magazine"
    if "creamermedia.com" in u:
        return "Engineering News Aquaculture"
    if "aquageek.substack.com" in u:
        return "aquablurb Substack"
    if "thefishsite.com" in u:
        return "The Fish Site"
    if "arxiv.org" in u:
        return "arXiv"
    if "github.com" in u:
        return "GitHub"

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
    return src_map.get((src or "").lower(), src.capitalize() if src else "Web")


def is_signal_tech(it):
    """Check if item is from a tech/research/open-source source."""
    topic = it.get("_topic") or it.get("topic") or ""
    src = (it.get("source") or "").lower()
    url = (it.get("url") or "").lower()
    if topic in ["AI/Tech", "Aquaculture & IoT"]:
        return True
    if any(k in src for k in ["github", "gh", "arxiv", "fish farmer", "creamermedia", "the fish site"]):
        return True
    if any(d in url for d in ["github.com", "arxiv.org", "fishfarmer", "creamermedia.com", "thefishsite.com"]):
        return True
    return False


def is_signal_funding(it):
    """Check if item is from a funding flow source."""
    topic = it.get("_topic") or it.get("topic") or ""
    src = (it.get("source") or "").lower()
    url = (it.get("url") or "").lower()
    if topic == "Funding":
        return True
    if any(k in src for k in ["agfunder", "crunchbase", "igrow", "techcrunch funding", "aquageek"]):
        return True
    if any(d in url for d in ["agfundernews.com", "igrownews.com", "news.crunchbase.com", "techcrunch.com/category/venture", "aquageek.substack.com"]):
        return True
    text = f"{it.get('title', '')} {it.get('summary', '')}".lower()
    return any(re.search(p, text, re.IGNORECASE) for p in FUNDING_FLOW_PATTERNS)


def is_cross_corroborated(tech_item, funding_item):
    """
    Check if a tech signal and a funding signal cover the EXACT SAME niche theme:
    - Aquaculture / fish farming / shrimp / aquaponics
    - Water quality / sensors / dissolved oxygen / salinity / leak detection / submetering
    - Agriculture robotics / farm automation / weeding
    """
    t_text = f"{tech_item.get('title', '')} {tech_item.get('summary', '')}".lower()
    f_text = f"{funding_item.get('title', '')} {funding_item.get('summary', '')}".lower()

    # Reject generic LLM / 3D graphics / animation papers
    if any(re.search(pat, t_text, re.IGNORECASE) for pat in GENERIC_LLM_APP_PATTERNS):
        return False
    if any(re.search(pat, f_text, re.IGNORECASE) for pat in GENERIC_LLM_APP_PATTERNS):
        return False

    if not (is_target_niche(t_text) and is_target_niche(f_text)):
        return False

    subtopics = [
        ("aquaculture", [r"\b(aquaculture|fish farm\w*|shrimp|fisher\w*|seafood|marine|pond|thủy sản|nuôi tôm|nuôi cá|aquaponics)\b"]),
        ("water_sensor", [r"\b(water quality|water sensor|dissolved oxygen|salinity|turbidity|ph sensor|water treatment|submetering|leak detection|leakage|waterwatch|purifyx|aquawatch|cảm biến nước|nguồn nước|quan trắc|chất lượng nước)\b"]),
        ("agritech_robotics", [r"\b(weeder|roboweeder|digit|humanoid|farm robot|crop farm|agriculture robot)\b"])
    ]

    for sub_name, pats in subtopics:
        t_has = any(re.search(p, t_text, re.IGNORECASE) for p in pats)
        f_has = any(re.search(p, f_text, re.IGNORECASE) for p in pats)
        if t_has and f_has:
            return True

    return False


def extract_funding_amount(text):
    """Extract funding dollar/currency amount from text if present, else N/A."""
    m = re.search(r"[\$€£]\d+(?:\.\d+)?\s*(?:billion|million|[kmb])\b", text, re.IGNORECASE)
    if m:
        return m.group(0).upper().replace("MILLION", "M").replace("BILLION", "B").replace(" ", "")
    m2 = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:million|billion)\s*(?:dollars?|usd|euro)?\b", text, re.IGNORECASE)
    if m2:
        unit = "B" if "billion" in m2.group(0).lower() else "M"
        return f"${m2.group(1)}{unit}"
    return "N/A"


def determine_deal_type(title, summary="", signal_types=None, summary_vi=""):
    """
    Classify funding deal type into 4 categories:
    - Gọi vốn
    - M&A
    - Xu hướng
    - Rút vốn
    """
    text = f"{title} {summary or ''} {summary_vi or ''}".lower()
    if any(k in text for k in ["acquires", "acquisition", "merger", "thâu tóm", "sáp nhập", "takes majority stake", "letter of intent to acquire"]):
        return "M&A"
    if any(k in text for k in ["funding fell", "decline", "cuts", "slash", "layoffs", "realign", "cắt giảm", "rút vốn", "funding gap", "plug"]):
        return "Rút vốn"
    if any(k in text for k in ["needs more than", "investment trends", "funding report", "report:", ": report", "biggest funding rounds", "vc dollars"]):
        return "Xu hướng"
    if any(k in text for k in ["raises", "raised", "series a", "series b", "series c", "series d", "seed round", "seed funding", "gọi vốn", "nabs", "secures", "lands", "closes", "financing round", "gọi $"]):
        return "Gọi vốn"
    if "$" in text or re.search(r"\b\d+\s*m\b", text):
        return "Gọi vốn"
    return "Xu hướng"


def determine_funding_sector(title, summary="", summary_vi=""):
    """
    Classify funding sector into 6 standard categories:
    - aquatech: 🐟 Thủy sản & Cảm biến nước
    - agtech: 🌱 Nông nghiệp & IoT
    - hardware: 🔧 Phần cứng & Robotics
    - ai_infra: 🤖 Hạ tầng AI
    - fintech: 💳 Fintech
    - other: 📦 Khác
    """
    text = f"{title} {summary or ''} {summary_vi or ''}".lower()
    if any(k in text for k in ["aquaculture", "fish", "shrimp", "seafood", "marine", "ocean", "water quality", "water sensor", "dissolved oxygen", "salinity", "turbidity", "submetering", "leak detection", "water treatment", "thủy sản", "nuôi tôm", "nuôi cá", "ao nuôi", "rò rỉ nước", "waterwatch", "purifyx"]):
        return "aquatech"
    if any(k in text for k in ["agtech", "agritech", "agriculture", "farm", "farmer", "crop", "soil", "weeder", "roboweeder", "biological", "nông nghiệp", "cây trồng", "trang trại", "harvest", "dairy", "livestock"]):
        return "agtech"
    if any(k in text for k in ["robot", "robotics", "humanoid", "drone", "sensor", "hardware", "camera", "microgrid", "solar", "thermal energy", "storage", "phần cứng", "thiết bị", "laser", "autonomous vehicle"]):
        return "hardware"
    if any(k in text for k in ["ai infra", "datacenter", "data center", "gpu", "supercomputer", "nuclear", "reactor", "semiconductor", "chipmaker"]):
        return "ai_infra"
    if any(k in text for k in ["fintech", "insurance", "insuretech", "bank", "banking", "payment", "checkout", "crypto", "blockchain", "lending"]):
        return "fintech"
    return "other"


def check_triple_signal(title, summary, sources, signal_types, summary_vi=""):
    """
    Phase 9: Triple Signal Detection
    Triggered when a core theme appears across:
    1. Funding (VC deal / price_shift / funding source)
    2. Tech (GitHub repository / arXiv paper)
    3. Social (Reddit discussions / Google Trends interest)
    """
    text = f"{title} {summary or ''} {summary_vi or ''}".lower()
    src_str = " ".join((s.get("name") or s.get("source") or "") for s in sources).lower()

    # Pillar 1: Funding
    has_funding = (
        "price_shift" in signal_types or
        any(k in src_str for k in ["agfunder", "igrow", "crunchbase", "venture", "techcrunch"]) or
        any(k in text for k in ["series a", "series b", "seed", "raises", "raised", "vc dollars", "$", "funding", "gọi vốn", "thương vụ", "m&a"])
    )

    # Pillar 2: Tech
    has_tech = (
        any(k in src_str for k in ["github", "arxiv", "hackernews", "code"]) or
        any(k in text for k in ["github", "arxiv", "repo", "model", "algorithm", "firmware", "esp32", "lorawan", "sensor node", "edge ai", "phần cứng", "cảm biến"])
    )

    # Pillar 3: Social Buzz
    has_social = (
        any(k in src_str for k in ["reddit", "google trends", "twitter", "quora"]) or
        any(k in text for k in ["water quality sensor", "aquaculture", "shrimp", "ao nuôi", "thủy sản", "smart agriculture", "robotics", "leakage", "water monitor", "ph", "dissolved oxygen"])
    )

    # Triple signal match: all 3 pillars present OR core target domain with high convergence
    is_triple = (has_funding and has_tech and has_social) or (
        (has_funding or has_tech) and ("aquaculture" in text or "thủy sản" in text or "ao nuôi" in text or "water quality" in text or "rò rỉ nước" in text or "robotics" in text or "smart agriculture" in text)
    )

    return is_triple, has_funding, has_tech, has_social


def load_raw_items():
    """Load items from signals.json or news.json, enriched with topic metadata."""
    items_map = {}

    # Gather topic metadata (matched_keyword, meta, category) from topic files
    topic_files = ["ai-tech.json", "funding.json", "aquaculture-iot.json", "social-buzz.json", "business.json", "igaming.json"]
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
                        it_copy = dict(it)
                        if it.get("topic") and not it_copy.get("_topic"):
                            it_copy["_topic"] = it["topic"]
                        items_map[k] = it_copy
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
    # (NGOẠI TRỪ các thương vụ dòng tiền đầu tư vào đúng ngách IoT/Aquaculture/Hardware/Sensors)
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

    # ==================== STEP 2: SOURCE GROUPING & CROSS-CORROBORATION ====================
    # Pass 1: Strict title comparison — gộp 2 tín hiệu khi NÓI VỀ CÙNG MỘT SỰ KIỆN/CHỦ ĐỀ.
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

    # Pass 2: Thematic Cross-Corroboration:
    # "Tín hiệu funding ở ngách phần cứng/cảm biến + tín hiệu tech từ arXiv/GitHub cùng chủ đề -> source_count = 2 -> multiplier 1.0"
    paired_funding_groups = set()

    # Prioritize tech repos/papers from GitHub & arXiv first
    def tech_priority(idx):
        it = merged_groups[idx][0]
        url = (it.get("url") or "").lower()
        src = (it.get("source") or "").lower()
        if "github.com" in url or src in ["gh", "github"]:
            return 0
        if "arxiv.org" in url or src == "arxiv":
            return 1
        return 2

    tech_indices_sorted = sorted(
        [idx for idx in range(len(merged_groups)) if is_signal_tech(merged_groups[idx][0])],
        key=tech_priority
    )

    for t_idx in tech_indices_sorted:
        grp = merged_groups[t_idx]
        t_item = grp[0]
        t_text = f"{t_item.get('title', '')} {t_item.get('summary', '')}".lower()
        if not is_target_niche(t_text):
            continue

        # Look for a corroborating funding signal in the same niche theme
        for f_idx, f_grp in enumerate(merged_groups):
            if f_idx == t_idx or f_idx in paired_funding_groups:
                continue
            f_item = f_grp[0]
            if not is_signal_funding(f_item):
                continue
            if is_cross_corroborated(t_item, f_item):
                paired_funding_groups.add(f_idx)
                # Append cloned copy of the funding items into the tech group for cross-source validation (source_count: 2)
                grp.extend([dict(it) for it in f_grp])
                break

    # Phase 7: Retain each funding item as an independent opportunity in opportunities.json!
    # (Do not remove paired_funding_groups from final_groups)
    final_groups = list(merged_groups)

    # ==================== STEP 3: SCORING & OUTPUT FILTERING ====================
    opportunities = []
    promoted_items = []
    STAGE_ORDER = {"drop": 0, "watch": 1, "research": 2, "build_ready": 3}


    for group in final_groups:
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

            src_name = normalize_source_name(srcs[0], it_url)
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

        # Enrich summary if cross-corroborated with additional source
        if len(group) > 1:
            secondary_infos = []
            for sec in group[1:]:
                sec_src = normalize_source_name((sec.get("sources") or [sec.get("source") or ""])[0], sec.get("url"))
                sec_title = sec.get("title", "")
                if sec_title and sec_title != title:
                    secondary_infos.append(f"{sec_src}: '{sec_title}'")
            if secondary_infos:
                summary = (summary or f"Tín hiệu công nghệ và cơ hội thị trường từ {formatted_sources[0]['name']}.") + f" [Đối chiếu dòng tiền & nguồn bổ sung: {'; '.join(secondary_infos)}]"

        # Collect text across the group for signal type and score
        group_titles = " ".join(it.get("title", "") for it in group)
        group_summaries = " ".join(it.get("summary", "") for it in group)
        group_urls = " ".join(it.get("url", "") for it in group)
        group_topics = " ".join(str(it.get("_topic") or it.get("topic") or "") for it in group)
        group_sources = " ".join(str(it.get("source", "")) for it in group)

        # Tag signal types based on group content
        signal_types = detect_signal_types(group_titles, group_summaries, group_urls, group_topics, group_sources)

        # Phase 9: Extract engagement metrics from group
        max_engagement = 0
        for it in group:
            eng = it.get("engagement") or it.get("upvotes") or it.get("score") or 0
            if isinstance(eng, (int, float)) and eng > max_engagement:
                max_engagement = eng
            elif isinstance(eng, str) and any(k in eng.lower() for k in ["100k", "200k", "500k", "1m"]):
                max_engagement = 100000

        # Score 3 filter layers based on content, user profile, and social engagement
        scores = score_item_filters(group_titles, group_summaries, signal_types, matched_kw, meta_str, engagement=max_engagement)

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

        summary_vi = generate_summary_vi(title, summary) if generate_summary_vi else title[:80]

        # Phase 8: Funding intelligence metadata
        funding_sector = determine_funding_sector(title, summary, summary_vi)
        deal_type = determine_deal_type(title, summary, signal_types, summary_vi)
        funding_amount = extract_funding_amount(f"{title} {summary} {summary_vi}")

        # Phase 9: Triple Signal Detection (Funding + Tech + Social)
        is_triple, has_f, has_t, has_s = check_triple_signal(title, summary, formatted_sources, signal_types, summary_vi)

        opp_record = {
            "id": opp_id,
            "title": title,
            "summary": summary if summary else f"Tín hiệu công nghệ và cơ hội thị trường từ {formatted_sources[0]['name']}.",
            "summary_vi": summary_vi,
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
            "velocity": velocity,
            "funding_sector": funding_sector,
            "deal_type": deal_type,
            "funding_amount": funding_amount,
            "triple_signal": is_triple,
            "triple_signal_badge": "🔥 Triple Signal" if is_triple else None,
            "pillar_funding": has_f,
            "pillar_tech": has_t,
            "pillar_social": has_s
        }
        opportunities.append(opp_record)

        # Phase 5B: Track stage promotion (Template 3)
        if prev_opp:
            old_stage = prev_opp.get("stage", "watch")
            old_total = prev_opp.get("total", 0)
            if STAGE_ORDER.get(stage, 0) > STAGE_ORDER.get(old_stage, 0):
                promoted_items.append({
                    "opp": opp_record,
                    "old_stage": old_stage,
                    "old_total": old_total,
                    "new_stage": stage,
                    "new_total": total
                })


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

        # Drop old opportunities that are junk or inactive for more than 30 days
        if is_junk_signal(prev_opp):
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

        # Clone and re-score with current profile criteria
        aged_opp = dict(prev_opp)
        aged_scores = score_item_filters(
            aged_opp.get("title", ""),
            aged_opp.get("summary", ""),
            aged_opp.get("signal_type", [])
        )
        aged_raw = aged_scores["durability"] + aged_scores["ai_support"] + aged_scores["your_leverage"]
        aged_mult = aged_opp.get("multiplier", 0.85)
        aged_total = int(round(aged_raw * aged_mult))
        if aged_total <= 3:
            continue

        aged_opp["scores"] = aged_scores
        aged_opp["total"] = aged_total
        aged_opp["stage"] = compute_stage(aged_total)
        if not aged_opp.get("summary_vi") or "tín hiệu công nghệ và cơ hội thị trường" in aged_opp.get("summary_vi", "").lower():
            aged_opp["summary_vi"] = generate_summary_vi(aged_opp.get("title", ""), aged_opp.get("summary", "")) if generate_summary_vi else aged_opp.get("title", "")[:80]

        # Phase 8: Funding intelligence metadata
        aged_opp["funding_sector"] = determine_funding_sector(aged_opp.get("title", ""), aged_opp.get("summary", ""), aged_opp.get("summary_vi", ""))
        aged_opp["deal_type"] = determine_deal_type(aged_opp.get("title", ""), aged_opp.get("summary", ""), aged_opp.get("signal_type", []), aged_opp.get("summary_vi", ""))
        aged_opp["funding_amount"] = extract_funding_amount(f"{aged_opp.get('title', '')} {aged_opp.get('summary', '')} {aged_opp.get('summary_vi', '')}")

        # Phase 9: Triple Signal Detection
        is_triple, has_f, has_t, has_s = check_triple_signal(
            aged_opp.get("title", ""),
            aged_opp.get("summary", ""),
            aged_opp.get("sources", []),
            aged_opp.get("signal_type", []),
            aged_opp.get("summary_vi", "")
        )
        aged_opp["triple_signal"] = is_triple
        aged_opp["triple_signal_badge"] = "🔥 Triple Signal" if is_triple else None
        aged_opp["pillar_funding"] = has_f
        aged_opp["pillar_tech"] = has_t
        aged_opp["pillar_social"] = has_s

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

        # Phase 5B: Track stage promotion for historical re-scored items
        old_stage = prev_opp.get("stage", "watch")
        old_total = prev_opp.get("total", 0)
        if STAGE_ORDER.get(aged_opp["stage"], 0) > STAGE_ORDER.get(old_stage, 0):
            promoted_items.append({
                "opp": aged_opp,
                "old_stage": old_stage,
                "old_total": old_total,
                "new_stage": aged_opp["stage"],
                "new_total": aged_total
            })


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

    def is_pure_funding_opp(opp):
        """Check if opportunity is primarily a pure funding signal (not a GitHub repo or paper)."""
        srcs = opp.get("sources", [])
        if not srcs:
            return False
        primary_url = (srcs[0].get("url") or "").lower()
        primary_name = (srcs[0].get("name") or "").lower()
        title = (opp.get("title") or "").lower()
        if any(k in primary_url for k in ["agfundernews.com", "igrownews.com", "crunchbase.com", "techcrunch.com/category/venture", "aquageek.substack.com"]):
            return True
        if any(k in primary_name for k in ["funding", "agfunder", "igrow", "crunchbase", "venture"]):
            return True
        if any(re.search(pat, title, re.IGNORECASE) for pat in FUNDING_FLOW_PATTERNS) and "github.com" not in primary_url and "arxiv.org" not in primary_url:
            return True
        return False

    opportunities.sort(
        key=lambda x: (
            VELOCITY_WEIGHT.get(x.get("velocity", "steady"), 1),
            x["total"],
            x["scores"]["your_leverage"],
            x["scores"]["durability"],
            x["source_count"],
            1 if is_pure_funding_opp(x) else 0,
            x["scores"]["ai_support"]
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
        print(f"      Summary_VI: {o.get('summary_vi')}")
        print(f"      Types: {', '.join(o['signal_type'])} | Scores: {o['scores']}")
        print(f"      Sources: {[s['name'] for s in o['sources']]}")

    # ==================== PHASE 5B: TELEGRAM ALERTS (3 TEMPLATES) ====================
    is_dry_run = "--dry-run" in sys.argv or "--dry-run-telegram" in sys.argv
    is_test_mode = "--test-telegram" in sys.argv

    if is_test_mode:
        run_telegram_tests(opportunities, dry_run=is_dry_run)
    else:
        send_phase5_alerts(opportunities, promoted_items, today_str, dry_run=is_dry_run)



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


# ==================== PHASE 5C HELPER FUNCTIONS (ANTI-SPAM & SENT HISTORY) ====================

def load_sent_history(today_str=None, history_file=SENT_HISTORY_FILE):
    """
    Phase 5C: Load sent history from sent_history.json.
    Structure per spec:
    {
        "<opp_id>": {
            "first_sent": "YYYY-MM-DD",
            "last_sent": "YYYY-MM-DD",
            "stage_when_sent": "research",
            "times_sent": 1
        }
    }
    Automatically prunes items older than 30 days (Requirement 5).
    """
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            print(f"[score] Note: could not load {history_file}: {e}")
            history = {}

    # Migration from old sent_opportunities.json if sent_history.json is not present or empty
    if not history and history_file == SENT_HISTORY_FILE and os.path.exists(SENT_OPPORTUNITIES_FILE):
        try:
            with open(SENT_OPPORTUNITIES_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if isinstance(old_data, dict):
                    fallback_date = today_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    for oid in old_data.get("sent_build_ready", []):
                        history[oid] = {
                            "first_sent": fallback_date,
                            "last_sent": fallback_date,
                            "stage_when_sent": "build_ready",
                            "times_sent": 1
                        }
                    for oid in old_data.get("sent_research_ids", []):
                        if oid not in history:
                            history[oid] = {
                                "first_sent": fallback_date,
                                "last_sent": fallback_date,
                                "stage_when_sent": "research",
                                "times_sent": 1
                            }
        except Exception:
            pass

    # Clean up entries older than 30 days (Phase 5C Requirement 5)
    cleaned_history = {}
    today_dt = datetime.strptime(today_str, "%Y-%m-%d").date() if today_str else datetime.now(timezone.utc).date()
    pruned_count = 0

    for oid, entry in history.items():
        if not isinstance(entry, dict):
            continue
        ref_date_str = entry.get("last_sent") or entry.get("first_sent")
        if ref_date_str:
            try:
                ref_dt = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
                if (today_dt - ref_dt).days > 30:
                    pruned_count += 1
                    continue
            except Exception:
                pass
        cleaned_history[oid] = entry

    if pruned_count > 0:
        print(f"[score] [Phase 5C] Cleaned up {pruned_count} entries older than 30 days from {os.path.basename(history_file)}.")

    return cleaned_history


def save_sent_history(history, history_file=SENT_HISTORY_FILE):
    """Save updated sent history into docs/data/sent_history.json."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[score] Warning: could not save {history_file}: {e}")


def send_phase5_alerts(opportunities, promoted_items, today_str, dry_run=False, history_file=SENT_HISTORY_FILE):
    """
    Phase 5C: Smart Telegram Alert Dispatcher with Anti-Spam & Max-Send Limits.

    Rules Matrix:
    1. Item MỚI, stage = build_ready      -> ✅ Gửi riêng (Template 1)
    2. Item MỚI, stage = research         -> ✅ Gộp vào tin hàng ngày (Template 2)
    3. Item MỚI, stage = watch/drop       -> ❌ Không gửi (lưu stage_when_sent, times_sent = 0)
    4. Item CŨ, tăng hạng (watch->research, research->build_ready)
                                          -> ✅ Gửi riêng (Template 3) (nếu times_sent < 2)
    5. Item CŨ, giữ nguyên stage          -> ❌ Không gửi
    6. Item CŨ, giảm hạng (research->watch)
                                          -> ❌ Không gửi
    7. Giới hạn: Mỗi ID tối đa 2 lần gửi   -> Đã gửi 2 lần -> chặn, không gửi nữa
    8. Hôm nay không có gì mới            -> ❌ Không gửi (Im lặng hoàn toàn)
    9. Dọn dẹp: > 30 ngày                 -> Tự động xóa khỏi sent_history.json
    """
    if not notify:
        print("[score] [Phase 5C] notify module is not available.")
        return 0

    STAGE_ORDER = {"drop": 0, "watch": 1, "research": 2, "build_ready": 3}
    sent_history = load_sent_history(today_str=today_str, history_file=history_file)
    history_changed = False
    alerts_sent = 0
    handled_ids = set()

    # 1. Phát hiện tăng hạng (Template 3)
    # Check both promoted_items and sent_history vs current opportunities
    promo_candidates = []
    seen_promo_ids = set()

    for promo in promoted_items:
        opp = promo["opp"]
        oid = opp.get("id")
        if oid and oid not in seen_promo_ids:
            seen_promo_ids.add(oid)
            promo_candidates.append({
                "opp": opp,
                "old_stage": promo["old_stage"],
                "old_total": promo.get("old_total", 0),
                "new_stage": promo["new_stage"],
                "new_total": promo.get("new_total", opp.get("total", 0))
            })

    # Also detect promotion from sent_history
    for opp in opportunities:
        oid = opp.get("id")
        if not oid or oid in seen_promo_ids:
            continue
        hist_entry = sent_history.get(oid)
        if hist_entry and hist_entry.get("stage_when_sent"):
            hist_stage = hist_entry["stage_when_sent"]
            curr_stage = opp.get("stage")
            if STAGE_ORDER.get(curr_stage, 0) > STAGE_ORDER.get(hist_stage, 0):
                seen_promo_ids.add(oid)
                promo_candidates.append({
                    "opp": opp,
                    "old_stage": hist_stage,
                    "old_total": opp.get("total", 0) - 1,
                    "new_stage": curr_stage,
                    "new_total": opp.get("total", 0)
                })

    # Safety: Cap promotions per run at maximum 3 to prevent Telegram spamming
    promo_candidates.sort(key=lambda x: x.get("new_total", 0), reverse=True)
    if len(promo_candidates) > 3:
        print(f"[score] [Phase 5C] Capping {len(promo_candidates)} promotions down to top 3 to prevent notification spam.")
        for extra in promo_candidates[3:]:
            e_id = extra["opp"]["id"]
            he = sent_history.get(e_id)
            if he:
                he["stage_when_sent"] = extra["new_stage"]
                history_changed = True
        promo_candidates = promo_candidates[:3]

    for promo in promo_candidates:
        opp = promo["opp"]
        opp_id = opp["id"]
        old_stage = promo["old_stage"]
        new_stage = promo["new_stage"]
        old_total = promo["old_total"]
        new_total = promo["new_total"]

        hist_entry = sent_history.get(opp_id)
        times_sent = hist_entry.get("times_sent", 0) if hist_entry else 0

        # Giới hạn gửi: Mỗi ID gửi tối đa 2 lần (lần đầu + 1 lần tăng hạng)
        if times_sent >= 2:
            print(f"[score] [Phase 5C] Bỏ qua tăng hạng cho {opp_id}: Đã đạt giới hạn tối đa 2 lần gửi ({times_sent}/2).")
            handled_ids.add(opp_id)
            continue

        msg = notify.format_template3_promotion(
            opp=opp,
            old_stage=old_stage,
            old_total=old_total,
            new_stage=new_stage,
            new_total=new_total
        )
        print(f"\n[score] [Phase 5C] Gửi Template 3 (TĂNG HẠNG: {old_stage} -> {new_stage}): {opp.get('title')[:60]}...")
        if dry_run:
            print("[score] [DRY RUN] Message:\n" + ("=" * 45) + f"\n{msg}\n" + ("=" * 45))
            first_sent = (hist_entry.get("first_sent") if hist_entry else None) or today_str
            sent_history[opp_id] = {
                "first_sent": first_sent,
                "last_sent": today_str,
                "stage_when_sent": new_stage,
                "times_sent": times_sent + 1
            }
            history_changed = True
            alerts_sent += 1
            handled_ids.add(opp_id)
        else:
            if notify.send_message(msg):
                print(f"[score] [Phase 5C] Đã gửi thành công Template 3 cho: {opp_id}")
                first_sent = (hist_entry.get("first_sent") if hist_entry else None) or today_str
                sent_history[opp_id] = {
                    "first_sent": first_sent,
                    "last_sent": today_str,
                    "stage_when_sent": new_stage,
                    "times_sent": times_sent + 1
                }
                history_changed = True
                alerts_sent += 1
                handled_ids.add(opp_id)
            else:
                print(f"[score] [Phase 5C] Gửi Template 3 thất bại cho: {opp_id}")

    # 2. Item MỚI, stage = build_ready (Template 1 - Tối đa 2 items/ngày)
    build_ready_candidates = [
        opp for opp in opportunities
        if (opp.get("total") or 0) >= 9 or opp.get("stage") == "build_ready"
    ]
    if len(build_ready_candidates) > 2:
        build_ready_candidates = build_ready_candidates[:2]
    for opp in build_ready_candidates:
        opp_id = opp.get("id")
        if not opp_id or opp_id in handled_ids:
            continue

        hist_entry = sent_history.get(opp_id)
        if hist_entry:
            # Item CŨ: giữ nguyên stage hoặc đã gửi
            if hist_entry.get("stage_when_sent") == "build_ready" and hist_entry.get("times_sent", 0) > 0:
                continue
            if hist_entry.get("times_sent", 0) >= 2:
                continue

        msg = notify.format_template1_build_ready(opp)
        print(f"\n[score] [Phase 5C] Gửi Template 1 (Build-Ready 9/9): {opp.get('title')[:60]}...")
        if dry_run:
            print("[score] [DRY RUN] Message:\n" + ("=" * 45) + f"\n{msg}\n" + ("=" * 45))
            times_sent = hist_entry.get("times_sent", 0) if hist_entry else 0
            sent_history[opp_id] = {
                "first_sent": (hist_entry.get("first_sent") if hist_entry else None) or today_str,
                "last_sent": today_str,
                "stage_when_sent": "build_ready",
                "times_sent": times_sent + 1
            }
            history_changed = True
            alerts_sent += 1
            handled_ids.add(opp_id)
        else:
            if notify.send_message(msg):
                print(f"[score] [Phase 5C] Đã gửi thành công Template 1 cho: {opp_id}")
                times_sent = hist_entry.get("times_sent", 0) if hist_entry else 0
                sent_history[opp_id] = {
                    "first_sent": (hist_entry.get("first_sent") if hist_entry else None) or today_str,
                    "last_sent": today_str,
                    "stage_when_sent": "build_ready",
                    "times_sent": times_sent + 1
                }
                history_changed = True
                alerts_sent += 1
                handled_ids.add(opp_id)
            else:
                print(f"[score] [Phase 5C] Gửi Template 1 thất bại cho: {opp_id}")

    # 3. Item MỚI, stage = research (Template 2 - Gộp 1 tin/ngày)
    all_research_candidates = [
        opp for opp in opportunities
        if opp.get("stage") == "research" and opp.get("stage") != "build_ready"
    ]
    new_research_candidates = []
    for opp in all_research_candidates:
        opp_id = opp.get("id")
        if not opp_id or opp_id in handled_ids:
            continue
        hist_entry = sent_history.get(opp_id)
        if hist_entry:
            # Item CŨ, giữ nguyên research -> không gửi lại
            if hist_entry.get("stage_when_sent") == "research" and hist_entry.get("times_sent", 0) > 0:
                continue
            if hist_entry.get("times_sent", 0) >= 2:
                continue
        new_research_candidates.append(opp)

    if not new_research_candidates:
        print("\n[score] [Phase 5C] Hôm nay không có cơ hội research mới -> Telegram hoàn toàn im lặng.")
    else:
        try:
            today_dt = datetime.strptime(today_str, "%Y-%m-%d")
            today_display = today_dt.strftime("%d/%m/%Y")
        except Exception:
            today_display = datetime.now(timezone.utc).strftime("%d/%m/%Y")

        digest_msg = notify.format_template2_research_digest(new_research_candidates, date_str=today_display)
        if digest_msg:
            print(f"\n[score] [Phase 5C] Gửi Template 2 (Research Digest, {len(new_research_candidates)} items mới)...")
            if dry_run:
                print("[score] [DRY RUN] Message:\n" + ("=" * 45) + f"\n{digest_msg}\n" + ("=" * 45))
                for opp in new_research_candidates:
                    oid = opp["id"]
                    he = sent_history.get(oid)
                    ts = he.get("times_sent", 0) if he else 0
                    sent_history[oid] = {
                        "first_sent": (he.get("first_sent") if he else None) or today_str,
                        "last_sent": today_str,
                        "stage_when_sent": "research",
                        "times_sent": ts + 1
                    }
                    handled_ids.add(oid)
                history_changed = True
                alerts_sent += 1
            else:
                if notify.send_message(digest_msg):
                    print(f"[score] [Phase 5C] Đã gửi thành công Template 2 daily research digest.")
                    for opp in new_research_candidates:
                        oid = opp["id"]
                        he = sent_history.get(oid)
                        ts = he.get("times_sent", 0) if he else 0
                        sent_history[oid] = {
                            "first_sent": (he.get("first_sent") if he else None) or today_str,
                            "last_sent": today_str,
                            "stage_when_sent": "research",
                            "times_sent": ts + 1
                        }
                        handled_ids.add(oid)
                    history_changed = True
                    alerts_sent += 1
                else:
                    print(f"[score] [Phase 5C] Gửi Template 2 digest thất bại.")

    # 4. Item MỚI, stage = watch / drop (❌ Không gửi, ghi nhận vào sent_history với times_sent = 0)
    for opp in opportunities:
        opp_id = opp.get("id")
        stage = opp.get("stage")
        if not opp_id or stage not in ("watch", "drop"):
            continue
        if opp_id not in sent_history:
            sent_history[opp_id] = {
                "first_sent": None,
                "last_sent": None,
                "stage_when_sent": stage,
                "times_sent": 0
            }
            history_changed = True

    if history_changed:
        save_sent_history(sent_history, history_file=history_file)

    return alerts_sent


def run_phase5c_tests(opportunities, dry_run=True):
    """
    Run dedicated test suite for Phase 5C validating all 6 Done Criteria:
    - [x] Gửi cùng ID 2 pipeline liên tiếp: lần 2 bị chặn (không gửi lại).
    - [x] Item tăng từ watch → research: gửi đúng Template 3 "⬆️ TĂNG HẠNG".
    - [x] Item giữ nguyên research: không gửi lại.
    - [x] Hôm nay không có gì mới: Telegram im lặng hoàn toàn.
    - [x] sent_history.json được tạo và cập nhật đúng sau mỗi lần chạy.
    - [x] Item cũ >30 ngày bị dọn khỏi sent_history.
    """
    print("\n" + ("#" * 65))
    print("[score] [Phase 5C] RUNNING AUTOMATED COMPLIANCE TEST SUITE")
    print(("#" * 65) + "\n")

    test_history_path = os.path.join(DATA_DIR, "test_sent_history.json")
    if os.path.exists(test_history_path):
        os.remove(test_history_path)

    today = "2026-10-24"

    # --- TEST 1: New items dispatch & consecutive duplicate rejection ---
    print("--- [TEST 1/6] ITEM MỚI GỬI LẦN 1, LẦN 2 BỊ CHẶN (CHỐNG TRÙNG) ---")
    item_res = {
        "id": "opp_test_p5c_res",
        "title": "Mô hình Edge AI phân tích oxy hòa tan",
        "summary_vi": "Cảm biến đo oxy hòa tan với thuật toán biên",
        "signal_type": ["tech_cheap"],
        "total": 8,
        "stage": "research"
    }
    sent1 = send_phase5_alerts([item_res], [], today, dry_run=True, history_file=test_history_path)
    print(f"  -> Pipeline Lần 1: Số tin gửi = {sent1} (Kỳ vọng: 1 - Digest có 1 item)")
    assert sent1 == 1, f"Expected 1, got {sent1}"

    sent2 = send_phase5_alerts([item_res], [], today, dry_run=True, history_file=test_history_path)
    print(f"  -> Pipeline Lần 2 (cùng item giữ nguyên stage): Số tin gửi = {sent2} (Kỳ vọng: 0 - Bị chặn)")
    assert sent2 == 0, f"Expected 0, got {sent2}"
    print("  ✅ PASS: Gửi cùng ID 2 lần liên tiếp bị chặn hoàn toàn.")

    # --- TEST 2: Promotion watch -> research ---
    print("\n--- [TEST 2/6] ITEM TĂNG HẠNG (watch -> research) ---")
    item_promo = {
        "id": "opp_test_p5c_watch",
        "title": "Trạm cảm biến quan trắc độ mặn",
        "summary_vi": "Thiết bị giám sát xâm nhập mặn ao nuôi",
        "signal_type": ["supply_gap"],
        "total": 5,
        "stage": "watch"
    }
    # Initial run: stage = watch (Not sent)
    send_phase5_alerts([item_promo], [], today, dry_run=True, history_file=test_history_path)
    hist = load_sent_history(today, history_file=test_history_path)
    assert hist["opp_test_p5c_watch"]["times_sent"] == 0, "Watch item should not be sent"
    print("  -> Item mới stage watch: Đã lưu sent_history với times_sent = 0 (Không gửi tin)")

    # Upgrade to research
    item_promo["stage"] = "research"
    item_promo["total"] = 7
    promo_record = {
        "opp": item_promo,
        "old_stage": "watch",
        "old_total": 5,
        "new_stage": "research",
        "new_total": 7
    }
    sent_promo = send_phase5_alerts([item_promo], [promo_record], today, dry_run=True, history_file=test_history_path)
    hist = load_sent_history(today, history_file=test_history_path)
    print(f"  -> Khi tăng hạng watch -> research: Số tin gửi = {sent_promo} (Kỳ vọng: 1 - Template 3)")
    print(f"  -> Trạng thái trong history: stage_when_sent = '{hist['opp_test_p5c_watch']['stage_when_sent']}', times_sent = {hist['opp_test_p5c_watch']['times_sent']}")
    assert sent_promo == 1, f"Expected 1, got {sent_promo}"
    assert hist["opp_test_p5c_watch"]["stage_when_sent"] == "research"
    assert hist["opp_test_p5c_watch"]["times_sent"] == 1
    print("  ✅ PASS: Tăng hạng watch -> research gửi đúng Template 3 và cập nhật sent_history.")

    # --- TEST 3: Max send limit (2/2) ---
    print("\n--- [TEST 3/6] GIỚI HẠN GỬI TỐI ĐA 2 LẦN ---")
    # Upgrade research -> build_ready (times_sent becomes 2)
    item_promo["stage"] = "build_ready"
    item_promo["total"] = 9
    promo_record2 = {
        "opp": item_promo,
        "old_stage": "research",
        "old_total": 7,
        "new_stage": "build_ready",
        "new_total": 9
    }
    sent_promo2 = send_phase5_alerts([item_promo], [promo_record2], today, dry_run=True, history_file=test_history_path)
    hist = load_sent_history(today, history_file=test_history_path)
    print(f"  -> Tăng hạng lần 2 (research -> build_ready): Số tin gửi = {sent_promo2}, times_sent = {hist['opp_test_p5c_watch']['times_sent']}")
    assert sent_promo2 == 1
    assert hist["opp_test_p5c_watch"]["times_sent"] == 2

    # Attempt to send again when already at times_sent = 2
    sent_blocked = send_phase5_alerts([item_promo], [promo_record2], today, dry_run=True, history_file=test_history_path)
    print(f"  -> Thử gửi lần 3: Số tin gửi = {sent_blocked} (Kỳ vọng: 0 - Đã chạm trần 2/2)")
    assert sent_blocked == 0
    print("  ✅ PASS: Chặn đúng quy tắc mỗi ID tối đa gửi 2 lần.")

    # --- TEST 4: Demotion or same stage ---
    print("\n--- [TEST 4/6] GIỮ NGUYÊN STAGE HOẶC GIẢM HẠNG (KHÔNG GỬI) ---")
    item_demote = {
        "id": "opp_test_demote",
        "title": "Hệ thống giảm hạng",
        "stage": "research",
        "total": 7
    }
    send_phase5_alerts([item_demote], [], today, dry_run=True, history_file=test_history_path)
    # Demote to watch
    item_demote["stage"] = "watch"
    item_demote["total"] = 5
    sent_demote = send_phase5_alerts([item_demote], [], today, dry_run=True, history_file=test_history_path)
    print(f"  -> Item giảm hạng (research -> watch): Số tin gửi = {sent_demote} (Kỳ vọng: 0)")
    assert sent_demote == 0
    print("  ✅ PASS: Giảm hạng hoàn toàn không gửi thông báo rác.")

    # --- TEST 5: Silence when nothing new ---
    print("\n--- [TEST 5/6] HÔM NAY KHÔNG CÓ GÌ MỚI (IM LẶNG HOÀN TOÀN) ---")
    sent_silent = send_phase5_alerts([], [], today, dry_run=True, history_file=test_history_path)
    print(f"  -> Batch rỗng: Số tin gửi = {sent_silent} (Kỳ vọng: 0)")
    assert sent_silent == 0
    print("  ✅ PASS: Không có tin mới -> Telegram hoàn toàn im lặng.")

    # --- TEST 6: 30-day cleanup ---
    print("\n--- [TEST 6/6] DỌN DẸP ITEM CŨ > 30 NGÀY KHỎI SENT_HISTORY.JSON ---")
    test_hist_data = {
        "opp_recent": {
            "first_sent": "2026-10-20",
            "last_sent": "2026-10-20",
            "stage_when_sent": "research",
            "times_sent": 1
        },
        "opp_ancient": {
            "first_sent": "2026-09-01",  # ~53 days ago
            "last_sent": "2026-09-01",
            "stage_when_sent": "build_ready",
            "times_sent": 1
        }
    }
    with open(test_history_path, "w", encoding="utf-8") as f:
        json.dump(test_hist_data, f)

    loaded_cleaned = load_sent_history("2026-10-24", history_file=test_history_path)
    print(f"  -> Trước khi dọn: 2 items (opp_recent: 4 ngày trước, opp_ancient: 53 ngày trước)")
    print(f"  -> Sau khi dọn: {len(loaded_cleaned)} items còn lại ({list(loaded_cleaned.keys())})")
    assert "opp_recent" in loaded_cleaned, "opp_recent should be kept"
    assert "opp_ancient" not in loaded_cleaned, "opp_ancient should be pruned"
    print("  ✅ PASS: Item cũ >30 ngày tự động được dọn dẹp sạch sẽ.")

    # Cleanup test file
    if os.path.exists(test_history_path):
        os.remove(test_history_path)

    print("\n" + ("#" * 65))
    print("[score] [Phase 5C] ALL 6 ACCEPTANCE CRITERIA PASSED!")
    print(("#" * 65) + "\n")


def run_telegram_tests(opportunities, dry_run=False):
    """
    Run full suite of Telegram template checks (Phase 5B) + Phase 5C compliance tests.
    """
    # Run Phase 5C compliance suite first
    run_phase5c_tests(opportunities, dry_run=True)

    print("\n" + ("#" * 65))
    print("[score] [Phase 5B/5C] DISPLAYING FORMATTED TEMPLATES")
    print(("#" * 65) + "\n")

    # Sample build-ready item (Nuôi tôm / nước)
    build_ready_sample = {
        "id": "opp_test_br_001",
        "title": "Hệ thống phao cảm biến đa chỉ số nước hồ nuôi tôm (DO, pH, độ mặn, nhiệt độ)",
        "summary": "Bộ thiết bị giám sát liên tục chất lượng nước ao nuôi tôm, cảnh báo sớm biến động oxy hòa tan và độ mặn qua LoRaWAN.",
        "summary_vi": "Cụm phao quan trắc tự động các chỉ số nước thiết yếu cho ao tôm thâm canh.",
        "signal_type": ["supply_gap", "tech_cheap"],
        "scores": {"durability": 3, "ai_support": 3, "your_leverage": 3},
        "multiplier": 1.0,
        "total": 9,
        "stage": "build_ready",
        "velocity": "rising",
        "source_count": 2,
        "sources": [
            {"name": "Fish Farmer Magazine", "url": "https://www.fishfarmermagazine.com/news/water-sensors-2026", "date": "2026-10-24"},
            {"name": "AgFunder News", "url": "https://agfundernews.com/aquaculture-iot-sensors", "date": "2026-10-24"}
        ]
    }

    # 1. Test Template 1
    print("--- [TEST 1/4] TEMPLATE 1: BUILD-READY (9/9) ---")
    msg1 = notify.format_template1_build_ready(build_ready_sample)
    print(msg1)
    if not dry_run and notify:
        notify.send_message(msg1)

    # 2. Test Template 2
    print("\n--- [TEST 2/4] TEMPLATE 2: RESEARCH DIGEST (CÓ ITEM) ---")
    research_samples = [
        {
            "id": "opp_test_res_001",
            "title": "Cảm biến quang học đo độ đục và vi tảo thời gian thực",
            "summary_vi": "Cảm biến quang phổ giá rẻ đo mật độ tảo và độ đục trong nuôi trồng thủy sản.",
            "signal_type": ["tech_cheap"],
            "total": 8
        },
        {
            "id": "opp_test_res_002",
            "title": "Mô hình Edge AI phát hiện sớm tôm bỏ ăn qua âm thanh thủy âm",
            "summary_vi": "Thiết bị hydrophone lắng nghe âm thanh tôm bắt mồi để điều tiết thức ăn tự động.",
            "signal_type": ["pain_repeat", "tech_cheap"],
            "total": 7
        }
    ]
    msg2 = notify.format_template2_research_digest(research_samples, date_str="24/10/2026")
    print(msg2)
    if not dry_run and notify:
        notify.send_message(msg2)

    # 3. Test Template 2 Silence
    print("\n--- [TEST 3/4] TEMPLATE 2: RESEARCH DIGEST (KHÔNG CÓ ITEM -> IM LẶNG) ---")
    msg2_empty = notify.format_template2_research_digest([])
    if msg2_empty is None:
        print("✅ SUCCESS: Khi danh sách research rỗng, hàm trả về None -> Telegram hoàn toàn im lặng (không gửi tin nhắn).")
    else:
        print("❌ FAIL: Hàm không trả về None khi danh sách rỗng.")

    # 4. Test Template 3
    print("\n--- [TEST 4/4] TEMPLATE 3: TĂNG HẠNG (PROMOTION) ---")
    promo_sample = {
        "id": "opp_test_promo_001",
        "title": "Mạng cảm biến LoRaWAN quan trắc xâm nhập mặn vùng đồng bằng sông Cửu Long",
        "summary_vi": "Trạm cảm biến quan trắc độ mặn từ xa cảnh báo xâm nhập mặn phục vụ tưới tiêu nông nghiệp.",
        "signal_type": ["supply_gap", "price_shift"],
        "sources": [{"name": "Báo Nông Nghiệp", "url": "https://nongnghiep.vn/xuat-hien-xam-nhap-man-som"}]
    }
    msg3 = notify.format_template3_promotion(
        opp=promo_sample,
        old_stage="watch",
        old_total=6,
        new_stage="research",
        new_total=8
    )
    print(msg3)
    if not dry_run and notify:
        notify.send_message(msg3)

    print("\n" + ("#" * 65))
    print("[score] [Phase 5C] COMPLETED ALL TELEGRAM & COMPLIANCE TESTS")
    print(("#" * 65) + "\n")




if __name__ == "__main__":
    main()
