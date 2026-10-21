# Phase 3 — Tab Opportunity Radar + bảng xếp hạng

**Ưu tiên:** This week
**Phụ thuộc:** Phase 2 (`opportunities.json` chạy tự động, dữ liệu hợp lý)
**Mục tiêu:** Thêm 1 tab mới vào My News (:8088) hiển thị bảng cơ hội. Không đổi các trang cũ.

---

## Việc cần làm

1. Thêm tab "Opportunity Radar" vào My News.
2. Đọc `opportunities.json`.
3. Hiện bảng tất cả record có `total` ≥ 4 (ẩn `drop`).
4. Sắp xếp theo `total` giảm dần.

## Cột bảng

| Cột | Nguồn dữ liệu | Hiển thị |
| --- | --- | --- |
| Tiêu đề | `title` + `summary` | Tên + mô tả ngắn |
| Loại | `signal_type` | Chip 4 màu |
| Điểm | `total` | "8/9" + thanh màu |
| Nguồn | `source_count` + `sources` | Số + icon từng nguồn |
| Xu hướng | `velocity` | ↑ rising / → steady / ↓ fading |
| Bước | `stage` | Watch / Research / Build-ready |

## Màu cờ theo stage
- `build_ready` → đỏ cam (Act now)
- `research` → vàng (This week)
- `watch` → xám (Can wait)

> Dùng đúng bộ màu đã quen trên dashboard cũ để đồng bộ.

## Done khi
- [ ] Tab mới hiện trên My News, xem được từ Mac 1, Mac 2, điện thoại.
- [ ] Bảng đọc đúng `opportunities.json`, sắp xếp đúng.
- [ ] Các trang cũ không bị ảnh hưởng.
