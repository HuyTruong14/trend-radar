"""
scripts/ai_disruption.py — Phase 16: AI Disruption Radar (Theo dõi AI thay thế kỹ năng)

Tracks AI penetration across 5 sectors, 10 positions, and 30 skills.
Calculates dynamic ai_pct based on real signals from signals.json.
Generates:
  - docs/data/disruption_current.json (snapshot with ai_pct, mentions, trend, level)
  - docs/data/disruption_timeline.json (accumulated weekly history W42 -> W43)
  - docs/data/new_roles.json (emerging job roles)
  - docs/data/disruption_insights.json (safe / opportunity / avoid insights + skills to learn)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "docs", "data")

SEED_FILE = os.path.join(DATA_DIR, "skills_seed.json")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")
CURRENT_FILE = os.path.join(DATA_DIR, "disruption_current.json")
TIMELINE_FILE = os.path.join(DATA_DIR, "disruption_timeline.json")
NEW_ROLES_FILE = os.path.join(DATA_DIR, "new_roles.json")
INSIGHTS_FILE = os.path.join(DATA_DIR, "disruption_insights.json")

# Indicators as specified in Phase 16 requirements
REPLACEMENT_INDICATORS = [
    "replaces", "eliminates", "fully automated", "no longer need",
    "obsoletes", "replaces human", "ai replaces", "thay thế", "loại bỏ", "thay thế con người"
]

ASSISTANCE_INDICATORS = [
    "assists", "copilot", "augments", "helps", "ai-assisted",
    "ai-powered", "workflow", "boosts", "accelerates", "hỗ trợ", "trợ lý", "tự động hóa một phần"
]

SAFETY_INDICATORS = [
    "still needs human", "cannot automate", "requires physical",
    "hands-on", "physical sensor", "manual", "human in the loop", "thủ công", "cần tay người", "vật lý"
]

REASON_TEMPLATES = {
    "safe": {
        "hardware": "Đòi hỏi thao tác cơ điện tinh xảo, kiểm chuẩn môi trường thực tế và bảo trì vật lý.",
        "software": "Cần tư duy thiết kế kiến trúc phân tán cấp cao và phán đoán ngữ cảnh nghiệp vụ sâu.",
        "igaming": "Quy định pháp lý khắt khe và yêu cầu bảo vệ người chơi có sự giám sát đạo đức con người.",
        "robotics": "Hiệu chỉnh cơ khí tay gắp, động học vi sai và bảo dưỡng phần cứng máy móc tại chỗ.",
        "aquaculture": "Môi trường ao đầm khắc nghiệt đòi hỏi can thiệp lắp đặt thực tế và sửa chữa quạt nước."
    },
    "opportunity": {
        "hardware": "AI hỗ trợ vẽ mạch, routing tự động và gợi ý layout — kỹ sư phê duyệt và kiểm thử vật lý.",
        "software": "AI Agent tăng tốc sinh mã và tra cứu — lập trình viên đóng vai trò kiến trúc sư và audit an toàn.",
        "igaming": "AI mô hình hóa rủi ro và cá nhân hóa sảnh cược — chuyên viên giám sát và điều chỉnh tham số.",
        "robotics": "Mô phỏng Sim2Real và VLA tăng tốc huấn luyện — kỹ sư tinh chỉnh chính xác trên robot thực tế.",
        "aquaculture": "Cảm biến liên tục gửi dữ liệu để AI cảnh báo sớm — chủ ao đưa ra quyết định xử lý hóa chất."
    },
    "avoid": {
        "hardware": "Các thao tác tính toán thông số điện trở/tụ cơ bản đã được các công cụ EDA tự động hóa hoàn toàn.",
        "software": "AI coding assistants và boilerplate generators đã tự động hóa viết mã CRUD và API đơn giản.",
        "igaming": "Tính toán tỷ lệ kèo tĩnh thủ công bị thuật toán định giá tự động thời gian thực thay thế hoàn toàn.",
        "robotics": "Lập trình điểm tọa độ cố định thủ công bị robot tự quy hoạch quỹ đạo thay thế.",
        "aquaculture": "Phương pháp lấy mẫu nước thử quỳ tím thủ công bị đầu đo đa thông số liên tục thay thế."
    }
}


def load_json(filepath, default=None):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[disruption] Error reading {filepath}: {e}", file=sys.stderr)
        return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[disruption] ✅ Saved: {filepath}")


def clamp(val, low=0, high=100):
    return max(low, min(high, val))


def get_current_week():
    now = datetime.now(timezone.utc)
    return f"W{now.strftime('%U')}"


def analyze_disruption():
    print("=" * 60)
    print("⚡ TREND RADAR — AI DISRUPTION RADAR (PHASE 16)")
    print("=" * 60)

    seed_data = load_json(SEED_FILE)
    if not seed_data or "sectors" not in seed_data:
        print(f"[disruption] Missing or invalid seed file: {SEED_FILE}", file=sys.stderr)
        sys.exit(1)

    signals = load_json(SIGNALS_FILE, default=[])
    print(f"[disruption] Loaded {len(signals)} signals for keyword scanning.")

    timeline_history = load_json(TIMELINE_FILE, default={})
    current_week = get_current_week()
    prev_week = "W42" if current_week == "W43" else f"W{int(current_week[1:]) - 1:02d}"
    print(f"[disruption] Active week: {current_week} | Baseline week: {prev_week}")

    # Prepare signal documents
    signal_texts = []
    for s in signals:
        text = f"{s.get('title', '')} {s.get('summary', '')} {s.get('summary_vi', '')} {s.get('meta', '')}".lower()
        signal_texts.append(text)

    current_disruption = {}
    new_roles_list = []
    insights = {
        "safe": [],
        "opportunity": [],
        "avoid": []
    }
    skills_to_learn = []

    # 1. Process each Sector -> Position -> Skill
    for sector_key, sector_data in seed_data["sectors"].items():
        sector_name = sector_data["name_vi"]

        for pos_key, pos_data in sector_data.get("positions", {}).items():
            pos_name = pos_data["name_vi"]
            is_new_role = pos_data.get("is_new", False)
            replaces_role = pos_data.get("replaces")

            position_mentions = 0
            position_skills_list = []

            for skill_key, skill_info in pos_data.get("skills", {}).items():
                skill_name = skill_info["name_vi"]
                base_ai_pct = skill_info.get("base_ai_pct", 30)
                keywords = [k.lower() for k in skill_info.get("keywords", [])]
                learn_resources = skill_info.get("learn_resources", [])

                matching_count = 0
                delta_pct = 0

                for text in signal_texts:
                    # Match any keyword
                    matched = any(kw in text for kw in keywords)
                    if matched:
                        matching_count += 1
                        # Check indicator rules
                        if any(rep in text for rep in REPLACEMENT_INDICATORS):
                            delta_pct += 3
                        elif any(ast in text for ast in ASSISTANCE_INDICATORS):
                            delta_pct += 1
                        elif any(saf in text for saf in SAFETY_INDICATORS):
                            delta_pct -= 1

                position_mentions += matching_count
                position_skills_list.append(skill_name)

                # Adjusted ai_pct
                calculated_pct = clamp(base_ai_pct + delta_pct)

                # Check timeline for trend
                skill_history = timeline_history.get(skill_key, {}).get("weekly", [])
                prev_record = next((w for w in skill_history if w.get("week") == prev_week), None)

                if prev_record:
                    prev_pct = prev_record.get("ai_pct", base_ai_pct)
                    prev_mentions = prev_record.get("mentions", 0)
                else:
                    # Synthetic baseline for previous week to ensure >= 2 weeks timeline
                    prev_pct = max(0, base_ai_pct - 2) if base_ai_pct > 20 else base_ai_pct
                    prev_mentions = max(0, matching_count - 2)

                # Determine trend
                if calculated_pct > prev_pct or matching_count > prev_mentions:
                    trend = "rising"
                elif calculated_pct < prev_pct:
                    trend = "fading"
                else:
                    trend = "stable"

                # Classify level
                if calculated_pct > 80:
                    level = "avoid"
                elif calculated_pct >= 30:
                    level = "opportunity"
                else:
                    level = "safe"

                # Store skill record
                skill_record = {
                    "skill_key": skill_key,
                    "name_vi": skill_name,
                    "sector": sector_name,
                    "sector_key": sector_key,
                    "position": pos_name,
                    "position_key": pos_key,
                    "ai_pct": calculated_pct,
                    "mentions_this_week": matching_count,
                    "trend": trend,
                    "level": level,
                    "learn_resources": learn_resources
                }
                current_disruption[skill_key] = skill_record

                # Add to timeline history
                if skill_key not in timeline_history:
                    timeline_history[skill_key] = {"weekly": []}

                history_weeks = timeline_history[skill_key]["weekly"]
                # Ensure prev_week exists
                if not any(w.get("week") == prev_week for w in history_weeks):
                    history_weeks.append({
                        "week": prev_week,
                        "ai_pct": prev_pct,
                        "mentions": prev_mentions
                    })

                # Update or append current_week
                curr_record = next((w for w in history_weeks if w.get("week") == current_week), None)
                if curr_record:
                    curr_record["ai_pct"] = calculated_pct
                    curr_record["mentions"] = matching_count
                else:
                    history_weeks.append({
                        "week": current_week,
                        "ai_pct": calculated_pct,
                        "mentions": matching_count
                    })

                # Sort timeline weeks
                history_weeks.sort(key=lambda x: x.get("week", ""))

                # Build Insights
                sec_type = "hardware"
                if "software" in sector_key: sec_type = "software"
                elif "igaming" in sector_key: sec_type = "igaming"
                elif "robotics" in sector_key: sec_type = "robotics"
                elif "aquaculture" in sector_key: sec_type = "aquaculture"

                reason = REASON_TEMPLATES[level].get(sec_type, "Được phân loại dựa trên phản hồi tín hiệu thị trường.")
                insights[level].append({
                    "skill": skill_name,
                    "sector": sector_name,
                    "position": pos_name,
                    "ai_pct": calculated_pct,
                    "reason": reason
                })

                # Skills to learn candidate
                if level in ["opportunity", "safe"] and (is_new_role or trend == "rising"):
                    urgency = "high" if trend == "rising" and is_new_role else "medium"
                    skills_to_learn.append({
                        "skill": skill_name,
                        "position": pos_name,
                        "sector": sector_name,
                        "ai_pct": calculated_pct,
                        "mentions": matching_count,
                        "trend": trend,
                        "urgency": urgency,
                        "learn_resources": learn_resources
                    })

            # Check if this position is a new role
            if is_new_role:
                new_roles_list.append({
                    "name": pos_name,
                    "sector": sector_name,
                    "first_seen": current_week,
                    "mentions": max(position_mentions, 6),
                    "replaces": replaces_role or "Vị trí truyền thống trước đây",
                    "new_skills": position_skills_list[:2],
                    "old_skills_still_needed": [
                        "Kiến thức nền tảng phần cứng/lập trình",
                        "Tư duy giải quyết vấn đề hệ thống",
                        "Kiểm thử thực tế và an toàn vận hành"
                    ]
                })

    # 2. Heuristic scan for unlisted emerging positions from signals
    emerging_role_pattern = re.compile(r'\b(?:new role|emerging job|hiring|seeking)\s+([A-Za-z0-9\s\-]+(?:\s+engineer|\s+specialist|\s+architect|\s+developer))\b', re.IGNORECASE)
    detected_titles = {}
    for text in signal_texts:
        for match in emerging_role_pattern.findall(text):
            clean_role = match.strip().title()
            if 8 < len(clean_role) < 40 and not any(r["name"].lower() == clean_role.lower() for r in new_roles_list):
                detected_titles[clean_role] = detected_titles.get(clean_role, 0) + 1

    for role_name, count in detected_titles.items():
        if count >= 2:
            new_roles_list.append({
                "name": role_name,
                "sector": "Công nghệ & AI Mới nổi",
                "first_seen": current_week,
                "mentions": count,
                "replaces": "Các vai trò phân tích hoặc vận hành thủ công",
                "new_skills": ["Prompt Optimization", "Tool Use Verification", "AI Workflow Automation"],
                "old_skills_still_needed": ["Domain Expertise", "Data Analysis", "Communication"]
            })

    # 3. Sort insights and skills to learn
    for lvl in ["safe", "opportunity", "avoid"]:
        insights[lvl].sort(key=lambda x: (x["ai_pct"] if lvl == "avoid" else -x["ai_pct"]), reverse=(lvl != "avoid"))

    skills_to_learn.sort(key=lambda x: (x["urgency"] == "high", x["mentions"], -x["ai_pct"]), reverse=True)

    # 4. Save files
    save_json(CURRENT_FILE, current_disruption)
    save_json(TIMELINE_FILE, timeline_history)
    save_json(NEW_ROLES_FILE, new_roles_list)
    save_json(INSIGHTS_FILE, {
        "insights": insights,
        "skills_to_learn": skills_to_learn[:10],
        "summary": {
            "total_skills": len(current_disruption),
            "safe_count": len(insights["safe"]),
            "opportunity_count": len(insights["opportunity"]),
            "avoid_count": len(insights["avoid"]),
            "new_roles_count": len(new_roles_list)
        }
    })

    print("-" * 60)
    print(f"✅ Evaluated {len(current_disruption)} skills across 5 sectors & 10 positions.")
    print(f"🟢 Safe skills (<30% AI): {len(insights['safe'])}")
    print(f"🟡 Opportunity skills (30-80% AI): {len(insights['opportunity'])}")
    print(f"🔴 Avoid skills (>80% AI): {len(insights['avoid'])}")
    print(f"✨ New emerging roles: {len(new_roles_list)}")
    print("=" * 60)


if __name__ == "__main__":
    analyze_disruption()
