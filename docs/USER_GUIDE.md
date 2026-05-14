# TriLex — User Guide

---

## Mục lục

1. [Cài đặt chi tiết](#1-cài-đặt-chi-tiết)
2. [Setup QT dictionaries](#2-setup-qt-dictionaries)
3. [Setup API keys](#3-setup-api-keys)
4. [Tạo project mới](#4-tạo-project-mới)
5. [Dịch chương đầu tiên](#5-dịch-chương-đầu-tiên)
6. [Dùng Obsidian vault](#6-dùng-obsidian-vault)
7. [Quản lý glossary](#7-quản-lý-glossary)
8. [Export](#8-export)

---

## 1. Cài đặt chi tiết

### Yêu cầu hệ thống

- **Python 3.11+** (kiểm tra: `python --version`)
- **uv** package manager
- Windows 10/11, macOS, hoặc Linux
- Internet connection (chỉ cho LLM calls — QT pass hoạt động offline)

### Cài uv

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Cài TriLex

```bash
# 1. Clone repo
git clone <repo-url>
cd trilex

# 2. Cài tất cả dependencies (tự động tạo .venv)
uv sync

# 3. Verify cài thành công
uv run trilex --help
```

### Khởi tạo database

```bash
uv run trilex db init
```

Lệnh này tạo file `data/trilex.db` và chạy Alembic migrations.

---

## 2. Setup QT dictionaries

QT dictionaries là trái tim của TriLex — chúng quyết định tên nhân vật và thuật ngữ được dịch như thế nào.

### Folder dictionaries

Đặt files vào:
```
trilex/
└── data/
    └── dictionaries/
        ├── VietPhrase.txt    ← bắt buộc (1.14M+ entries)
        ├── Names.txt         ← nên có (tên riêng)
        └── LuatNhan.txt      ← tùy chọn (quy tắc nhân xưng)
```

> **Lưu ý**: TriLex đọc dictionaries ở runtime — không cần thêm vào git, không cần config thêm.

### Format dictionaries

TriLex dùng format QuickTranslator gốc (UTF-8, tab-separated):

```
# VietPhrase.txt
修仙	tu tiên
李青	Lý Thanh
...

# Names.txt
李	Lý
...
```

### Kiểm tra dictionaries đã load

```bash
uv run trilex dict status
```

Hoặc vào UI → **Dictionary** tab.

### Build automaton cache

Lần đầu chạy, TriLex tự build Aho-Corasick automaton và cache vào `data/cache/`. Quá trình này mất 10–30 giây tùy số entries. Các lần sau tải từ cache (< 1 giây).

Nếu muốn rebuild thủ công:
```bash
uv run trilex dict rebuild-cache
```

---

## 3. Setup API keys

### Lấy Gemini API key

1. Vào [Google AI Studio](https://aistudio.google.com/apikey)
2. Tạo API key mới
3. Copy key

### Tạo file `.env`

```bash
# Copy từ template
cp .env.example .env
```

Sửa `.env`:
```env
# Bắt buộc
GEMINI_API_KEY=AIzaSy...

# Tùy chọn
GEMINI_MODEL=gemini-2.5-flash
FALLBACK_KEY_1=AIzaSy...    # key dự phòng nếu key chính hết quota
FALLBACK_KEY_2=AIzaSy...
```

> **Bảo mật**: `.env` đã có trong `.gitignore`. **Không** commit file này lên git.

### Verify API key

Vào UI → **Settings** tab — sẽ hiển thị key đã mask (`AIzaSy...XXXXXX`) và model đang dùng.

Hoặc:
```bash
uv run trilex config show
```

---

## 4. Tạo project mới

Mỗi tiểu thuyết = 1 project trong TriLex.

### Qua UI

1. Mở UI: `uv run streamlit run src/trilex/ui/app.py`
2. Vào **Library** tab
3. Click **New Project**
4. Điền thông tin:
   - **Title**: Tên tiểu thuyết (hiển thị)
   - **Slug**: Tên ngắn, không dấu, không space (e.g. `tu-tien-chi-dao`) — dùng làm tên folder vault
   - **Source language**: ZH / EN / VN
   - **Target language**: VN / EN
   - **Genre**: `tu_tien` / `litrpg` / `vu_su` / `hien_dai`
5. Click **Create**

### Qua CLI

```bash
uv run trilex project create \
  --title "Tu Tiên Chi Đạo" \
  --slug "tu-tien-chi-dao" \
  --source zh \
  --target vn \
  --genre tu_tien
```

### Genre ảnh hưởng gì?

Genre quyết định **style pack** được dùng trong LLM prompt:
- `tu_tien`: văn phong tu tiên, dùng Hán-Việt, nghiêm trang
- `litrpg`: system status, game terminology, hiện đại
- `vu_su`: urban fantasy, mix hiện đại + huyền ảo
- `hien_dai`: ngôn ngữ thường nhật

---

## 5. Dịch chương đầu tiên

### Qua UI (khuyến nghị)

1. Vào **Translate** tab
2. Chọn project từ sidebar
3. Paste nội dung chương vào text area
4. Đặt **Chapter index** (số thứ tự, bắt đầu từ 0)
5. Chọn **Mode**:
   - **Convert**: dùng QT pass, không AI — nhanh, free
   - **Polish**: QT pass + AI — chất lượng cao nhất
   - **Side-by-side**: xuất 3 cột để review
6. Click **Translate Now**
7. Kết quả xuất hiện bên dưới + tự động lưu vào vault

### Qua CLI

```bash
# Convert (no AI)
uv run trilex translate \
  --project tu-tien-chi-dao \
  --chapter 0 \
  --mode convert \
  input.txt

# Polish (with AI)
uv run trilex translate \
  --project tu-tien-chi-dao \
  --chapter 0 \
  --mode polish \
  input.txt
```

### Resume nếu bị ngắt

Nếu đang dịch bị ngắt (mất điện, đóng laptop), mở lại và click **Translate Now** lại — pipeline tự detect từ đâu cần tiếp tục.

---

## 6. Dùng Obsidian vault

Mỗi chương sau khi dịch được lưu vào:
```
data/vault/
└── {project-slug}/
    ├── _index.md          # Tổng quan project
    ├── Chapter_0000.md    # Chương 0
    ├── Chapter_0001.md    # Chương 1
    └── ...
```

### Mở vault trong Obsidian

1. Mở Obsidian
2. **Open folder as vault** → chọn `data/vault/`
3. Obsidian tự index tất cả files

### Frontmatter của mỗi chương

```yaml
---
title: "Chapter 1"
project: tu-tien-chi-dao
chapter_index: 0
source_lang: zh
target_lang: vn
mode: polish
model: gemini-2.5-flash
created_at: 2026-05-14T10:00:00
---
```

### Edit trong Obsidian

Có thể edit trực tiếp trong Obsidian. Tuy nhiên, nếu retranslate cùng chapter index từ UI → sẽ **ghi đè** file trong vault. Đặt một bản backup trước khi retranslate nếu đã edit thủ công.

---

## 7. Quản lý glossary

Glossary = bảng thuật ngữ khoá per-novel. Khi một term bị lock, nó sẽ luôn được dịch đúng — cả trong QT pass lẫn LLM prompt.

### Xem glossary

UI → **Glossary** tab → chọn project.

### Thêm term thủ công

1. Vào **Glossary**
2. Click **Add term**
3. Điền:
   - **Source**: từ gốc (e.g. `李青`)
   - **Target**: dịch khoá (e.g. `Lý Thanh`)
   - **Type**: `character` / `place` / `skill` / `item` / `realm` / `other`
   - **Lock**: bật để enforce strict
4. Click **Save**

### Term được thêm tự động

Scout (Gemini Flash) tự extract entities từ mỗi chương dịch và đề xuất terms mới. Vào Glossary → **Suggestions** để approve/reject.

### Export glossary

```bash
uv run trilex glossary export --project tu-tien-chi-dao --format csv
```

---

## 8. Export

### Export một chương

UI → **Export** tab → chọn chapter → **Download plain text**

Hoặc:
```bash
uv run trilex export chapter \
  --project tu-tien-chi-dao \
  --chapter 5 \
  --format plain
```

### Export toàn bộ novel thành EPUB

UI → **Export** tab → **Export all chapters** → **EPUB**

Hoặc:
```bash
uv run trilex export epub \
  --project tu-tien-chi-dao \
  --output "Tu Tien Chi Dao.epub"
```

### Format output

| Format | Dùng cho |
|---|---|
| `plain` | Copy-paste lên tangthuvien, sstruyen, wikidich |
| `markdown` | Obsidian vault (đã auto-export) |
| `epub` | Đọc trên ebook reader |
| `side-by-side` | Review, chỉnh sửa thủ công |

---

## Phím tắt trong UI

| Action | Phím |
|---|---|
| Submit translate | `Ctrl + Enter` |
| Copy output | Nút **Copy** bên cạnh kết quả |
| Stop job đang chạy | Nút **Stop** trong Jobs tab |
