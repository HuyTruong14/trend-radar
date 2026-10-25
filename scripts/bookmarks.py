#!/usr/bin/env python3
"""
scripts/bookmarks.py — Research Bookmarks Manager (Phase 14)

Manages docs/data/bookmarks.json:
[
  {
    "opp_id": "opp_...",
    "title": "Smart-Aquaculture-Assistant",
    "bookmarked_at": "2026-10-25T13:00:00+07:00",
    "status": "new",          # "new" | "researching" | "done" | "skipped"
    "notes": "Xem code repo, so sánh với Seneye",
    "score": 9
  }
]

CLI Usage:
  python scripts/bookmarks.py list [--status new]
  python scripts/bookmarks.py add opp_2026_1024_499128aa --notes "Kiểm tra firmware"
  python scripts/bookmarks.py update opp_2026_1024_499128aa --status researching --notes "Đang clone repo"
  python scripts/bookmarks.py remove opp_2026_1024_499128aa
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "docs", "data")
BOOKMARKS_FILE = os.path.join(DATA_DIR, "bookmarks.json")
OPPORTUNITIES_FILE = os.path.join(DATA_DIR, "opportunities.json")

VALID_STATUSES = ["new", "researching", "done", "skipped"]
STATUS_EMOJIS = {
    "new": "📌 new",
    "researching": "🔍 researching",
    "done": "✅ done",
    "skipped": "❌ skipped"
}


def load_bookmarks():
    """Load bookmarks from docs/data/bookmarks.json."""
    if not os.path.exists(BOOKMARKS_FILE):
        return []
    try:
        with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[bookmarks] Warning: failed to load {BOOKMARKS_FILE}: {e}")
        return []


def save_bookmarks(bookmarks):
    """Save bookmarks list to docs/data/bookmarks.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=2)
    print(f"[bookmarks] Saved {len(bookmarks)} bookmarks to {BOOKMARKS_FILE}")


def find_opportunity_info(opp_id):
    """Lookup title and score from opportunities.json if available."""
    if not os.path.exists(OPPORTUNITIES_FILE):
        return None, 0
    try:
        with open(OPPORTUNITIES_FILE, "r", encoding="utf-8") as f:
            opps = json.load(f)
            for o in opps:
                if o.get("id") == opp_id:
                    return o.get("title", opp_id), o.get("total", 0)
    except Exception:
        pass
    return opp_id, 0


