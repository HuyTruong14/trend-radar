# Phase 5 — Lọc cảnh báo Telegram

**Ưu tiên:** Can wait
**Phụ thuộc:** Phase 2 (`opportunities.json` chạy tự động)
**Mục tiêu:** Telegram chỉ bắn cảnh báo cho tín hiệu mạnh nhất, tránh spam.

---

## Việc cần làm

1. Dùng lại cơ chế Telegram đang có của Trend Radar.
2. Thêm điều kiện: chỉ gửi record có `total` = 9 (`build_ready`).
3. Mỗi cơ hội chỉ bắn **1 lần** (lưu id đã gửi, tránh lặp mỗi lần chạy).

## Nội dung tin nhắn gợi ý
```
🔴 CƠ HỘI MỚI (9/9) — Act now
[title]
[summary]
Loại: [signal_type]
Nguồn: [source_count] nguồn xác nhận
→ Tuần này: đi hỏi 3 người thật
```

## Lưu ý
- Đừng bắn stage `research` hay `watch` qua Telegram — để trong dashboard là đủ. Telegram chỉ dành cho việc cần làm ngay.

## Done khi
- [x] Chỉ record điểm 9 mới bắn Telegram.
- [x] Không bắn lặp cùng một cơ hội.
- [x] Tin nhắn rõ ràng, có câu hành động.
