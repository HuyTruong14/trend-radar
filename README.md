# Trend Radar

Tool cá nhân theo dõi tín hiệu sớm (Hacker News, arXiv, GitHub, RSS ngành)
cho 2 chủ đề: **AI & Technology** và **iGaming & Gaming**. Chạy tự động mỗi
ngày trên GitHub Actions, kết quả xem trên 1 trang web tĩnh (GitHub Pages).

## Setup (làm 1 lần, ~5 phút)

1. Tạo một repo mới trên GitHub (private hoặc public đều được), ví dụ `trend-radar`.
2. Copy toàn bộ nội dung thư mục này vào repo, rồi commit + push:
   ```bash
   git init
   git add .
   git commit -m "Initial trend radar setup"
   git branch -M main
   git remote add origin https://github.com/<your-username>/trend-radar.git
   git push -u origin main
   ```
3. Bật GitHub Pages:
   - Vào repo → **Settings → Pages**
   - Source: **Deploy from a branch**
   - Branch: `main`, folder: **/docs**
   - Save. Sau ~1 phút, trang sẽ có ở `https://<your-username>.github.io/trend-radar/`
4. Bật quyền ghi cho Actions (để workflow tự commit data mới):
   - **Settings → Actions → General → Workflow permissions**
   - Chọn **Read and write permissions** → Save
5. Chạy thử lần đầu thủ công:
   - Tab **Actions** → chọn workflow **Fetch trends** → **Run workflow**
   - Đợi ~1 phút, refresh trang dashboard để thấy data.

Sau bước này, workflow tự chạy mỗi ngày lúc 07:00 UTC (14:00 giờ VN) —
không cần mở máy tính.

## Tùy chỉnh

- **Đổi/thêm từ khóa, nguồn**: sửa `config.yaml` — không cần đụng code.
- **Đổi tần suất chạy**: sửa dòng `cron` trong
  `.github/workflows/fetch-trends.yml` (định dạng cron chuẩn UTC).
- **Thêm nguồn RSS mới cho iGaming**: thêm URL feed vào mục `rss:` trong
  `config.yaml`.
- **Thêm chủ đề thứ 3**: copy 1 block trong `config.yaml`, đặt key mới
  (vd. `web3`), rồi thêm key đó vào mảng `TOPICS` trong `docs/index.html`.

## Giới hạn hiện tại (đáng biết)

- GitHub Search API không cần token vẫn chạy được nhưng giới hạn ~10
  request/phút — đủ cho vài query mỗi ngày, không nên thêm quá 5-6 query
  vào `github_search`.
- RSS feed của SBC News / iGaming Business dùng URL WordPress mặc định —
  nếu trang đổi cấu trúc, sửa lại URL trong `config.yaml`.
- Chưa có Reddit / Product Hunt / Google Trends (cần OAuth token) — nếu
  muốn thêm, nói để tôi bổ sung.
- AI scoring (tóm tắt + điểm liên quan 1-5), cross-source correlation, và
  alert Telegram cho item điểm cao đã có code (Phase 1 & 3) nhưng **đang
  tắt** vì repo chưa cấu hình `ANTHROPIC_API_KEY` (dùng API Anthropic trả
  phí theo token — khác với gói Claude Pro trên claude.ai, không dùng
  chung được). Thêm secret đó vào repo là bật được ngay, không cần sửa
  code.

## Phase 4 (roadmap — chưa làm)

Chưa bắt đầu, ghi lại để làm tiếp khi cần:

- **Tránh báo trùng Telegram**: hiện tại 1 item có thể bị báo lại nhiều
  lần nếu nó vẫn còn nằm trong danh sách "fresh" (do `freshness_days`)
  ở các lần chạy sau — Phase 3 chấp nhận việc này để giữ đơn giản. Cần
  lưu lại "đã báo item nào" (vd. set URL đã alert, có TTL) để chỉ báo 1
  lần cho mỗi item. Chỉ đáng làm sau khi `ANTHROPIC_API_KEY` được bật,
  vì hiện alert theo điểm/cross-source chưa kích hoạt.
- **Thêm nguồn mới**: Reddit, Product Hunt, Google Trends — đều cần
  OAuth/API key riêng, chưa có trong `requirements.txt`/`fetch.py`.
- **RSS dự phòng**: khi 1 feed 404 (như a16z, hbr.org từng bị), tự động
  thử feed thay thế thay vì phải sửa `config.yaml` thủ công mỗi lần.
- **Dọn label nguồn**: một số feed trả `<title>` xấu (vd. feed HBR trả
  "HBR CMS" thay vì "Harvard Business Review") — có thể thêm field
  `display_name` tùy chọn trong `config.yaml` để override label hiển thị
  trên dashboard.
