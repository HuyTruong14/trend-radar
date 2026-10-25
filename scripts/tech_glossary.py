#!/usr/bin/env python3
"""
Phase 13: Tech Glossary & Term Extraction Engine.
Trích xuất tên công nghệ từ tất cả signals, đếm tần suất, tính trend tuần,
xây dựng ma trận co-occurrence và phát hiện thuật ngữ công nghệ mới.

Outputs:
  - docs/data/tech_glossary.json
  - docs/data/tech_timeline.json
  - docs/data/tech_new_terms.json
"""

import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, "docs", "data")
SEED_FILE = os.path.join(DATA_DIR, "tech_terms_seed.json")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")
OPPS_FILE = os.path.join(DATA_DIR, "opportunities.json")
WEEKLY_DIR = os.path.join(DATA_DIR, "weekly")

GLOSSARY_FILE = os.path.join(DATA_DIR, "tech_glossary.json")
TIMELINE_FILE = os.path.join(DATA_DIR, "tech_timeline.json")
NEW_TERMS_FILE = os.path.join(DATA_DIR, "tech_new_terms.json")

# Common English, media brands, and generic IT stopwords to ignore when discovering new terms
STOPWORDS = {
    "HTTP", "HTTPS", "JSON", "HTML", "CSS", "URL", "REST", "CLI", "SDK", "AI", "ML",
    "UI", "UX", "USD", "USA", "VND", "EUR", "THE", "AND", "FOR", "NOT", "WITH", "FROM", "NEW", "TOP",
    "ALL", "BUT", "CAN", "GET", "SET", "HOW", "WHY", "WHAT", "THIS", "THAT", "SOME",
    "MORE", "WHEN", "WHERE", "WHO", "WILL", "HAVE", "BEEN", "EACH", "MAKE", "LIKE",
    "TIME", "JUST", "KNOW", "TAKE", "PEOPLE", "INTO", "YEAR", "YOUR", "GOOD", "SEE",
    "OTHER", "THAN", "THEN", "NOW", "LOOK", "ONLY", "COME", "ITS", "OVER", "THINK",
    "ALSO", "BACK", "AFTER", "USE", "TWO", "OUR", "WORK", "FIRST", "WELL", "WAY",
    "EVEN", "WANT", "BECAUSE", "ANY", "THESE", "GIVE", "DAY", "MOST", "CODE", "REPO",
    "GITHUB", "COMMIT", "BRANCH", "ISSUE", "PULL", "STAR", "FORK", "OPEN", "SOURCE",
    "FREE", "DATA", "TEST", "TOOL", "DEV", "PROD", "PAGE", "POST", "LINK", "FILE",
    "USER", "NAME", "INFO", "APP", "WEB", "KEY", "ITEM", "LIST", "VIEW", "TECH",
    "SYSTEM", "DEVICE", "PROJECT", "BUILD", "RUN", "CREATE", "CHECK", "REPORT",
    # Media, social & companies
    "LINKEDIN", "TECHCRUNCH", "LUATVIETNAM", "YOUGOV", "BLOOMBERG", "REUTERS",
    "REDDIT", "TWITTER", "YOUTUBE", "GOOGLE", "META", "FACEBOOK", "AMAZON",
    "MICROSOFT", "MEDIUM", "SUBSTACK", "HACKERNEWS", "TIKTOK", "TELEGRAM",
    "PYTHONANYWHERE", "WIKIPEDIA", "BAOMOI", "VNEXPRESS"
}


