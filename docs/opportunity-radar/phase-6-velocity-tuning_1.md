# Phase 6 — Velocity + tinh chỉnh ngưỡng

**Ưu tiên:** Can wait (làm sau khi dùng thật ~1 tháng)
**Phụ thuộc:** Phase 1–5 chạy ổn, đã có dữ liệu thật tích lũy
**Mục tiêu:** Giảm nhiễu, tăng độ chính xác dựa trên dữ liệu thật.

---

## Việc cần làm

### 1. Tính `velocity` thật
So `first_seen` với `last_seen` và số lần tín hiệu xuất hiện:

| velocity | Điều kiện |
| --- | --- |
| `rising` | Xuất hiện ngày càng nhiều trong 2 tuần gần nhất |
| `steady` | Đều đặn, không tăng không giảm |
| `fading` | Thưa dần, lâu không thấy lại |

→ Cơ hội `fading` nên hạ ưu tiên dù điểm cao (xu hướng đang tắt).

### 2. Tinh chỉnh ngưỡng
Sau 1 tháng, nhìn lại:
- Ngưỡng điểm 9 có quá chặt (không ra cơ hội nào)? → cân nhắc hạ xuống 8.
- Hay quá lỏng (ra quá nhiều)? → siết lại hoặc tăng yêu cầu `source_count`.

### 3. Hiệu chỉnh công thức chấm
- Xem lại các cơ hội bạn đã **thực sự đi hỏi khách**: điểm hệ thống chấm có khớp với giá trị thật không?
- Nếu lệch, chỉnh trọng số 3 lớp lọc cho sát thực tế của bạn.

## Done khi
- [x] `velocity` tính tự động, `fading` bị hạ ưu tiên.
- [x] Ngưỡng điều chỉnh dựa trên dữ liệu thật, không phải phỏng đoán.
- [x] Hệ thống cho ra 1–3 cơ hội đáng đi hỏi khách mỗi tuần — đúng mục tiêu cuối.
