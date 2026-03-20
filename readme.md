# LiTTrans v4.4 — Pipeline Dịch Truyện LitRPG / Tu Tiên

Dịch tự động truyện LitRPG / Tu Tiên từ tiếng Anh sang tiếng Việt bằng **Gemini AI**.  
Giữ nhất quán tên nhân vật, xưng hô, thuật ngữ và kỹ năng xuyên suốt hàng trăm chương.

Có hai cách dùng: **Web UI** (giao diện trình duyệt, dễ dùng hơn) và **CLI** (dòng lệnh).

---

## Mục lục

1. [Trước khi bắt đầu](#1-trước-khi-bắt-đầu)
2. [Lấy Gemini API Key](#2-lấy-gemini-api-key)
3. [Cài đặt — Cách 1: Chạy trực tiếp trên máy](#3-cài-đặt--cách-1-chạy-trực-tiếp-trên-máy)
4. [Cài đặt — Cách 2: Docker (khuyến nghị cho người mới)](#4-cài-đặt--cách-2-docker-khuyến-nghị-cho-người-mới)
5. [Cấu hình .env](#5-cấu-hình-env)
6. [Sử dụng Web UI](#6-sử-dụng-web-ui)
7. [Sử dụng CLI](#7-sử-dụng-cli)
8. [Tính năng Scout Glossary Suggest](#8-tính-năng-scout-glossary-suggest)
9. [Cấu trúc thư mục](#9-cấu-trúc-thư-mục)
10. [Pipeline hoạt động như thế nào](#10-pipeline-hoạt-động-như-thế-nào)
11. [Xử lý sự cố thường gặp](#11-xử-lý-sự-cố-thường-gặp)
12. [Tất cả tùy chọn cấu hình](#12-tất-cả-tùy-chọn-cấu-hình)

---

## 1. Trước khi bắt đầu

### Bạn cần cài gì?

**Cách 1 — Chạy trực tiếp:** Cần Python 3.11 trở lên.

**Cách 2 — Docker:** Cần Docker Desktop. Không cần cài Python.

> **Nếu bạn không chắc nên chọn cách nào:** Hãy dùng Docker. Bạn chỉ cần cài một thứ duy nhất, không lo xung đột phiên bản, và các lệnh đều ngắn gọn.

### Kiểm tra đã có Python chưa (Cách 1)

Mở Terminal (macOS/Linux) hoặc PowerShell (Windows) và gõ:

```bash
python --version
```

Nếu thấy `Python 3.11.x` hoặc cao hơn → OK.  
Nếu thấy `Python 3.9` hoặc báo lỗi → Tải Python tại [python.org](https://www.python.org/downloads/).

### Kiểm tra đã có Docker chưa (Cách 2)

```bash
docker --version
```

Nếu báo lỗi → Tải Docker Desktop tại [docker.com](https://www.docker.com/products/docker-desktop/).  
Sau khi cài xong, khởi động Docker Desktop trước khi làm bước tiếp theo.

---

## 2. Lấy Gemini API Key

Pipeline dùng Gemini AI của Google để dịch. Bạn cần một API key miễn phí.

**Bước 1:** Truy cập [aistudio.google.com](https://aistudio.google.com)

**Bước 2:** Đăng nhập bằng tài khoản Google

**Bước 3:** Click **"Get API key"** → **"Create API key"**

**Bước 4:** Copy key vừa tạo (dạng `AIzaSy...`) — giữ key này bí mật, không chia sẻ công khai

> **Lưu ý về giới hạn miễn phí:** Gemini Flash cho phép khoảng 1.000 request/ngày miễn phí. Nếu dịch số lượng lớn, bạn có thể cần nâng cấp lên tài khoản trả phí hoặc thêm key dự phòng.

---

## 3. Cài đặt — Cách 1: Chạy trực tiếp trên máy

### Bước 1: Tải source code

```bash
git clone <repo-url>
cd littrans
```

Hoặc tải file ZIP từ GitHub → giải nén → mở Terminal trong thư mục vừa giải nén.

### Bước 2: Tạo môi trường ảo (khuyến nghị)

Môi trường ảo giúp tránh xung đột với các package Python khác trên máy bạn.

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
```

Bạn biết đang trong môi trường ảo khi thấy `(.venv)` xuất hiện ở đầu dòng lệnh.

### Bước 3: Cài thư viện

```bash
# Cài đặt cơ bản
pip install -e .

# Cài thêm pyahocorasick để filter glossary nhanh hơn ~10 lần (khuyến nghị)
pip install ".[fast]"

# Cài thêm nếu muốn dùng Web UI
pip install streamlit pandas
```

### Bước 4: Tạo file cấu hình

```bash
cp .env.example .env
```

Mở file `.env` bằng bất kỳ text editor nào và điền API key vào dòng đầu:

```env
GEMINI_API_KEY=AIzaSy...   ← dán key của bạn vào đây
```

### Bước 5: Chạy thử

```bash
# Web UI
python run_ui.py

# Hoặc CLI
python main.py --help
```

---

## 4. Cài đặt — Cách 2: Docker (khuyến nghị cho người mới)

Docker đóng gói toàn bộ môi trường vào một "hộp" — bạn không cần cài Python, không lo xung đột phiên bản.

### Bước 1: Tải source code

```bash
git clone <repo-url>
cd littrans
```

### Bước 2: Khởi tạo thư mục và file cấu hình

```bash
# macOS / Linux
make init

# Windows (nếu chưa có make, chạy thủ công)
mkdir inputs outputs logs
mkdir data\glossary data\characters data\skills data\memory
copy .env.example .env
```

Lệnh này tạo tất cả thư mục cần thiết và copy file `.env` từ template.

### Bước 3: Điền API key vào .env

Mở file `.env` và sửa dòng đầu tiên:

```env
GEMINI_API_KEY=AIzaSy...   ← dán key của bạn vào đây
```

### Bước 4: Build image Docker

```bash
make build

# Nếu không có make:
docker compose build
```

Lần đầu mất **3–5 phút** do cần tải và compile thư viện. Các lần sau nhanh hơn nhiều.

Bạn sẽ thấy output như sau — đây là bình thường:

```
[+] Building 87.3s (14/14) FINISHED
 => [builder 1/3] FROM python:3.11-slim
 => [builder 3/3] RUN pip wheel ... pyahocorasick ...
 => [runtime 3/6] RUN pip install /tmp/wheels/*.whl
```

### Bước 5: Chạy Web UI

```bash
make ui

# Nếu không có make:
docker compose up ui
```

Mở trình duyệt và truy cập: **http://localhost:8501**

---

## 5. Cấu hình .env

File `.env` chứa toàn bộ cấu hình. Những thứ quan trọng nhất:

```env
# ── BẮT BUỘC ──────────────────────────────────────────────────────
GEMINI_API_KEY=AIzaSy...          # API key chính — phải có

# ── KEY DỰ PHÒNG (tùy chọn, khuyến nghị nếu dịch nhiều) ──────────
# Khi key chính bị rate limit, pipeline tự động chuyển sang key dự phòng
FALLBACK_KEY_1=AIzaSy...
FALLBACK_KEY_2=AIzaSy...

# ── MODEL ─────────────────────────────────────────────────────────
# gemini-2.5-flash  → nhanh, rẻ, chất lượng tốt (khuyến nghị)
# gemini-2.5-pro    → chậm hơn, đắt hơn, chất lượng cao nhất
GEMINI_MODEL=gemini-2.5-flash

# ── TỐC ĐỘ (điều chỉnh nếu bị rate limit) ────────────────────────
SUCCESS_SLEEP=30        # Nghỉ 30 giây giữa các chương
RATE_LIMIT_SLEEP=60     # Nghỉ 60 giây khi bị giới hạn tốc độ
```

> **Web UI:** Bạn có thể chỉnh tất cả cấu hình này trong tab **⚙️ Cài đặt** mà không cần sửa file `.env` thủ công.

---

## 6. Sử dụng Web UI

### Khởi động

```bash
# Cách 1: Chạy trực tiếp
python run_ui.py

# Cách 2: Docker
make ui
# hoặc: docker compose up ui
```

Mở trình duyệt: **http://localhost:8501**

---

### Lần đầu sử dụng — làm theo 4 bước này

#### Bước 1 — Kiểm tra API key

Mở tab **⚙️ Cài đặt** → mục **🔑 API** → xác nhận đã có `GEMINI_API_KEY`.  
Nếu chưa có → điền vào ô rồi nhấn **💾 Lưu .env**.

#### Bước 2 — Upload file chương

Mở tab **📄 Dịch** → kéo thả file `.txt` hoặc `.md` vào ô **Upload file chương**.

**Quy tắc đặt tên file:**
- Mỗi file = một chương
- Đặt tên có số thứ tự để pipeline sắp xếp đúng
- Ví dụ: `chapter_001.txt`, `chapter_002.txt`, ...  
  hoặc: `Chapter 1.txt`, `Chapter 2.txt`, ...

#### Bước 3 — Chạy pipeline

Nhấn nút **▶ Chạy pipeline**.

Log sẽ hiện theo thời gian thực. Với mỗi chương, bạn sẽ thấy các bước:

```
▶  [1] Dịch: chapter_001.txt
  🔭 Scout đọc 10 chương (...)
  📖 Glossary Suggest: +5 thuật ngữ → Staging
  🔍 Pre-call...
  ✅ Chapter map: 12 tên · 3 skill · 8 pronoun pair
  ⚙️  Trans-call 1/5 | gemini-2.5-flash
  🔎 Post-call 1/3...
  ✅ Dịch xong: chapter_001.txt
```

#### Bước 4 — Xem kết quả

Mở tab **🔍 Xem chương** → click tên chương → chọn tab xem:

- **🔀 Song song**: EN bên trái, VN bên phải, cuộn đồng bộ
- **🇻🇳 Bản dịch**: xem toàn văn + nút tải xuống
- **⚡ Diff**: highlight đoạn mới/thay đổi so với bản gốc

---

### Các tab trong Web UI

| Tab | Chức năng |
|---|---|
| **📄 Dịch** | Upload file, xem trạng thái, chạy pipeline, xem log real-time |
| **🔍 Xem chương** | Đọc song song EN/VN, tải xuống, dịch lại chương cụ thể |
| **👤 Nhân vật** | Xem profile nhân vật, xưng hô strong/weak, emotion state |
| **📚 Từ điển** | Xem/tìm kiếm glossary, xác nhận thuật ngữ Scout đề xuất |
| **📊 Thống kê** | Tiến độ dịch, số thuật ngữ, nhân vật, biểu đồ |
| **⚙️ Cài đặt** | Toàn bộ cấu hình pipeline, lưu vào .env |

---

### Dịch lại một chương

1. Mở tab **🔍 Xem chương**
2. Click chương cần dịch lại trong danh sách bên trái
3. Cuộn xuống dưới → nhấn **↺ Dịch lại…**
4. Chọn tùy chọn nếu cần:
   - **Cập nhật data** — cập nhật Glossary/Characters/Skills sau khi dịch lại
   - **Chạy Scout AI trước** — phân tích lại context trước khi dịch
5. Nhấn **⚡ Xác nhận dịch lại**

> ⚠️ Bản dịch cũ sẽ bị **ghi đè**.

---

## 7. Sử dụng CLI

CLI phù hợp khi bạn muốn chạy tự động hoặc dùng trên server không có giao diện.

### Cách chạy

```bash
# Chạy trực tiếp (đã activate venv)
python main.py <lệnh>

# Chạy qua Docker
docker compose run --rm cli python main.py <lệnh>

# Chạy qua make (shortcut)
make <lệnh>
```

---

### Workflow cơ bản

```bash
# 1. Dịch tất cả chương chưa dịch
python main.py translate

# 2. Sau khi dịch xong — xác nhận thuật ngữ Scout đề xuất
python main.py clean glossary

# 3. Merge nhân vật mới vào database
python main.py clean characters --action merge

# 4. Kiểm tra và sửa lỗi tên (nếu có)
python main.py fix-names
```

---

### Tất cả lệnh CLI

#### `translate` — Dịch hàng loạt

```bash
python main.py translate
```

Dịch tất cả chương trong `inputs/` chưa có bản dịch. Pipeline tự động bỏ qua chương đã dịch, chạy Scout AI theo chu kỳ, và retry khi gặp lỗi.

---

#### `retranslate` — Dịch lại một chương

```bash
# Chọn theo số thứ tự (xem danh sách trước)
python main.py retranslate --list
python main.py retranslate 5

# Chọn theo tên file (gõ một phần cũng được)
python main.py retranslate "chapter_005"

# Dịch lại và cập nhật Glossary/Characters/Skills
python main.py retranslate 5 --update-data
```

---

#### `clean glossary` — Xác nhận thuật ngữ mới

```bash
python main.py clean glossary
```

Đọc các thuật ngữ Scout đề xuất trong Staging → dùng AI phân loại vào đúng nhóm → ghi vào file Glossary tương ứng.

---

#### `clean characters` — Quản lý nhân vật

```bash
# Xem toàn bộ profile đang active
python main.py clean characters --action review

# Merge nhân vật mới từ Staging → Active
python main.py clean characters --action merge

# Tự động sửa lỗi nhỏ trong profile
python main.py clean characters --action fix

# Kiểm tra schema, cảnh báo profile thiếu thông tin
python main.py clean characters --action validate

# Xuất báo cáo Markdown ra thư mục Reports/
python main.py clean characters --action export

# Xem nhân vật đã archive (lâu không xuất hiện)
python main.py clean characters --action archive
```

---

#### `fix-names` — Sửa lỗi tên vi phạm Name Lock

```bash
# Xem danh sách vi phạm
python main.py fix-names --list

# Xem trước sẽ sửa gì (không ghi file)
python main.py fix-names --dry-run

# Sửa thật (chỉ các chương có vi phạm)
python main.py fix-names

# Sửa toàn bộ tất cả chương
python main.py fix-names --all-chapters
```

---

#### `stats` — Thống kê nhanh

```bash
python main.py stats
```

---

### Shortcut với make (Docker)

```bash
make translate                    # dịch tất cả
make CHAPTER=5 retranslate        # dịch lại chương 5
make stats                        # thống kê
make clean-glossary               # xác nhận thuật ngữ
make merge-chars                  # merge nhân vật
make fix-names                    # sửa lỗi tên
make validate-chars               # kiểm tra schema
make export-chars                 # xuất báo cáo
make shell                        # mở shell debug
```

---

## 8. Tính năng Scout Glossary Suggest

Đây là tính năng mới trong v4.4. Scout AI không chỉ viết context notes mà còn **tự động phát hiện thuật ngữ chuyên biệt** chưa có trong Glossary và đề xuất bản dịch.

### Thuật ngữ nào được đề xuất?

Scout ưu tiên tìm và đề xuất theo thứ tự:

1. Tên kỹ năng, chiêu thức, phép thuật
2. Danh hiệu, cảnh giới tu luyện, tước vị
3. Tên tổ chức, hội phái, môn phái
4. Địa danh, cõi giới, dungeon
5. Vật phẩm đặc biệt, vũ khí, đan dược
6. Thuật ngữ hệ thống: pathway, sequence, ability class

Scout **không** đề xuất tên nhân vật (đã có hệ thống riêng) và từ tiếng Anh thông thường.

### Luồng hoạt động

```
Pipeline dịch chương
    ↓
Scout chạy (mỗi 5 chương theo mặc định)
    ↓
Scout đọc window chương gần nhất
    ↓
Phát hiện thuật ngữ mới + đề xuất bản dịch VN
    ↓
Lọc theo confidence ≥ 0.7 + dedup với glossary hiện có
    ↓
Ghi vào Staging_Terms.md
    ↓
Bạn chạy "clean glossary" để xác nhận và phân loại
    ↓
Thuật ngữ vào đúng Glossary file, sẵn sàng dùng cho chương tiếp theo
```

### Xem và xác nhận thuật ngữ

**Web UI:** Tab **📚 Từ điển** sẽ hiện banner vàng khi có thuật ngữ chờ xác nhận. Nhấn **🔄 Clean glossary**.

**CLI:**
```bash
python main.py clean glossary
```

### Tắt tính năng này

Nếu muốn tắt để tiết kiệm API call:

```env
SCOUT_SUGGEST_GLOSSARY=false
```

Hoặc chỉnh trong **⚙️ Cài đặt** → tab **📖 Glossary Suggest**.

### Điều chỉnh độ nhạy

```env
SCOUT_SUGGEST_MIN_CONFIDENCE=0.7   # Tăng lên 0.85 nếu muốn ít gợi ý hơn nhưng chắc chắn hơn
SCOUT_SUGGEST_MAX_TERMS=20         # Số thuật ngữ tối đa mỗi lần Scout chạy
```

---

## 9. Cấu trúc thư mục

```
littrans/
│
├── main.py              # Entry point CLI
├── run_ui.py            # Entry point Web UI
├── .env                 # Cấu hình của bạn (tạo từ .env.example)
├── .env.example         # Template cấu hình
│
├── Dockerfile           # Docker: multi-stage build
├── docker-compose.yml   # Docker: services ui + cli
├── docker-entrypoint.sh # Docker: script khởi tạo
├── .dockerignore        # Docker: loại file không cần trong image
├── Makefile             # Shortcut commands
│
├── src/littrans/
│   ├── engine/          # Pipeline orchestrator, Scout AI, Pre/Post-call, Quality guard
│   ├── managers/        # Glossary, Characters, Skills, Name Lock, Memory
│   ├── llm/             # Gemini API client, schemas, token budget
│   ├── tools/           # clean_glossary, clean_characters, fix_names
│   ├── ui/              # Streamlit Web UI
│   └── config/          # Settings (đọc từ .env)
│
├── prompts/
│   ├── system_agent.md       # Hướng dẫn dịch chính
│   └── character_profile.md  # Hướng dẫn lập profile nhân vật
│
├── inputs/              # ← Đặt file chương gốc vào đây (.txt / .md)
├── outputs/             # Bản dịch (*_VN.txt) — tự sinh
│
└── data/
    ├── glossary/
    │   ├── Glossary_Pathways.md       # Hệ thống tu luyện, cảnh giới
    │   ├── Glossary_Organizations.md  # Tổ chức, hội phái
    │   ├── Glossary_Items.md          # Vật phẩm, vũ khí
    │   ├── Glossary_Locations.md      # Địa danh, cõi giới
    │   ├── Glossary_General.md        # Thuật ngữ chung, kỹ năng
    │   └── Staging_Terms.md           # Thuật ngữ Scout đề xuất, chờ xác nhận
    ├── characters/
    │   ├── Characters_Active.json     # Nhân vật xuất hiện gần đây
    │   ├── Characters_Archive.json    # Nhân vật lâu không thấy
    │   └── Staging_Characters.json    # Nhân vật mới, chờ merge
    ├── skills/
    │   └── Skills.json                # Kỹ năng đã biết + evolution chain
    └── memory/
        ├── Context_Notes.md           # Ghi chú ngắn hạn từ Scout
        └── Arc_Memory.md             # Bộ nhớ arc dài hạn
```

---

## 10. Pipeline hoạt động như thế nào

Với mỗi chương, pipeline chạy theo trình tự sau:

### Scout AI (mỗi 5 chương)

Trước khi dịch, Scout đọc các chương gần nhất và làm 4 việc:

1. **Context Notes** — Ghi chú mạch truyện đặc biệt, flashback, xưng hô đang active
2. **Arc Memory** — Tóm tắt sự kiện quan trọng, append vào bộ nhớ dài hạn
3. **Emotion Tracker** — Cập nhật trạng thái cảm xúc từng nhân vật
4. **Glossary Suggest** *(mới v4.4)* — Phát hiện thuật ngữ mới, đề xuất vào Staging

### Pre-call

Phân tích nhanh chương sắp dịch: xác định tên/kỹ năng/xưng hô đang active, phát hiện alias và scene bất thường.

### Translation call

Dịch nội dung chính. System prompt gồm 8 phần:
- Hướng dẫn dịch + Glossary + Character profiles
- Chapter Map từ Pre-call
- Arc Memory + Context Notes
- Name Lock Table (bảng tên đã chốt — ưu tiên tuyệt đối)

### Quality Guard (kiểm tra cơ học)

Kiểm tra 7 tiêu chí: dính dòng, thiếu dòng trống, mất đoạn, dòng chưa dịch, system box lỗi... Tự động retry nếu phát hiện vấn đề.

### Post-call

Review chất lượng dịch thuật: tên sai, pronoun sai, đoạn mất. Tự sửa lỗi trình bày. Extract metadata: thuật ngữ mới, nhân vật mới, quan hệ thay đổi, kỹ năng mới.

### Name Lock validate

Quét bản dịch tìm tên tiếng Anh còn sót. Ghi vi phạm vào `data/name_fixes.json` để sửa sau bằng `fix-names`.

---

## 11. Xử lý sự cố thường gặp

### Lỗi "Thiếu GEMINI_API_KEY"

```
❌ Thiếu GEMINI_API_KEY trong .env
```

Kiểm tra file `.env` có dòng:
```env
GEMINI_API_KEY=AIzaSy...
```
Không để dấu cách trước/sau dấu `=`. Không bọc trong dấu ngoặc kép.

---

### Bị rate limit (lỗi 429)

```
❌ Lỗi 1/5: 429 Resource exhausted
⚠️  Rate limit → chờ 60s...
```

Pipeline tự xử lý và chờ. Nếu vẫn bị liên tục:
- Thêm key dự phòng vào `.env`: `FALLBACK_KEY_1=AIzaSy...`
- Tăng thời gian nghỉ: `SUCCESS_SLEEP=60`
- Đổi sang model flash (nhanh hơn, ít bị rate limit hơn): `GEMINI_MODEL=gemini-2.5-flash`

---

### Bản dịch bị lỗi chất lượng

```
⚠️  Lỗi chất lượng (1/5): DÍNH DÒNG NGHIÊM TRỌNG
```

Pipeline tự retry. Nếu vẫn lỗi sau nhiều lần, thử dịch lại chương đó:

```bash
python main.py retranslate <số thứ tự hoặc tên file>
```

---

### Tên nhân vật bị sai trong bản dịch

```
🔒 Name Lock — 2 vi phạm
```

Pipeline ghi lại vi phạm. Sau khi dịch xong, chạy:

```bash
python main.py fix-names --list    # xem danh sách
python main.py fix-names           # sửa tự động
```

---

### Docker: lỗi permission trên Linux/macOS

```
permission denied: docker-entrypoint.sh
```

```bash
chmod +x docker-entrypoint.sh
```

---

### Docker: port 8501 đã bị dùng

Sửa trong `docker-compose.yml`:
```yaml
ports:
  - "8502:8501"   # đổi 8501 bên trái thành port khác
```
Sau đó truy cập `http://localhost:8502`.

---

### Docker: muốn sửa prompts mà không rebuild

Bỏ comment dòng này trong `docker-compose.yml` (service `ui`):
```yaml
# - ./prompts:/app/prompts:ro
```
Thành:
```yaml
- ./prompts:/app/prompts:ro
```
Rồi `docker compose restart ui`. Không cần rebuild image.

---

### Dùng Windows và gặp lỗi encoding

```bash
set PYTHONUTF8=1
python main.py translate
```

Hoặc thêm vào đầu PowerShell session:
```powershell
$env:PYTHONUTF8 = "1"
```

---

## 12. Tất cả tùy chọn cấu hình

Tất cả đều có thể chỉnh trong file `.env` hoặc qua tab **⚙️ Cài đặt** trong Web UI.

### API

| Biến | Mặc định | Mô tả |
|---|---|---|
| `GEMINI_API_KEY` | *(bắt buộc)* | API key chính |
| `FALLBACK_KEY_1` | *(trống)* | Key dự phòng 1 |
| `FALLBACK_KEY_2` | *(trống)* | Key dự phòng 2 |
| `KEY_ROTATE_THRESHOLD` | `3` | Số lỗi liên tiếp trước khi chuyển key |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp` | Model Gemini sử dụng |

### Pipeline

| Biến | Mặc định | Mô tả |
|---|---|---|
| `USE_THREE_CALL` | `true` | `true` = Pre+Trans+Post call. `false` = 1-call legacy |
| `MAX_RETRIES` | `5` | Số lần retry khi gặp lỗi |
| `SUCCESS_SLEEP` | `30` | Nghỉ (giây) sau mỗi chương thành công |
| `RATE_LIMIT_SLEEP` | `60` | Nghỉ (giây) khi bị rate limit |
| `MIN_CHARS_PER_CHAPTER` | `500` | Cảnh báo nếu chương ngắn hơn số ký tự này |
| `PRE_CALL_SLEEP` | `5` | Nghỉ (giây) giữa Pre-call và Trans-call |
| `POST_CALL_SLEEP` | `5` | Nghỉ (giây) giữa Trans-call và Post-call |
| `POST_CALL_MAX_RETRIES` | `2` | Số lần retry Trans-call khi Post báo lỗi dịch thuật |
| `TRANS_RETRY_ON_QUALITY` | `true` | Có retry Trans-call khi Post báo lỗi không |

### Scout AI

| Biến | Mặc định | Mô tả |
|---|---|---|
| `SCOUT_REFRESH_EVERY` | `5` | Chạy Scout mỗi N chương |
| `SCOUT_LOOKBACK` | `10` | Đọc N chương gần nhất |
| `ARC_MEMORY_WINDOW` | `3` | Số arc entry đưa vào prompt |

### Scout Glossary Suggest

| Biến | Mặc định | Mô tả |
|---|---|---|
| `SCOUT_SUGGEST_GLOSSARY` | `true` | Bật/tắt tính năng đề xuất thuật ngữ |
| `SCOUT_SUGGEST_MIN_CONFIDENCE` | `0.7` | Ngưỡng confidence tối thiểu (0.0–1.0) |
| `SCOUT_SUGGEST_MAX_TERMS` | `20` | Số thuật ngữ tối đa mỗi lần Scout |

### Nhân vật

| Biến | Mặc định | Mô tả |
|---|---|---|
| `ARCHIVE_AFTER_CHAPTERS` | `60` | Chuyển nhân vật sang Archive sau N chương không thấy |
| `EMOTION_RESET_CHAPTERS` | `5` | Tự reset emotional state về normal sau N chương |

### Merge & Retry

| Biến | Mặc định | Mô tả |
|---|---|---|
| `IMMEDIATE_MERGE` | `true` | Merge Staging → Active ngay sau mỗi chương |
| `AUTO_MERGE_GLOSSARY` | `false` | Tự động chạy clean glossary cuối pipeline |
| `AUTO_MERGE_CHARACTERS` | `false` | Tự động merge characters cuối pipeline |
| `RETRY_FAILED_PASSES` | `3` | Số vòng retry các chương thất bại cuối pipeline |

### Token Budget

| Biến | Mặc định | Mô tả |
|---|---|---|
| `BUDGET_LIMIT` | `150000` | Giới hạn token cho context (0 = tắt) |

Khi vượt giới hạn, pipeline tự cắt context theo thứ tự: Arc Memory → Staging glossary → Character profiles phụ → Toàn bộ Arc Memory.

### Đường dẫn

| Biến | Mặc định | Mô tả |
|---|---|---|
| `INPUT_DIR` | `inputs` | Thư mục chứa file chương gốc |
| `OUTPUT_DIR` | `outputs` | Thư mục chứa bản dịch |
| `DATA_DIR` | `data` | Thư mục chứa Glossary, Characters, Skills, Memory |
| `PROMPTS_DIR` | `prompts` | Thư mục chứa system prompts |
| `LOG_DIR` | `logs` | Thư mục chứa log file |

---

## Lệnh tham khảo nhanh

```bash
# ── Lần đầu setup ─────────────────────────────────────────────────
make init                         # tạo thư mục + .env (Docker)
make build                        # build Docker image

# ── Chạy hàng ngày ────────────────────────────────────────────────
make ui                           # khởi động Web UI
make translate                    # dịch tất cả chương
make stats                        # xem thống kê

# ── Sau khi dịch ──────────────────────────────────────────────────
make clean-glossary               # xác nhận thuật ngữ Scout đề xuất
make merge-chars                  # merge nhân vật mới
make fix-names                    # sửa lỗi tên

# ── Xử lý sự cố ───────────────────────────────────────────────────
make CHAPTER=5 retranslate        # dịch lại chương 5
make validate-chars               # kiểm tra schema nhân vật
make export-chars                 # xuất báo cáo nhân vật

# ── Debug ──────────────────────────────────────────────────────────
make shell                        # mở shell trong container
make logs                         # xem log Web UI real-time
```

---

*LiTTrans v4.4 — Powered by Google Gemini*