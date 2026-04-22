# LiTTrans v5.7

**Pipeline dịch tự động truyện LitRPG / Tu Tiên** — từ tiếng Anh sang tiếng Việt, nhất quán từ chương 1 đến chương 1000.

> Dùng **Gemini AI** (miễn phí) hoặc **Claude (Anthropic)** làm engine dịch.  
> Giữ nhất quán tên nhân vật, xưng hô, kỹ năng và thuật ngữ xuyên suốt toàn bộ tác phẩm.

---

## Mục lục

- [LiTTrans làm được gì?](#littrans-làm-được-gì)
- [Hướng dẫn cho người chưa biết code](#hướng-dẫn-cho-người-chưa-biết-code)
  - [Bước 0 — Cài Python](#bước-0--cài-python)
  - [Bước 1 — Tải LiTTrans](#bước-1--tải-littrans)
  - [Bước 2 — Mở Terminal](#bước-2--mở-terminal)
  - [Bước 3 — Cài thư viện](#bước-3--cài-thư-viện)
  - [Bước 4 — Lấy API Key](#bước-4--lấy-api-key)
  - [Bước 5 — Điền API Key](#bước-5--điền-api-key)
  - [Bước 6 — Khởi động](#bước-6--khởi-động)
- [Sử dụng Web UI](#sử-dụng-web-ui)
  - [Cào truyện từ web](#cào-truyện-từ-web)
  - [Pipeline 1-click (web → dịch)](#pipeline-1-click-web--dịch)
  - [Xử lý file EPUB](#xử-lý-file-epub)
  - [Dịch file thủ công](#dịch-file-thủ-công)
  - [Xem bản dịch](#xem-bản-dịch)
  - [Quản lý nhân vật và từ điển](#quản-lý-nhân-vật-và-từ-điển)
- [Tính năng chính](#tính-năng-chính)
- [Bible System](#bible-system)
- [Pipeline hoạt động như thế nào?](#pipeline-hoạt-động-như-thế-nào)
- [Xử lý sự cố](#xử-lý-sự-cố)
- [Tất cả tùy chọn cấu hình](#tất-cả-tùy-chọn-cấu-hình)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Dùng CLI (nâng cao)](#dùng-cli-nâng-cao)

---

## LiTTrans làm được gì?

Khi dịch truyện dài hàng trăm chương bằng ChatGPT thông thường, bạn sẽ gặp vấn đề: **nhân vật bị gọi bằng 5 cái tên khác nhau, xưng hô loạn xạ, kỹ năng dịch mỗi chương một kiểu**. LiTTrans giải quyết điều này bằng cách xây dựng "bộ nhớ" cho toàn bộ quá trình dịch.

| Vấn đề thường gặp | LiTTrans giải quyết như thế nào |
|---|---|
| Phải tự copy-paste từng chương | **Scraper** — tự cào truyện từ web, resume được nếu bị ngắt |
| Tên nhân vật bị dịch khác nhau | **Name Lock** — chốt cứng một bản dịch duy nhất |
| Xưng hô "anh/em" → "ta/ngươi" loạn | **EPS** — theo dõi mức độ thân mật từng cặp nhân vật |
| Kỹ năng dịch mỗi chương một kiểu | **Skills DB** — lưu và tái sử dụng tên kỹ năng |
| AI quên bối cảnh chương trước | **Arc Memory + Scout AI** — tóm tắt và nhắc bối cảnh |
| Phải ngồi canh từng chương | **Batch pipeline** — tự động chạy hết queue, có retry |
| Có file EPUB muốn dịch | **EPUB Processor** — bóc nội dung EPUB → dịch → xuất EPUB mới |

---

## Hướng dẫn cho người chưa biết code

> Đọc hết phần này trước khi làm. Mỗi bước có giải thích cụ thể.

### Bước 0 — Cài Python

**Python là gì?** Là phần mềm để chạy code. LiTTrans viết bằng Python nên bạn cần cài nó trước.

**Kiểm tra xem đã có Python chưa:**

1. Nhấn `Windows + R` → gõ `cmd` → nhấn Enter (mở cửa sổ đen gọi là "terminal")
2. Gõ lệnh sau rồi nhấn Enter:
   ```
   python --version
   ```
3. Nếu thấy `Python 3.11.x` trở lên → đã có, bỏ qua bước này.
4. Nếu thấy lỗi hoặc số version < 3.11 → cần cài.

**Cài Python 3.11+ (Windows):**

1. Vào trang [python.org/downloads](https://www.python.org/downloads/) → nhấn nút **"Download Python 3.x.x"**
2. Chạy file vừa tải, **QUAN TRỌNG: tích vào ô "Add Python to PATH"** trước khi nhấn Install
3. Nhấn **"Install Now"** → đợi xong
4. Đóng terminal cũ, mở terminal mới → gõ lại `python --version` để kiểm tra

---

### Bước 1 — Tải LiTTrans

**Cách 1 — Tải file zip (dễ nhất):**

1. Nhấn nút **"Code"** màu xanh ở góc trên phải trang GitHub
2. Chọn **"Download ZIP"**
3. Giải nén ra Desktop → đổi tên thư mục thành `NovelPipeline` cho gọn

**Cách 2 — Dùng git (nếu đã biết):**

```bash
git clone <repo-url>
cd NovelPipeline
```

---

### Bước 2 — Mở Terminal

**Terminal là gì?** Là cửa sổ đen để gõ lệnh. Không cần biết code — chỉ cần copy-paste các lệnh bên dưới.

**Mở terminal tại thư mục NovelPipeline:**

- Vào thư mục `NovelPipeline` bằng File Explorer
- Nhấn vào thanh địa chỉ (nơi hiện đường dẫn như `C:\Users\...`)
- Gõ `cmd` rồi nhấn Enter

Hoặc:
- Nhấn `Windows + R` → gõ `cmd` → Enter
- Gõ lệnh: `cd "C:\Users\TÊN_BẠN\Desktop\NovelPipeline"` (thay đường dẫn thật của bạn)

---

### Bước 3 — Cài thư viện

Copy từng lệnh sau, paste vào terminal, nhấn Enter, đợi xong rồi mới làm lệnh tiếp:

**1. Tạo môi trường ảo** (giữ cài đặt riêng, không làm ảnh hưởng Python chung):
```bash
python -m venv .venv
```

**2. Kích hoạt môi trường ảo:**
```bash
.venv\Scripts\activate
```
> Thấy `(.venv)` ở đầu dòng là thành công. Từ đây các lệnh đều chạy trong môi trường này.

**3. Cài LiTTrans và tất cả thư viện cần thiết:**
```bash
pip install -e .
pip install ".[fast]"
```
> Lần đầu cài có thể mất 5–10 phút. Bình thường.

**4. Cài browser cho scraper** (chỉ làm 1 lần):
```bash
playwright install chromium
```
> Tải ~130MB — lần đầu mất vài phút. Lần sau không cần làm lại.

---

### Bước 4 — Lấy API Key

**API Key là gì?** Là "mật khẩu" để dùng dịch vụ AI của Google. Miễn phí.

**Lấy Gemini API Key (bắt buộc, miễn phí):**

1. Vào [aistudio.google.com](https://aistudio.google.com) — đăng nhập tài khoản Google
2. Nhấn **"Get API key"** → **"Create API key"** → chọn project bất kỳ
3. Copy key (trông như `AIzaSyAbc123...`) — lưu vào notepad

> **Gói miễn phí:** ~1.000 request/ngày — đủ dịch 30–50 chương/ngày.  
> **Mẹo tăng quota:** Tạo key từ 2-3 tài khoản Google khác nhau → điền vào `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`... pipeline tự xoay vòng.

---

### Bước 5 — Điền API Key

**Cách 1 — Qua Web UI (dễ nhất, khuyến nghị):**

Khởi động Web UI (xem Bước 6), vào tab **⚙️ Cài đặt** → điền key → nhấn **💾 Lưu**.

**Cách 2 — Sửa file `.env` trực tiếp:**

1. Trong thư mục `NovelPipeline`, sao chép file `.env.example` → đổi tên thành `.env`
2. Mở file `.env` bằng Notepad (chuột phải → Open with → Notepad)
3. Tìm dòng `GEMINI_API_KEY=` → điền key của bạn vào sau dấu `=`
4. Lưu file

```env
GEMINI_API_KEY=AIzaSyAbc123xyz...
```

> **Lưu ý:** File `.env` chứa API key — **đừng chia sẻ** với người khác và **đừng đăng lên GitHub**.

---

### Bước 6 — Khởi động

Mỗi lần dùng LiTTrans, làm theo thứ tự:

**1. Mở terminal tại thư mục NovelPipeline**

**2. Kích hoạt môi trường ảo:**
```bash
.venv\Scripts\activate
```

**3. Khởi động Web UI:**
```bash
python scripts/run_ui.py
```

**4. Mở trình duyệt** → vào địa chỉ **http://localhost:8501** ✅

> Terminal sẽ hiện các log — bình thường, đừng đóng cửa sổ terminal. Nhấn `Ctrl+C` để dừng.

---

## Sử dụng Web UI

Giao diện chính có thanh menu bên trái. Chọn truyện từ dropdown **📚 Truyện đang chọn** trước khi làm bất cứ gì.

### Cào truyện từ web

Tab **🌐 Cào Truyện**

1. Nhập URL trang danh sách chương (ví dụ: `https://www.royalroad.com/fiction/12345/ten-truyen`)
2. Nhập tên novel (tên thư mục lưu — không dùng ký tự đặc biệt)
3. Nhấn **Cào** — lần đầu AI học cấu trúc site (~1 phút), các lần sau dùng lại
4. Dừng giữa chừng được — lần sau tự resume từ chương cuối cùng
5. Kết quả lưu vào `inputs/{novel_name}/`

> **Site thay đổi, không cào được?** Thêm `!relearn domain.com` vào trước URL.  
> Ví dụ: `!relearn royalroad.com https://www.royalroad.com/fiction/...`

---

### Pipeline 1-click (web → dịch)

Tab **🚀 Pipeline** → mode **🌐→🇻🇳 Cào web + dịch**

Làm tất cả trong 1 lần: cào web → dịch → xong.

1. Nhập URL + tên novel → nhấn **Chạy**
2. Giai đoạn 1: Cào web → `inputs/{novel}/`
3. Giai đoạn 2: Dịch toàn bộ → `outputs/{novel}/`
4. Thanh tiến độ hiển thị real-time trong UI

> Để cửa sổ trình duyệt mở — UI tự cập nhật. Có thể để máy chạy qua đêm.

---

### Xử lý file EPUB

**Nhập EPUB để dịch:**

Tab **🚀 Pipeline** → mode **📚 Chỉ xử lý EPUB → .md**

1. Upload file `.epub` (kéo thả hoặc Browse)
2. Nhập tên novel → nhấn **Chạy**
3. Pipeline bóc nội dung → lưu từng chương vào `inputs/{novel_name}/`
4. Sau đó dịch bình thường qua tab **📄 Dịch**

**Xuất EPUB từ bản dịch:**

Tab **📚 EPUB**

1. Nhập tên tác phẩm, tác giả
2. Nhấn **🔄 Tạo EPUB** → đợi vài giây
3. Nhấn **⬇️ Download** để tải về

---

### Dịch file thủ công

Nếu bạn đã có file chương (`.txt` hoặc `.md`):

1. Đặt file vào thư mục `inputs/{tên_novel}/`
   - Đặt tên file theo thứ tự: `0001_Chapter 1.txt`, `0002_Chapter 2.txt`...
2. Vào tab **📄 Dịch** → chọn novel từ dropdown bên trái
3. Nhấn **▶ Chạy pipeline**
4. Bản dịch lưu vào `outputs/{tên_novel}/`

> **Định dạng tên file:** Số 4 chữ số ở đầu để sắp xếp đúng thứ tự. Ví dụ: `0001_`, `0002_`...

---

### Xem bản dịch

Tab **🔍 Xem chương**

- Chọn chương từ danh sách
- Xem song ngữ EN/VN cạnh nhau
- So sánh bản dịch lại với bản gốc

---

### Quản lý nhân vật và từ điển

**Tab 👤 Nhân vật:**
- Xem profile từng nhân vật (tên, xưng hô, cấp độ, quan hệ, cảm xúc hiện tại)
- **📥 Merge** — thêm nhân vật mới từ Staging vào danh sách theo dõi
- **✔ Validate** — kiểm tra dữ liệu nhân vật có hợp lệ không
- **📄 Export** — xuất báo cáo nhân vật ra file

**Tab 📚 Từ điển:**
- Xem toàn bộ thuật ngữ đã học (kỹ năng, địa danh, vật phẩm...)
- **🔄 Phân loại** — AI tự sắp xếp thuật ngữ mới vào đúng danh mục
- Tìm kiếm thuật ngữ, lọc theo danh mục

**Tab 📊 Thống kê:**
- Tiến độ tổng thể (bao nhiêu chương đã dịch)
- Số nhân vật, thuật ngữ đang theo dõi
- Biểu đồ phân bổ từ điển

---

## Tính năng chính

### 🌐 Scraper — Cào truyện từ web

- Hỗ trợ mọi site tiểu thuyết — AI học cấu trúc HTML lần đầu, các lần sau chạy thuần code
- Playwright cho site JS-heavy (Royal Road, Wuxiaworld...), curl_cffi cho site tĩnh
- Tự động resume nếu bị ngắt giữa chừng
- Profile site lưu vào `data/site_profiles.json` — không cần learn lại

### 🔒 Name Lock — Chốt tên nhất quán

Một khi tên đã được dịch (ví dụ: "Xiao Yan" → "Tiêu Viêm"), nó **chốt cứng** xuyên suốt pipeline. Vi phạm bị phát hiện và ghi log tự động.

### 💬 EPS — Theo dõi mức độ thân mật

| Mức | Tên | Ý nghĩa |
|---|---|---|
| 1 | FORMAL | Lạnh lùng — giữ kính ngữ |
| 2 | NEUTRAL | Mặc định |
| 3 | FRIENDLY | Thân thiện — câu thoải mái |
| 4 | CLOSE | Rất thân — bỏ kính ngữ |
| 5 | INTIMATE | Ngôn ngữ riêng tư |

### 🔭 Scout AI

Mỗi N chương, Scout đọc trước và:
- Ghi chú mạch truyện (flashback, alias đang dùng)
- Cập nhật trạng thái cảm xúc nhân vật
- Phát hiện thuật ngữ mới → đề xuất thêm Glossary
- Tóm tắt sự kiện → Arc Memory

### 🧹 Post-processor 14-pass

Làm sạch bản dịch bằng code (không dùng AI): dấu câu, em dash, ellipsis, tách lượt thoại, xóa lời mở đầu/kết thúc do AI tự thêm...

### 🤖 Dual-Model

| Nhiệm vụ | Model |
|---|---|
| Scout / Pre-call / Post-call | Gemini (tiết kiệm quota) |
| Dịch chính (Trans-call) | Gemini hoặc Claude |

```env
# Dùng Claude để dịch chính (chất lượng cao hơn, có phí):
TRANSLATION_PROVIDER=anthropic
TRANSLATION_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Bible System

Bible xây dựng **knowledge base có cấu trúc** từ toàn bộ tác phẩm, gồm 3 tầng:

```
Tầng 1 — Database:       nhân vật, kỹ năng, địa danh, vật phẩm, tổ chức
Tầng 2 — WorldBuilding:  hệ thống tu luyện, quy luật thế giới, địa lý
Tầng 3 — Main Lore:      tóm tắt chương, plot threads, timeline
```

Khi bật `BIBLE_MODE=true`, pipeline dùng Bible thay cho các file riêng lẻ.

**Khởi động Bible qua UI:** Tab **📖 Bible System** → nhấn **Scan** → đợi xong → vào **⚙️ Cài đặt** → bật **"Bật Bible Mode"** → lưu.

**Khởi động Bible qua CLI:**

```bash
python scripts/main.py bible scan
# Sau đó bật BIBLE_MODE=true trong .env
python scripts/main.py translate
```

### Lệnh Bible

```bash
python scripts/main.py bible scan --depth quick|standard|deep
python scripts/main.py bible query "Tiêu Viêm"
python scripts/main.py bible ask "Ai là kẻ thù chính của MC?"
python scripts/main.py bible crossref
python scripts/main.py bible export --format markdown|timeline|characters
python scripts/main.py bible consolidate
python scripts/main.py bible stats
```

| Depth | Tốc độ | Dùng khi nào |
|---|---|---|
| `quick` | Nhanh nhất | Lần đầu, muốn data nhanh |
| `standard` | Trung bình | Dùng hàng ngày ✓ |
| `deep` | Chậm nhất | Cần chất lượng cao, loại duplicate |

---

## Pipeline hoạt động như thế nào?

Mỗi chương đi qua **4 bước**:

```
① PRE-CALL
   Gemini đọc chương → tạo "Chapter Map":
   tên/kỹ năng nào xuất hiện, xưng hô đang active, có flashback không
        ↓
② TRANS-CALL
   Dịch với full context:
   [Hướng dẫn] + [Glossary] + [Nhân vật] + [Chapter Map]
   + [Arc Memory] + [Name Lock Table] + [Bible nếu bật]
        ↓
③ POST-PROCESSOR (14 pass, không dùng AI)
   Làm sạch: dấu câu, lời thừa, system box...
        ↓
④ POST-CALL
   Gemini review: tên sai? pronoun lệch?
   → Extract nhân vật/thuật ngữ mới
   → Lỗi nghiêm trọng → auto-fix pass → retry Trans-call nếu cần
```

**Scout AI** chạy song song mỗi N chương (mặc định N=5).

---

## Xử lý sự cố

### ❌ Không mở được Web UI — "No module named streamlit"

Chưa kích hoạt môi trường ảo. Chạy lại:
```bash
.venv\Scripts\activate
python scripts/run_ui.py
```

### ❌ Thiếu GEMINI_API_KEY

```
ValueError: GEMINI_API_KEY not found
```

Vào tab **⚙️ Cài đặt** → điền API Key → nhấn **💾 Lưu**. Hoặc sửa file `.env`.

### ❌ Rate limit liên tục (lỗi 429)

Có nghĩa là quota miễn phí hết. Giải pháp:

```env
GEMINI_API_KEY_1=AIzaSy...   # thêm key từ tài khoản Google khác
GEMINI_API_KEY_2=AIzaSy...
SUCCESS_SLEEP=60             # nghỉ lâu hơn giữa chương
RATE_LIMIT_SLEEP=120         # chờ lâu hơn khi bị giới hạn
```

### ❌ Tên nhân vật bị dịch sai

```bash
python scripts/main.py fix-names --list    # xem vi phạm
python scripts/main.py fix-names --dry-run # xem trước thay đổi
python scripts/main.py fix-names           # tự động sửa
```

### ❌ Scraper không cào được — site thay đổi cấu trúc

UI → tab **🌐 Cào Truyện** → thêm `!relearn domain.com` trước URL.

Ví dụ: `!relearn royalroad.com https://www.royalroad.com/fiction/12345`

### ❌ Bible: "Not an Aho-Corasick automaton yet"

```bash
python scripts/main.py bible scan
```

### ❌ Windows: lỗi encoding (ký tự Unicode)

```bash
set PYTHONUTF8=1
python scripts/run_ui.py
```

Hoặc thêm vào đầu file `.env`:
```env
PYTHONUTF8=1
```

### ❌ Pipeline chạy chậm

```bash
pip install pyahocorasick   # hoặc
pip install ".[fast]"
```

### ❌ "playwright install" báo lỗi

```bash
pip install playwright
playwright install chromium
```

### ❌ Không thấy thư mục `.venv` sau khi tạo

Đảm bảo bạn đang đứng trong thư mục `NovelPipeline`:
```bash
cd "C:\Users\TÊN_BẠN\Desktop\NovelPipeline"
python -m venv .venv
```

### ❌ `.venv\Scripts\activate` báo lỗi trên PowerShell

Chuyển sang dùng `cmd` thay vì PowerShell. Hoặc chạy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Tất cả tùy chọn cấu hình

Tất cả cài đặt có thể chỉnh qua **⚙️ Cài đặt** trong Web UI, hoặc sửa trực tiếp file `.env`.

### API & Model

| Biến | Mặc định | Mô tả |
|---|---|---|
| `GEMINI_API_KEY` | *(bắt buộc)* | API key Gemini chính |
| `GEMINI_API_KEY_N` | — | Key bổ sung (N = 1, 2, 3...) |
| `FALLBACK_KEY_1/2` | — | Key dự phòng |
| `KEY_ROTATE_THRESHOLD` | `3` | Lỗi liên tiếp trước khi đổi key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model cho Scout/Pre/Post |
| `TRANSLATION_PROVIDER` | `gemini` | `gemini` hoặc `anthropic` |
| `TRANSLATION_MODEL` | *(tự chọn)* | Để trống = dùng mặc định |
| `ANTHROPIC_API_KEY` | — | API key Anthropic (nếu dùng Claude) |

### Tốc độ & Ổn định

| Biến | Mặc định | Mô tả |
|---|---|---|
| `MAX_RETRIES` | `5` | Retry tối đa khi lỗi |
| `SUCCESS_SLEEP` | `30` | Nghỉ (giây) sau mỗi chương |
| `RATE_LIMIT_SLEEP` | `60` | Nghỉ khi bị rate limit |
| `PRE_CALL_SLEEP` | `5` | Nghỉ giữa Pre và Trans |
| `POST_CALL_SLEEP` | `5` | Nghỉ giữa Trans và Post |
| `POST_CALL_MAX_RETRIES` | `2` | Retry Trans khi Post báo lỗi |
| `TRANS_RETRY_ON_QUALITY` | `true` | Retry khi phát hiện lỗi dịch |
| `MIN_CHARS_PER_CHAPTER` | `500` | Chương ngắn hơn → cảnh báo |

### Scout AI

| Biến | Mặc định | Mô tả |
|---|---|---|
| `SCOUT_REFRESH_EVERY` | `5` | Chạy Scout mỗi N chương |
| `SCOUT_LOOKBACK` | `10` | Đọc N chương gần nhất |
| `ARC_MEMORY_WINDOW` | `3` | Số arc entry đưa vào prompt |
| `SCOUT_SUGGEST_GLOSSARY` | `true` | Tự đề xuất thuật ngữ mới |
| `SCOUT_SUGGEST_MIN_CONFIDENCE` | `0.7` | Ngưỡng tin cậy tối thiểu |
| `SCOUT_SUGGEST_MAX_TERMS` | `20` | Thuật ngữ tối đa mỗi Scout |

### Bible System

| Biến | Mặc định | Mô tả |
|---|---|---|
| `BIBLE_MODE` | `false` | Dùng Bible khi dịch |
| `BIBLE_SCAN_DEPTH` | `standard` | `quick` / `standard` / `deep` |
| `BIBLE_SCAN_BATCH` | `5` | Consolidate sau N chương scan |
| `BIBLE_SCAN_SLEEP` | `10` | Nghỉ (giây) giữa các chương |
| `BIBLE_CROSS_REF` | `true` | Kiểm tra mâu thuẫn sau scan |

### Nhân vật & Merge

| Biến | Mặc định | Mô tả |
|---|---|---|
| `ARCHIVE_AFTER_CHAPTERS` | `60` | Archive nhân vật sau N chương vắng |
| `EMOTION_RESET_CHAPTERS` | `5` | Reset emotion state sau N chương |
| `IMMEDIATE_MERGE` | `true` | Merge staging ngay sau mỗi chương |
| `AUTO_MERGE_GLOSSARY` | `false` | Tự động clean glossary cuối pipeline |
| `AUTO_MERGE_CHARACTERS` | `false` | Tự động merge nhân vật cuối pipeline |
| `RETRY_FAILED_PASSES` | `3` | Retry các chương thất bại |
| `BUDGET_LIMIT` | `150000` | Giới hạn token (0 = tắt) |

---

## Cấu trúc thư mục

```
NovelPipeline/
│
├── inputs/{novel_name}/     ← Chương gốc (.txt / .md)
├── outputs/{novel_name}/    ← Bản dịch (*_VN.txt)
├── progress/                ← Trạng thái scraper
│
├── data/
│   ├── site_profiles.json   ← Profile cấu trúc từng site
│   ├── glossary/            ← Từ điển thuật ngữ
│   ├── characters/          ← Profile nhân vật (Active, Archive, Staging)
│   ├── skills/              ← Database kỹ năng
│   ├── memory/              ← Arc Memory + Context Notes
│   └── bible/               ← Bible System data
│
├── src/littrans/
│   ├── config/settings.py   ← Settings dataclass + key management
│   ├── llm/client.py        ← ApiKeyPool, Gemini + Claude clients
│   ├── core/pipeline.py     ← Translation orchestrator
│   ├── context/             ← Glossary, Characters, NameLock, Memory, Bible
│   ├── modules/scraper/     ← Web scraper (Playwright + curl_cffi)
│   ├── tools/
│   │   ├── epub_processor.py  ← EPUB → inputs/{novel}/*.md
│   │   └── epub_exporter.py   ← outputs/{novel}/*_VN.txt → .epub
│   └── ui/
│       ├── app.py           ← Streamlit entry point (router)
│       ├── pages/           ← Từng trang UI riêng
│       ├── pipeline_page.py ← Pipeline 1-click
│       ├── scraper_page.py  ← Scraper UI
│       ├── epub_ui.py       ← EPUB processor UI
│       ├── bible_ui.py      ← Bible System UI
│       └── runner.py        ← Background thread runners
│
├── scripts/
│   ├── run_ui.py            ← Khởi động Web UI
│   └── main.py              ← CLI entry point
│
├── .env                     ← Cấu hình (KHÔNG commit)
└── .env.example             ← Template
```

---

## Dùng CLI (nâng cao)

Dành cho người dùng thành thạo terminal — tất cả tính năng đều có qua Web UI.

```bash
# ── Khởi động ──────────────────────────────────────────────────────────
python scripts/run_ui.py              # Web UI tại http://localhost:8501
python scripts/main.py translate      # Dịch tất cả (CLI)

# ── Dịch ───────────────────────────────────────────────────────────────
python scripts/main.py retranslate 5              # Dịch lại chương 5
python scripts/main.py stats                      # Xem tiến độ

# ── Data management ────────────────────────────────────────────────────
python scripts/main.py clean glossary
python scripts/main.py clean characters --action merge
python scripts/main.py fix-names
python scripts/main.py fix-names --dry-run

# ── Bible System ───────────────────────────────────────────────────────
python scripts/main.py bible scan
python scripts/main.py bible scan --depth deep
python scripts/main.py bible stats
python scripts/main.py bible query "tên entity"
python scripts/main.py bible ask "câu hỏi về truyện"
python scripts/main.py bible crossref
python scripts/main.py bible consolidate
python scripts/main.py bible export --format markdown
```

---

*LiTTrans v5.7 — Powered by Google Gemini & Anthropic Claude*
