# Phase 4 — Bộ lọc + phần Act now nổi bật

**Ưu tiên:** This week
**Phụ thuộc:** Phase 3 (bảng đã chạy)
**Mục tiêu:** Hoàn thiện trang — thêm phần Act now trên cùng và bộ lọc sidebar.

---

## Việc cần làm

### 1. Phần Act now (trên cùng trang)
- Chỉ hiện record có `total` = 9 (`build_ready`).
- Thẻ to, màu nổi.
- Nút "Đánh dấu đã đi hỏi khách" — lưu trạng thái để không hiện lại mãi.

### 2. Bộ lọc (sidebar)

| Lọc theo | Giá trị |
| --- | --- |
| Loại tín hiệu | pain_repeat / price_shift / supply_gap / tech_cheap |
| Khoảng điểm | 4–6 / 7–8 / 9 |
| Xu hướng | rising / steady / fading |
| Bước | watch / research / build_ready |

## Lưu ý thiết kế
- Trang phải kết thúc bằng hành động, không chỉ để ngắm.
- Phần Act now đứng trên cùng để mỗi lần mở là thấy ngay "tuần này đi hỏi ai".

## Done khi
- [ ] Phần Act now hiện đúng record điểm 9, nút đánh dấu hoạt động.
- [ ] Bộ lọc chạy đúng cả 4 chiều.
- [ ] Trang nhìn gọn, dùng được trên điện thoại.
