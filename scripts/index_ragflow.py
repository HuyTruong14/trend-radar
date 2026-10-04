"""
Push collected trend data into RAGFlow for knowledge base search.

Usage:
  python scripts/index_ragflow.py                    # index all topics
  python scripts/index_ragflow.py ai-tech             # index one topic

Requires RAGFLOW_API_KEY env var (get from RAGFlow UI → User Settings → API).
RAGFlow must be running (docker compose -f docker-compose.ragflow.yml up -d).
"""
import json
import os
import sys
import glob
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "docs", "data")

RAGFLOW_URL = os.environ.get("RAGFLOW_URL", "http://localhost:9380")
RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "")

def log(msg):
    print(f"[ragflow-index] {msg}", flush=True)


def api(method, path, **kwargs):
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}", "Content-Type": "application/json"}
    r = requests.request(method, f"{RAGFLOW_URL}/api/v1{path}", headers=headers, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def get_or_create_dataset(name):
    resp = api("GET", "/datasets", params={"name": name})
    datasets = resp.get("data", [])
    for ds in datasets:
        if ds.get("name") == name:
            log(f"  Dataset '{name}' exists (id={ds['id']})")
            return ds["id"]
    resp = api("POST", "/datasets", json={"name": name})
    ds_id = resp["data"]["id"]
    log(f"  Created dataset '{name}' (id={ds_id})")
    return ds_id


def index_topic(topic_key):
    path = os.path.join(DATA_DIR, f"{topic_key}.json")
    if not os.path.exists(path):
        log(f"  ! No data file for '{topic_key}'")
        return

    with open(path) as f:
        data = json.load(f)

    label = data.get("label", topic_key)
    items = data.get("items", [])
    if not items:
        log(f"  ! No items in '{topic_key}'")
        return

    ds_id = get_or_create_dataset(f"trend-radar-{topic_key}")

    content_lines = [f"# {label}\n"]
    for it in items:
        title = it.get("title", "")
        url = it.get("url", "")
        source = it.get("source", "")
        summary = it.get("summary", "")
        what = it.get("what", "")
        apply_text = it.get("apply", "")
        score = it.get("relevance_score", "")
        meta = it.get("meta", "")

        content_lines.append(f"## {title}")
        content_lines.append(f"Source: {source} | {meta}")
        if url:
            content_lines.append(f"URL: {url}")
        if summary:
            content_lines.append(f"Summary: {summary}")
        if what:
            content_lines.append(f"What: {what}")
        if apply_text:
            content_lines.append(f"Apply: {apply_text}")
        if score:
            content_lines.append(f"Relevance: {score}/5")
        content_lines.append("")

    content = "\n".join(content_lines)

    # upload as document via file upload
    resp = requests.post(
        f"{RAGFLOW_URL}/api/v1/datasets/{ds_id}/documents",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        files={"file": (f"{topic_key}.md", content.encode(), "text/markdown")},
        timeout=30,
    )
    resp.raise_for_status()
    log(f"  Indexed '{topic_key}': {len(items)} items → RAGFlow dataset")


def main():
    if not RAGFLOW_API_KEY:
        log("Set RAGFLOW_API_KEY to use this script")
        log("Get it from RAGFlow UI → User Settings → API Key")
        sys.exit(1)

    # check ragflow is reachable
    try:
        requests.get(f"{RAGFLOW_URL}/api/v1/datasets", headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"}, timeout=5)
    except Exception as e:
        log(f"Cannot reach RAGFlow at {RAGFLOW_URL}: {e}")
        log("Start it: docker compose -f docker-compose.ragflow.yml up -d")
        sys.exit(1)

    topics = sys.argv[1:] if len(sys.argv) > 1 else []
    if not topics:
        topics = [os.path.basename(f).replace(".json", "") for f in sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
                  if not f.endswith(("-stats.json", "manifest.json", "recommended.json"))]

    log(f"Indexing {len(topics)} topic(s) into RAGFlow")
    for topic in topics:
        try:
            index_topic(topic)
        except Exception as e:
            log(f"  ! Failed to index '{topic}': {e}")

    log("Done.")


if __name__ == "__main__":
    main()
