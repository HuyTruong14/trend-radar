# UI Refactor Prompt — Trend Radar Dashboard

> File: `docs/index.html` (7228 dòng, single-page)
> Mục tiêu: Tinh gọn giao diện, giảm visual clutter, cải thiện UX trên cả desktop và mobile.
> Không thay đổi logic fetch data hay scoring — chỉ refactor phần hiển thị.

---

## 1. Gom header buttons vào dropdown menu

### Hiện trạng

Header (`.header`, dòng ~3225–3266) chứa 9 elements ngang hàng:
- Sync status pill
- 4 tool buttons trong `.header-tools-group`: AI Disruption, Repo Combos, Tech Glossary, Bookmarks
- 3 link buttons trong `.header-links-group`: Báo cáo tuần, Workflow Hub, Skill Funnel
- Theme toggle

Trên mobile, các pill wrap thành 3–4 dòng, chiếm ~40% viewport height. Header mất vai trò navigation bar, trở thành toolbar.

### Yêu cầu

**Header chỉ giữ lại 4 thứ ngang hàng:**
1. Logo + title (giữ nguyên `.header-brand`)
2. Sync status pill (giữ nguyên `.sync-status`)
3. Theme toggle (giữ nguyên `.theme-toggle-btn`)
4. Nút "Tools ▾" — một button duy nhất, click mở dropdown menu

**Dropdown menu chứa tất cả tool buttons + external links:**
```
┌─────────────────────────────┐
│ ⚡ AI Disruption (30)       │
│ 💡 Repo Combos (5)          │
│ 🔬 Tech Glossary            │
│ 📌 Bookmarks (1)            │
│ ─────────────────────────── │
│ 📊 Báo cáo tuần        ↗   │
│ ⚡ Workflow Hub          ↗   │
│ 🎯 Skill Funnel         ↗   │
└─────────────────────────────┘
```

**Quy tắc:**
- Dropdown xuất hiện dưới nút "Tools", align phải, z-index trên sticky header
- Click ngoài vùng dropdown → đóng
- Mỗi item trong dropdown giữ nguyên `onclick` handler hiện tại (ví dụ `openDisruptionModal()`)
- External links (Báo cáo tuần, Workflow Hub, Skill Funnel) có icon ↗ và `target="_blank"`
- Badge count (30, 5, 1) vẫn hiển thị inline bên phải mỗi item
- Dùng CSS variables hiện có (`--bg-card`, `--border`, `--fg`, `--fg-dim`) cho dropdown styling
- Border-radius: `var(--radius-md)`, shadow: `var(--shadow-elevated)`
- Mobile: dropdown full-width, padding thoải mái hơn (touch target ≥ 44px)

**CSS cần xóa sau refactor:**
- `.header-tools-group` và tất cả child styles
- `.header-links-group` và tất cả child styles
- `.workflow-hub-btn`, `.funnel-nav-btn`, `.weekly-nav-btn` và hover states
- `.disruption-nav-btn`, `.combos-nav-btn`, `.glossary-nav-btn`, `.bookmarks-nav-btn` và hover states

**CSS cần thêm:**
- `.header-tools-dropdown` — container dropdown
- `.header-tools-trigger` — nút "Tools ▾"
- `.dropdown-item` — mỗi item trong dropdown
- `.dropdown-divider` — separator giữa tools và external links

---

## 2. Chuyển modals thành tabs hoặc trang riêng

### Hiện trạng

Dashboard hiện có **5 full-screen modal overlays** (dòng ~3415–3568):
1. Daily Digest Modal (`#dailyDigestModal`)
2. Bookmarks Modal (`#bookmarksModal`)
3. Tech Glossary Modal (`#glossaryModal`)
4. Repo Combos Modal (`#combosModal`)
5. AI Disruption Radar Modal (`#disruptionModal`)

Mỗi modal là một trang con hoàn chỉnh: header + filter bar + scrollable list + footer. Trên mobile, modal chiếm toàn màn hình giống trang mới, nhưng không có URL riêng (không bookmark/share được), không có browser back button.

### Yêu cầu

