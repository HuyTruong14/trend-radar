# Pipeline Monitor — Implementation Spec

## Overview

Dashboard hiển thị real-time status của 2 pipeline flow, mỗi step có log riêng. Serve trên port riêng, gắn link vào Glance sidebar.

## Architecture

```
Single static HTML file (monitor/index.html)
├── Served bởi halverneus/static-file-server trên port 8766
├── Browser-side polling (30s interval)
├── Data sources: GitHub API + HTTP ping + GitHub Pages JSON
└── Gắn vào Glance sidebar qua iframe hoặc bookmarks widget
```

Không cần backend mới. Browser gọi trực tiếp GitHub API (dùng token từ config.json) và ping localhost services.

---

## Flow 1: Data → Glance Dashboard

| # | Step | Mô tả | Data source kiểm tra | Risk |
|---|------|--------|----------------------|------|
| 1 | Actions trigger | Cron 14:00 VN hoặc manual | GitHub API: `GET /repos/HuyTruong14/trend-radar/actions/runs?per_page=1` → check `status`, `created_at` | — |
| 2 | Crawl trending | GitHub Trending, arXiv, news | Cùng API trên → xem `status=in_progress` hoặc `conclusion` | API rate limit |
| 3 | Gemini scoring | summary + relevance_score + category | Cùng workflow run → parse logs nếu cần (hoặc chỉ check pass/fail) | Gemini overloaded / quota |
| 4 | Analyze top 5 | Deep analysis what/apply | Cùng workflow run status | — |
| 5 | Update history | Lưu github_repos cho new/returning | Cùng workflow run status | — |
| 6 | Generate stats | ai-tech-stats.json | Cùng workflow run status | — |
| 7 | Git commit + push | Push data lên repo | Workflow run `conclusion === 'success'` | Git conflict |
| 8 | GitHub Pages deploy | Data public | `GET https://huytruong14.github.io/trend-radar/data/manifest.json` + check `Last-Modified` header hoặc response timestamp | Deploy chậm |
| 9 | Glance reads data | Dashboard hiện trends | Ping `http://localhost:8686` → HTTP 200 | — |
| 10 | Telegram digest | Gửi top-5 daily | Nằm trong workflow run, check conclusion | Token / chat_id sai |

**Cách xác định status từng step:**
- Step 1-7, 10: Dựa vào GitHub Actions workflow run. Một run chứa tất cả steps → gọi `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs` để lấy từng job step status.
- Step 8: Ping GitHub Pages URL, check response timestamp so với workflow completion time.
- Step 9: Ping Glance localhost.

---

## Flow 2: Send → Skill-funnel Extract

| # | Step | Mô tả | Data source kiểm tra | Risk |
|---|------|--------|----------------------|------|
| 1 | User nhấn Send | Chọn repo từ dashboard | Local action — luôn pass khi user click | — |
| 2 | Ghi sources.md | GitHub API → skill-funnel/sources.md | `GET /repos/HuyTruong14/skill-funnel/contents/sources.md` → check repo có trong file | Token hết hạn |
| 3 | Workflow trigger | skill-funnel Actions detect push | `GET /repos/HuyTruong14/skill-funnel/actions/runs?per_page=1` → check có run mới | Workflow không trigger |
| 4 | Read pending | Parse sources.md → danh sách | Cùng workflow run jobs | — |
| 5 | Clone & scan | Clone repo, phân tích structure | Cùng workflow run jobs | Repo quá lớn / private |
| 6 | AI extract | License, markers, purpose, recommendation | Cùng workflow run jobs | AI fail / timeout |
| 7 | Save dashboard.json | Ghi kết quả extraction | Cùng workflow run jobs | — |
| 8 | Commit + push | Push data lên skill-funnel | Workflow `conclusion` | Git conflict |
| 9 | Dashboard "Extracting" | Repo xuất hiện ở tab | `GET /repos/HuyTruong14/skill-funnel/contents/data/dashboard.json` → check repo in pending[] | — |
| 10 | User Approve/Reject | Review extract → quyết định | Local action | — |
| 11 | Approve workflow | Move → approved/ hoặc rejected/ | `GET /repos/HuyTruong14/skill-funnel/actions/workflows/approve.yml/runs?per_page=1` | — |

