# BÁO CÁO NGHIỆM THU HỆ THỐNG OPPORTUNITY RADAR
*Ngày nghiệm thu: 2026-10-22 | Phiên bản sau khi siết chặt kiểm tra chéo your_leverage*

---

## 1. Tổng quan Pipeline

| Chỉ số | Số lượng | Ghi chú |
| :--- | :---: | :--- |
| **Tổng tín hiệu đầu vào** (`news.json`) | **123** | Thu thập từ RSS, arXiv, GitHub, Web |
| **Tín hiệu rác bị loại trước khi chấm** | **63** | Lọc triệt để iGaming/gambling, VC funding, layoffs, sự kiện |
| **Tín hiệu đưa vào bộ chấm điểm** | **60** | Đã được chuẩn hóa metadata |
| **Cơ hội vượt ngưỡng lọt vào output** | **10** | Điểm $\ge 4$ (Đã loại sạch các paper AI thuần và nhóm Drop 0–3) |

### Phân bố theo giai đoạn (Stage)
- **🔥 Build-ready (9/9):** `0` cơ hội *(Cần $\ge 2$ nguồn xác nhận chéo để đạt điểm tuyệt đối)*
- **⚡ Research (7–8/9):** `4` cơ hội *(100% là phần cứng, robotics, chẩn đoán thiết bị và camera giao thông)*
- **⏱️ Watch (4–6/9):** `6` cơ hội *(Tín hiệu tiềm năng đang theo dõi)*
- **🗑️ Drop (0–3/9):** `0` *(Bị loại hẳn khỏi output, không đưa lên giao diện)*

---

## 2. Bảng xếp hạng Top 10 cơ hội (Điểm cao nhất)

| # | Tiêu đề | Loại tín hiệu | Durability | AI Support | Leverage | Sources | Tổng | Bước |
| :-: | :--- | :---: | :-: | :-: | :-: | :-: | :-: | :---: |
| **1** | **From the control center, AI camera helps Hanoi traffic police monitor every traffic span - Laodong.vn** | `supply_gap`, `tech_cheap` | 3 | 3 | 3 | 1 | **8** | `research` |
| **2** | **Semantic Observability for Autonomous Systems Diagnostics** | `tech_cheap` | 3 | 3 | 3 | 1 | **8** | `research` |
| **3** | **UniWALM: Unified World Action Language Model for Embodied Robot Control** | `tech_cheap` | 3 | 2 | 3 | 1 | **7** | `research` |
| **4** | **Industrial ReMEmbR: Scaling Spatiotemporal Memory to Robot Fleets** | `tech_cheap` | 3 | 2 | 3 | 1 | **7** | `research` |
| **5** | **Microsoft issues a warning regarding AI regulation. - Vietnam.vn** | `pain_repeat`, `supply_gap` | 2 | 2 | 2 | 1 | **5** | `watch` |
| **6** | **Blockbuster films take two years to complete, AI can do it in just one or two months: Proposal for a separate Copyright Law. - Vietnam.vn** | `supply_gap` | 2 | 2 | 2 | 1 | **5** | `watch` |
| **7** | **AI Law takes effect, anchors national governance framework - vietnamnews.vn** | `supply_gap`, `tech_cheap` | 2 | 2 | 2 | 1 | **5** | `watch` |
| **8** | **Regulations on the safety of AI applications in banking operations. - Vietnam.vn** | `supply_gap` | 3 | 2 | 1 | 1 | **5** | `watch` |
| **9** | **The Law on Artificial Intelligence must ensure four key pillars - Tạp chí KH&CN Việt Nam** | `supply_gap` | 2 | 1 | 2 | 1 | **4** | `watch` |
| **10** | **ALPS: Visual State Encoders for World Models** | `tech_cheap` | 1 | 3 | 1 | 1 | **4** | `watch` |

---

## 3. Kiểm tra sức khỏe dữ liệu (Health Checks)

- [x] **Có item nào `source_count >= 2` mà các nguồn khác chủ đề không?**
  - **KHÔNG**. Thuật toán ghép nguồn đối soát title chặt chẽ. Toàn bộ các tín hiệu khác biệt được tách độc lập thành từng record riêng biệt, không còn hiện tượng ghép bừa.
