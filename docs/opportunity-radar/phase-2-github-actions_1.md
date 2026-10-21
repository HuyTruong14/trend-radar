# Phase 2 — Gắn vào GitHub Actions

**Ưu tiên:** Act now
**Phụ thuộc:** Phase 1 (`score.py` chạy được)
**Mục tiêu:** `score.py` chạy tự động sau `aggregate.py` mỗi lần fetch, không cần máy local.

---

## Việc cần làm

1. Mở workflow GitHub Actions hiện tại của Trend Radar (file `.yml` trong `.github/workflows/`).
2. Thêm 1 step chạy `score.py` **ngay sau** step chạy `aggregate.py`.
3. Đảm bảo `opportunities.json` được commit/publish cùng chỗ với `signals.json` (để frontend đọc được).

## Vị trí trong pipeline
```
step: fetch      → signals thô
step: aggregate  → signals.json
step: score      → opportunities.json   ← THÊM Ở ĐÂY
step: publish    → đẩy lên GitHub Pages
```

## Lưu ý
- `score.py` không gọi mạng → không cần thêm secret hay quota.
- Nếu `aggregate.py` fail thì `score.py` nên skip (đừng chạy trên dữ liệu thiếu).
- Giữ nguyên lịch chạy (schedule) đang có, không đổi.

## Done khi
- [ ] Workflow chạy tự động, `opportunities.json` được cập nhật sau mỗi lần fetch.
- [ ] File lên đúng chỗ frontend đọc được.
- [ ] **Mốc kiểm tra:** xem `opportunities.json` sau 1–2 lần chạy thật. Kết quả hợp lý mới sang Phase 3. Nếu không → quay lại chỉnh công thức ở Phase 1.
