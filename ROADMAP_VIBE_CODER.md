# TriLex — Roadmap Vibe Coder Edition 🛠️

> **Cho ai?** Người không rành code, dùng Claude Code làm gần như mọi việc, chỉ cần biết copy-paste prompt và kiểm tra kết quả.
>
> **Cách dùng**: Đi tuần tự từ trên xuống. Mỗi PHASE có nhiều STEP. Mỗi STEP có 4 phần:
> - 🎯 **Mục tiêu** — step này làm xong sẽ có gì
> - 🗣️ **Bạn nói với Claude Code** — copy nguyên block này dán vào CC
> - 🙋 **Bạn cần làm tay** — việc con người, không thể automate
> - ✅ **Kiểm tra** — cách verify step OK trước khi sang step tiếp
>
> **Quy tắc vàng**: Đừng bao giờ skip step. Step 3 hỏng là step 4 sẽ vỡ. Mỗi step xong, commit git ngay.

---

## 📋 Pre-flight Checklist (làm 1 lần duy nhất, trước Phase 1)

Trước khi bắt đầu, đảm bảo máy bạn có:

- [ ] **Python 3.11 hoặc cao hơn** — gõ `python --version` trong terminal
- [ ] **Claude Code đã cài và login** — gõ `claude` trong terminal phải mở được
- [ ] **Git** đã cài — gõ `git --version`
- [ ] **VS Code** (khuyến nghị, không bắt buộc)
- [ ] **Obsidian** đã tải về máy (chưa cần mở)
- [ ] **Bộ QuickTranslator dictionaries** — bạn nói đã có rồi, để sẵn 1 chỗ dễ tìm
- [ ] **Ít nhất 1 API key**: Gemini (free tier OK) hoặc Claude
- [ ] **Quota internet ổn** — vì sẽ download nhiều package

Nếu thiếu cái nào, search Google "cài [tên cái thiếu] Windows/Mac" trước. Đừng nhờ Claude Code làm việc cài đặt hệ thống — dễ hỏng máy.

---

## 🌱 PHASE 0 — Setup môi trường (1 buổi tối, ~2 giờ)

### STEP 0.1 — Tạo folder dự án

🎯 **Mục tiêu**: Có 1 folder `trilex/` trống, mở được bằng Claude Code.

🙋 **Bạn cần làm tay**:
1. Chọn 1 chỗ trên máy có nhiều dung lượng (>5GB free), ví dụ `D:\Projects\` hoặc `~/Projects/`
2. Tạo folder mới tên `trilex`
3. Mở terminal trong folder đó:
   - **Windows**: Vào folder, gõ `cmd` lên thanh địa chỉ → Enter
   - **Mac**: Right-click folder → "New Terminal at Folder"
4. Trong terminal đó, gõ: `claude`
5. Đợi Claude Code mở session

✅ **Kiểm tra**: Claude Code phải hiển thị bạn đang ở folder `trilex` (xem dòng path trên cùng).

---

### STEP 0.2 — Khởi tạo dự án Python

🎯 **Mục tiêu**: Có file `pyproject.toml`, `.gitignore`, `README.md` chuẩn, virtual environment hoạt động.

🗣️ **Bạn nói với Claude Code**:
```
Tôi muốn khởi tạo dự án Python tên "trilex" trong folder hiện tại.
Yêu cầu:
1. Dùng Python 3.11+
2. Quản lý package bằng `uv` (cài uv nếu chưa có)
3. Tạo virtual environment .venv
4. Tạo pyproject.toml chuẩn với metadata cơ bản
5. Tạo .gitignore phù hợp Python project (ignore .venv, __pycache__, *.db, data/, .env)
6. Tạo README.md skeleton (chỉ tiêu đề và 1 dòng mô tả)
7. Khởi tạo git repo và làm initial commit
8. Tạo file .env.example (rỗng, để sau điền)
9. Verify mọi thứ OK bằng cách activate venv và in version Python

Sau khi xong, hãy hỏi tôi confirm trước khi sang bước tiếp.
```

🙋 **Bạn cần làm tay**:
- Trả lời "yes" hoặc "OK" khi Claude Code hỏi confirm cài uv hoặc tạo file
- Nếu Claude Code hỏi tên/email cho git config, cứ điền tên thật của bạn

✅ **Kiểm tra**:
- Trong folder phải có: `pyproject.toml`, `.gitignore`, `README.md`, `.env.example`, `.venv/`, `.git/`
- Gõ `git log` phải thấy 1 commit "Initial commit"
- Không có file `.env` (chỉ có `.env.example`)

---

### STEP 0.3 — Cấu trúc folder cơ bản

🎯 **Mục tiêu**: Có cấu trúc folder theo BLUEPRINT, sẵn sàng nhận code.

🗣️ **Bạn nói với Claude Code**:
```
Tạo cấu trúc folder cho dự án theo BLUEPRINT.md (file này tôi sẽ paste sau).
Tạo các folder rỗng với 1 file .gitkeep trong mỗi folder để git track:

src/trilex/
  core/
    models/
    routing/
    pipeline/
      stages/
    transforms/
  qt_dict/
    importers/
  providers/
  ingest/
    scrapers/
  output/
  persistence/
    migrations/
    repos/
  memory/
  ui/
    pages/
    runners/
  cli/

data/
  dictionaries/
  vault/
  cache/

packs/
  style/
  archetypes/
  examples/
  obsidian_template/

scripts/

tests/
  unit/
  integration/

