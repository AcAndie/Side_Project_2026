# LiTTrans v5.3 — Pipeline Dịch Truyện LitRPG / Tu Tiên

Dịch tự động truyện LitRPG / Tu Tiên từ tiếng Anh sang tiếng Việt bằng **Gemini AI** hoặc **Claude (Anthropic)**.
Giữ nhất quán tên nhân vật, xưng hô, thuật ngữ và kỹ năng xuyên suốt hàng trăm chương.

Có hai cách dùng: **Web UI** (giao diện trình duyệt, dễ dùng hơn) và **CLI** (dòng lệnh).

---

## Mục lục

1. [Trước khi bắt đầu](#1-trước-khi-bắt-đầu)
2. [Lấy API Key](#2-lấy-api-key)
3. [Cài đặt — Cách 1: Chạy trực tiếp](#3-cài-đặt--cách-1-chạy-trực-tiếp-trên-máy)
4. [Cài đặt — Cách 2: Docker](#4-cài-đặt--cách-2-docker-khuyến-nghị-cho-người-mới)
5. [Cấu hình .env](#5-cấu-hình-env)
6. [Sử dụng Web UI](#6-sử-dụng-web-ui)
7. [Sử dụng CLI](#7-sử-dụng-cli)
8. [Bible System](#8-bible-system)
9. [Tính năng nổi bật v5.3](#9-tính-năng-nổi-bật-v53)
10. [Cấu trúc thư mục](#10-cấu-trúc-thư-mục)
11. [Pipeline hoạt động như thế nào](#11-pipeline-hoạt-động-như-thế-nào)
12. [Xử lý sự cố thường gặp](#12-xử-lý-sự-cố-thường-gặp)
13. [Tất cả tùy chọn cấu hình](#13-tất-cả-tùy-chọn-cấu-hình)

---

## 1. Trước khi bắt đầu

### Bạn cần cài gì?

**Cách 1 — Chạy trực tiếp:** Cần Python 3.11 trở lên.

**Cách 2 — Docker:** Cần Docker Desktop. Không cần cài Python.

> **Nếu bạn không chắc nên chọn cách nào:** Hãy dùng Docker.

### Kiểm tra đã có Python chưa (Cách 1)

```bash
python --version
```

Nếu thấy `Python 3.11.x` hoặc cao hơn → OK.

### Kiểm tra đã có Docker chưa (Cách 2)

```bash
docker --version
```

Nếu báo lỗi → Tải Docker Desktop tại [docker.com](https://www.docker.com/products/docker-desktop/).

---

## 2. Lấy API Key

### Gemini API Key (bắt buộc)

**Bước 1:** Truy cập [aistudio.google.com](https://aistudio.google.com)

**Bước 2:** Đăng nhập bằng tài khoản Google

**Bước 3:** Click **"Get API key"** → **"Create API key"**

**Bước 4:** Copy key vừa tạo (dạng `AIzaSy...`)

> **Giới hạn miễn phí:** Gemini Flash cho phép khoảng 1.000 request/ngày miễn phí.

### Anthropic API Key (tùy chọn — cho Dual-Model)

**Bước 1:** Truy cập [console.anthropic.com](https://console.anthropic.com)

**Bước 2:** Vào **API Keys** → **Create Key**

**Bước 3:** Copy key (dạng `sk-ant-...`) và thêm vào `.env`

---

## 3. Cài đặt — Cách 1: Chạy trực tiếp trên máy

```bash
git clone <repo-url>
cd littrans

# Tạo môi trường ảo
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell

# Cài thư viện
pip install -e .
pip install ".[fast]"            # pyahocorasick — tăng tốc filter 10x (khuyến nghị)
pip install streamlit pandas     # nếu dùng Web UI
pip install anthropic            # nếu dùng Claude

# Tạo file cấu hình
cp .env.example .env
# Mở .env và điền GEMINI_API_KEY
```

---

## 4. Cài đặt — Cách 2: Docker

```bash
git clone <repo-url>
cd littrans

make init     # tạo thư mục + .env
# Điền GEMINI_API_KEY vào .env

make build    # build image (~3-5 phút lần đầu)
make ui       # khởi động Web UI
```

Mở trình duyệt: **http://localhost:8501**

---

## 5. Cấu hình .env

```env
# ── BẮT BUỘC ──────────────────────────────────────────────────────
GEMINI_API_KEY=AIzaSy...

# ── KEY DỰ PHÒNG (khuyến nghị nếu dịch nhiều) ─────────────────────
FALLBACK_KEY_1=AIzaSy...
FALLBACK_KEY_2=AIzaSy...

# ── MODEL DỊCH THUẬT ──────────────────────────────────────────────
TRANSLATION_PROVIDER=gemini        # gemini | anthropic
TRANSLATION_MODEL=                 # để trống = dùng mặc định
# ANTHROPIC_API_KEY=sk-ant-...     # cần nếu dùng anthropic

# ── GEMINI MODEL ──────────────────────────────────────────────────
GEMINI_MODEL=gemini-2.5-flash

# ── TỐC ĐỘ ────────────────────────────────────────────────────────
SUCCESS_SLEEP=30
RATE_LIMIT_SLEEP=60

# ── BIBLE SYSTEM ──────────────────────────────────────────────────
BIBLE_MODE=false                   # true để dùng Bible khi dịch
BIBLE_SCAN_DEPTH=standard          # quick | standard | deep
BIBLE_SCAN_BATCH=5
BIBLE_SCAN_SLEEP=10
BIBLE_CROSS_REF=true
BIBLE_DIR=data/bible
```

---

## 6. Sử dụng Web UI

```bash
python run_ui.py        # chạy trực tiếp
make ui                 # chạy qua Docker
```

Mở trình duyệt: **http://localhost:8501**

### Các tab trong Web UI

| Tab | Chức năng |
|---|---|
| **📄 Dịch** | Upload file, chạy pipeline, xem log real-time |
| **🔍 Xem chương** | Đọc song song EN/VN, tải xuống, dịch lại |
| **👤 Nhân vật** | Xem profile, xưng hô, EPS, emotion state |
| **📚 Từ điển** | Xem/tìm glossary, xác nhận thuật ngữ Scout |
| **📊 Thống kê** | Tiến độ dịch, biểu đồ, số liệu |
| **📖 Bible** | Overview, Database, WorldBuilding, Lore, Export |
| **⚙️ Cài đặt** | Toàn bộ cấu hình, lưu vào .env |

---

## 7. Sử dụng CLI

### Lệnh cơ bản

```bash
# Dịch tất cả chương chưa dịch
python main.py translate

# Dịch lại 1 chương
python main.py retranslate 5
python main.py retranslate "chapter_005"

# Xác nhận thuật ngữ Scout đề xuất
python main.py clean glossary

# Merge nhân vật mới
python main.py clean characters --action merge

# Sửa lỗi tên vi phạm Name Lock
python main.py fix-names

# Thống kê
python main.py stats
```

### Dual-Model — override qua CLI

```bash
python main.py translate --provider anthropic --model claude-sonnet-4-6
python main.py retranslate 5 --provider gemini --model gemini-2.5-pro
```

### Shortcut với make (Docker)

```bash
make translate
make CHAPTER=5 retranslate
make stats
make clean-glossary
make merge-chars
make fix-names
make shell
```

---

## 8. Bible System

Bible System xây dựng **knowledge base** từ toàn bộ truyện, lưu trữ nhân vật, kỹ năng, địa danh, tóm tắt chương, tuyến truyện... Khi `BIBLE_MODE=true`, pipeline dùng Bible thay cho các file Manager riêng lẻ.

### Workflow cơ bản

```
1. Scan chương → 2. Consolidate → 3. Dịch với Bible context
```

### CLI Commands

```bash
# Scan chương mới (chỉ chương chưa scan)
python main.py bible scan

# Scan với depth khác nhau
python main.py bible scan --depth quick      # nhanh, chỉ entities
python main.py bible scan --depth standard   # đầy đủ (mặc định)
python main.py bible scan --depth deep       # kỹ nhất + verification

# Scan lại toàn bộ (kể cả đã scan)
python main.py bible scan --all --force

# Thống kê
python main.py bible stats

# Tìm kiếm entity
python main.py bible query "Lý Thanh Vân"
python main.py bible query "Arthur" --type character

# Hỏi AI về nội dung truyện
python main.py bible ask "Ai là kẻ thù chính của nhân vật?"

# Consolidate staging thủ công (không cần scan)
python main.py bible consolidate

# Chạy cross-reference check
python main.py bible crossref

# Xuất báo cáo
python main.py bible export --format markdown
python main.py bible export --format json
python main.py bible export --format timeline
python main.py bible export --format characters
python main.py bible export --format consistency

# Rebuild index (khi index bị corrupt)
python main.py bible rebuild-index
```

### Scan depth so sánh

| Depth | Tốc độ | Nội dung | Dùng khi |
|---|---|---|---|
| `quick` | Nhanh nhất | Chỉ entities (nhân vật, kỹ năng, địa danh) | Lần đầu scan nhanh để có data |
| `standard` | Trung bình | Entities + WorldBuilding + Lore đầy đủ | Mặc định, dùng hàng ngày |
| `deep` | Chậm nhất | Standard + verification call để loại duplicate | Khi cần data chất lượng cao |

### Bật Bible Mode khi dịch

Thêm vào `.env`:

```env
BIBLE_MODE=true
```

Khi bật, pipeline sẽ:
- Dùng BibleStore thay vì filter_glossary/characters riêng lẻ
- Inject tóm tắt chương gần nhất và tuyến truyện đang mở vào prompt
- Cập nhật Bible sau mỗi chương dịch xong

### Cấu trúc dữ liệu Bible

```
data/bible/
  meta.json                    ← metadata, scan progress
  database/
    characters.json            ← nhân vật
    items.json                 ← vật phẩm
    locations.json             ← địa danh
    skills.json                ← kỹ năng
    factions.json              ← tổ chức
    concepts.json              ← khái niệm
    index.json                 ← search index
  worldbuilding.json           ← hệ thống tu luyện, quy luật thế giới
  main_lore.json               ← tóm tắt chương, plot threads, revelations
  staging/
    stage_chapter_001.json     ← raw scan output chờ consolidate
```

---

## 9. Tính năng nổi bật v5.3

### Pipeline 3-Call

Mỗi chương được xử lý qua 3 bước:

1. **Pre-call** — Phân tích chương, tạo Chapter Map (tên/skill/pronoun đang active)
2. **Trans-call** — Dịch với full context (Glossary + Characters + Chapter Map + Bible)
3. **Post-processor (14-pass)** — Code cleanup thuần regex, không tốn API
4. **Post-call** — AI review chất lượng + extract metadata (nhân vật mới, thuật ngữ mới)

### EPS — Emotional Proximity Signal

Theo dõi mức độ thân mật giữa các cặp nhân vật (1–5) để điều chỉnh văn phong xưng hô:

| Mức | Nhãn | Ý nghĩa |
|---|---|---|
| 1 | FORMAL | Lạnh lùng, trang trọng |
| 2 | NEUTRAL | Mặc định |
| 3 | FRIENDLY | Thân thiện, câu ngắn hơn |
| 4 | CLOSE | Rất thân, nickname ok |
| 5 | INTIMATE | Ngôn ngữ riêng tư |

### Dual-Model

Dùng Claude (Anthropic) làm model dịch chính, Gemini cho Scout/Pre/Post:

```env
TRANSLATION_PROVIDER=anthropic
TRANSLATION_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

| Provider | Model | Ghi chú |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | Nhanh, rẻ (khuyến nghị) |
| `gemini` | `gemini-2.5-pro` | Chất lượng cao nhất |
| `anthropic` | `claude-sonnet-4-6` | Cân bằng |
| `anthropic` | `claude-opus-4-6` | Chất lượng cao nhất của Claude |
| `anthropic` | `claude-haiku-4-5-20251001` | Nhanh nhất |

### Scout Glossary Suggest

Scout AI tự động phát hiện thuật ngữ mới chưa có trong Glossary và đề xuất vào Staging. Xác nhận bằng `python main.py clean glossary`.

---

## 10. Cấu trúc thư mục

```
littrans/
│
├── main.py                    # Entry point CLI
├── run_ui.py                  # Entry point Web UI
├── .env                       # Cấu hình (tạo từ .env.example)
├── .env.example               # Template
│
├── src/littrans/
│   ├── engine/
│   │   ├── pipeline.py        # Orchestrator chính
│   │   ├── scout.py           # Scout AI
│   │   ├── pre_processor.py   # Pre-call: Chapter Map
│   │   ├── post_analyzer.py   # Post-call: review + metadata
│   │   ├── prompt_builder.py  # Build system prompt
│   │   └── quality_guard.py   # Kiểm tra chất lượng (7 tiêu chí)
│   ├── bible/
│   │   ├── bible_store.py     # Data layer: đọc/ghi 3 tầng Bible
│   │   ├── bible_scanner.py   # Scan engine: inputs/ → staging
│   │   ├── bible_consolidator.py  # Merge staging → database
│   │   ├── bible_prompt_builder.py # Build prompt từ Bible
│   │   ├── bible_exporter.py  # Export markdown/json/timeline
│   │   ├── bible_query.py     # Query: search + LLM Q&A
│   │   ├── bible_cli.py       # CLI commands: bible scan/stats/...
│   │   ├── cross_reference.py # Kiểm tra mâu thuẫn cốt truyện
│   │   ├── pipeline_bible_patch.py  # Kết nối Bible ↔ Pipeline
│   │   └── schemas.py         # Pydantic schemas
│   ├── managers/
│   │   ├── glossary.py        # Glossary + Aho-Corasick filter
│   │   ├── characters.py      # Tiered Characters + EPS
│   │   ├── skills.py          # Skills + evolution chain
│   │   ├── name_lock.py       # Name Lock: chốt tên nhất quán
│   │   └── memory.py          # Arc Memory + Context Notes
│   ├── llm/
│   │   ├── client.py          # Gemini + Anthropic client
│   │   ├── schemas.py         # Pydantic schemas (EPS, ...)
│   │   └── token_budget.py    # Smart context truncation
│   ├── tools/
│   │   ├── clean_glossary.py  # Phân loại thuật ngữ Staging
│   │   ├── clean_characters.py # Quản lý Character Profile
│   │   └── fix_names.py       # Sửa lỗi Name Lock
│   ├── utils/
│   │   ├── io_utils.py        # Atomic write, load/save JSON
│   │   ├── text_normalizer.py # Chuẩn hóa raw text
│   │   ├── post_processor.py  # 14-pass code cleanup
│   │   └── data_versioning.py # Backup & versioning
│   └── config/
│       └── settings.py        # Đọc cấu hình từ .env
│
├── prompts/
│   ├── system_agent.md        # Hướng dẫn dịch chính
│   ├── character_profile.md   # Hướng dẫn lập profile
│   └── bible_scan.md          # Prompt cho BibleScanner
│
├── inputs/                    # ← Đặt file chương gốc vào đây
├── outputs/                   # Bản dịch (*_VN.txt)
└── data/
    ├── glossary/              # Glossary files + Staging_Terms.md
    ├── characters/            # Characters_Active/Archive/Staging
    ├── skills/                # Skills.json
    ├── memory/                # Arc_Memory.md, Context_Notes.md
    └── bible/                 # Bible System data (xem mục 8)
```

---

## 11. Pipeline hoạt động như thế nào

### Scout AI (mỗi N chương)

Chạy trước khi dịch, làm 4 việc:

1. **Context Notes** — Ghi chú mạch truyện, xưng hô đang active
2. **Arc Memory** — Tóm tắt sự kiện, append vào bộ nhớ dài hạn
3. **Emotion Tracker** — Cập nhật trạng thái cảm xúc nhân vật
4. **Glossary Suggest** — Phát hiện thuật ngữ mới → Staging

### Luồng dịch 1 chương

```
Pre-call (Chapter Map)
    ↓
Build System Prompt
  [Normal mode] Glossary + Characters + Arc Memory + Name Lock
  [Bible mode]  BibleStore entities + recent lore + worldbuilding
    ↓
Token estimate warning (nếu > 70% budget)
    ↓
Trans-call (dịch)
    ↓
Post-processor 14-pass (code cleanup)
    ↓
Quality Guard (7 tiêu chí cơ học)
    ↓ retry nếu lỗi
Post-call (AI review + extract metadata)
    ↓ retry Trans-call nếu lỗi dịch thuật
Name Lock validate
    ↓
Ghi file + Update data (Glossary, Characters, Skills, Bible)
```

### Bible Scan flow

```
inputs/*.txt
    ↓
BibleScanner.scan_one()
  → normalize text
  → inject known entities (tránh duplicate)
  → call_gemini_json() → ScanOutput
  → save staging/
    ↓
Mỗi BIBLE_SCAN_BATCH chương:
BibleConsolidator.run()  [FileLock]
  → auto-backup database files
  → EntityResolver (exact + fuzzy + LLM arbitration)
  → upsert_entity() → database/
  → update_worldbuilding()
  → append MainLore (summaries, events, plot threads)
  → xóa staging của chapters THÀNH CÔNG
    ↓
CrossReferenceEngine (nếu BIBLE_CROSS_REF=true)
```

---

## 12. Xử lý sự cố thường gặp

### Lỗi "No such command 'bible'"

```
❌ No such command 'bible'.
```

File `src/littrans/bible/bible_cli.py` chưa tồn tại. Tạo file này từ repo.

---

### Lỗi "Not an Aho-Corasick automaton yet"

```
AttributeError: Not an Aho-Corasick automaton yet
```

Xảy ra khi scan lần đầu tiên (index rỗng). Cập nhật `bible_store.py` lên v1.1+. Fix đã có trong bản hiện tại.

---

### Lỗi "Thiếu GEMINI_API_KEY"

```
❌ Thiếu GEMINI_API_KEY trong .env
```

Mở `.env` và điền:
```env
GEMINI_API_KEY=AIzaSy...
```

---

### Bị rate limit (lỗi 429)

Pipeline tự xử lý. Nếu vẫn bị liên tục:

```env
FALLBACK_KEY_1=AIzaSy...
FALLBACK_KEY_2=AIzaSy...
SUCCESS_SLEEP=60
```

---

### Bible scan chậm

Cài `pyahocorasick` để tăng tốc entity matching O(N×M) → O(N):

```bash
pip install pyahocorasick
# hoặc
pip install ".[fast]"
```

---

### Staging tích tụ không xóa

Nếu consolidation gặp lỗi, staging của chapter đó được giữ lại để retry. Chạy thủ công:

```bash
python main.py bible consolidate
```

---

### Tên nhân vật bị sai trong bản dịch

```bash
python main.py fix-names --list    # xem vi phạm
python main.py fix-names           # sửa tự động
```

---

### Docker: port 8501 đã dùng

Sửa trong `docker-compose.yml`:

```yaml
ports:
  - "8502:8501"
```

---

### Windows: lỗi encoding

```bash
set PYTHONUTF8=1
python main.py translate
```

---

## 13. Tất cả tùy chọn cấu hình

### API

| Biến | Mặc định | Mô tả |
|---|---|---|
| `GEMINI_API_KEY` | *(bắt buộc)* | API key Gemini chính |
| `FALLBACK_KEY_1` | *(trống)* | Key dự phòng 1 |
| `FALLBACK_KEY_2` | *(trống)* | Key dự phòng 2 |
| `KEY_ROTATE_THRESHOLD` | `3` | Lỗi liên tiếp trước khi chuyển key |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp` | Model Gemini cho Scout/Pre/Post |
| `TRANSLATION_PROVIDER` | `gemini` | `gemini` hoặc `anthropic` |
| `TRANSLATION_MODEL` | *(tự chọn)* | Model dịch thuật |
| `ANTHROPIC_API_KEY` | *(trống)* | API key Anthropic |

### Pipeline

| Biến | Mặc định | Mô tả |
|---|---|---|
| `MAX_RETRIES` | `5` | Số lần retry khi lỗi |
| `SUCCESS_SLEEP` | `30` | Nghỉ (giây) sau mỗi chương |
| `RATE_LIMIT_SLEEP` | `60` | Nghỉ (giây) khi rate limit |
| `PRE_CALL_SLEEP` | `5` | Nghỉ giữa Pre-call và Trans-call |
| `POST_CALL_SLEEP` | `5` | Nghỉ giữa Trans-call và Post-call |
| `POST_CALL_MAX_RETRIES` | `2` | Retry Trans-call khi Post báo lỗi |
| `TRANS_RETRY_ON_QUALITY` | `true` | Retry khi Post báo lỗi dịch thuật |
| `BUDGET_LIMIT` | `150000` | Giới hạn token (0 = tắt) |

### Scout AI

| Biến | Mặc định | Mô tả |
|---|---|---|
| `SCOUT_REFRESH_EVERY` | `5` | Chạy Scout mỗi N chương |
| `SCOUT_LOOKBACK` | `10` | Đọc N chương gần nhất |
| `ARC_MEMORY_WINDOW` | `3` | Số arc entry đưa vào prompt |
| `SCOUT_SUGGEST_GLOSSARY` | `true` | Bật glossary suggest |
| `SCOUT_SUGGEST_MIN_CONFIDENCE` | `0.7` | Ngưỡng confidence tối thiểu |
| `SCOUT_SUGGEST_MAX_TERMS` | `20` | Thuật ngữ tối đa mỗi lần |

### Bible System

| Biến | Mặc định | Mô tả |
|---|---|---|
| `BIBLE_MODE` | `false` | Dùng Bible khi dịch |
| `BIBLE_SCAN_DEPTH` | `standard` | `quick` / `standard` / `deep` |
| `BIBLE_SCAN_BATCH` | `5` | Consolidate sau mỗi N chương |
| `BIBLE_SCAN_SLEEP` | `10` | Nghỉ (giây) giữa các chapter khi scan |
| `BIBLE_CROSS_REF` | `true` | Chạy cross-reference sau scan |
| `BIBLE_DIR` | `data/bible` | Thư mục lưu Bible data |

### Nhân vật

| Biến | Mặc định | Mô tả |
|---|---|---|
| `ARCHIVE_AFTER_CHAPTERS` | `60` | Archive nhân vật sau N chương vắng |
| `EMOTION_RESET_CHAPTERS` | `5` | Reset emotion state sau N chương |

### Merge & Retry

| Biến | Mặc định | Mô tả |
|---|---|---|
| `IMMEDIATE_MERGE` | `true` | Merge Staging → Active ngay sau mỗi chương |
| `AUTO_MERGE_GLOSSARY` | `false` | Tự động clean glossary cuối pipeline |
| `AUTO_MERGE_CHARACTERS` | `false` | Tự động merge characters cuối pipeline |
| `RETRY_FAILED_PASSES` | `3` | Vòng retry các chương thất bại |

### Đường dẫn

| Biến | Mặc định | Mô tả |
|---|---|---|
| `INPUT_DIR` | `inputs` | File chương gốc |
| `OUTPUT_DIR` | `outputs` | Bản dịch |
| `DATA_DIR` | `data` | Glossary, Characters, Skills, Memory |
| `PROMPTS_DIR` | `prompts` | System prompts |
| `LOG_DIR` | `logs` | Log file |

---

## Lệnh tham khảo nhanh

```bash
# ── Setup ────────────────────────────────────────────────────────
make init && make build           # Docker: lần đầu
python -m venv .venv && pip install -e ".[fast]"   # local

# ── Dịch ─────────────────────────────────────────────────────────
make ui                           # Web UI
python main.py translate          # CLI: dịch tất cả
make CHAPTER=5 retranslate        # dịch lại chương 5

# ── Bible ─────────────────────────────────────────────────────────
python main.py bible scan         # scan chương mới
python main.py bible scan --depth quick   # scan nhanh
python main.py bible stats        # thống kê
python main.py bible query "tên"  # tìm entity
python main.py bible consolidate  # consolidate thủ công
python main.py bible export --format markdown
python main.py bible crossref     # check mâu thuẫn

# ── Data ─────────────────────────────────────────────────────────
python main.py clean glossary     # xác nhận thuật ngữ mới
python main.py clean characters --action merge
python main.py fix-names          # sửa lỗi tên
python main.py stats              # thống kê tổng

# ── Debug ─────────────────────────────────────────────────────────
make shell                        # shell trong Docker container
make logs                         # log Web UI real-time
python main.py bible rebuild-index  # rebuild index khi corrupt
```

---

*LiTTrans v5.3 — Powered by Google Gemini & Anthropic Claude*