---

## GitHub API Calls

Mỗi lần refresh (30s) cần:

```
1. GET /repos/HuyTruong14/trend-radar/actions/runs?per_page=1
2. GET /repos/HuyTruong14/trend-radar/actions/runs/{id}/jobs  (nếu run đang in_progress)
3. GET /repos/HuyTruong14/skill-funnel/actions/runs?per_page=1
4. GET /repos/HuyTruong14/skill-funnel/actions/runs/{id}/jobs  (nếu run đang in_progress)
5. HEAD https://huytruong14.github.io/trend-radar/data/manifest.json  (check Pages deploy)
6. Ping http://localhost:8686  (Glance up?)
7. Ping http://localhost:8765  (Skill Dashboard up?)
8. Ping http://localhost:1200  (RSSHub up?)
9. Ping http://localhost:8080  (Miniflux up?)
```

= 4-5 GitHub API calls + 4-5 localhost pings per refresh.
30s interval = ~600 API calls/giờ. Rate limit 5000/giờ → safe.

---

## UI Spec

### Theme — match Glance

```css
--bg: hsl(225 14% 10%);
--surface: hsl(225 14% 14%);
--widget: hsl(225 14% 12%);
--border: hsl(225 10% 20%);
--text: hsl(225 10% 85%);
--muted: hsl(225 10% 50%);
--primary: hsl(43 50% 70%);
--positive: hsl(120 50% 50%);
--negative: hsl(0 70% 60%);
--accent: hsl(215 70% 55%);
--warning: hsl(35 90% 55%);
```

### Layout

```
┌─────────────────────────────────────────────┐
│ Pipeline monitor          ● Live  Updated 5s ago  [Refresh] │
├─────────────────────────────────────────────┤
│  [Passed: 7]  [Running: 1]  [Failed: 2]  [Waiting: 3]      │
├─────────────────────────────────────────────┤
│  [ Data → Glance ]  [ Send → Extract ]     │ ← tabs
├─────────────────────────────────────────────┤
│                                             │
│  ● Step 1: Actions trigger          14:00:02│
│  │  Cron 14:00 VN / manual dispatch         │
│  │  ┌──────────────────────────────┐        │
│  │  │ 14:00:02 Workflow triggered  │ ← log  │
│  │  │ 14:00:04 Python 3.11 ready   │        │
│  │  └──────────────────────────────┘        │
│  │                                          │
│  ● Step 2: Crawl trending          14:00:15 │
│  │  GitHub Trending + arXiv + news          │
│  │  ┌──────────────────────────────┐        │
│  │  │ 14:00:08 Fetching GitHub...  │        │
│  │  │ 14:00:15 30 repos fetched    │        │
│  │  └──────────────────────────────┘        │
│  │                                          │
│  ◉ Step 3: Gemini scoring  (pulsing)        │
│  │  ⚠ Gemini overloaded / quota             │
│  │  ┌──────────────────────────────┐        │
│  │  │ 14:01:03 Scoring 30 items... │        │
│  │  └──────────────────────────────┘        │
│  │                                          │
│  ○ Step 4: Update history   (dimmed)        │
│     Waiting...                              │
│                                             │
└─────────────────────────────────────────────┘
```

### Step Status Visual

| Status | Dot | Line | Name color | Log border |
|--------|-----|------|------------|------------|
| pass | ✓ green bg | green | normal | green left |
| fail | ✗ red bg | red | normal | red left |
| run | ↻ blue bg + pulse animation | blue | normal | blue left |
| wait | ○ border only | gray | muted/dimmed | — (no log) |

### Animations

1. **Live dot**: green dot nhấp nháy (opacity 1→0.3→1, 2s cycle)
2. **Running step dot**: pulse scale (1→1.2→1, 1.5s cycle)
3. **Refresh button icon**: spin 0.8s khi click
4. **Step transition**: khi status thay đổi, dùng CSS transition trên background-color

### Per-step Log Box

- Chỉ hiện khi step có logs (pass/fail/run)
- Step wait: không hiện log box
- Border-left 3px, màu theo status (green/red/blue)
- Background: --widget
- Font: monospace, 11px
- Mỗi line: `[timestamp] [message]`
- Message color: log-ok (green), log-err (red), log-info (blue), log-warn (orange)