Tạo file __init__.py rỗng trong mỗi folder Python (src/trilex/...).
Sau đó commit với message "Add project structure".
```

🙋 **Bạn cần làm tay**: Không có. Chỉ ngồi xem Claude Code chạy.

✅ **Kiểm tra**: Mở folder `trilex` trong File Explorer, thấy đủ các folder con. Gõ `git log` thấy 2 commits.

---

### STEP 0.4 — Paste BLUEPRINT làm reference

🎯 **Mục tiêu**: Claude Code biết toàn bộ vision của dự án để tham chiếu.

🙋 **Bạn cần làm tay**:
1. Tải file `BLUEPRINT.md` (file mình đã tạo ở chat trước) vào folder `trilex/`
2. Tải file `ROADMAP_VIBE_CODER.md` (file này) vào folder `trilex/`
3. Tải cả `system prompt JP→VN` và `Ref_SENSORY_LEXICON.md` vào folder `trilex/docs/inspiration/` (tạo folder mới)

🗣️ **Bạn nói với Claude Code**:
```
Trong root folder có file BLUEPRINT.md - đây là kiến trúc tổng thể của dự án.
Trong folder docs/inspiration/ có 2 file system prompt JP→VN và Sensory Lexicon - 
đây là reference style/quality cho output tiếng Việt.

Hãy đọc cả 3 file này, tóm tắt cho tôi nghe trong 5 bullet points để xác nhận 
bạn hiểu đúng vision. Đừng tạo code nào, chỉ đọc và confirm.
```

✅ **Kiểm tra**: Claude Code tóm tắt phải nhắc đến: QT dictionaries, AI polish, 4 routes (ZH→VN, ZH→EN, EN→VN, VN→EN), Obsidian output, single-user. Nếu thiếu → bảo nó đọc lại.

---

## 🧱 PHASE 1 — QT Dictionary Engine (1-2 tuần)

> **Why first?** Đây là trái tim của hệ thống. Nó hoạt động độc lập, không cần API. Làm xong là bạn đã có 1 cái QuickTranslator chạy bằng Python.

### STEP 1.1 — Đặt dictionary files vào đúng chỗ

🎯 **Mục tiêu**: Dictionary files của bạn được TriLex tìm thấy.

🙋 **Bạn cần làm tay** (đây là việc QUAN TRỌNG nhất bạn phải làm tay):
1. Mở folder QuickTranslator của bạn (chỗ bạn cài QT trên máy)
2. Tìm các file `.txt` này (KHÔNG sửa tên, để nguyên):
   - `VietPhrase.txt` (file lớn nhất, ~50-100MB)
   - `Names.txt` và `Names2.txt` (nếu có)
   - `ChinesePhienAmWords.txt`
   - `LuatNhan.txt`
   - `Pronouns.txt` (nếu có)
   - `LacViet.txt` (nếu có)
   - `Babylon.txt` (nếu có, dành cho ZH→EN)
3. Copy tất cả vào `trilex/data/dictionaries/`
4. Mở 1 file bằng Notepad++ (hoặc VS Code) để check encoding — phải là **UTF-8**. Nếu là UTF-16 hoặc GBK, save lại thành UTF-8.

🗣️ **Bạn nói với Claude Code**:
```
Tôi đã copy các file dictionary của QuickTranslator vào data/dictionaries/.
Hãy:
1. Liệt kê các file trong đó
2. Đọc 10 dòng đầu của mỗi file và in ra cho tôi xem
3. Báo encoding của mỗi file
4. Báo size của mỗi file

KHÔNG modify hay convert file nào. Chỉ inspect.
```

✅ **Kiểm tra**:
- Claude Code phải liệt kê được ít nhất 3 file (`VietPhrase.txt`, `Names.txt`, `ChinesePhienAmWords.txt`)
- Encoding tất cả phải là `utf-8`
- 10 dòng đầu phải có format `汉字=Hán Việt` hoặc tương tự
- Nếu file nào lỗi encoding → quay lại làm bằng tay step trên

---

### STEP 1.2 — Build QT Dictionary Parser

🎯 **Mục tiêu**: Code Python đọc được tất cả file dictionary, parse thành data structure.

🗣️ **Bạn nói với Claude Code**:
```
Bây giờ build module qt_dict để parse các file dictionary của QuickTranslator.

Yêu cầu:
1. File src/trilex/qt_dict/parser.py
2. Parse được các format:
   - VietPhrase.txt: dòng "汉字=nghĩa1;nghĩa2;nghĩa3" (separator có thể là ; hoặc /)
   - Names.txt, Names2.txt: tương tự
   - ChinesePhienAmWords.txt: dòng "汉=hán" (single char → Hán Việt)
   - LuatNhan.txt: dòng "不比{0}强=không mạnh bằng {0}" (có placeholder)
   - Pronouns.txt: dòng "我=ta" hoặc tương tự
