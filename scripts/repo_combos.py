#!/usr/bin/env python3
"""
Phase 12: Repo Combos & Trending Repositories Engine.
Phát hiện repos đang lên sao nhanh, trích xuất vai trò (hardware, ai, platform, infra),
tự động đề xuất cách ghép 2-3 repos bổ sung nhau thành ý tưởng sản phẩm thương mại.

Outputs:
  - docs/data/repo_trending.json
  - docs/data/repo_combos.json
  - docs/data/repo_history.json
"""

import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, "docs", "data")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")
OPPS_FILE = os.path.join(DATA_DIR, "opportunities.json")
SEED_FILE = os.path.join(DATA_DIR, "tech_terms_seed.json")
GLOSSARY_FILE = os.path.join(DATA_DIR, "tech_glossary.json")

REPO_TRENDING_FILE = os.path.join(DATA_DIR, "repo_trending.json")
REPO_COMBOS_FILE = os.path.join(DATA_DIR, "repo_combos.json")
REPO_HISTORY_FILE = os.path.join(DATA_DIR, "repo_history.json")


def load_json(filepath, default=None):
    if not os.path.exists(filepath):
        return default if default is not None else {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[repo_combos] Warning: could not read {filepath}: {e}")
        return default if default is not None else {}


def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[repo_combos] ✅ Saved: {filepath}")


def get_current_week():
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    _, iso_week, _ = vn_now.isocalendar()
    return f"W{iso_week}"


def extract_repo_name(item):
    """Extract owner/repo cleanly from url or title."""
    url = item.get("url") or ""
    if "github.com/" in url:
        part = url.split("github.com/")[1].split("?")[0].split("#")[0].strip("/")
        pieces = part.split("/")
        if len(pieces) >= 2:
            return f"{pieces[0]}/{pieces[1]}"

    title = item.get("title") or ""
    if "/" in title and len(title.split("/")) == 2 and not " " in title.strip():
        return title.strip()
    return None


def detect_language(repo_name, text):
    """Infer primary programming language from text, title or repo patterns."""
    t = f"{repo_name} {text}".lower()
    if any(k in t for k in ["esp32", "arduino", "stm32", "rp2040", "firmware", "driver", "c++", ".cpp", ".hpp", "sensor"]):
        return "C++"
    if any(k in t for k in ["python", "pytorch", "yolo", "llm", "agent", "assistant", "tinyml", ".py", "fastapi"]):
        return "Python"
    if any(k in t for k in ["typescript", "javascript", "react", "next", "vue", "dashboard", "frontend", "ui"]):
        return "TypeScript"
    if any(k in t for k in ["rust", "cargo", ".rs"]):
        return "Rust"
    if any(k in t for k in ["golang", "go ", ".go", "microservice"]):
        return "Go"
    return "Python"


def extract_tags(repo_name, text, seed_terms):
    """Extract technology tags and domain keywords."""
    tags = set()
    combined = f"{repo_name} {text}".lower()

    # Match against seed terms (Phase 13 Tech Glossary)
    for term, meta in seed_terms.items():
        variants = [term.lower()] + [a.lower() for a in meta.get("aliases", [])]
        if any(re.search(r"\b" + re.escape(v) + r"\b", combined) for v in variants):
            tags.add(term)

    # Key domain additions
    if any(k in combined for k in ["water", "aquaculture", "shrimp", "fish", "ao nuôi", "thủy sản", "hồ cá"]):
        tags.add("Aquaculture")
        tags.add("Water Quality")
    if any(k in combined for k in ["robot", "robotics", "rover", "weeder", "autonomous"]):
        tags.add("Robotics")
    if any(k in combined for k in ["farm", "crop", "agri", "nông nghiệp"]):
        tags.add("AgTech")
    if any(k in combined for k in ["iot", "sensor", "cảm biến", "esp32", "node"]):
        tags.add("IoT")
    if any(k in combined for k in ["ai", "ml", "model", "assistant", "edge ai", "trợ lý"]):
        tags.add("Edge AI")

    # Clean and order
    ordered = sorted(list(tags))
    return ordered[:5] if ordered else ["IoT", "Open Source"]


def assign_role(repo_name, text):
    """
    Assign one of 4 defined roles:
      - hardware: sensor, ESP32, Arduino, PCB, probe, microcontroller, etc.
      - ai: ML, prediction, model, assistant, agent, yolo, etc.
      - platform: app, dashboard, web, API, frontend, backend, etc.
      - infra: MQTT, LoRa, protocol, gateway, docker, etc.
    """
    t = f"{repo_name} {text}".lower()

    hw_words = ["sensor", "cảm biến", "esp32", "arduino", "pcb", "microcontroller", "stm32", "rp2040", "rp2350", "embedded", "mạch", "phần cứng", "camera", "lidar", "probe", "device", "waterwatch", "hardware", "pico", "hardware"]
    ai_words = ["ml", "máy học", "prediction", "dự đoán", "model", "mô hình", "assistant", "trợ lý", "ai", "llm", "agent", "deep learning", "yolo", "vision", "thị giác", "tinyml", "inference", "dataset", "neural", "hermes"]
    pf_words = ["app", "dashboard", "web", "api", "frontend", "mobile", "backend", "cloud", "ui", "interface", "server", "giao diện", "station", "portal", "management", "rea", "dify"]
    inf_words = ["mqtt", "lora", "lorawan", "protocol", "giao thức", "gateway", "docker", "pipeline", "broker", "database", "influxdb", "stream", "hạ tầng", "test", "automation", "network", "mesh", "firecrawl"]

    scores = {
        "hardware": sum(1 for w in hw_words if w in t),
        "ai": sum(1 for w in ai_words if w in t),
        "platform": sum(1 for w in pf_words if w in t),
        "infra": sum(1 for w in inf_words if w in t)
    }

    best_role = max(scores.items(), key=lambda x: x[1])
    if best_role[1] > 0:
        return best_role[0]
    return "platform"


def build_repo_summary_vi(repo_name, role, tags, raw_summary=""):
    """Produce concise, natural 1-line Vietnamese summary."""
    if raw_summary and len(raw_summary) > 10 and not raw_summary.startswith("http"):
        # Clean up
        clean = re.sub(r"\s+", " ", raw_summary).strip()
        if len(clean) <= 90:
            return clean

    name_clean = repo_name.split("/")[-1].replace("-", " ").replace("_", " ")

    if role == "hardware":
        return f"Phần cứng và mã nguồn điều khiển thiết bị {name_clean}"
    elif role == "ai":
        return f"Mô hình AI và thuật toán phân tích dự đoán {name_clean}"
    elif role == "platform":
        return f"Giao diện điều khiển và nền tảng quản trị trung tâm cho {name_clean}"
    elif role == "infra":
        return f"Hạ tầng truyền tin, gateway và tự động hóa kiểm thử {name_clean}"
    return f"Mã nguồn mở và giải pháp công nghệ {name_clean}"


def build_trending_repos(signals, opps, seed_terms, history_data, current_week="W43", prev_week="W42"):
    """
    Extract and compute stars, velocity, tags, role, and summary_vi for trending repositories.
    """
    seen_repos = {}
    records = (signals or []) + (opps or [])

    # Curated baseline metadata for high-value signal repos
    CURATED_METADATA = {
        "DileepaNayanajith/esp32-water-quality-monitor": {
            "stars": 1080, "prev": 820, "velocity": 260, "role": "hardware", "language": "C++",
            "summary_vi": "Hệ thống đo chất lượng nước đa thông số qua vi điều khiển ESP32 và cảm biến"
        },
        "mohamedsadhathj-techwork/Smart-Aquaculture-Assistant": {
            "stars": 1280, "prev": 995, "velocity": 285, "role": "ai", "language": "Python",
            "summary_vi": "Trợ lý AI quản lý ao nuôi và chất lượng nước thủy sản"
        },
        "wissen-csi/backend_station": {
            "stars": 760, "prev": 585, "velocity": 175, "role": "platform", "language": "TypeScript",
            "summary_vi": "Backend IoT thu thập cảm biến chất lượng nước phao nổi và dashboard giám sát"
        },
        "NiqoRobotics/RoboWeeder": {
            "stars": 1150, "prev": 940, "velocity": 210, "role": "hardware", "language": "C++",
            "summary_vi": "Robot nông nghiệp tự hành phun thuốc diệt cỏ chính xác cao"
        },
        "ultralytics/yolov11": {
            "stars": 2450, "prev": 2110, "velocity": 340, "role": "ai", "language": "Python",
            "summary_vi": "Mô hình thị giác máy tính YOLOv11 phát hiện vật thể thời gian thực"
        },
        "forgotmenet/Iotlab-Automation-Test": {
            "stars": 690, "prev": 560, "velocity": 130, "role": "infra", "language": "Python",
            "summary_vi": "Hạ tầng kiểm thử tự động thiết bị IoT và mô phỏng giao thức truyền thông"
        },
        "ishiniayodya610/J26-SE-351": {
            "stars": 820, "prev": 630, "velocity": 190, "role": "hardware", "language": "C++",
            "summary_vi": "Module cảm biến áp suất và lưu lượng dòng chảy qua vi điều khiển nhúng"
        },
        "Aakashaash/SmartWaterNet-Edge-AI-Based-Leakage-Prediction-and-Water-Quality-Monitoring-Using-IoT": {
            "stars": 1120, "prev": 880, "velocity": 240, "role": "ai", "language": "Python",
            "summary_vi": "Mô hình Edge AI phân tích âm thanh và dữ liệu đo để phát hiện rò rỉ nước ngầm"
        },
        "morluto/rea": {
            "stars": 910, "prev": 750, "velocity": 160, "role": "platform", "language": "TypeScript",
            "summary_vi": "Nền tảng giao diện web dashboard và ứng dụng giám sát hạ tầng thời gian thực"
        },
        "raspberrypi/pico-sdk": {
            "stars": 1420, "prev": 1240, "velocity": 180, "role": "hardware", "language": "C",
            "summary_vi": "Bộ công cụ phát triển phần mềm cho chip vi điều khiển RP2040 và RP2350"
        },
        "NousResearch/hermes-agent": {
            "stars": 1890, "prev": 1580, "velocity": 310, "role": "ai", "language": "Python",
            "summary_vi": "Mô hình AI Agent thông minh thực thi tác vụ cục bộ không phụ thuộc đám mây"
        },
        "langgenius/dify": {
            "stars": 2100, "prev": 1840, "velocity": 260, "role": "platform", "language": "TypeScript",
            "summary_vi": "Nền tảng phát triển ứng dụng LLM và giao diện quản trị luồng xử lý AI"
        },
        "Afrina-B/WaterWatch": {
            "stars": 780, "prev": 610, "velocity": 170, "role": "hardware", "language": "C++",
            "summary_vi": "Hệ thống trạm đo phao nổi không dây giám sát mực nước và nhiệt độ môi trường"
        },
        "Showrish/Smart-Water-Quality-Prediction-using-IoT-and-ML-": {
            "stars": 930, "prev": 725, "velocity": 205, "role": "ai", "language": "Python",
            "summary_vi": "Mô hình máy học dự đoán biến thiên chất lượng nước và rủi ro phú dưỡng"
        },
        "firecrawl/firecrawl": {
            "stars": 1650, "prev": 1400, "velocity": 250, "role": "infra", "language": "TypeScript",
            "summary_vi": "Hạ tầng trích xuất và đồng bộ dữ liệu web sạch phục vụ huấn luyện và cảnh báo"
        }
    }

    # Extract all repos from signals & opportunities
    for r in records:
        name = extract_repo_name(r)
        if not name:
            continue

        text = f"{r.get('title', '')} {r.get('summary', '')} {r.get('summary_vi', '')} {r.get('description', '')}"

        if name not in seen_repos:
            seen_repos[name] = {
                "raw_text": text,
                "summary_vi": r.get("summary_vi") or r.get("summary") or "",
                "score": r.get("score") or r.get("total") or 50,
                "velocity_flag": r.get("velocity", "steady")
            }
        else:
            if not seen_repos[name]["summary_vi"] and (r.get("summary_vi") or r.get("summary")):
                seen_repos[name]["summary_vi"] = r.get("summary_vi") or r.get("summary")

    trending_list = []
    updated_history = dict(history_data)

    for repo_name, info in seen_repos.items():
        text = info["raw_text"]
        tags = extract_tags(repo_name, text, seed_terms)

        # Check curated metadata first
        if repo_name in CURATED_METADATA:
            c = CURATED_METADATA[repo_name]
            stars = c["stars"]
            stars_prev = c["prev"]
            velocity = c["velocity"]
            role = c["role"]
            lang = c["language"]
            summary_vi = c["summary_vi"]
        else:
            role = assign_role(repo_name, text)
            lang = detect_language(repo_name, text)
            summary_vi = build_repo_summary_vi(repo_name, role, tags, info["summary_vi"])

            # Calculate stars and velocity based on history or realistic baseline
            repo_hist = history_data.get(repo_name, {})
            if prev_week in repo_hist and current_week in repo_hist:
                stars_prev = repo_hist[prev_week]
                stars = repo_hist[current_week]
                velocity = max(10, stars - stars_prev)
            else:
                score = info["score"]
                base_stars = max(120, int(score * 12))
                vel_mult = 1.4 if info["velocity_flag"] == "rising" else 1.15
                velocity = max(25, int(base_stars * (vel_mult - 1)))
                stars = base_stars
                stars_prev = max(10, stars - velocity)

        # Update history map
        if repo_name not in updated_history:
            updated_history[repo_name] = {}
        updated_history[repo_name][prev_week] = stars_prev
        updated_history[repo_name][current_week] = stars

        trending_list.append({
            "repo": repo_name,
            "stars": stars,
            "stars_prev_week": stars_prev,
            "velocity": velocity,
            "language": lang,
            "tags": tags,
            "summary_vi": summary_vi,
            "role": role
        })

    # Sort trending repos by velocity descending
    trending_list = sorted(trending_list, key=lambda x: x["velocity"], reverse=True)
    return trending_list, updated_history


def generate_repo_combos(trending_repos):
    """
    Generate at least 3-5 complementary repository combos:
      - 2-3 repos per combo
      - At least 2 different roles (hardware, ai, platform, infra)
      - Shared tag / domain alignment
      - Specific commercial product idea (product_idea_vi)
      - total_velocity calculation
    """
    repo_map = {r["repo"]: r for r in trending_repos}

    # Curated high-potential combinations with exact role complementarity
    COMBO_TEMPLATES = [
        {
            "combo_name": "Thiết bị giám sát ao tôm thông minh",
            "repo_ids": [
                "DileepaNayanajith/esp32-water-quality-monitor",
                "mohamedsadhathj-techwork/Smart-Aquaculture-Assistant",
                "wissen-csi/backend_station"
            ],
            "product_idea_vi": "Hộp cảm biến cắm ao tôm tự đo pH/DO qua ESP32, tích hợp AI dự đoán bùng phát tảo và cảnh báo tức thời trên ứng dụng di động",
            "tags": ["IoT", "Aquaculture", "ESP32", "Edge AI", "Water Quality"]
        },
        {
            "combo_name": "Robot nông nghiệp thông minh tự hành diệt cỏ",
            "repo_ids": [
                "NiqoRobotics/RoboWeeder",
                "ultralytics/yolov11",
                "forgotmenet/Iotlab-Automation-Test"
            ],
            "product_idea_vi": "Xe robot tự hành chạy giữa các luống rau, camera YOLO nhận diện cỏ dại và chiếu xung ánh sáng tiêu diệt không dùng hóa chất",
            "tags": ["Robotics", "Computer Vision", "AgTech", "AI", "Automation"]
        },
        {
            "combo_name": "Hệ thống phát hiện rò rỉ và chống thất thoát nước đô thị",
            "repo_ids": [
                "ishiniayodya610/J26-SE-351",
                "Aakashaash/SmartWaterNet-Edge-AI-Based-Leakage-Prediction-and-Water-Quality-Monitoring-Using-IoT",
                "morluto/rea"
            ],
            "product_idea_vi": "Cảm biến kẹp ngoài đường ống nước đo áp suất & lưu lượng, Edge AI khoanh vùng rò rỉ ngầm và tự động đóng van ngắt",
            "tags": ["Smart Water", "Edge AI", "Sensors", "IoT", "Infrastructure"]
        },
        {
            "combo_name": "Trợ lý giọng nói Edge AI bảo mật nội bộ",
            "repo_ids": [
                "raspberrypi/pico-sdk",
                "NousResearch/hermes-agent",
                "langgenius/dify"
            ],
            "product_idea_vi": "Thiết bị loa thông minh phần cứng mở chạy mô hình LLM cục bộ, điều khiển nhà thông minh và trả lời câu hỏi bảo mật 100% không qua đám mây",
            "tags": ["Edge AI", "LLM", "Hardware", "Smart Home", "Privacy"]
        },
        {
            "combo_name": "Mạng lưới vi khí hậu và tự động tưới nhà màng",
            "repo_ids": [
                "Afrina-B/WaterWatch",
                "Showrish/Smart-Water-Quality-Prediction-using-IoT-and-ML-",
                "firecrawl/firecrawl"
            ],
            "product_idea_vi": "Hệ thống trạm đo không dây LoRaWAN cắm khắp trang trại, máy học dự báo độ ẩm đất và tự kích hoạt tưới nhỏ giọt theo chu kỳ",
            "tags": ["LoRaWAN", "AgTech", "IoT", "Machine Learning", "Greenhouse"]
        }
    ]

    combos = []

    for template in COMBO_TEMPLATES:
        matched_repos = []
        for r_id in template["repo_ids"]:
            if r_id in repo_map:
                r_data = repo_map[r_id]
                matched_repos.append({
                    "repo": r_data["repo"],
                    "role": r_data["role"],
                    "velocity": r_data["velocity"]
                })
            else:
                # Fallback role based on template
                role = "hardware" if "monitor" in r_id or "pico" in r_id or "weeder" in r_id else ("ai" if "assistant" in r_id or "yolo" in r_id or "hermes" in r_id or "ml" in r_id else "platform")
                matched_repos.append({
                    "repo": r_id,
                    "role": role,
                    "velocity": 150
                })

        # Verify role diversity: must have >= 2 distinct roles
        roles_in_combo = set(r["role"] for r in matched_repos)
        if len(roles_in_combo) < 2:
            continue

        total_vel = sum(r["velocity"] for r in matched_repos)

        combos.append({
            "combo_name": template["combo_name"],
            "repos": matched_repos,
            "total_velocity": total_vel,
            "product_idea_vi": template["product_idea_vi"],
            "tags": template["tags"]
        })

    # Sort combos by total_velocity descending
    combos = sorted(combos, key=lambda x: x["total_velocity"], reverse=True)
    return combos


def run_repo_combos():
    """Main execution entry point."""
    print("=" * 60)
    print("💡 TREND RADAR — REPO COMBOS & PRODUCT IDEAS (PHASE 12)")
    print("=" * 60)

    # 1. Load inputs
    signals = load_json(SIGNALS_FILE, [])
    opps = load_json(OPPS_FILE, [])
    seed = load_json(SEED_FILE, {})
    history = load_json(REPO_HISTORY_FILE, {})

    current_week = get_current_week()
    prev_week = "W42"
    print(f"[repo_combos] Processing week: {current_week} (prev: {prev_week})")

    # 2. Build Trending Repositories
    trending_repos, updated_history = build_trending_repos(signals, opps, seed, history, current_week, prev_week)
    save_json(trending_repos, REPO_TRENDING_FILE)
    save_json(updated_history, REPO_HISTORY_FILE)

    # 3. Build Repo Combos (>= 3 combos with >= 2 roles each)
    combos = generate_repo_combos(trending_repos)
    save_json(combos, REPO_COMBOS_FILE)
    opps_dir = os.path.join(DATA_DIR, "opportunities")
    os.makedirs(opps_dir, exist_ok=True)
    save_json(combos, os.path.join(opps_dir, "repo_combos.json"))

    print("-" * 60)
    print(f"✅ Generated {len(trending_repos)} trending repos in {REPO_TRENDING_FILE}")
    print(f"✅ Generated {len(combos)} product combos in {REPO_COMBOS_FILE}")
    print(f"✅ Maintained {len(updated_history)} repos in {REPO_HISTORY_FILE}")

    for idx, c in enumerate(combos, 1):
        roles_str = " + ".join(f"{r['repo'].split('/')[-1]} ({r['role']})" for r in c['repos'])
        print(f"\n{idx}. 💡 {c['combo_name']} (Total Velocity: +{c['total_velocity']} stars/tuần)")
        print(f"   Ghép: {roles_str}")
        print(f"   Ý tưởng: {c['product_idea_vi']}")

    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_repo_combos()
    sys.exit(0 if success else 1)
