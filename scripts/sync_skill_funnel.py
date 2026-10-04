"""
Detect repos with skill/agent files from trending data and sync to skill-funnel.

Checks each GitHub-sourced repo for SKILL.md, AGENTS.md, .claude/, or rules/ dirs.
New finds get appended to HuyTruong14/skill-funnel sources.md via GitHub API.

Usage:
  python scripts/sync_skill_funnel.py          # scan all topics
  SKILL_FUNNEL_REPO=other/repo python ...      # target different repo

Requires GITHUB_TOKEN with repo scope for writing to skill-funnel.
"""
import json
import glob
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "docs", "data")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
SKILL_FUNNEL_REPO = os.environ.get("SKILL_FUNNEL_REPO", "HuyTruong14/skill-funnel")
SKILL_MARKERS = ["SKILL.md", "AGENTS.md", ".claude", "rules"]

API = "https://api.github.com"


def log(msg):
    print(f"[skill-sync] {msg}", flush=True)


def gh_get(path, **kwargs):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = requests.get(f"{API}{path}", headers=headers, timeout=15, **kwargs)
    return r


def gh_has_skill_files(full_name):
    """Check if a repo has any skill marker files/dirs at root."""
    r = gh_get(f"/repos/{full_name}/contents/")
    if r.status_code != 200:
        return []
    names = [item["name"] for item in r.json()]
    return [m for m in SKILL_MARKERS if m in names]


def get_sources_md():
    """Fetch current sources.md content and sha from skill-funnel."""
    r = gh_get(f"/repos/{SKILL_FUNNEL_REPO}/contents/sources.md")
    if r.status_code != 200:
        log(f"Cannot read sources.md: {r.status_code}")
        return None, None
    import base64
    data = r.json()
    content = base64.b64decode(data["content"]).decode()
    return content, data["sha"]


def extract_existing_repos(sources_content):
    """Parse repo names already in sources.md."""
    repos = set()
    for line in sources_content.splitlines():
        if "github.com/" in line:
            for part in line.split("github.com/"):
                slug = part.split(")")[0].split("|")[0].split(" ")[0].strip("/")
                if "/" in slug and len(slug.split("/")) == 2:
                    repos.add(slug.lower())
    return repos


def update_sources_md(sources_content, sha, new_repos):
    """Append new repos to sources.md via GitHub API."""
    import base64

    lines = sources_content.rstrip().split("\n")

    marker = "## From Trend Radar"
    marker_idx = None
    for i, line in enumerate(lines):
        if marker in line:
            marker_idx = i
            break

    next_num = sources_content.count("| ") // 2 + 1

    new_lines = []
    for repo_name, stars, markers, desc in new_repos:
        strengths = ", ".join(markers)
        new_lines.append(
            f"| {next_num} | {repo_name} | https://github.com/{repo_name} "
            f"| {strengths} ({stars} stars) | Pending |"
        )
        next_num += 1

    if marker_idx is not None:
        comment_idx = marker_idx + 1
        while comment_idx < len(lines) and lines[comment_idx].strip().startswith("<!--"):
            comment_idx += 1
        for nl in reversed(new_lines):
            lines.insert(comment_idx, nl)
    else:
        lines.append("")
        lines.append("## From Trend Radar (auto-detected)")
        lines.extend(new_lines)

    updated = "\n".join(lines) + "\n"
    encoded = base64.b64encode(updated.encode()).decode()

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = requests.put(
        f"{API}/repos/{SKILL_FUNNEL_REPO}/contents/sources.md",
        headers=headers,
        json={
            "message": f"Add {len(new_repos)} repo(s) from Trend Radar",
            "content": encoded,
            "sha": sha,
        },
        timeout=15,
    )
    if r.status_code in (200, 201):
        log(f"Updated sources.md with {len(new_repos)} new repo(s)")
        return True
    log(f"Failed to update sources.md: {r.status_code} {r.text[:200]}")
    return False


def main():
    if not GITHUB_TOKEN:
        log("GITHUB_TOKEN required")
        sys.exit(1)

    data_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    data_files = [f for f in data_files if not f.endswith(("-stats.json", "manifest.json", "recommended.json"))]

    github_repos = {}
    for path in data_files:
        with open(path) as f:
            data = json.load(f)
        for item in data.get("items", []):
            if item.get("source") != "GitHub":
                continue
            full_name = item.get("title", "")
            if "/" not in full_name:
                continue
            if full_name not in github_repos:
                github_repos[full_name] = {
                    "stars": item.get("score", 0),
                    "desc": item.get("summary") or "",
                    "url": item.get("url", ""),
                }

    log(f"Found {len(github_repos)} GitHub repos in trending data")

    sources_content, sha = get_sources_md()
    if sources_content is None:
        sys.exit(1)

    existing = extract_existing_repos(sources_content)
    log(f"Already tracking {len(existing)} repos in sources.md")

    new_repos = []
    for full_name, info in github_repos.items():
        if full_name.lower() in existing:
            continue
        time.sleep(0.5)
        markers = gh_has_skill_files(full_name)
        if markers:
            log(f"  + {full_name}: {markers}")
            new_repos.append((full_name, info["stars"], markers, info["desc"]))

    if not new_repos:
        log("No new skill repos found")
        return

    log(f"Detected {len(new_repos)} new skill repo(s)")
    update_sources_md(sources_content, sha, new_repos)


if __name__ == "__main__":
    main()
