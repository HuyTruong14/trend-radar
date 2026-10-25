"""
scripts/notify.py — Telegram Notification Engine (Phase 5B)

Sends alerts to Telegram via plain Bot HTTP API according to 3 dedicated templates:
- Template 1: Build-ready (total = 9) -> gửi riêng từng item
- Template 2: Research (total 7-8) -> gộp 1 tin/ngày (im lặng nếu không có)
- Template 3: Tăng hạng (watch -> research, research -> build_ready) -> gửi riêng
"""
import os
from datetime import datetime, timezone
import requests

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_LEN = 4096
TIMEOUT = 15
DEFAULT_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://huytruong14.github.io/trend-radar/")

SIGNAL_TYPE_LABELS_VI = {
    "pain_repeat": "🔁 Nỗi đau lặp lại",
    "price_shift": "💰 Dòng tiền dịch chuyển",
    "supply_gap": "🕳️ Khoảng trống thị trường",
    "tech_cheap": "⚙️ Công nghệ vừa rẻ đi",
}

VELOCITY_LABELS_VI = {
    "rising": "📈 ↑ đang tăng",
    "steady": "➡️ ổn định",
    "fading": "📉 ↓ đang giảm",
}

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def log(msg):
    print(f"[notify] {msg}", flush=True)


def format_signal_types_vi(signal_types):
    if not signal_types:
        return "⚙️ Công nghệ vừa rẻ đi"
    items = [SIGNAL_TYPE_LABELS_VI[st] for st in signal_types if st in SIGNAL_TYPE_LABELS_VI]
    return " · ".join(items) if items else "⚙️ Công nghệ vừa rẻ đi"


def format_velocity_vi(velocity):
    return VELOCITY_LABELS_VI.get(velocity, "➡️ ổn định")


