# Phase 1 — Lõi chấm điểm (`score.py`)

**Ưu tiên:** Act now
**Phụ thuộc:** không (phase đầu tiên)
**Mục tiêu:** Đọc `signals.json`, gắn nhãn 4 loại tín hiệu, chấm 3 lớp lọc, ghi ra `opportunities.json`.

---

## Đầu vào / đầu ra
- **Đọc:** `signals.json` (output của `aggregate.py`)
- **Ghi:** `opportunities.json`
- **Không** gọi nguồn ngoài — chỉ đọc file đã có. Chạy nhanh, không tốn quota.

## Việc cần làm

1. Đọc `signals.json`, lặp qua từng tín hiệu.
2. Gắn nhãn loại tín hiệu (`signal_type`) — xem bảng dưới.
3. Chấm 3 lớp lọc, mỗi lớp 0–3 điểm.
4. Áp quy tắc chống nhiễu (multiplier).
5. Tính `total`, suy ra `stage`.
6. Ghi mảng record ra `opportunities.json`.

## 4 loại tín hiệu (gắn nhãn `signal_type`)

| Mã | Loại | Dấu hiệu |
| --- | --- | --- |
| `pain_repeat` | Nỗi đau lặp lại | Cùng than phiền xuất hiện nhiều lần (Reddit, X, Quora) |
| `price_shift` | Lệch giá / chi phí | Giá linh kiện, năng lượng biến động mạnh (RSS, HN) |
| `supply_gap` | Khoảng trống cung | "Có tool nào làm X không?" chưa có đáp án |
| `tech_cheap` | Công nghệ vừa đủ rẻ | Repo mới, cảm biến/mô hình rẻ đi (GitHub, arXiv) |

Một tín hiệu có thể mang nhiều nhãn.

## Công thức 3 lớp lọc (0–3 điểm mỗi lớp)

| Lớp | 0 điểm | 3 điểm |
| --- | --- | --- |
| `durability` (Bền) | Mốt nhất thời | Nhu cầu gốc không mất trong 10 năm |
| `ai_support` (AI hỗ trợ không thay) | AI thay sạch / AI vô dụng | Người giữ phần vật lý + trách nhiệm |
| `your_leverage` (Đòn bẩy của bạn) | Không liên quan | Khớp AI + build tool + tư duy hệ thống |

## Quy tắc chống nhiễu
- `source_count` < 2 → `multiplier` = 0.7
- `source_count` ≥ 2 (khác loại nguồn) → `multiplier` = 1.0
- `total` = (durability + ai_support + your_leverage) × multiplier, làm tròn.

## Ngưỡng → stage

| total | stage |
| --- | --- |
| 0–3 | `drop` |
| 4–6 | `watch` |
| 7–8 | `research` |
| 9 | `build_ready` |

## Schema `opportunities.json`
```json
{
  "id": "opp_2026_1021_001",
  "title": "Cảm biến chất lượng nước giá rẻ",
  "summary": "Mô tả ngắn 1-2 câu",
  "signal_type": ["tech_cheap", "supply_gap"],
  "sources": [
    {"name": "GitHub", "url": "...", "date": "2026-10-20"},
    {"name": "Reddit", "url": "...", "date": "2026-10-19"}
  ],
  "source_count": 2,
  "scores": {"durability": 3, "ai_support": 3, "your_leverage": 2},
  "multiplier": 1.0,
  "total": 8,
  "stage": "research",
  "first_seen": "2026-10-19",
  "last_seen": "2026-10-21",
  "velocity": "steady"
}
```
> `velocity` để trống hoặc "steady" ở Phase 1 — tính thật ở Phase 6.

## Done khi
- [ ] `score.py` chạy không lỗi, đọc được `signals.json` thật.
- [ ] `opportunities.json` sinh ra đúng schema.
- [ ] Mở file xem bằng mắt: điểm cao/thấp có hợp lý không? Nếu toàn rác điểm cao hoặc toàn điểm thấp → chỉnh công thức trước khi sang Phase 2.
