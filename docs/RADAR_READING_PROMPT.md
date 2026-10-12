# TASK: Tích hợp Giao diện Radar Reading & AI Summary Song ngữ vào Trend Radar Dashboard

## 1. Mục tiêu công việc
Nâng cấp giao diện Trend Radar (`docs/index.html`) đang chạy tại GitHub Pages (https://huytruong14.github.io/trend-radar/):
1. **Triển khai Slide-over Reading Drawer**: Cho phép người dùng click vào bất kỳ bài báo nào trên tất cả các tab (đặc biệt là tab News và AI/Tech) để đọc bài trực tiếp trong giao diện tập trung (Clean Reader View), không bị nhảy trang ra ngoài.
2. **Khối AI Executive Summary Song ngữ**: Hiển thị TL;DR, 3 bullet points điểm then chốt và nút gạt ngôn ngữ tức thì `[ 🇻🇳 VI | 🇬🇧 EN ]`.
3. **Khu vực "🔥 Sự kiện nổi bật trong ngày (Top Daily Stories)"**: Bổ sung phần điểm tin tiêu điểm ở đầu trang/chuyên mục với thiết kế thẻ Hero Card hiện đại theo phong cách Editorial.
4. **Giữ nguyên Theme & Data**: Tương thích hoàn toàn với cấu trúc dữ liệu hiện tại (`docs/data/manifest.json`, `docs/data/*.json`) và tông màu tối chuẩn của Trend Radar (`--bg: #07090e`, `--surface: #0e131f`).

---

## 2. Thông tin kỹ thuật & Files can thiệp
- **Thư mục làm việc**: `/Users/felixtruong/Projects/trend-radar`
- **File cần chỉnh sửa chính**: `docs/index.html`

---

## 3. Hướng dẫn thực hiện chi tiết

### Phần A: Bổ sung CSS vào thẻ `<style>` của `docs/index.html`
Thêm các class sau để hỗ trợ Reading Drawer, Hero Grid và AI Brief Card:

```css
/* --- RADAR READING DRAWER & EDITORIAL STYLES --- */
.reader-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  z-index: 999;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}
.reader-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.reader-drawer {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: min(720px, 100vw);
  background: #0e131f;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: -15px 0 40px rgba(0, 0, 0, 0.7);
  z-index: 1000;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}
.reader-overlay.open .reader-drawer {
  transform: translateX(0);
}

.drawer-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(14, 19, 31, 0.95);
}
.btn-close-drawer {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--dim);
  width: 34px;
  height: 34px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
}
.btn-close-drawer:hover {
  color: #fff;
  border-color: var(--dim);
  background: var(--surface-2);
}
.drawer-link-orig {
  color: var(--cyan);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid rgba(6, 182, 212, 0.3);
  background: rgba(6, 182, 212, 0.08);
  transition: all 0.2s;
}
.drawer-link-orig:hover {
  background: rgba(6, 182, 212, 0.18);
}

.drawer-scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px;
}
.drawer-meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 12px;
}
.drawer-badge {
  background: rgba(16, 185, 129, 0.15);
  color: var(--accent);
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 11px;
}
.drawer-title {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.35;
  color: #fff;
  margin-bottom: 24px;
}

/* AI Executive Summary Card */
.ai-brief-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(6, 182, 212, 0.08) 100%);
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 28px;
}
.ai-brief-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.ai-badge {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 700;
  color: #818cf8;
  display: flex;
  align-items: center;
  gap: 6px;
}
.ai-model-tag {
  font-size: 11px;
  color: var(--dim);
}
.ai-tldr-text {
  font-size: 15px;
  font-weight: 500;
  color: #f8fafc;
  line-height: 1.6;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
}
.ai-points-title {
  font-size: 12px;
  text-transform: uppercase;
  color: var(--dim);
  margin-bottom: 8px;
  font-weight: 600;
}
.ai-points-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-points-list li {
  position: relative;
  padding-left: 18px;
  font-size: 14px;
  color: var(--text);
  line-height: 1.5;
}
.ai-points-list li::before {
  content: "•";
  position: absolute;
  left: 4px;
  color: var(--cyan);
  font-size: 18px;
  top: -2px;
}

/* Reader Typography */
.reader-content-body {
  font-size: 17px;
  line-height: 1.8;
  color: #cbd5e1;
  font-family: Georgia, -apple-system, serif;
}
.reader-content-body p {
  margin-bottom: 18px;
}

/* Bilingual Switcher */
.lang-toggle-pill {
  display: inline-flex;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 2px;
}
.lang-toggle-btn {
  background: transparent;
  border: none;
  color: var(--dim);
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s;
}
.lang-toggle-btn.active {
  background: var(--accent);
  color: #07090e;
}

/* Hero Daily Grid */
.hero-daily-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}
.hero-story-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--R);
  padding: 20px;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.hero-story-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
```

---

### Phần B: Bổ sung HTML Component vào `docs/index.html`

1. **Thêm nút gạt ngôn ngữ tại `.hdr-right` (Header)**:
```html
<div class="lang-toggle-pill">
  <button class="lang-toggle-btn active" id="btn-lang-vi" onclick="setGlobalLang('vi')">🇻🇳 VI</button>
  <button class="lang-toggle-btn" id="btn-lang-en" onclick="setGlobalLang('en')">🇬🇧 EN</button>
</div>
```

2. **Thêm Reading Drawer Markup vào cuối trang (ngay trước thẻ đóng `</body>`)**:
```html
<div class="reader-overlay" id="reader-overlay" onclick="closeReaderDrawer(event)">
  <aside class="reader-drawer" onclick="event.stopPropagation()">
    <div class="drawer-header">
      <div style="display: flex; align-items: center; gap: 10px;">
        <button class="btn-close-drawer" onclick="closeReaderDrawer()" title="Đóng (Esc)">✕</button>
        <span id="drawer-source-badge" class="drawer-badge">SOURCE</span>
      </div>
      <div style="display: flex; align-items: center; gap: 12px;">
        <div class="lang-toggle-pill">
          <button id="drawer-btn-vi" class="lang-toggle-btn active" onclick="setDrawerLang('vi')">VI</button>
          <button id="drawer-btn-en" class="lang-toggle-btn" onclick="setDrawerLang('en')">EN</button>
        </div>
        <a id="drawer-orig-link" href="#" target="_blank" class="drawer-link-orig">Mở bài gốc ↗</a>
      </div>
    </div>

    <div class="drawer-scroll-body">
      <div class="drawer-meta-row">
        <span id="drawer-cat-tag" class="drawer-badge" style="background: rgba(255,255,255,0.08); color: var(--text);">NEWS</span>
        <span id="drawer-pub-date">Vừa xong</span>
      </div>
      <h1 id="drawer-article-title" class="drawer-title">Tiêu đề bài viết</h1>

      <!-- AI Summary -->
      <div class="ai-brief-card" id="drawer-ai-card">
        <div class="ai-brief-header">
          <div class="ai-badge">✨ AI Executive Brief</div>
          <div class="ai-model-tag">Gemini Flash</div>
        </div>
        <div id="drawer-ai-tldr" class="ai-tldr-text">Đang tải tóm tắt bài viết...</div>
        <div class="ai-points-title">Điểm then chốt (Key Takeaways):</div>
        <ul id="drawer-ai-points" class="ai-points-list"></ul>
      </div>

      <!-- Clean Article Content -->
      <div class="reader-content-body" id="drawer-article-body">
        <p>Nội dung chi tiết bài viết...</p>
      </div>
    </div>
  </aside>
</div>
```

---

### Phần C: Cập nhật JavaScript trong `docs/index.html`

Cập nhật hàm render bài viết và bổ sung các hàm tương tác sau:

```javascript
let currentAppLang = 'vi';
let activeReaderArticle = null;

// Hàm mở Drawer
function openReaderDrawer(item) {
  if (!item) return;
  activeReaderArticle = item;
  updateDrawerUI();
  
  const overlay = document.getElementById('reader-overlay');
  if (overlay) {
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

// Hàm đóng Drawer
function closeReaderDrawer(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('btn-close-drawer')) return;
  const overlay = document.getElementById('reader-overlay');
  if (overlay) {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }
}

// Cập nhật nội dung trong Drawer theo bài viết và ngôn ngữ
function updateDrawerUI() {
  if (!activeReaderArticle) return;
  const a = activeReaderArticle;
  const isVi = currentAppLang === 'vi';

  // Fallback thông tin nếu chưa có ai_summary song ngữ
  const title = (isVi && a.title_vi) ? a.title_vi : a.title;
  const tldr = a.ai_summary 
    ? (isVi ? (a.ai_summary.vi?.tldr || a.ai_summary.tldr) : (a.ai_summary.en?.tldr || a.ai_summary.tldr))
    : (a.summary || a.description || "Bài viết từ nguồn tin sớm. Bấm vào bài gốc để xem nội dung đầy đủ.");
  
  const points = a.ai_summary 
    ? (isVi ? (a.ai_summary.vi?.key_points || a.ai_summary.points) : (a.ai_summary.en?.key_points || a.ai_summary.points))
    : [];

  const bodyContent = (isVi && a.body_vi) ? a.body_vi : (a.content || a.summary || a.description || "");

  document.getElementById('drawer-article-title').innerText = title;
  document.getElementById('drawer-ai-tldr').innerText = tldr;
  document.getElementById('drawer-source-badge').innerText = a.source || 'FEED';
  document.getElementById('drawer-orig-link').href = a.url || a.link || '#';
  document.getElementById('drawer-pub-date').innerText = a.published || a.time || '';
  
  // Render points
  const pointsList = document.getElementById('drawer-ai-points');
  if (points && points.length > 0) {
    pointsList.innerHTML = points.map(p => `<li>${p}</li>`).join('');
    document.getElementById('drawer-ai-card').style.display = 'block';
  } else {
    pointsList.innerHTML = `<li>Cập nhật từ nguồn tin ${a.source || 'gốc'}.</li>`;
  }

  // Render article body
  const bodyEl = document.getElementById('drawer-article-body');
  if (bodyContent.startsWith('<p>')) {
    bodyEl.innerHTML = bodyContent;
  } else {
    bodyEl.innerHTML = `<p>${bodyContent}</p>`;
  }

  // Update Drawer lang buttons
  document.getElementById('drawer-btn-vi').className = isVi ? 'lang-toggle-btn active' : 'lang-toggle-btn';
  document.getElementById('drawer-btn-en').className = !isVi ? 'lang-toggle-btn active' : 'lang-toggle-btn';
}

function setGlobalLang(lang) {
  currentAppLang = lang;
  const isVi = lang === 'vi';
  document.getElementById('btn-lang-vi').className = isVi ? 'lang-toggle-btn active' : 'lang-toggle-btn';
  document.getElementById('btn-lang-en').className = !isVi ? 'lang-toggle-btn active' : 'lang-toggle-btn';
  if (activeReaderArticle) updateDrawerUI();
}

function setDrawerLang(lang) {
  setGlobalLang(lang);
}

// Bắt phím Escape để đóng drawer
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeReaderDrawer();
});
```

---

## 4. Xác minh sau khi triển khai
1. Chạy máy chủ kiểm tra local:
   ```bash
   python -m http.server 8000 --directory docs
   ```
2. Mở trình duyệt `http://localhost:8000`:
   - Click vào bất kỳ bài báo nào trên tab `News (theo từ khóa)` và các tab còn lại.
   - Kiểm tra Drawer trượt ra từ bên phải mượt mà, typography thoáng đãng, dễ đọc.
   - Thử bấm nút chuyển đổi ngôn ngữ [VI / EN] ở góc trên và trong Drawer.
   - Bấm phím `Escape` để kiểm tra thao tác đóng Drawer.
