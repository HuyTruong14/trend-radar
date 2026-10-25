#!/usr/bin/env python3
"""
scripts/last_updated.py — Pipeline timestamp and freshness metadata tracker (Phase 14)

Maintains docs/data/last_updated.json:
{
  "last_run": "2026-10-25T07:00:00+07:00",
  "signals_count": 525,
  "status": "success"
}
"""

import os
import json
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "docs", "data")
LAST_UPDATED_FILE = os.path.join(DATA_DIR, "last_updated.json")


def update_last_updated(signals_count=None, status="success"):
    """Update docs/data/last_updated.json with current VN timestamp and signals count."""
    os.makedirs(DATA_DIR, exist_ok=True)
    vn_now = datetime.now(timezone(timedelta(hours=7))).isoformat()

    if signals_count is None:
        try:
            signals_file = os.path.join(DATA_DIR, "signals.json")
            if os.path.exists(signals_file):
                with open(signals_file, "r", encoding="utf-8") as f:
                    sigs = json.load(f)
                    signals_count = len(sigs) if isinstance(sigs, list) else 0
            else:
                signals_count = 0
        except Exception:
            signals_count = 0

    payload = {
        "last_run": vn_now,
        "signals_count": signals_count,
        "status": status
    }

    try:
        with open(LAST_UPDATED_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[last_updated] Updated {LAST_UPDATED_FILE}: {payload}")
    except Exception as e:
        print(f"[last_updated] Warning: could not write {LAST_UPDATED_FILE}: {e}")

    return payload


if __name__ == "__main__":
    update_last_updated()
