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
    Strict Rule: KHÔNG viết generic 'điểm cao vì phù hợp'.
    Must directly reference the domain (water, sensor, camera, robotics, aquaculture).
    """
    title = (opp.get("title") or "").lower()
    summary = (opp.get("summary") or "").lower()
    summary_vi = (opp.get("summary_vi") or "").lower()
    combined = f"{title} {summary} {summary_vi}"
    scores = opp.get("scores", {})
    dur = scores.get("durability", 3)
    ai = scores.get("ai_support", 3)
    lev = scores.get("your_leverage", 3)

    # 1. Bền (Durability)
    if "tôm" in combined or "shrimp" in combined:
        exp_dur = "nuôi tôm luôn cần nước sạch"
    elif "cá" in combined or "fish" in combined:
        exp_dur = "nuôi cá luôn cần nước sạch"
    elif any(k in combined for k in ["water", "aqua", "thủy sản", "hồ", "ao", "nước", "ph", "do", "turbidity", "salinity", "purif", "buoy", "phao"]):
        exp_dur = "chất lượng nước luôn là sống còn"
    elif any(k in combined for k in ["traffic", "giao thông", "camera", "police", "xe"]):
        exp_dur = "giao thông đô thị nhu cầu vĩnh cửu"
    elif any(k in combined for k in ["diagnost", "chẩn đoán", "hỏng", "log", "fault", "sensor monitoring"]):
        exp_dur = "thiết bị phần cứng luôn cần bảo trì"
    elif any(k in combined for k in ["robot", "weeder", "farm", "crop", "nông nghiệp"]):
        exp_dur = "nông nghiệp luôn cần tăng năng suất"
    elif any(k in combined for k in ["energy", "solar", "battery", "năng lượng"]):
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
    if any(k in combined for k in ["water", "aqua", "tôm", "cá", "thủy sản", "nước", "purif", "buoy"]):
        exp_ai = "AI đọc số, người thay nước"
    elif any(k in combined for k in ["sensor", "cảm biến", "monitor"]):
        exp_ai = "AI đọc cảm biến, người xử lý"
    elif any(k in combined for k in ["traffic", "camera", "giao thông"]):
        exp_ai = "AI soi lỗi, cảnh sát xử lý"
    elif any(k in combined for k in ["diagnost", "chẩn đoán", "log", "fault"]):
        exp_ai = "AI đọc log, kỹ sư sửa chữa"
    elif any(k in combined for k in ["robot", "weeder", "embodied"]):
        exp_ai = "AI điều hướng, robot thao tác"
    elif ai == 3:
        if "tech_cheap" in opp.get("signal_type", []):
            exp_ai = "AI mã nguồn mở tối ưu phần cứng"
        else:
            exp_ai = "AI cảm biến nhận diện, người xác nhận"
    elif ai == 2:
        exp_ai = "AI phân tích, người ra quyết định"
    else:
        exp_ai = "AI hỗ trợ tự động hóa một phần"

    # 3. Đòn bẩy (Leverage)
    if any(k in combined for k in ["water", "aqua", "tôm", "cá", "thủy sản", "nước", "phao"]):
        exp_lev = "đúng ngách IoT nước của bạn"
    elif any(k in combined for k in ["traffic", "camera", "edge ai"]):
        exp_lev = "đúng thế mạnh camera phần cứng"
    elif any(k in combined for k in ["sensor", "cảm biến", "hardware", "esp32", "modbus", "rs485"]):
        exp_lev = "tận dụng bo mạch phần cứng sẵn có"
    elif any(k in combined for k in ["robot", "weeder", "automation"]):
        exp_lev = "hợp kỹ năng tự động hóa hệ thống"
    elif lev == 3:
        if "tech_cheap" in opp.get("signal_type", []):
            exp_lev = "chi phí công nghệ giảm sâu dễ làm"
        else:
            exp_lev = "đúng ngách IoT phần cứng mục tiêu"
    elif lev == 2:
        exp_lev = "hợp năng lực lập trình hệ thống"
    else:
        exp_lev = "phù hợp khả năng triển khai thực tế"

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


def send_message(text):
    """Send a Telegram message. Never raises — failures are logged only."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram alert")
        return False

    if len(text) > TELEGRAM_MAX_LEN:
        text = text[: TELEGRAM_MAX_LEN - 20].rstrip() + "\n… (cắt bớt)"

    try:
        r = requests.post(
            f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=TIMEOUT,
        )
        if not r.ok:
            log(f"Telegram API returned {r.status_code}: {r.text[:300]}")
            return False
        return True
    except Exception as e:
        log(f"Telegram send failed: {e}")
        return False