---

## File Structure

```
trend-radar/
├── monitor/
│   └── index.html          ← single file, toàn bộ HTML/CSS/JS
├── docker-compose.yml      ← thêm service pipeline-monitor
└── glance.yml              ← thêm link vào Skills sidebar
```

### Docker Compose — thêm service

```yaml
pipeline-monitor:
  image: halverneus/static-file-server:latest
  volumes:
    - ./monitor:/web
  environment:
    PORT: 8766
  ports:
    - 8766:8766
  restart: unless-stopped
```

### Glance — thêm bookmark vào Skills page sidebar

```yaml
# Trong Skills page, sidebar bookmarks, thêm:
- title: Pipeline Monitor
  url: http://localhost:8766
  icon: mdi:monitor-dashboard
```

---

## Token

Monitor dùng chung token với Skill Funnel dashboard. Đọc từ `config.json`:

```javascript
// monitor/index.html sẽ fetch config từ skill-dashboard
const cfg = await fetch('http://localhost:8765/config.json').then(r => r.json()).catch(() => null);
TOKEN = cfg?.github_token || localStorage.getItem('gh_token') || '';
```

Hoặc tạo `monitor/config.json` riêng (copy token, thêm vào .gitignore).

---

## Mapping GitHub Actions → Steps

### Cách đọc workflow run status

```javascript
// 1. Lấy run mới nhất
const run = await ghApi(`/repos/HuyTruong14/trend-radar/actions/runs?per_page=1`);
// run.workflow_runs[0] → { id, status, conclusion, created_at, updated_at }

// 2. Nếu status === 'in_progress', lấy jobs detail
const jobs = await ghApi(`/repos/HuyTruong14/trend-radar/actions/runs/${runId}/jobs`);
// jobs.jobs[0].steps[] → { name, status, conclusion, started_at, completed_at }
```

### Mapping workflow steps → monitor steps

Workflow `fetch-trends.yml` có các steps:
```
"Check out repo"       → không map (internal)
"Set up Python"        → không map (internal)
"Install dependencies" → gộp vào Step 1 (trigger)
"Run fetcher"          → map Step 2-6 (crawl → stats)
"Index into RAGFlow"   → không map (optional)
"Commit updated data"  → map Step 7 (commit)
"Alert on failure"     → map Step 10 (telegram, nếu fail)
```

Vì "Run fetcher" là 1 step chứa cả crawl + score + analyze + history + stats, monitor sẽ:
- Khi step "Run fetcher" đang `in_progress` → hiện step 2-6 lần lượt dựa vào thời gian elapsed:
  - 0-10s: Step 2 running
  - 10-50s: Step 3 running
  - 50-90s: Step 4 running
  - 90-100s: Step 5 running
  - 100s+: Step 6 running
- Khi `completed + success` → tất cả step 2-6 pass
- Khi `completed + failure` → step cuối cùng đang running → fail, còn lại wait

### Nâng cấp sau (optional)

Nếu muốn log chính xác từng sub-step, fetch.py có thể ghi progress vào file:
```python
# fetch.py thêm:
with open("docs/data/pipeline-status.json", "w") as f:
    json.dump({"step": "scoring", "progress": "15/30", "timestamp": "..."}, f)
```
Monitor đọc file này từ GitHub Pages sau mỗi deploy. Nhưng delay = thời gian deploy, nên chỉ accurate cho lần chạy trước, không real-time.

---

## Implementation Checklist

1. [ ] Tạo `monitor/index.html` — single file với đầy đủ HTML/CSS/JS
2. [ ] Implement GitHub API polling (30s interval)
3. [ ] Implement localhost service pinging
4. [ ] Map workflow run steps → monitor steps
5. [ ] Render 2 flow tabs với per-step logs
6. [ ] Thêm `pipeline-monitor` service vào `docker-compose.yml`
7. [ ] Thêm bookmark link vào `glance.yml` sidebar
8. [ ] Test: chạy manual workflow dispatch, verify monitor cập nhật
9. [ ] Test: stop một service (RSSHub), verify monitor detect
