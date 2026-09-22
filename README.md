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
- Đây là bản MVP cho keyword-matching đơn giản, chưa có AI tóm tắt/xếp
  hạng độ liên quan — có thể nâng cấp sau bằng cách gọi Claude API trong
  bước fetch.
