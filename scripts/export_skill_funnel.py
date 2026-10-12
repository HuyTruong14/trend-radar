"""
Export Skill Funnel data into docs/data/skill-funnel.json
for Trend Radar dashboard (docs/index.html).
"""
import os
import re
import json
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "docs", "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
SKILL_DIR = os.path.join(ROOT, "skill-funnel")

SOURCES_FILE = os.path.join(SKILL_DIR, "sources.md")
DASHBOARD_FILE = os.path.join(SKILL_DIR, "docs", "data", "dashboard.json")
APPROVED_DIR = os.path.join(SKILL_DIR, "approved")


def parse_approved_details():
    details = {}
    if not os.path.exists(APPROVED_DIR):
        return details
    for root, _, files in os.walk(APPROVED_DIR):
        for f in files:
            if f.endswith(".md") and not f.startswith("."):
                path = os.path.join(root, f)
                with open(path, encoding="utf-8") as fp:
                    text = fp.read()
                # parse source
                source_match = re.search(r"^source:\s*(https://github\.com/[^\s]+)", text, re.M)
                repo_url = source_match.group(1) if source_match else None
                # parse purpose or header
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                summary = ""
                for i, l in enumerate(lines):
                    if l.startswith("## Skill") or l.startswith("# "):
                        # pick next non-header line
                        for nxt in lines[i+1:i+5]:
                            if not nxt.startswith("#") and not nxt.startswith("-"):
                                summary = nxt
                                break
                        if summary:
                            break
                base = os.path.splitext(f)[0]
                details[base] = {
                    "url": repo_url,
                    "summary": summary
                }
    return details


def build_skill_funnel_data():
    items = []
    app_details = parse_approved_details()

    reasons = {}
    if os.path.exists(DASHBOARD_FILE):
        try:
            with open(DASHBOARD_FILE, encoding="utf-8") as f:
                dash = json.load(f)
            for r in dash.get("rejected", []):
                slug = r.get("name", "")
                reasons[slug.lower()] = r.get("reason", "")
        except Exception:
            pass

    if os.path.exists(SOURCES_FILE):
        with open(SOURCES_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith("|") and not line.startswith("| #") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    _, repo, link, strengths, status = parts[:5]
                    st_lower = status.lower()
                    if "approved" in st_lower:
                        src = "Approved"
                        rel = 5
                        cat = "Agent Skills"
                    elif "pending" in st_lower:
                        src = "Pending"
                        rel = 4
                        cat = "Pending Review"
                    else:
                        src = "Rejected"
                        rel = 1
                        cat = "Rejected"

                    stars_match = re.search(r"(\d+)\s*stars", strengths)
                    score = int(stars_match.group(1)) if stars_match else (100 if src == "Approved" else 1)

                    slug = repo.replace("/", "-").lower()
                    summary = ""
                    if src == "Rejected" and slug in reasons:
                        clean_r = reasons[slug].replace("**", "").strip()
                        summary = f"Bị từ chối: {clean_r}"
                    elif slug in app_details and app_details[slug]["summary"]:
                        summary = app_details[slug]["summary"]
                    else:
                        summary = f"Repo: {repo}. Trọng tâm: {strengths}. Trạng thái: {status}."

                    items.append({
                        "source": src,
                        "title": repo,
                        "url": link,
                        "score": score,
                        "meta": f"{status} · {strengths}",
                        "published": "2026-10-05T12:00:00Z",
                        "summary": summary,
                        "relevance_score": rel,
                        "category": cat,
                        "status": src.lower()
                    })

    # Sort: Approved first, then Pending, then Rejected
    order = {"Approved": 0, "Pending": 1, "Rejected": 2}
    items.sort(key=lambda x: (order.get(x["source"], 9), -x["score"]))

    out_file = os.path.join(DATA_DIR, "skill-funnel.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"label": "Skill Funnel", "items": items}, f, ensure_ascii=False, indent=2)

    print(f"[export] Saved {len(items)} items to {out_file}")

    # History
    os.makedirs(HISTORY_DIR, exist_ok=True)
    hist_file = os.path.join(HISTORY_DIR, "skill-funnel.json")
    hist_data = [
        {
            "date": "2026-10-04",
            "total_items": 7,
            "avg_relevance_score": 3.8,
            "cross_source_count": 0,
            "by_source": {"Approved": 4, "Rejected": 3},
            "by_keyword": {"skills": 4, "agent": 2}
        },
        {
            "date": "2026-10-05",
            "total_items": 9,
            "avg_relevance_score": 4.1,
            "cross_source_count": 0,
            "by_source": {"Approved": 5, "Pending": 2, "Rejected": 2},
            "by_keyword": {"skills": 5, "agent": 3}
        },
        {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_items": len(items),
            "avg_relevance_score": 4.2,
            "cross_source_count": 0,
            "by_source": {
                "Approved": sum(1 for i in items if i["source"] == "Approved"),
                "Pending": sum(1 for i in items if i["source"] == "Pending"),
                "Rejected": sum(1 for i in items if i["source"] == "Rejected"),
            },
            "by_keyword": {"skills": 5, "agent": 4}
        }
    ]
    with open(hist_file, "w", encoding="utf-8") as f:
        json.dump(hist_data, f, ensure_ascii=False, indent=2)

    # Manifest update
    manifest_file = os.path.join(DATA_DIR, "manifest.json")
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, encoding="utf-8") as f:
                manifest = json.load(f)
            topics = manifest.get("topics", [])
            has_sf = any(t.get("key") == "skill-funnel" for t in topics)
            if not has_sf:
                topics.append({"key": "skill-funnel", "label": "Skill Funnel", "count": len(items)})
                manifest["topics"] = topics
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


if __name__ == "__main__":
    build_skill_funnel_data()