def generate_score_explanations(opp):
    """
    Generate ~5-word Vietnamese explanations for each of the 3 score layers:
    - Bền (durability)
    - AI hỗ trợ (ai_support)
    - Đòn bẩy (your_leverage)
    Phase 11: Sinh động theo từng chủ đề và nội dung thực tế của item.
    KHÔNG hardcode cố định 'nuôi tôm' hay 'thay nước'.
    """
    title = (opp.get("title") or "").lower()
    summary = (opp.get("summary") or "").lower()
    summary_vi = (opp.get("summary_vi") or "").lower()
    combined = f"{title} {summary} {summary_vi}"
    scores = opp.get("scores", {})
    dur = scores.get("durability", 3)
    ai = scores.get("ai_support", 3)
    lev = scores.get("your_leverage", 3)

    is_igaming = any(k in combined for k in ["igaming", "gambling", "betting", "sportsbook", "casino", "poker", "odds", "cá cược", "game platform", "game inventory", "sbc", "igb", "gr8_tech", "slot machine", "lula", "dgoj"])
    is_robotics = any(k in combined for k in ["robot", "robotics", "humanoid", "drone", "quadruped", "amr", "agv", "manipulator", "embodied"])
    is_water_aqua = any(k in combined for k in ["water quality", "water sensor", "thủy sản", "hồ", "ao", "nước", "shrimp", "fish", "turbidity", "salinity", "dissolved oxygen", "purif", "buoy", "phao", "aquaculture"])
    is_hardware = any(k in combined for k in ["sensor", "cảm biến", "hardware", "esp32", "microcontroller", "camera", "embedded", "phần cứng", "thiết bị", "traffic", "giao thông", "diagnost"])
    is_ai_tool = any(k in combined for k in ["agent", "tool", "workflow", "automation", "devtool", "developer", "pipeline", "scraper", "copilot", "cli", "assistant"])
    is_agtech = any(k in combined for k in ["agtech", "agriculture", "farm", "crop", "soil", "nông nghiệp", "cây trồng", "roboweeder"])
    is_energy = any(k in combined for k in ["energy", "solar", "battery", "grid", "năng lượng", "power", "thermal energy"])

    # 1. Bền (Durability)
    if is_igaming:
        exp_dur = "ngành cá cược luôn cần nền tảng"
    elif is_robotics:
        exp_dur = "tự động hóa lao động thiếu hụt"
    elif is_water_aqua:
        exp_dur = "giám sát môi trường luôn cần thiết"
    elif is_hardware:
        exp_dur = "hạ tầng vật lý luôn cần vận hành"
    elif is_ai_tool:
        exp_dur = "nhu cầu tối ưu quy trình làm việc"
    elif is_agtech:
        exp_dur = "nông nghiệp luôn cần tăng năng suất"
    elif is_energy:
        exp_dur = "nhu cầu điện năng liên tục lâu dài"
    elif dur == 3:
        if "pain_repeat" in opp.get("signal_type", []):
            exp_dur = "nỗi đau lặp lại chưa có lời giải"
        elif "supply_gap" in opp.get("signal_type", []):
            exp_dur = "khoảng trống cung cầu cần giải quyết"
        elif "price_shift" in opp.get("signal_type", []):
            exp_dur = "dòng tiền thị trường dịch chuyển mạnh"
        else:
            exp_dur = "nhu cầu hạ tầng vật lý trường tồn"
    elif dur == 2:
        exp_dur = "vận hành kỹ thuật ổn định lâu dài"
    else:
        exp_dur = "nhu cầu thị trường duy trì ổn định"

    # 2. AI hỗ trợ (AI Support)
    if is_igaming:
        exp_ai = "AI phân tích odds, người ra quyết định"
    elif is_robotics:
        exp_ai = "AI điều khiển thị giác, kỹ sư giám sát"
    elif is_water_aqua:
        exp_ai = "AI đọc cảm biến, người bảo trì"
    elif is_hardware:
        exp_ai = "AI đọc số liệu, kỹ thuật viên xử lý"
    elif is_ai_tool:
        exp_ai = "AI tự động hóa tác vụ, người kiểm duyệt"
    elif is_agtech:
        exp_ai = "AI phân tích mùa vụ, nông dân thao tác"
    elif is_energy:
        exp_ai = "AI điều tiết tải, kỹ sư vận hành"
    elif ai == 3:
        exp_ai = "AI cảm biến nhận diện, người xác nhận"
    elif ai == 2:
        exp_ai = "AI phân tích, người ra quyết định"
    else:
        exp_ai = "AI hỗ trợ tự động hóa một phần"

    # 3. Đòn bẩy (Leverage)
    if is_igaming:
        exp_lev = "liên quan công việc hiện tại"
    elif is_robotics:
        exp_lev = "đúng hướng phần cứng & robotics"
    elif is_water_aqua or is_hardware:
        exp_lev = "đúng hướng kinh doanh phần cứng"
    elif is_ai_tool:
        exp_lev = "tăng năng suất công việc thực tế"
    elif is_agtech:
        exp_lev = "ngành sản xuất lân cận theo dõi"
    elif is_energy:
        exp_lev = "ngành hạ tầng năng lượng theo dõi"
    elif lev == 3:
        exp_lev = "đúng hướng kinh doanh phần cứng mục tiêu"
    elif lev == 2:
        exp_lev = "liên quan năng lực hệ thống hiện tại"
    else:
        exp_lev = "theo dõi thông tin ngành lân cận"

    return exp_dur, exp_ai, exp_lev



def format_template1_build_ready(opp):
    """
    Template 1: Build-ready (total = 9) -> gửi RIÊNG từng item.
    """
    title = (opp.get("title") or "").strip()
    summary_vi = (opp.get("summary_vi") or opp.get("summary") or "").strip()
    scores = opp.get("scores", {})
    durability = scores.get("durability", 3)
    ai_support = scores.get("ai_support", 3)
    your_leverage = scores.get("your_leverage", 3)
    source_count = opp.get("source_count", 1)

    exp_dur, exp_ai, exp_lev = generate_score_explanations(opp)
    signal_type_vi = format_signal_types_vi(opp.get("signal_type", []))
    velocity_vi = format_velocity_vi(opp.get("velocity", "steady"))

    sources = opp.get("sources") or []
    source_url = sources[0].get("url") if sources else opp.get("url", "")

    return (
        f"🔴 CƠ HỘI 9/9 — Hành động tuần này\n\n"
        f"📌 {title}\n\n"
        f"📝 {summary_vi}\n\n"
        f"💡 Vì sao điểm cao:\n"
        f"   Bền: {durability}/3 — {exp_dur}\n"
        f"   AI hỗ trợ: {ai_support}/3 — {exp_ai}\n"
        f"   Đòn bẩy: {your_leverage}/3 — {exp_lev}\n"
        f"   Nguồn: {source_count} nguồn xác nhận\n\n"
        f"🏷️ {signal_type_vi}\n"
        f"📈 {velocity_vi}\n"
        f"🔗 {source_url}\n\n"
        f"→ VIỆC CẦN LÀM: Đi hỏi 3 người thật về cơ hội này tuần này."
    )