def add_bookmark(opp_id, notes="", status="new", title=None, score=None):
    """Add a new bookmark or update existing."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    bookmarks = load_bookmarks()
    now_vn = datetime.now(timezone(timedelta(hours=7))).isoformat()

    # Check if already bookmarked
    for b in bookmarks:
        if b.get("opp_id") == opp_id:
            if status:
                b["status"] = status
            if notes:
                b["notes"] = notes
            b["updated_at"] = now_vn
            save_bookmarks(bookmarks)
            print(f"[bookmarks] ✅ Updated existing bookmark for {opp_id}: status={status}")
            return b

    # Auto-lookup title and score if not provided
    if not title or score is None:
        looked_title, looked_score = find_opportunity_info(opp_id)
        title = title or looked_title
        score = score if score is not None else looked_score

    new_bm = {
        "opp_id": opp_id,
        "title": title or opp_id,
        "bookmarked_at": now_vn,
        "status": status,
        "notes": notes,
        "score": score or 0
    }
    bookmarks.append(new_bm)
    save_bookmarks(bookmarks)
    print(f"[bookmarks] ✅ Added new bookmark: [{STATUS_EMOJIS.get(status, status)}] {title} (ID: {opp_id})")
    return new_bm


def update_bookmark(opp_id, status=None, notes=None):
    """Update status and/or notes of an existing bookmark."""
    bookmarks = load_bookmarks()
    found = False
    now_vn = datetime.now(timezone(timedelta(hours=7))).isoformat()

    for b in bookmarks:
        if b.get("opp_id") == opp_id:
            if status:
                if status not in VALID_STATUSES:
                    raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
                b["status"] = status
            if notes is not None:
                b["notes"] = notes
            b["updated_at"] = now_vn
            found = True
            break

    if not found:
        print(f"[bookmarks] ⚠️ Bookmark with opp_id '{opp_id}' not found.")
        return False

    save_bookmarks(bookmarks)
    print(f"[bookmarks] ✅ Updated bookmark {opp_id}: status={status or 'unchanged'}")
    return True


def remove_bookmark(opp_id):
    """Remove a bookmark by opp_id."""
    bookmarks = load_bookmarks()
    orig_len = len(bookmarks)
    bookmarks = [b for b in bookmarks if b.get("opp_id") != opp_id]
    if len(bookmarks) == orig_len:
        print(f"[bookmarks] ⚠️ No bookmark found with opp_id '{opp_id}' to remove.")
        return False
    save_bookmarks(bookmarks)
    print(f"[bookmarks] 🗑️ Removed bookmark {opp_id}")
    return True


def list_bookmarks(status_filter=None):
    """List all bookmarks formatted cleanly."""
    bookmarks = load_bookmarks()
    if status_filter:
        bookmarks = [b for b in bookmarks if b.get("status") == status_filter]

    print("\n" + "="*70)
    print("📌 RESEARCH BOOKMARKS (PHASE 14)")
    print("="*70)

    if not bookmarks:
        print("Trống — Chưa có cơ hội nào được đánh dấu.")
        print("="*70 + "\n")
        return bookmarks

    for idx, b in enumerate(bookmarks, 1):
        st = b.get("status", "new")
        st_label = STATUS_EMOJIS.get(st, st)
        title = b.get("title", b.get("opp_id"))
        score = b.get("score", 0)
        notes = b.get("notes") or "(không có ghi chú)"
        date_str = (b.get("bookmarked_at") or "")[:10]
        print(f"{idx}. [{st_label}] {title} ({score}/9)")
        print(f"   ID: {b.get('opp_id')} | Ngày: {date_str}")
        print(f"   Ghi chú: {notes}")
        print("-" * 70)

    print(f"Tổng cộng: {len(bookmarks)} bookmarks\n")
    return bookmarks


def main():
    parser = argparse.ArgumentParser(description="Trend Radar — Research Bookmarks Manager (Phase 14)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    p_list = subparsers.add_parser("list", help="List bookmarks")
    p_list.add_argument("--status", choices=VALID_STATUSES, help="Filter by status")

    # add
    p_add = subparsers.add_parser("add", help="Add a bookmark")
    p_add.add_argument("opp_id", help="Opportunity ID to bookmark")
    p_add.add_argument("--notes", default="", help="Research notes")
    p_add.add_argument("--status", default="new", choices=VALID_STATUSES, help="Status")
    p_add.add_argument("--title", help="Custom title (optional)")
    p_add.add_argument("--score", type=int, help="Custom score (optional)")

    # update
    p_update = subparsers.add_parser("update", help="Update bookmark status or notes")
    p_update.add_argument("opp_id", help="Opportunity ID to update")
    p_update.add_argument("--status", choices=VALID_STATUSES, help="New status")
    p_update.add_argument("--notes", help="New notes")

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove a bookmark")
    p_remove.add_argument("opp_id", help="Opportunity ID to remove")

    args = parser.parse_args()
    if not args.command or args.command == "list":
        list_bookmarks(getattr(args, "status", None))
    elif args.command == "add":
        add_bookmark(args.opp_id, notes=args.notes, status=args.status, title=args.title, score=args.score)
    elif args.command == "update":
        update_bookmark(args.opp_id, status=args.status, notes=args.notes)
    elif args.command == "remove":
        remove_bookmark(args.opp_id)


if __name__ == "__main__":
    main()