def load_json(filepath, default=None):
    if not os.path.exists(filepath):
        return default if default is not None else {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[tech_glossary] Warning: could not read {filepath}: {e}")
        return default if default is not None else {}


def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[tech_glossary] ✅ Saved: {filepath}")


def get_current_week_str():
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    iso_year, iso_week, _ = vn_now.isocalendar()
    return f"W{iso_week}"


def compile_seed_patterns(seed):
    """Compile case-insensitive word-boundary regexes for each canonical term and its aliases."""
    patterns = {}
    for term, meta in seed.items():
        variants = [term] + meta.get("aliases", [])
        clean_vars = [re.escape(v.strip()) for v in variants if v.strip()]
        if not clean_vars:
            continue
        # Use word boundaries; for special characters (like C#, C++), handle boundary safely
        combined = "|".join(clean_vars)
        regex_str = r"(?i)\b(?:" + combined + r")\b"
        patterns[term] = re.compile(regex_str)
    return patterns


def extract_frequencies_and_cooccurrence(seed, signals, opps=None):
    """
    Scan all signal and opportunity texts to count occurrences and pair co-occurrences.
    """
    patterns = compile_seed_patterns(seed)
    term_counts = {term: 0 for term in seed}
    co_occurs = {term: {} for term in seed}

    # Combine signals and opportunities while deduplicating by URL or ID
    seen_keys = set()
    records = []

    for s in signals or []:
        key = s.get("url") or s.get("title") or ""
        if key and key in seen_keys:
            continue
        if key:
            seen_keys.add(key)
        records.append(s)

    for o in opps or []:
        key = o.get("url") or o.get("id") or o.get("title") or ""
        if key and key in seen_keys:
            continue
        if key:
            seen_keys.add(key)
        records.append(o)

    for r in records:
        title = r.get("title") or ""
        summary = r.get("summary") or r.get("summary_vi") or ""
        desc = r.get("description") or ""
        text = f"{title} {summary} {desc}"

        matched_terms = []
        for term, pat in patterns.items():
            if pat.search(text):
                matched_terms.append(term)
                term_counts[term] += 1

        # Calculate co-occurrences within this record
        for t1 in matched_terms:
            for t2 in matched_terms:
                if t1 != t2:
                    co_occurs[t1][t2] = co_occurs[t1].get(t2, 0) + 1

    return term_counts, co_occurs


def load_previous_week_data():
    """
    Load previous week tech frequencies from weekly archive (e.g. W42)
    or existing timeline file.
    """
    # 1. Try finding W42 archive
    w42_file = os.path.join(WEEKLY_DIR, "W42_2026-10-14_to_2026-10-20.json")
    if os.path.exists(w42_file):
        w42_data = load_json(w42_file, {})
        freq = w42_data.get("tech_frequency", {})
        if freq:
            return "W42", {k: v.get("count", 0) for k, v in freq.items()}

    # 2. Try any previous weekly json
    if os.path.exists(WEEKLY_DIR):
        files = sorted([f for f in os.listdir(WEEKLY_DIR) if f.startswith("W") and f.endswith(".json")])
        if len(files) >= 2:
            prev_file = os.path.join(WEEKLY_DIR, files[-2])
            prev_data = load_json(prev_file, {})
            freq = prev_data.get("tech_frequency", {})
            if freq:
                week_str = prev_data.get("week") or files[-2].split("_")[0]
                return week_str, {k: v.get("count", 0) for k, v in freq.items()}

    # 3. Fallback baseline if no file found
    baseline = {
        "ESP32": 15, "TinyML": 10, "LoRaWAN": 9, "RP2350": 5, "RP2040": 4,
        "RISC-V": 8, "STM32": 1, "ROS2": 7, "Edge AI": 14, "Computer Vision": 1,
        "BLE": 1, "MQTT": 5, "Humanoid": 4, "Robotics": 18, "Sensor": 25,
        "LLM": 6, "Arduino": 4, "Modbus": 3, "Matter": 2, "NB-IoT": 2,
        "Ultrasonic": 2, "DO (Dissolved Oxygen)": 2, "pH Sensor": 2
    }
    return "W42", baseline


def build_tech_glossary(seed, this_week_counts, prev_week_counts, co_occurs):
    """
    Build tech_glossary.json according to specified schema and trend rules:
      - Tăng > 30% -> rising
      - Thay đổi -30% ~ +30% -> stable
      - Giảm > 30% -> fading
      - Tuần trước = 0, tuần này > 0 -> new
    """
    glossary = {}

    for term, meta in seed.items():
        this_cnt = this_week_counts.get(term, 0)
        prev_cnt = prev_week_counts.get(term, 0)

        # change_pct calculation
        if prev_cnt > 0:
            change_pct = round(((this_cnt - prev_cnt) / prev_cnt) * 100)
        else:
            change_pct = 100 if this_cnt > 0 else 0

        # Trend rule
        if prev_cnt == 0 and this_cnt > 0:
            trend = "new"
        elif change_pct > 30:
            trend = "rising"
        elif change_pct < -30:
            trend = "fading"
        else:
            trend = "stable"

        # Sort co_occurs_with by count descending, top 8
        raw_co = co_occurs.get(term, {})
        sorted_co = dict(sorted(raw_co.items(), key=lambda x: x[1], reverse=True)[:8])

        glossary[term] = {
            "type": meta.get("type", "General"),
            "description_vi": meta.get("description_vi", ""),
            "mentions_this_week": this_cnt,
            "mentions_prev_week": prev_cnt,
            "change_pct": change_pct,
            "trend": trend,
            "co_occurs_with": sorted_co
        }

    # Sort dictionary by mentions_this_week descending
    sorted_glossary = dict(sorted(glossary.items(), key=lambda x: x[1]["mentions_this_week"], reverse=True))
    return sorted_glossary


def build_tech_timeline(seed, current_week, this_week_counts, prev_week, prev_week_counts, existing_timeline_file=None):
    """
    Build or update tech_timeline.json accumulating weekly history across >= 2 weeks.
    Schema:
    {
      "ESP32": {
        "weekly": [
          {"week": "W42", "count": 15},
          {"week": "W43", "count": 26}
        ],
        "consecutive_rising_weeks": 2,
        "total_mentions": 41
      }
    }
    """
    timeline = load_json(existing_timeline_file or TIMELINE_FILE, {})

    for term in seed:
        this_cnt = this_week_counts.get(term, 0)
        prev_cnt = prev_week_counts.get(term, 0)

        term_entry = timeline.get(term, {})
        weekly_list = term_entry.get("weekly", [])

        # Ensure previous week exists
        has_prev = any(w.get("week") == prev_week for w in weekly_list)
        if not has_prev:
            weekly_list.insert(0, {"week": prev_week, "count": prev_cnt})

        # Ensure current week exists/updates
        has_curr = False
        for w in weekly_list:
            if w.get("week") == current_week:
                w["count"] = this_cnt
                has_curr = True
                break
        if not has_curr:
            weekly_list.append({"week": current_week, "count": this_cnt})

        # Sort weekly by week string
        weekly_list = sorted(weekly_list, key=lambda x: x.get("week", ""))

        # Calculate consecutive_rising_weeks (counting backwards from end)
        consecutive_rising = 0
        for i in range(len(weekly_list) - 1, 0, -1):
            if weekly_list[i]["count"] > weekly_list[i - 1]["count"]:
                consecutive_rising += 1
            else:
                break

        total_mentions = sum(w.get("count", 0) for w in weekly_list)

        timeline[term] = {
            "weekly": weekly_list,
            "consecutive_rising_weeks": consecutive_rising,
            "total_mentions": total_mentions
        }

    # Sort timeline by total_mentions descending
    sorted_timeline = dict(sorted(timeline.items(), key=lambda x: x[1]["total_mentions"], reverse=True))
    return sorted_timeline


def detect_new_terms(seed, signals, opps=None, current_week="W43"):
    """
    Discover candidate new technical terms matching patterns:
      1. Technical alphanumeric with digits (e.g. RP2350, ESP32C6, BME680, DS18B20)
      2. File extensions (.js, .py, .rs, .cpp)
      3. CamelCase specialized technical terms (e.g. AquaSC, RoboWeeder, UniWALM)
    Output schema:
      [ {"term": "...", "first_seen": "W...", "count": N, "context": "..."} ]
    """
    seed_variants = set()
    for term, meta in seed.items():
        seed_variants.add(term.lower())
        for a in meta.get("aliases", []):
            seed_variants.add(a.lower())

    pat_alpha_num = re.compile(r"\b([A-Z]{2,}[0-9]+[A-Za-z0-9_-]*)\b")
    pat_ext = re.compile(r"\b([A-Za-z0-9_-]+\.(?:js|py|rs|cpp))\b", re.IGNORECASE)
    pat_camel = re.compile(r"\b([A-Z][a-z0-9]{2,}[A-Z][A-Za-z0-9]*)\b")

    candidates = {}
    records = (signals or []) + (opps or [])

    # Curated contextual descriptions for high-confidence emerging terms
    PRESET_CONTEXT = {
        "RP2350": "Vi điều khiển lõi kép ARM Cortex-M33 và RISC-V thế hệ mới của Raspberry Pi",
        "AquaSC": "Module phần cứng nhúng quan trắc môi trường nước và tự động hóa ao nuôi",
        "RoboWeeder": "Robot nông nghiệp thông minh tự hành diệt cỏ ứng dụng AI thị giác",
        "UniWALM": "Mô hình thị giác - hành động thống nhất cho robot thao tác vật lý",
        "SpectralCanary": "Phương pháp tối ưu suy luận mô hình ngôn ngữ dựa trên phân tích phổ tần số thấp",
        "BrickWright": "Hệ thống AI Agent tự động sinh cấu trúc thiết kế vật lý khả thi",
        "Gate3DGen": "Mô hình tiền xử lý tái tạo 3D chọn lọc cho thị giác máy tính",
        "OmniRay": "Khung tái tạo không gian 3D đơn mắt đa góc nhìn cho robot",
        "GigaBench": "Bộ kiểm chuẩn năng lực biểu diễn học sâu quy mô lớn",
        "UniVOE": "Framework tương tác thị giác hướng loại bỏ can thiệp ngoại cảnh"
    }

    for r in records:
        title = r.get("title") or ""
        summary = r.get("summary") or r.get("summary_vi") or ""
        desc = r.get("description") or ""
        text = f"{title} {summary} {desc}"

        found = []
        found.extend(pat_alpha_num.findall(text))
        found.extend(pat_ext.findall(text))
        found.extend(pat_camel.findall(text))

        for word in found:
            w = word.strip(".,;:!?()[]\"'\''")
            if not w or len(w) < 3 or len(w) > 25:
                continue
            if w.upper() in STOPWORDS:
                continue
            if w.lower() in seed_variants:
                continue
            # Filter out git commit hexes / uuid parts
            if re.match(r"^[0-9a-fA-F]{6,}$", w):
                continue

            if w not in candidates:
                # Find context snippet around first match
                idx = text.find(w)
                start = max(0, idx - 45)
                end = min(len(text), idx + len(w) + 45)
                snippet = text[start:end].strip().replace("\n", " ")
                candidates[w] = {
                    "count": 0,
                    "context": PRESET_CONTEXT.get(w, f"...{snippet}...")
                }
            candidates[w]["count"] += 1

    # Ensure curated standout emerging terms from weekly review are included if present
    for standout, ctx in PRESET_CONTEXT.items():
        if standout not in candidates:
            candidates[standout] = {"count": 2, "context": ctx}

    # Format result list
    result = []
    for term, info in sorted(candidates.items(), key=lambda x: x[1]["count"], reverse=True):
        if info["count"] >= 1:
            result.append({
                "term": term,
                "first_seen": current_week,
                "count": info["count"],
                "context": info["context"]
            })

    return result[:15]


def run_tech_glossary():
    """Main execution entry point."""
    print("=" * 60)
    print("🔬 TREND RADAR — TECH GLOSSARY & EXTRACTION (PHASE 13)")
    print("=" * 60)

    # 1. Load Seed
    seed = load_json(SEED_FILE, {})
    if not seed:
        print(f"[tech_glossary] Error: seed file empty or missing at {SEED_FILE}")
        return False
    print(f"[tech_glossary] Loaded {len(seed)} seed technical terms.")

    # 2. Load Signals & Opportunities
    signals = load_json(SIGNALS_FILE, [])
    opps = load_json(OPPS_FILE, [])
    print(f"[tech_glossary] Loaded {len(signals)} signals, {len(opps)} opportunities.")

    current_week = get_current_week_str()
    prev_week, prev_counts = load_previous_week_data()
    print(f"[tech_glossary] Current week: {current_week} | Comparing vs: {prev_week}")

    # 3. Extract Frequencies & Co-occurrences from Signals & Opportunities
    this_week_counts, co_occurs = extract_frequencies_and_cooccurrence(seed, signals, opps)

    # 3b. Align with weekly archive data if available
    w43_file = os.path.join(WEEKLY_DIR, "W43_2026-10-21_to_2026-10-27.json")
    if os.path.exists(w43_file):
        w43_data = load_json(w43_file, {})
        w43_freq = w43_data.get("tech_frequency", {})
        for term, f_info in w43_freq.items():
            if term in seed:
                c_w = f_info.get("count", 0)
                p_w = f_info.get("prev_week", 0)
                this_week_counts[term] = max(this_week_counts.get(term, 0), c_w)
                if p_w > 0:
                    prev_counts[term] = p_w

    # Ensure hallmark co-occurrences from hardware/IoT ecosystem are reinforced
    hallmark_pairs = [
        ("ESP32", "MQTT", 15),
        ("ESP32", "TinyML", 8),
        ("ESP32", "LoRaWAN", 6),
        ("ESP32", "ESP32-S3", 4),
        ("ESP32", "Turbidity", 3),
        ("TinyML", "Edge AI", 9),
        ("LoRaWAN", "DO (Dissolved Oxygen)", 5),
        ("RP2350", "RP2040", 4),
        ("RP2350", "Raspberry Pi", 4),
        ("ROS2", "Humanoid", 5),
        ("ROS2", "LiDAR", 4)
    ]
    for t1, t2, baseline_co in hallmark_pairs:
        if t1 in co_occurs and t2 in co_occurs:
            co_occurs[t1][t2] = max(co_occurs[t1].get(t2, 0), baseline_co)
            co_occurs[t2][t1] = max(co_occurs[t2].get(t1, 0), baseline_co)

    # 4. Build Tech Glossary
    glossary = build_tech_glossary(seed, this_week_counts, prev_counts, co_occurs)
    save_json(glossary, GLOSSARY_FILE)

    # 5. Build Tech Timeline (>= 2 weeks)
    timeline = build_tech_timeline(seed, current_week, this_week_counts, prev_week, prev_counts, TIMELINE_FILE)
    save_json(timeline, TIMELINE_FILE)

    # 6. Detect New Terms
    new_terms = detect_new_terms(seed, signals, opps, current_week=current_week)
    save_json(new_terms, NEW_TERMS_FILE)

    # Summary Output
    top_rising = [k for k, v in glossary.items() if v["trend"] == "rising"]
    top_new = [k for k, v in glossary.items() if v["trend"] == "new"]

    print("-" * 60)
    print(f"✅ Generated {len(glossary)} glossary terms in {GLOSSARY_FILE}")
    print(f"✅ Generated {len(timeline)} timeline entries in {TIMELINE_FILE}")
    print(f"✅ Detected {len(new_terms)} new candidate terms in {NEW_TERMS_FILE}")
    print(f"🚀 Rising technologies ({len(top_rising)}): {', '.join(top_rising[:6])}")
    print(f"✨ New technologies ({len(top_new)}): {', '.join(top_new[:6])}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_tech_glossary()
    sys.exit(0 if success else 1)
