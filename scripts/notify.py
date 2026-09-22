"""
Trend Radar — sends alerts to Telegram via the plain Bot HTTP API.

No extra dependency: reuses `requests`, already in requirements.txt.
Reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from the environment; if either
is missing, send_message() logs a warning and returns without erroring, so
fetch.py keeps running fine for anyone who hasn't set up Telegram yet.
"""
import os

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_LEN = 4096
TIMEOUT = 15


def log(msg):
    print(f"[notify] {msg}", flush=True)


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


if __name__ == "__main__":
    ok = send_message("test từ trend-radar")
    log("send_message result: " + ("OK" if ok else "FAILED/SKIPPED"))