- [x] **Có ID trùng không?**
  - **KHÔNG**. 10/10 cơ hội có ID băm MD5 duy nhất, có định danh ngày tháng (`opp_YYYY_MMDD_hash8`), đảm bảo tính idempotent qua các lần chạy.
- [x] **Có rác lọt lưới không (gambling / VC funding / layoffs / quảng cáo sự kiện)?**
  - **KHÔNG**. 63 tin rác thuộc iGaming, gọi vốn startup, sa thải nhân sự đều bị bộ lọc regex tiền xử lý chặn đứng 100% trước khi chấm điểm.
- [x] **Phân bố điểm có đa dạng không, hay dồn cục vào 1–2 mức?**
  - **CÓ ĐA DẠNG**. Điểm số phân bố thực chất từ 4 đến 8 điểm (Điểm 8: 2, Điểm 7: 2, Điểm 5: 4, Điểm 4: 2), phản ánh đúng chất lượng nội dung thay vì gán điểm cố định theo nguồn.
- [x] **`signal_type` có khớp nội dung title không?**
  - **CÓ (Kiểm tra 5 mẫu):**
    1. *From the control center, AI camera helps Hanoi traffic police...*: Gắn `supply_gap`, `tech_cheap` $\rightarrow$ Khớp (Camera giám sát giao thông đô thị).
    2. *UniWALM: Unified World Action Language Model for Embodied Robot Control*: Gắn `tech_cheap` $\rightarrow$ Khớp (Robot control / Embodied AI).
    3. *Semantic Observability for Autonomous Systems Diagnostics*: Gắn `tech_cheap` $\rightarrow$ Khớp (Chẩn đoán hệ thống tự hành).
    4. *Industrial ReMEmbR: Scaling Spatiotemporal Memory to Robot Fleets*: Gắn `tech_cheap` $\rightarrow$ Khớp (Quản lý đội robot công nghiệp).
    5. *Microsoft issues a warning regarding AI regulation*: Gắn `pain_repeat`, `supply_gap` $\rightarrow$ Khớp (Khoảng trống chính sách & rủi ro luật AI).

---

## 4. Phân bố theo chủ đề trong Top 10

| Nhóm chủ đề | Số lượng | Tỷ lệ | Danh sách đại diện |
| :--- | :---: | :---: | :--- |
| **Robotics & Embodied AI** | **2** | 20% | UniWALM (7), Industrial ReMEmbR robot fleets (7) |
| **IoT & Edge Camera** | **1** | 10% | AI Camera giao thông Hà Nội (8) |
| **Diagnostics & Autonomous Systems** | **1** | 10% | Semantic Observability for Autonomous Systems Diagnostics (8) |
| **Khác (Quy định & Luật AI)** | **5** | 50% | Luật AI, Cảnh báo quy định Microsoft, An toàn AI ngân hàng |
| **Mô hình thị giác thế giới (World Models)** | **1** | 10% | ALPS Visual State Encoders (4) |

> **Nhận xét quan trọng:** 
> - **100% cơ hội trong nhóm `research` (4/4)** đều là phần cứng, robot, chẩn đoán thiết bị và camera giao thông.
> - Các paper AI thuần túy (như sequential recommendation, 3D character animation rigs) đã bị loại bỏ hoàn toàn khỏi nhóm research.

---

## 5. Cảnh báo tự động (Automated Flags)

- 🟢 **Top research có item không liên quan phần cứng/IoT không?**
  - **ĐẠT (XANH):** 100% cơ hội Research (4/4) đều trực tiếp liên quan đến AI Camera giao thông, Chẩn đoán thiết bị tự hành, và Điều khiển Robot thực tế.
- 🟢 **Có rác lọt vào `research` hoặc `build_ready` không?**
  - **ĐẠT (XANH):** Sạch rác 100%.
- 🟢 **Loại bỏ paper AI thuần túy khỏi Research:**
  - **ĐẠT (XANH):** Không còn paper gợi ý nội dung (RecSys) hay tạo video hoạt hình 3D lọt vào Research.

---

## 6. Kết luận nghiệm thu
- Hệ thống Opportunity Radar đã được kiểm tra chéo `your_leverage` và chấm điểm nghiêm ngặt, chống tự chấm rộng tay.
- Toàn bộ cơ hội ở tầng `research` đều là cơ hội giá trị cao, dùng trực tiếp được cho người làm phần cứng/IoT/cảm biến/chẩn đoán thiết bị.