def format_template2_research_digest(research_opps, date_str=None, dashboard_url=DEFAULT_DASHBOARD_URL):
    """
    Template 2: Research (total 7-8) -> GỘP 1 tin/ngày.
    Nếu không có research mới -> trả về None (im lặng).
    """
    if not research_opps:
        return None

    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    count = len(research_opps)
    lines = [
        f"⚡ RADAR HÀNG NGÀY — {date_str}",
        f"{count} cơ hội đáng nghiên cứu hôm nay\n"
    ]

    # Show top items (up to 10 for clean mobile reading)
    for idx, opp in enumerate(research_opps[:10]):
        emoji = NUMBER_EMOJIS[idx] if idx < len(NUMBER_EMOJIS) else f"{idx+1}."
        title = (opp.get("title") or "").strip()
        total = opp.get("total", 7)
        sig_vi = format_signal_types_vi(opp.get("signal_type", []))
        sum_vi = (opp.get("summary_vi") or opp.get("summary") or "").strip()

        lines.append(f"{emoji} {title} — {total}/9")
        lines.append(f"   {sig_vi}")
        lines.append(f"   → {sum_vi}\n")

    if count > 10:
        lines.append(f"... và {count - 10} cơ hội khác trên dashboard.\n")

    lines.append(f"📊 Xem chi tiết: {dashboard_url}")
    return "\n".join(lines).strip()


def format_template3_promotion(opp, old_stage, old_total, new_stage, new_total, dashboard_url=DEFAULT_DASHBOARD_URL):
    """
    Template 3: Tăng hạng -> gửi riêng từng item.
    """
    title = (opp.get("title") or "").strip()
    summary_vi = (opp.get("summary_vi") or opp.get("summary") or "").strip()
    signal_type_vi = format_signal_types_vi(opp.get("signal_type", []))

    sources = opp.get("sources") or []
    source_url = sources[0].get("url") if sources else opp.get("url", "")

    return (
        f"⬆️ TĂNG HẠNG: {old_stage} → {new_stage}\n\n"
        f"📌 {title}\n"
        f"📝 {summary_vi}\n\n"
        f"Điểm: {old_total} → {new_total}/9\n"
        f"🏷️ {signal_type_vi}\n"
        f"🔗 {source_url}\n\n"
        f"📊 Chi tiết trên dashboard"
    )


def get_bookmark_inline_keyboard(opp_id=None, dashboard_url=DEFAULT_DASHBOARD_URL):
    """Generate Telegram inline keyboard for bookmarking an opportunity."""
    url = f"{dashboard_url}#bookmarks"
    if opp_id:
        url += f"?id={opp_id}"
    return {
        "inline_keyboard": [
            [
                {"text": "📌 Đánh dấu nghiên cứu", "url": url}
            ]
        ]
    }


def send_message(text, reply_markup=None):
    """Send a Telegram message with optional inline keyboard. Never raises — failures are logged only."""
    import json
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram alert")
        return False

    if len(text) > TELEGRAM_MAX_LEN:
        text = text[: TELEGRAM_MAX_LEN - 20].rstrip() + "\n… (cắt bớt)"

    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else str(reply_markup)

    try:
        r = requests.post(
            f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
            data=data,
            timeout=TIMEOUT,
        )
        if not r.ok:
            log(f"Telegram API returned {r.status_code}: {r.text[:300]}")
            return False
        return True
    except Exception as e:
        log(f"Telegram send failed: {e}")
        return False