3. Skip dòng comment (bắt đầu bằng #) và dòng rỗng
4. Auto-detect separator (; hay /) bằng cách đếm trong file
5. Trả về object QTDictionary với:
   - .entries: dict {chinese: list[vietnamese]}
   - .meta: file source, count, separator detected
6. Handle encoding: thử utf-8 trước, fallback utf-16 và GBK
7. Log warning cho dòng không parse được (nhưng không crash)

Cũng tạo:
- tests/unit/test_qt_dict.py với 5-10 test case (tạo file dictionary giả nhỏ trong test)
- Chạy pytest và đảm bảo pass

Sau khi xong, demo cho tôi xem bằng cách load thử VietPhrase.txt và in:
- Tổng số entries
- 5 entries random
- 5 entries dài nhất (Chinese key dài nhất)
```

🙋 **Bạn cần làm tay**: Chỉ confirm khi Claude Code hỏi.

✅ **Kiểm tra**:
- `pytest tests/unit/test_qt_dict.py` phải pass tất cả
- Demo load thật phải in ra `Total entries: 800000+` (hoặc gần con số bạn expect)
- 5 entries random phải có nghĩa (không phải toàn rỗng/lỗi)

⚠️ **Nếu lỗi**:
- "MemoryError" → file quá to, bảo Claude Code dùng generator/streaming thay vì load full
- "UnicodeDecodeError" → encoding sai, kiểm tra lại STEP 1.1
- Parse được rất ít entry → separator detection sai, paste 20 dòng đầu file cho Claude xem

---

### STEP 1.3 — Build Aho-Corasick Automaton

🎯 **Mục tiêu**: Có engine match nhanh — quét 1 đoạn ZH dài, tìm tất cả từ trong dict trong vài ms.

🗣️ **Bạn nói với Claude Code**:
```
Bây giờ build module src/trilex/qt_dict/automaton.py.

Yêu cầu:
1. Cài package `pyahocorasick` (thêm vào pyproject.toml)
2. Class AhoMatcher:
   - .build(entries: dict[str, str]) - build automaton từ dict
   - .find_all(text: str) -> list[Match] - tìm tất cả match (start, end, key, value)
   - .find_longest_non_overlapping(text) -> list[Match] - longest match, no overlap
3. Cache automaton ra file (pickle) vì build từ 800k entries mất thời gian.
   - Lưu vào data/cache/automaton_{hash}.pkl
   - Hash = md5 của file dict gốc (để invalidate khi dict thay đổi)
4. Có method .stats() in ra: số nodes, memory dùng, time build

Test với:
- tests/unit/test_automaton.py (5-10 case)
- Demo: build từ VietPhrase.txt thật, query 1 đoạn ZH 500 chars, in time + matches

Note: Lần đầu build sẽ chậm (10-30 giây). Lần 2 phải <1 giây nhờ cache.
```

✅ **Kiểm tra**:
- `pytest tests/unit/test_automaton.py` pass
- Demo: Query 1 đoạn ZH thật phải <100ms
- Chạy demo lần 2: phải nhanh hơn nhiều nhờ cache hit
- File `data/cache/automaton_*.pkl` xuất hiện

---

### STEP 1.4 — Build QT Applier (the "QT pass")

🎯 **Mục tiêu**: Có function nhận text ZH, trả về convert text Hán-Việt.

🗣️ **Bạn nói với Claude Code**:
```
Bây giờ build src/trilex/qt_dict/applier.py - đây là core logic của "QT pass".

Yêu cầu:
1. Class QTApplier:
   - __init__(dict_dir: Path): load tất cả dict từ folder, build automatons
   - .convert(text: str, custom_glossary: dict = None) -> str
2. Logic convert (theo thứ tự ưu tiên, longest-match within each tier):
   Tier 1: custom_glossary (per-novel locked terms) - HIGHEST
   Tier 2: LuatNhan patterns (apply trước vì có placeholder)
   Tier 3: Names.txt + Names2.txt
   Tier 4: VietPhrase.txt (main)
   Tier 5: LacViet.txt (nếu có)
   Tier 6: ChinesePhienAmWords.txt (single char fallback) - LOWEST
3. Trong mỗi tier: longest non-overlapping match
4. Char nào không match dict nào → giữ nguyên (hoặc convert qua Pronouns.txt nếu có)
5. Multi-meaning entries: lấy nghĩa đầu tiên (sau separator) - mode "VietPhrase một nghĩa"
6. Có flag verbose: log tier nào match cho từ nào

Test:
- tests/unit/test_applier.py với case cụ thể:
  Input: "李青走进了青云宗"
  Expected: "Lý Thanh đi vào Thanh Vân tông" (hoặc tương tự)
- Chạy với 1 đoạn ZH thật ~500 chars, in side-by-side: original | converted
- Performance: <500ms cho đoạn 1000 chars

Lưu ý: Đây không phải dịch hoàn hảo, chỉ convert thô. Đó là design intent.
```

🙋 **Bạn cần làm tay**: 
- Test thử với 1 đoạn truyện ZH bạn quen thuộc (~500 chars)
- Đối chiếu output với QuickTranslator desktop xem có ra giống không
- Nếu khác nhiều → có thể priority order sai, báo Claude Code điều chỉnh

✅ **Kiểm tra**:
- Test pass
- Output convert phải đọc được như Wikidich/Sangtacviet
- Tên riêng (Lý Thanh, Thanh Vân Tông) phải dịch đúng

🎉 **Mốc quan trọng**: Sau STEP 1.4, bạn đã có 1 cái **QuickTranslator chạy bằng Python**! Free, offline, không cần AI. Đây là 50% giá trị của dự án.

---

### STEP 1.5 — CLI để test convert

🎯 **Mục tiêu**: Có command line để bạn dùng QT pass nhanh từ terminal.

🗣️ **Bạn nói với Claude Code**:
```
Tạo CLI đơn giản dùng Typer để test QT pass.

File src/trilex/cli/main.py với command:
  trilex convert <input.txt> [--output output.txt] [--custom-dict glossary.txt]

Behavior:
- Đọc input file (UTF-8)
- Apply QT pass
- Ghi output ra file (hoặc stdout nếu không có --output)
- In stats: time, char count input/output, số match per tier

Cũng add command:
  trilex dict-info     # In stats về dictionaries đang load (count, source files)

Update pyproject.toml để có script entry point:
  trilex = "trilex.cli.main:app"

Sau cài, gõ `trilex --help` phải hoạt động.
```

🙋 **Bạn cần làm tay**:
1. Test thử: tạo file `test.txt` chứa 1 chương ZH, chạy `trilex convert test.txt`
2. So sánh output với QT desktop hoặc Wikidich
3. Nếu OK → commit

✅ **Kiểm tra**: 
- `trilex convert test.txt` chạy được, ra output Hán-Việt readable
- `trilex dict-info` hiển thị số entry của mỗi dict file

---

## 🤖 PHASE 2 — LLM Polish Pipeline (1-2 tuần)

### STEP 2.1 — Setup API key

🎯 **Mục tiêu**: TriLex gọi được Gemini API.

🙋 **Bạn cần làm tay**:
1. Vào https://aistudio.google.com/app/apikey
2. Tạo API key mới (free tier OK cho thử nghiệm)
3. Copy API key
4. Mở file `.env.example`, save as `.env` (cùng folder)
5. Mở `.env`, thêm dòng:
   ```
   GEMINI_API_KEY=AIza...your_key_here
   ```
6. **QUAN TRỌNG**: Đảm bảo `.env` đã trong `.gitignore` (kiểm tra `.gitignore` có dòng `.env`)
7. ⚠️ **KHÔNG BAO GIỜ commit file `.env` lên git** — leak API key cực nguy hiểm

🗣️ **Bạn nói với Claude Code**:
```
Tôi đã đặt API key Gemini vào file .env (variable GEMINI_API_KEY).

Build module config:
1. src/trilex/config.py dùng pydantic-settings
2. Load từ .env, validate có GEMINI_API_KEY
3. Có settings: default_model="gemini-2.5-flash", request_timeout=60, max_retries=3
4. Verify .env nằm trong .gitignore
5. Tạo command CLI: `trilex check-config` in ra (đã mask key, chỉ show 6 char đầu + cuối)

KHÔNG được hardcode API key vào code, KHÔNG được log full key, 
KHÔNG được commit .env. Verify lại bằng cách check git status sau khi xong.
```

✅ **Kiểm tra**:
- `trilex check-config` chạy được, in ra `GEMINI_API_KEY=AIza...XXXX` (mask)
- `git status` KHÔNG hiển thị `.env` (phải bị ignore)
- Nếu `.env` bị track → STOP NGAY, bảo Claude Code remove khỏi git history

---

### STEP 2.2 — Provider Base + Gemini Adapter

🎯 **Mục tiêu**: Có abstraction để gọi LLM (sau này thêm Claude/DeepSeek dễ).

🗣️ **Bạn nói với Claude Code**:
```
Build src/trilex/providers/

Yêu cầu:
1. providers/base.py:
   - Abstract class LLMProvider
   - Methods: complete(prompt, system=None, max_tokens=4000) -> ProviderResponse
   - ProviderResponse có: text, tokens_used, model, latency_ms, finish_reason
   - Async methods (dùng asyncio + httpx)
   
2. providers/gemini.py:
   - Implement LLMProvider cho Gemini
   - Dùng google-generativeai package (cài vào pyproject)
   - Auto retry với exponential backoff (max 3 lần)
   - Handle các lỗi: quota exceeded, safety block, timeout
   - Log mọi call (tokens, latency) ra file data/logs/llm_calls.jsonl

3. tests/unit/test_providers.py:
   - Mock test cho base
   - Skip integration test với Gemini thật (dùng pytest.mark.integration)

4. CLI test: 
   - `trilex test-llm "Dịch sang tiếng Việt: 你好世界"` 
   - In response + stats

Sau khi xong, demo bằng cách chạy CLI test thật với Gemini.
```

🙋 **Bạn cần làm tay**:
- Chạy `trilex test-llm "Dịch: 你好"` để verify
- Nếu lỗi quota → bình thường, đợi reset hoặc dùng key khác

✅ **Kiểm tra**:
- Có response từ Gemini
- File `data/logs/llm_calls.jsonl` có entry mới
- API key vẫn không leak vào log

---

### STEP 2.3 — Style Pack cho Tu Tiên

🎯 **Mục tiêu**: Có file YAML chứa "style guide" cho thể loại tu tiên (vocab, examples).

🗣️ **Bạn nói với Claude Code**:
```
Tạo packs/style/tu_tien.vn.yaml - style pack cho dịch tu tiên sang tiếng Việt.

Schema YAML:
  name: "Tu Tiên - Vietnamese"
  source_langs: [zh]
  target_lang: vn
  
  vocabulary_rules:
    prefer_han_viet: true
    examples:
      - {zh: "修为", vn: "tu vi"}  # NOT "khả năng tu luyện"
      - {zh: "境界", vn: "cảnh giới"}
      - {zh: "突破", vn: "đột phá"}
  
  realm_ladder:  # 9-tier xianxia chuẩn
    - {zh: "练气", vn: "Luyện Khí"}
    - {zh: "筑基", vn: "Trúc Cơ"}
    - {zh: "金丹", vn: "Kim Đan"}
    - {zh: "元婴", vn: "Nguyên Anh"}
    - {zh: "化神", vn: "Hóa Thần"}
    - {zh: "炼虚", vn: "Luyện Hư"}
    - {zh: "合体", vn: "Hợp Thể"}
    - {zh: "大乘", vn: "Đại Thừa"}
    - {zh: "渡劫", vn: "Độ Kiếp"}
  
  honorifics:
    - {zh: "道友", vn: "đạo hữu"}
    - {zh: "前辈", vn: "tiền bối"}
    - {zh: "师父", vn: "sư phụ"}
    # ...thêm nhiều
  
  sect_suffixes: ["tông", "phái", "môn", "các", "lâu", "sơn trang"]
  
  banned_phrases:  # Cấm AI dịch như sau
    - "một cách"
    - "đang được"
    - "vẻ đẹp của"
  
  preferred_phrases:
    - "linh khí" (NOT "năng lượng tâm linh")
    - "pháp bảo" (NOT "vật phẩm phép thuật")
  
  few_shot_examples:  # 3-5 đoạn mẫu chất lượng cao
    - source: |
        李青走进青云宗，心中既紧张又兴奋。
      target: |
        Lý Thanh bước vào Thanh Vân tông, trong lòng vừa hồi hộp vừa hưng phấn.
    # ...

Build src/trilex/core/style_pack.py để load + validate YAML này.
Tạo tests/unit/test_style_pack.py.

Chứa rich data thật, không placeholder. Đây là spec quan trọng cho quality output.
```

🙋 **Bạn cần làm tay**:
- Đọc qua file YAML Claude Code tạo
- Bổ sung từ vựng tu tiên bạn quen thuộc (nếu thấy thiếu)
- Sửa lại few_shot examples nếu thấy chưa đúng style

✅ **Kiểm tra**:
- File `packs/style/tu_tien.vn.yaml` tồn tại
- `pytest tests/unit/test_style_pack.py` pass
- File chứa **realm ladder đầy đủ 9 tier**, **ít nhất 30 từ vựng**, **3+ few-shot examples**

---

### STEP 2.4 — Polish Stage (LLM call chính)

🎯 **Mục tiêu**: Function nhận (ZH original + convert text + style pack) → polish bằng LLM.

🗣️ **Bạn nói với Claude Code**:
```
Build src/trilex/core/pipeline/stages/polish.py - đây là stage gọi LLM polish.

Function signature:
  async def polish(
      original: str,           # ZH gốc
      converted: str,           # Output từ QT pass
      style_pack: StylePack,
      glossary: list[Term] = [],   # Locked terms
      provider: LLMProvider,
  ) -> PolishResult

PolishResult chứa:
  text: str
  tokens_used: int
  warnings: list[str]   # nếu detect drift, missing translation, etc.

Logic:
1. Build prompt với:
   - System prompt: "Bạn là dịch giả tu tiên..."
   - Style guide từ style_pack
   - Glossary slice (chỉ terms xuất hiện trong chương)
   - Few-shot examples từ pack
   - Instruction: polish convert thành VN mượt
   - Original ZH (làm reference)
   - Convert text (làm bulk)
2. Call provider
3. Validate output:
   - Không có HTML/markdown garbage
   - Tên trong glossary giữ nguyên (regex check)
   - Không có chữ Hán còn sót lại
   - Length reasonable (0.8x - 1.5x convert length)
4. Return PolishResult

Tests:
- Unit test với mock provider
- Integration test với Gemini thật (skip mặc định, mark @pytest.mark.integration)

CLI demo:
  trilex polish-demo <chapter.txt>
  → Convert + Polish, in 3-column: Original | Convert | Polish
```

🙋 **Bạn cần làm tay**:
- Chạy demo với 1 chương ZH thật ngắn (500-1000 chars)
- Đọc output polish: có mượt hơn convert không? Tên có sai không?
- Nếu chất lượng kém → bảo Claude Code điều chỉnh prompt

✅ **Kiểm tra**:
- Demo chạy thành công
- Output polish phải tốt hơn convert raw
- Không có chữ Hán sót
- Tên riêng được giữ đúng

🎉 **Mốc quan trọng**: Sau STEP 2.4, bạn đã có **toàn bộ pipeline ZH→VN end-to-end**. Mọi thứ sau là polish + UX.

---

### STEP 2.5 — Pipeline Orchestrator

🎯 **Mục tiêu**: Function `translate_chapter()` chạy full pipeline 1 chương.

🗣️ **Bạn nói với Claude Code**:
```
Build src/trilex/core/pipeline/orchestrator.py.

Function chính:
  async def translate_chapter(
      source_text: str,
      project_config: ProjectConfig,
      mode: Literal["convert", "polish", "side_by_side"] = "polish",
  ) -> ChapterResult

Stages chạy:
  1. Pre-process (clean junk, normalize)
  2. QT pass (apply dictionaries) [SKIP nếu source != "zh"]
  3. Polish (LLM call) [SKIP nếu mode == "convert"]
  4. Post-process (clean punctuation)

ChapterResult:
  source_text, convert_text, polished_text
  state, warnings, stats (tokens, time)

Lưu mọi thứ vào ChapterResult, không persist (persist là việc của repo).

CLI:
  trilex translate <input.txt> [--mode polish] [--style-pack tu_tien.vn]
  → In ra polished result, save log

Test với 1 chương thật, đo time + token.
```

✅ **Kiểm tra**: Translate 1 chương ~2000 chars, time <30s, token <2000.

---

## 💾 PHASE 3 — Persistence (SQLite + Vault) (~1 tuần)

### STEP 3.1 — Database Setup

🎯 **Mục tiêu**: SQLite database với schema cho Project, Chapter, Term, Job.

🗣️ **Bạn nói với Claude Code**:
```
Setup persistence layer dùng SQLAlchemy 2.0 + Alembic.

1. Cài: sqlalchemy, alembic, sqlmodel (optional wrapper)
2. src/trilex/persistence/db.py: connection setup, session maker
3. src/trilex/persistence/models.py: SQL models cho:
   - Project (id, name, slug, source_lang, target_lang, genre, vault_path, created_at)
   - Chapter (id, project_id FK, index, source_text, convert_text, polished_text, state, ...)
   - Term (id, project_id FK nullable, category, locked_zh, locked_vn, locked_en, ...)
   - Job (id, project_id FK, type, status, progress, error, created_at, ...)
4. Init Alembic, create initial migration
5. CLI:
   - `trilex db init` - create db file + run migrations
   - `trilex db status` - show migration state

Database file: data/trilex.db

Test: Tạo db, insert mock data, query lại.
```

✅ **Kiểm tra**: 
- `trilex db init` tạo file `data/trilex.db`
- Mở bằng SQLite Browser thấy đủ tables

---

### STEP 3.2 — Repositories

🎯 **Mục tiêu**: CRUD cho mỗi model.

🗣️ **Bạn nói với Claude Code**:
```
Build src/trilex/persistence/repos/:
- project_repo.py: create, get, list, update, delete projects
- chapter_repo.py: + bulk insert, get by index range, count by state
- term_repo.py: + search by zh/vn, find conflicts, bulk insert from QT dict
- job_repo.py: + get pending, mark running, mark complete

Mỗi method async. Dùng dependency injection cho session.

Tests cho mỗi repo (có db test riêng, dùng SQLite in-memory).
```

✅ **Kiểm tra**: `pytest tests/unit/test_repos.py` pass.

---

### STEP 3.3 — Vault Writer (Obsidian Output)

🎯 **Mục tiêu**: Mỗi chương dịch xong → ghi ra `.md` file trong vault, format Obsidian-friendly.

🗣️ **Bạn nói với Claude Code**:
```
Build src/trilex/output/obsidian.py.

Function chính:
  def write_chapter(
      vault_path: Path,
      project_slug: str,
      chapter: Chapter,
  )

Output structure:
  {vault_path}/projects/{project_slug}/chapters/{index:04d}.md

Markdown format:
  ---
  chapter: 47
  title:
    zh: "..."
    vn: "..."
  state: polished
  characters: ["[[Lý Thanh]]", "[[Trương Lão]]"]
  ---
  
  # Chương 47 - {title.vn}
  
  > [!source]- Bản gốc
  > {original ZH}
  
  > [!info]- Bản convert
  > {convert text}
  
  ## Bản dịch
  
  {polished text với wiki-links cho characters}

Cũng tạo:
- write_character(vault, project, character) - tạo file character/{name}.md
- write_project_dashboard(vault, project) - file _dashboard.md với Dataview queries
- ensure_vault_structure(vault, project) - tạo folder structure ban đầu

Test: write 3 chương fake, verify file được tạo, format đúng.
```

🙋 **Bạn cần làm tay**:
1. Mở Obsidian
2. "Open folder as vault" → chọn `data/vault/`
3. Verify thấy folder `projects/test_project/chapters/0001.md`
4. Click thử wiki-link, callout, frontmatter — tất cả phải work

✅ **Kiểm tra**: 
- File tạo đúng location
- Mở trong Obsidian render đẹp
- Wiki-links clickable

---

## 🖥️ PHASE 4 — Streamlit UI (~1 tuần)

### STEP 4.1 — Streamlit App Skeleton

🎯 **Mục tiêu**: Web UI tối thiểu chạy được.

🗣️ **Bạn nói với Claude Code**:
```
Setup Streamlit app: src/trilex/ui/app.py

Pages (multi-page app):
  pages/01_Library.py - list projects, button "New Project"
  pages/02_Translate.py - paste text, choose mode, button Translate
  pages/03_Jobs.py - active job monitoring (refresh every 2s)
  pages/04_Dictionary.py - upload/manage QT dict files
  pages/05_Glossary.py - per-novel terms editor
  pages/06_Settings.py - API key, model selection (read from .env)

Sidebar: project selector (active project)

Run command: `streamlit run src/trilex/ui/app.py`

Page Translate: 
  - Text area input (ZH/EN)
  - Dropdown: source/target lang, mode, style pack
  - Button "Translate Now"
  - Output: 2 columns Original | Polished, copy buttons mỗi cột
  - Progress bar during translation

Test: chạy streamlit, paste 1 đoạn ZH ngắn, click translate, thấy result.
```

🙋 **Bạn cần làm tay**:
- Mở browser tại `http://localhost:8501`
- Click qua các pages, verify load không lỗi
- Test translate nhanh 1 đoạn

✅ **Kiểm tra**: UI chạy, các page mở được, translate end-to-end OK.

---

### STEP 4.2 — Project Workflow Integration

🎯 **Mục tiêu**: Tạo project → import chapters → batch translate → output vault.

🗣️ **Bạn nói với Claude Code**:
```
Wire up full workflow trong UI:

Library page:
- Form "New Project": name, source_lang, target_lang, genre, vault_path
- List projects với link click → switch active project

Translate page (when project active):
- Tab 1 "Single Chapter": paste text or pick file → translate → save to vault
- Tab 2 "Batch": pick folder hoặc range, translate background, monitor in Jobs page
- Tab 3 "From URL": paste URL truyện → scrape → translate (chỉ stub, sẽ làm sau)

Jobs page:
- Live table: job_id, type, project, progress %, status, ETA
- Click row để xem detail/cancel

Backend: BackgroundJobRunner trong src/trilex/ui/runners/
- Dùng threading.Thread (đơn giản, đủ cho single user)
- Update progress vào DB, UI poll DB

Test: 
1. Tạo project test
2. Paste 1 chương ZH ngắn → translate → verify file tạo trong vault
3. Mở Obsidian → check file
```

✅ **Kiểm tra**: End-to-end flow work: create project → translate → file xuất hiện trong Obsidian vault.

---

## 🎨 PHASE 5 — Polish & Other Routes (~1 tuần)

### STEP 5.1 — Glossary Auto-extraction

🎯 **Mục tiêu**: Khi dịch chương đầu, AI auto-extract tên + thuật ngữ vào glossary.

🗣️ **Bạn nói với Claude Code**:
```
Build memory/scout.py - lightweight scout cho new term extraction.

Function:
  async def scout_terms(chapter, existing_glossary, provider) -> list[NewTerm]

Logic:
- Send LLM 1 prompt: "Đây là chương ZH + bản dịch. List các tên riêng + thuật ngữ NEW chưa có trong glossary đã cho. Output JSON."
- Parse JSON response
- Dedupe with existing
- Return list NewTerm để user confirm

UI Glossary page: 
- "Pending Review" section: hiển thị NewTerm chờ user accept/reject/edit
- Khi accept: lưu vào Term table với source="scout_extracted"

Run scout sau mỗi 5 chương đã dịch (configurable).

Test: dịch 5 chương, scout phải tìm được character names.
```

✅ **Kiểm tra**: 5 chương đầu → scout đề xuất ít nhất 3-5 character names, accept rồi dịch chương 6 thấy names lock đúng.

---

### STEP 5.2 — EN→VN Route (Port từ LiTTrans logic)

🎯 **Mục tiêu**: Dịch English novels (RoyalRoad, isekai LitRPG) sang Việt.

🗣️ **Bạn nói với Claude Code**:
```
Add route EN → VN.

Khác biệt với ZH→VN:
- KHÔNG dùng QT pass (English không có Hán-Việt)
- LLM dịch trực tiếp (full translation, not polish)
- Style pack riêng: packs/style/litrpg.vn.yaml (cho LitRPG genre)

Build:
- packs/style/litrpg.vn.yaml: rules cho LitRPG (giữ [Skill], [Stat] format, etc.)
- Update orchestrator để route đúng pipeline based on (source_lang, target_lang)
- UI Translate: dropdown direction tự update style pack candidates

Test: dịch 1 chương RoyalRoad ngắn EN → VN.
```

✅ **Kiểm tra**: EN chapter dịch sang VN giữ format LitRPG ([Stat], [Skill]), style mượt.

---

### STEP 5.3 — ZH→EN, VN→EN Routes

🎯 **Mục tiêu**: Hoàn thành 4 routes.

🗣️ **Bạn nói với Claude Code**:
```
Add 2 routes còn lại:
- ZH → EN (no Hán-Việt shortcut, LLM dịch thẳng)
- VN → EN

Tạo style packs:
- packs/style/tu_tien.en.yaml
- packs/style/general.en.yaml

Update routing logic.

Test mỗi route với 1 chương.
```

✅ **Kiểm tra**: 4 routes đều dịch được.

---

### STEP 5.4 — Copy/Export Helpers

🎯 **Mục tiêu**: Dễ dàng copy bản dịch lên truyendichai/sstruyen/wikidich.

🗣️ **Bạn nói với Claude Code**:
```
Add export features ở UI:

Per chapter:
- Button "Copy Plain Text" (clean, no markdown)
- Button "Copy with BBCode" (cho forums)
- Button "Download .txt"

Per project:
- Button "Export as EPUB" - bundle toàn bộ chapters thành 1 EPUB
  Dùng package `EbookLib`
- Button "Export as ZIP" - tất cả .md files

Test: copy 1 chương, paste vào notepad, verify clean text. Export EPUB, mở bằng Calibre.
```

✅ **Kiểm tra**: Copy được text sạch, EPUB export mở được.

---

## 🐛 PHASE 6 — Testing & Hardening (1 tuần)

### STEP 6.1 — Comprehensive Bug Sweep

🎯 **Mục tiêu**: Tìm và fix các bug ẩn.

🗣️ **Bạn nói với Claude Code**:
```
Bug sweep toàn bộ codebase:

1. Run pytest với --cov, identify modules có coverage <80%, viết thêm test
2. Run black + ruff, fix lint issues
3. Run mypy --strict, fix type errors
4. Test edge cases:
   - Chương rỗng
   - Chương có chữ ngoại lai (Anh, số, ký hiệu)
   - Chương cực dài (>10k chars) - phải split nếu cần
   - Dictionary file lỗi format
   - API quota exceeded
   - Network timeout
   - SQLite locked
5. Test concurrency: 5 jobs cùng chạy
6. Memory leak: dịch 100 chương liên tiếp, monitor RAM

Output: file BUGS_FOUND.md liệt kê issues, fix một loạt.
```

🙋 **Bạn cần làm tay**:
- Đọc BUGS_FOUND.md
- Confirm fix nào để Claude Code làm
- Test lại sau khi fix

✅ **Kiểm tra**: 
- Coverage >80%
- Không có mypy error
- 100 chương test pass không crash

---

### STEP 6.2 — Error Handling & Recovery

🎯 **Mục tiêu**: App không crash khi gặp lỗi, có thể resume.

🗣️ **Bạn nói với Claude Code**:
```
Hardening errors:

1. Mọi LLM call phải retry (3 lần, exp backoff)
2. Job failure không corrupt data: dùng transactions, rollback nếu fail
3. Resume capability: nếu dịch batch đến chương 50/100 thì crash, restart phải tiếp từ 51
4. Graceful degradation: API down → fallback sang convert mode (mode A)
5. UI: hiển thị error message rõ ràng, không stack trace
6. Logging: rotate logs (max 10 file, 10MB mỗi file)

Test crash scenarios:
- Kill process giữa chừng → restart, verify state OK
- Hết quota → behavior đúng
- Network down → queue để retry
```

✅ **Kiểm tra**: Mô phỏng crash, verify không mất data.

---

### STEP 6.3 — Documentation

🎯 **Mục tiêu**: README + user guide để 6 tháng sau bạn vẫn dùng được.

🗣️ **Bạn nói với Claude Code**:
```
Viết documentation:

1. README.md root:
   - Tổng quan project (1 đoạn)
   - Features chính
   - Quick start (5 bước cài + dịch chương đầu)
   - Screenshots (chừa placeholder, tôi sẽ chụp)
   - Tech stack
   - License

2. docs/USER_GUIDE.md:
   - Cài đặt chi tiết
   - Setup QT dictionaries
   - Setup API keys
   - Tạo project mới
   - Dịch chương đầu
   - Dùng Obsidian vault
   - Glossary management
   - Export

3. docs/TROUBLESHOOTING.md:
   - Lỗi thường gặp + cách fix

4. docs/ARCHITECTURE.md:
   - Tóm tắt từ BLUEPRINT, technical
```

🙋 **Bạn cần làm tay**: Đọc, sửa lại từ ngữ cho đúng tone, chụp screenshots.

✅ **Kiểm tra**: Người lạ đọc README có làm được Quick Start không.

---

## 🎉 PHASE 7 — Ship It

### STEP 7.1 — Final Test với Truyện Thật

🎯 **Mục tiêu**: Dịch 1 quyển truyện thật end-to-end để validate.

🙋 **Bạn cần làm tay**:
1. Chọn 1 truyện ZH bạn quen (best: bạn đã đọc bản dịch hay rồi để compare)
2. Tạo project mới
3. Import 50 chương đầu
4. Translate batch
5. Đọc bản dịch trong Obsidian
6. So sánh với bản dịch của truyendichai/sstruyen
7. Note các vấn đề chất lượng

🗣️ **Bạn nói với Claude Code (sau khi note)**:
```
Tôi đã test với truyện thật. Issues phát hiện:
[paste your notes]

Hãy phân tích, đề xuất fix, và implement.
```

✅ **Kiểm tra**: Bản dịch ngang hoặc tốt hơn truyendichai cho cùng chương.

---

### STEP 7.2 — Backup & Maintenance Plan

🎯 **Mục tiêu**: Không mất data, dễ update.

🗣️ **Bạn nói với Claude Code**:
```
Setup:
1. Auto-backup: script bash/python backup data/trilex.db + data/vault hàng ngày
2. Update script: trilex update (pull git, run migrations, reload deps)
3. Health check: trilex doctor (check API key, dict files, db, disk space)
4. Cron job example trong docs cho người muốn schedule
```

✅ **Kiểm tra**: Chạy `trilex doctor` ra healthy report.

---

## 📊 Quy tắc Vàng cho Vibe Coder

### Khi nào commit git?
**Sau MỖI step xong và test pass.** Nếu Claude Code không tự commit, bảo nó.

### Khi nào revert?
Nếu một step phá hỏng cái trước:
```
git log --oneline    # xem các commits gần nhất
git revert HEAD       # undo commit cuối (an toàn)
# hoặc
git reset --hard HEAD~1   # xóa commit cuối (nguy hiểm, chỉ khi chắc)
```

### Cách yêu cầu Claude Code fix bug
KHÔNG nói: "Code không chạy, fix đi"
NÓI: 
```
Khi tôi chạy lệnh: trilex translate test.txt
Tôi gặp lỗi này:
[paste full error]

File liên quan: src/trilex/...
Tôi expect: output là VN polished
Thực tế: crash với traceback trên

Hãy debug và fix.
```

### Khi Claude Code suggest gì lạ
- "Cài thêm package X" — OK nếu hợp lý, hỏi tại sao nếu không
- "Refactor toàn bộ module Y" — STOP, hỏi tại sao trước, scope creep nguy hiểm
- "Xóa file Z" — luôn xác nhận, đảm bảo có git backup trước
- "Sửa file ngoài project" — TUYỆT ĐỐI KHÔNG, chỉ động trong folder `trilex/`

### Quản lý expectation
- **Phase 0-1**: 1-2 tuần. Mới bắt đầu, đừng nản.
- **Phase 2-3**: 2 tuần. Mọi thứ work cơ bản. Lúc này dự án ~50% xong.
- **Phase 4-5**: 2 tuần. Có UI, có 4 routes. ~80% xong.
- **Phase 6-7**: 1-2 tuần. Polish, ship.

**Tổng: 6-8 tuần làm part-time** (1-2 giờ/ngày). Full-time có thể xong trong 3-4 tuần.

Đừng so sánh tốc độ với người khác. Vibe coding với Claude Code là approach mới — bạn là director, không phải coder. Skill của bạn là **biết yêu cầu cái gì + biết verify**, không phải gõ code.

---

## 🆘 Khi nào bí, hỏi Claude (chat) thay vì Claude Code

Claude Code giỏi: implement code, fix bug cụ thể, refactor file
Claude (chat) giỏi: design decision, debate kiến trúc, giải thích concept

**Hỏi chat khi**:
- "Step này có nhất thiết không?"
- "Tại sao dùng SQLite mà không Postgres?"
- "Style pack nên có những gì?"
- "Dự án mình có vấn đề gì không?"
- Bí kỹ thuật mà Claude Code không hiểu yêu cầu

**Đừng hỏi chat**:
- "Viết code cho tôi" → việc của Code
- "Tại sao file này lỗi?" → Code thấy file, chat không

---

## ✅ Definition of Done

Dự án "xong" khi:
- [ ] Dịch được 4 routes (ZH→VN, ZH→EN, EN→VN, VN→EN)
- [ ] QT dict pass hoạt động (convert mode work standalone)
- [ ] LLM polish hoạt động với Gemini
- [ ] Streamlit UI có 6 pages, tất cả functional
- [ ] Output ra Obsidian vault, render đẹp
- [ ] Có copy plain text + export EPUB
- [ ] Translate 50+ chương 1 truyện không crash
- [ ] README + USER_GUIDE viết xong
- [ ] Bạn dùng được nó hằng ngày để dịch truyện đọc

---

**END ROADMAP**

*Chúc bạn vibe coding vui vẻ. Khi gặp khó khăn, quay lại file này. Mỗi step là 1 win nhỏ.* 🚀
