# Opportunity Radar — lớp chấm điểm cơ hội cho Trend Radar

Thư mục đề xuất: `trend-radar/docs/opportunity-radar/`

Lớp này gắn **lên trên** Trend Radar đang chạy. Nó biến tín hiệu thô (`signals.json` từ `aggregate.py`) thành danh sách cơ hội kinh doanh đã xếp hạng, feed vào quy trình **Share → Watch → Research → Build**.

## Nguyên tắc
- Tái dùng, không dựng mới: `score.py` chỉ đọc output của `aggregate.py`.
- Feed vào quy trình sẵn có, không tự quyết định thay bạn.
- Lọc đa lớp: ≥ 2 nguồn khác loại mới tính đủ điểm.
- Mỗi tuần ép ra 1 hành động: "đi hỏi 3 người về X".

## Luồng chạy
```
fetch.py → aggregate.py → score.py → opportunities.json → My News (frontend) + Telegram
```

## Thứ tự làm các phase

| Phase | File | Việc | Trạng thái |
| --- | --- | --- | --- |
| 1 | `phase-1-score-engine.md` | Lõi `score.py` — chấm điểm, ghi `opportunities.json` | ✅ Hoàn thành |
| 2 | `phase-2-github-actions.md` | Gắn vào GitHub Actions sau aggregate | ✅ Hoàn thành |
| 3 | `phase-3-frontend-table.md` | Tab Opportunity Radar + bảng xếp hạng | ✅ Hoàn thành |
| 4 | `phase-4-filters-actnow.md` | Bộ lọc + phần Act now nổi bật | ✅ Hoàn thành |
| 5 | `phase-5-telegram.md` | Lọc Telegram chỉ bắn điểm 9 | ✅ Hoàn thành |
| 6 | `phase-6-velocity-tuning.md` | Velocity + tinh chỉnh ngưỡng sau 1 tháng | ⏳ Tiếp theo |

## Mốc kiểm tra quan trọng
Sau Phase 2, kiểm tra `opportunities.json` ra kết quả hợp lý **trước khi** làm frontend. Đừng xây giao diện trên dữ liệu sai.