**Giữ lại dạng modal cho:** Daily Digest (#1) — vì nội dung ngắn, xem nhanh rồi đóng.

**Chuyển thành trang HTML riêng cho 4 tính năng lớn:**

| Modal hiện tại | File mới | Lý do |
|---|---|---|
| Bookmarks | `bookmarks.html` | Có filter phức tạp (5 trạng thái), export JSON, quản lý nhiều mục |
| Tech Glossary | `glossary.html` | 3 sub-tabs (Terms, Timeline, New terms), 62+ items, search |
| Repo Combos | `combos.html` | 2 sub-tabs (Combos, Trending), dữ liệu dày |
| AI Disruption | `disruption.html` | 5 sub-tabs, 30+ skills, matrix view phức tạp |

**Quy tắc cho mỗi trang mới:**
- Copy shared styles từ `index.html` (design tokens, reset, base typography, card styles, badge styles)
- Giữ nguyên look & feel: dark theme default, glassmorphism cards, same fonts
- Header đơn giản: logo nhỏ + tiêu đề trang + nút "← Về Dashboard" (link về `index.html`)
- Toàn bộ logic render (JS) di chuyển nguyên vẹn từ modal handler sang page-level script
- Data fetching giữ nguyên: đọc từ `data/*.json` tương đối
- Các filter/tab/search hoạt động chính xác như trong modal cũ
- Theme toggle hoạt động độc lập trên mỗi trang (đọc/ghi `localStorage` key `theme`)

**Cập nhật `index.html`:**
- Xóa toàn bộ HTML block của 4 modals đã chuyển
- Xóa CSS classes liên quan mà không còn dùng (`.bookmarks-modal-box`, `.bookmarks-filter-bar`, `.bm-filter-btn`, `.bookmarks-list`, `.bookmarks-footer-bar`, tất cả glossary-specific styles, combos-specific styles, disruption-specific styles)
- Xóa JS functions liên quan (`openBookmarksModal()`, `closeBookmarksModal()`, `handleBookmarksBackdropClick()`, `setBookmarkFilter()`, tương tự cho glossary/combos/disruption)
- Thay handler `onclick="openBookmarksModal()"` trong dropdown (từ refactor #1) bằng `window.location.href = 'bookmarks.html'` hoặc tốt hơn: dùng `<a href="bookmarks.html">` trực tiếp

**Kết quả dự kiến:**
- `index.html` giảm từ ~7228 dòng xuống ~4500–5000 dòng
- Mỗi trang mới ~500–800 dòng (compact hơn vì không embedded trong overlay)
- User có thể bookmark/share trực tiếp URL từng tính năng
- Browser back button hoạt động tự nhiên

---

## 3. Compact cards mặc định cho Opportunity Radar

### Hiện trạng

Mỗi "ACT NOW (BUILD-READY)" card trong Opportunity Radar section (`.act-now-card`, dòng ~1241–1392) chiếm ~200–250px chiều cao, gồm:
- Badge row: "ACT NOW (BUILD-READY)" pill + "Cơ hội điểm 9/9" + score circle
- Title (18px bold, 1–2 dòng)
- Summary paragraph (14px, 2–4 dòng tiếng Việt)
- Score breakdown chips (3 layers: Bền / AI hỗ trợ / Đòn bẩy)
- Action box: prompt text + "Đánh dấu đã đi hỏi khách" button

Khi có 4–5 items điểm 9/9, user phải scroll rất dài chỉ để scan danh sách. Thông tin detail ít khi cần đọc hết cho mọi item cùng lúc.

### Yêu cầu

**Compact mode (mặc định):**
```
┌──────────────────────────────────────────────────────────┐
│ 9/9  ishiniayodya610/Z6-SE-351                    ▸ 📡  │
│      AI-driven smart aquaculture...  [rising] [2 src]    │
└──────────────────────────────────────────────────────────┘
```

Mỗi card compact chỉ 1–2 dòng, ~56–64px height:
- **Dòng 1:** Score badge (nhỏ, inline) + Title (truncate ellipsis nếu dài) + expand chevron (▸) + bookmark icon
- **Dòng 2:** Summary truncate 1 dòng + velocity badge + source count pill

**Expanded mode (click vào card):**
- Card mở rộng smooth (CSS transition `max-height`) hiển thị đầy đủ:
  - Full summary paragraph
  - Score breakdown (Bền / AI hỗ trợ / Đòn bẩy) với explanation
  - Signal type chips
  - Action box + "Đánh dấu đã đi hỏi khách" button
  - Source links
- Chevron xoay từ ▸ thành ▾
- Chỉ 1 card expanded tại một thời điểm (accordion behavior) — click card khác tự đóng card đang mở

**Áp dụng cho tất cả tiers, không chỉ ACT NOW:**
- ACT NOW (score 9) — compact row, left border `var(--hot)` (cam)
- Research (score 7–8) — compact row, left border `var(--score-mid)` (vàng)
- Watch (score ≤6) — compact row, left border `var(--score-low)` (xám)

**Toggle view mode:**
- Thêm 1 nút nhỏ ở section header: "☰ Compact" / "▤ Expanded"
- Click toggle giữa compact (accordion) và expanded (tất cả mở sẵn như hiện tại)
- Lưu preference vào `localStorage` key `opp-view-mode`

**CSS guidance:**
- `.opp-card-compact` — card wrapper, `overflow: hidden`, `cursor: pointer`
- `.opp-card-compact .opp-card-preview` — dòng 1+2 luôn visible
- `.opp-card-compact .opp-card-detail` — phần detail, `max-height: 0; overflow: hidden; transition: max-height 0.3s ease`
- `.opp-card-compact.expanded .opp-card-detail` — `max-height: 600px` (hoặc dùng JS set exact height)
- `.opp-card-compact.expanded .opp-chevron` — `transform: rotate(90deg)`

**Kết quả dự kiến:**
- 5 items score 9/9: từ ~1000px scroll xuống ~320px (giảm 68%)
- User scan nhanh toàn bộ pipeline, click vào item quan tâm để xem detail
- Vẫn giữ nguyên tất cả thông tin — chỉ thay đổi cách hiển thị mặc định

---

## Thứ tự thực hiện đề xuất

1. **Refactor #3 (Compact cards)** — thay đổi nhỏ nhất, impact UX lớn nhất, không ảnh hưởng cấu trúc file
2. **Refactor #1 (Header dropdown)** — thay đổi vừa, giảm clutter ngay lập tức
3. **Refactor #2 (Tách modals)** — thay đổi lớn nhất, cần tạo 4 file mới + refactor JS, nhưng giảm complexity đáng kể cho long-term maintenance

---

## Lưu ý chung

- **Không thay đổi data flow:** Tất cả JSON data fetching (`data/news.json`, `data/opportunities.json`, v.v.) giữ nguyên
- **Không thay đổi scoring/filtering logic:** JS business logic (filter, sort, search) giữ nguyên, chỉ di chuyển sang file mới
- **Giữ nguyên theme system:** CSS variables `:root` + `[data-theme="light"]` giữ nguyên
- **Backward compatible URLs:** `index.html` vẫn là entry point chính, các trang mới là sibling files
- **Test trên mobile (375px) sau mỗi refactor** — header dropdown và compact cards cần hoạt động tốt trên touch
