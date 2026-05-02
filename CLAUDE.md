# CLAUDE.md

> **Đây là file context mà Claude Code đọc tự động mỗi khi mở project.**
> KHÔNG xóa file này. KHÔNG sửa trừ khi cần update vision/scope.
> File này định hướng mọi quyết định code của Claude Code.

---

## 1. Project Identity

**Tên**: TriLex (placeholder, có thể đổi sau)
**Loại**: Single-user translation tool cho tiểu thuyết online
**Owner**: Vibe coder — không rành code, dùng Claude Code làm chính
**Inspiration**: LiTTrans v5.7, JP→VN system prompt, QuickTranslator (QT) ecosystem, truyendichai/Chivi

## 2. Vision (1 dòng)

**"Một QuickTranslator hiện đại có AI polish, output ra Obsidian vault, hỗ trợ 4 routes ZH/EN/VN."**

## 3. Scope Lock (KHÔNG vượt quá)

### IN SCOPE (bắt buộc làm)
- 4 translation routes: **ZH→VN, ZH→EN, EN→VN, VN→EN**
- QT dictionary engine (re-implement QuickTranslator bằng Python)
- LLM polish layer (Gemini default, Claude/DeepSeek optional)
- 3 modes: Convert (no AI), Polish (AI), Side-by-side
- Streamlit UI cho operations
- Obsidian vault output
- SQLite persistence
- 4 genres: tu_tien, litrpg, vu_su, hien_dai

### OUT OF SCOPE (TUYỆT ĐỐI KHÔNG làm trong MVP)
- ❌ Routes có ZH là target (EN→ZH, VN→ZH)
- ❌ Multi-user, auth, public hosting
- ❌ Browser extension
- ❌ Mobile app riêng
- ❌ Custom Obsidian plugin (Phase 3+ may consider)
- ❌ Web frontend Next.js
- ❌ Real-time collaboration
- ❌ Payment, billing
- ❌ Public API endpoints

**Khi user (hoặc bạn) đề xuất feature ngoài scope → STOP, bảo họ defer to "Phase 8+ Future Work"**

## 4. Tech Stack (đã quyết định, không debate lại)

| Layer | Tech | Rationale |
|---|---|---|
| Language | Python 3.11+ | User quen, rich ecosystem |
| Package manager | uv | Hiện đại, nhanh hơn pip 10x |
| Async | asyncio + httpx | Standard cho I/O parallel |
| Database | SQLite + SQLAlchemy 2.0 + Alembic | Solo user, transactional, file-based |
| Validation | Pydantic v2 | Type safety, auto JSON serialization |
| LLM SDK | google-generativeai (Gemini), anthropic (Claude), openai (DeepSeek-compat) | Official SDKs |
| Fast string match | pyahocorasick | Aho-Corasick automaton cho QT pass |
| UI | Streamlit | User quen, đủ cho operations |
| CLI | Typer | Modern, type-hinted |
| Testing | pytest + pytest-asyncio + pytest-cov | Standard |
| Lint/Format | ruff + black + mypy | Fast, modern |
| Output format | Markdown (Obsidian) + EPUB (EbookLib) | User-facing |

**KHÔNG đề xuất swap tech stack trừ khi có lý do cực mạnh. KHÔNG dùng:**
- Django/Flask (overkill)
- Postgres/MongoDB (single-user không cần)
- React/Next.js (Streamlit đủ)
- Celery/Redis (asyncio đủ)
- Docker (Phase 7+ may consider)

## 5. Architecture Pillars (4 cột chính)

```
┌─────────────────────────────────────────────────────────┐
│ 1. QT DICTIONARY LAYER  (deterministic, free, fast)     │
│    Apply VietPhrase.txt + Names.txt + LuatNhan.txt etc. │
│    → Convert raw ZH text to Hán-Việt readable form      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. LLM POLISH LAYER  (AI, costs tokens, polishes only)  │
│    Send (original + convert + glossary + context) to LLM│
│    → Smooth Vietnamese translation                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. PERSISTENCE LAYER                                     │
│    SQLite (state, glossary, jobs)                        │
│    Obsidian vault (markdown content)                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. UI LAYER                                              │
│    Streamlit (operations, settings, dictionary mgmt)     │
│    Obsidian (reading, glossary edit, plot canvas)        │
└─────────────────────────────────────────────────────────┘
```

**KEY INSIGHT**: AI không "dịch" — nó chỉ "polish" cái QT đã convert sẵn. Đây là điểm khác biệt với 99% tool khác.

## 6. Folder Structure

```
trilex/
├── src/trilex/
│   ├── core/           # Pure logic, zero I/O, fully testable
│   │   ├── models/     # Pydantic v2 schemas
│   │   ├── routing/    # Direction + genre detection
│   │   ├── pipeline/   # Orchestrator + stages
│   │   └── transforms/ # Pure text transformations
│   ├── qt_dict/        # QuickTranslator engine re-implementation
│   ├── providers/      # LLM adapters (Gemini, Claude, DeepSeek)
│   ├── ingest/         # Input adapters (scrapers, EPUB, paste)
│   ├── output/         # Output adapters (Obsidian, plain, EPUB)
│   ├── persistence/    # SQLAlchemy + repos
│   ├── memory/         # Arc memory, scout, bible
│   ├── ui/             # Streamlit pages
│   └── cli/            # Typer commands
├── data/               # User data (gitignored)
│   ├── dictionaries/   # QT .txt files (drop in as-is)
│   ├── vault/          # Obsidian vault
│   ├── cache/          # Automaton pickles
│   └── trilex.db       # SQLite
├── packs/              # Style packs (versioned in git)
│   ├── style/          # Per (genre × target_lang) YAML
│   ├── archetypes/     # Character voice patterns
│   └── examples/       # Few-shot translations
├── scripts/            # Migration, import, benchmark
└── tests/              # pytest unit + integration
```

## 7. Naming Conventions

### Terminology (CHUẨN, dùng nhất quán)
- **QT** = QuickTranslator (engine/app)
- **VietPhrase** = dictionary file (`VietPhrase.txt`), đôi khi cộng đồng dùng để chỉ cả engine
- **QT pass** = bước apply QT dictionaries (deterministic conversion)
- **Polish** = bước LLM refine convert thành VN mượt
- **Convert** = output của QT pass (raw Hán-Việt readable)
- **Polished** = output cuối sau LLM
- **Term** = entry trong glossary (character, skill, realm, place...)
- **Lock** = enforce 1 term được dịch consistent

### Code naming
- snake_case cho variables, functions, modules
- PascalCase cho classes
- UPPER_SNAKE cho constants
- Tên file: `qt_dict.py` không `vietphrase.py`
- Tên class: `QTApplier`, `LLMProvider`, `Term`, `Chapter`, `Project`

## 8. Coding Standards

### Mandatory
- **Type hints everywhere** (mypy --strict pass)
- **Pydantic v2** cho mọi data structure
- **Async by default** cho I/O (LLM calls, DB, file)
- **No global state** (dependency injection)
- **Tests cho mọi module** trong `core/` và `qt_dict/`
- **Logging** dùng `logging` module, level INFO mặc định
- **Errors có ý nghĩa** (custom exceptions, không raise bare)

### Forbidden
- ❌ `from x import *` (wildcard import)
- ❌ Mutable default arguments (`def f(x=[]):`)
- ❌ `print()` cho debugging (dùng `logger`)
- ❌ Magic numbers (define constants)
- ❌ Functions > 50 lines (refactor)
- ❌ Files > 500 lines (split module)
- ❌ Silent except (`except: pass`)
- ❌ Hardcoded paths (dùng `Path` từ config)
- ❌ Hardcoded secrets (dùng `.env`)

### Style
- Line length: 100 chars (ruff default)
- Docstrings: Google style cho public APIs
- Comments: giải thích **WHY**, không phải WHAT
- Test naming: `test_<function>_<scenario>_<expected>`

## 9. Critical Rules — Security & Safety

### Secrets (TUYỆT ĐỐI)
- **NEVER** hardcode API keys trong source
- **NEVER** log full API keys (mask: `AIza...XXXX`)
- **NEVER** commit `.env` lên git
- **ALWAYS** verify `.env` trong `.gitignore` trước khi commit
- **ALWAYS** dùng `pydantic-settings` để load config

### File Operations
- **NEVER** modify files trong `data/dictionaries/` (read-only at runtime)
- **NEVER** delete user data without explicit confirmation
- **ALWAYS** backup `data/trilex.db` trước migrations
- **ALWAYS** dùng transactions cho DB writes

### LLM Calls
- **ALWAYS** retry với exponential backoff (max 3 lần)
- **ALWAYS** timeout (default 60s)
- **ALWAYS** log tokens used + latency
- **NEVER** send full glossary nếu chương ngắn (chỉ send terms xuất hiện)

### User Data
- **ALWAYS** ask user confirmation cho destructive ops (delete project, reset DB)
- **ALWAYS** show preview trước khi bulk operation
- **NEVER** auto-overwrite user-edited content trong vault

## 10. Communication Style với Vibe Coder

User là **vibe coder** — không rành code. Khi communicate:

### DO
- ✅ Giải thích bằng tiếng Việt (mix Eng technical terms OK)
- ✅ Show output/result sau khi xong (file đã tạo, test pass, etc.)
- ✅ Hỏi confirm trước action lớn (delete, refactor, install package)
- ✅ Đề xuất commit message rõ ràng cho mỗi step
- ✅ Demo bằng cách run real example, không chỉ unit test
- ✅ Liệt kê "Bạn cần làm gì tay" sau khi xong code

### DON'T
- ❌ Không bắt user hiểu code chi tiết — show high-level
- ❌ Không refactor toàn bộ module mà không hỏi
- ❌ Không cài package mới mà không giải thích lý do
- ❌ Không tạo file ngoài project folder
- ❌ Không assume user biết debug — show full error
- ❌ Không skip confirm cho destructive ops

### When user paste error
Trả lời theo format:
1. **Vấn đề là gì** (1 dòng, plain Vietnamese)
2. **Tại sao xảy ra** (1-2 dòng)
3. **Fix như nào** (numbered steps)
4. **Verify** (cách check fix work)

## 11. Definition of Done (mỗi step)

Một step được coi là "done" khi:

- [ ] Code chạy được không crash trên happy path
- [ ] Có test cho logic chính (`pytest` pass)
- [ ] Type check pass (`mypy --strict`)
- [ ] Lint pass (`ruff check`)
- [ ] User đã verify bằng demo thật
- [ ] Git commit với message rõ ràng (e.g. `feat(qt_dict): add Aho-Corasick automaton`)
- [ ] Update relevant doc nếu có thay đổi public API

## 12. Reference Documents

Trong root folder có các file reference quan trọng:

- `BLUEPRINT.md` — Kiến trúc tổng thể, schemas, decisions
- `ROADMAP_VIBE_CODER.md` — Hướng dẫn step-by-step
- `RESEARCH_BEST_PRACTICES.md` — Best practices từ GalTransl, Sakura, etc.
- `PRE_FLIGHT_CHECKLIST.md` — Checklist chuẩn bị
- `docs/inspiration/` — JP→VN system prompt + Sensory Lexicon (style reference)

**Khi user hỏi về vision/architecture → tham chiếu BLUEPRINT.md**
**Khi user paste step number → tham chiếu ROADMAP_VIBE_CODER.md**
**Khi gặp design decision khó → tham chiếu RESEARCH_BEST_PRACTICES.md**

## 13. Multi-Provider Strategy (CRITICAL)

Mỗi LLM có "cá tính" khác. Dùng đúng model cho đúng task:

```python
# Default routing logic
PROVIDER_ROUTING = {
    "scout":     "gemini-2.5-flash",   # cheap, fast extract
    "translate": {
        "zh_to_vn": "deepseek-v4",      # best for ZH source
        "zh_to_en": "deepseek-v4",      # best COMET
        "en_to_vn": "claude-sonnet",    # best literary VN
        "vn_to_en": "claude-sonnet",
    },
    "polish":    "claude-opus",         # best lexical taste
    "audit":     "gemini-2.5-flash",    # cheap quality check
}
```

### Model-Specific Prompt Patterns

**Claude** → XML tags
```xml
<role>...</role>
<task>...</task>
<glossary>...</glossary>
<source>...</source>
<output_format>...</output_format>
```

**Gemini** → Numbered instructions + clear format
```
TASK: ...
INSTRUCTIONS:
1. ...
2. ...
SOURCE: ...
OUTPUT: ...
```

**DeepSeek** → ZH prompts work better than English
```
任务：...
要求：...
原文：...
输出：...
```

### Gemini Safety Settings
**ALWAYS disable** safety filters cho Gemini (else dễ refuse content tu tiên/võ thuật):
```python
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}
```

## 14. Name Lock Architecture (CRITICAL)

Tên nhân vật, địa danh, kỹ năng PHẢI consistent. 3 layers enforcement:

### Layer 1: Pre-translation (deterministic)
Apply project glossary với highest priority TRƯỚC khi gọi LLM.

### Layer 2: Prompt Engineering
Inject glossary vào prompt với constraint cứng:
```
**MANDATORY GLOSSARY** (you MUST use these EXACT translations):
- 李青 → Lý Thanh (NEVER: Lý Xanh, Li Qing, or other variants)
```

### Layer 3: Post-validation (deterministic)
Sau LLM trả về, regex check + auto-fix nếu violate.

```python
def validate_name_lock(output, glossary, original):
    for term in glossary:
        if term.source in original and term.locked not in output:
            output = re.sub(forbidden_pattern, term.locked, output)
    return output
```

## 15. Cache Schema (như GalTransl)

Mỗi câu/đoạn dịch lưu cache đầy đủ để resume + debug:

```python
class CacheEntry(BaseModel):
    index: int
    name: str | None              # speaker
    pre_source: str               # raw original
    post_source: str              # after pre-dict cleaning
    convert: str                  # after QT pass
    translation_v1: str | None    # first pass LLM
    translation_v2: str | None    # proofread pass (optional)
    final: str                    # final output
    translated_by: str            # model name
    proofread_by: str | None
    problems: list[str]           # auto-detected issues
    timestamp: datetime
```

**Resume logic**: Nếu `final` is None → cần dịch tiếp từ entry này.

## 16. Auto Problem Detection (như GalTransl)

Sau dịch, scan các vấn đề:

```python
PROBLEM_TYPES = [
    "residue_zh",         # còn chữ Hán chưa dịch
    "residue_en",         # English sót
    "frequency_anomaly",  # từ lặp bất thường  
    "name_violation",     # tên không match glossary
    "length_anomaly",     # output >1.3x hoặc <0.5x source
    "translationese",     # "một cách", "có vẻ như"
    "mixed_register",     # lẫn lộn Hán-Việt với pure Việt
    "missing_translation", # đoạn bị skip
]
```

Flag trong cache → UI hiển thị → user batch retranslate.

## 17. Default Pipeline (per chapter)

```
INPUT: Source text (zh/en/vn)
   ↓
[Stage 1] Pre-process
   - Normalize encoding
   - Strip ads/junk (regex)
   ↓
[Stage 2] QT Pass (only if source=zh)
   - Apply 4-tier dict (universal → project → conditional → fallback)
   - Output: raw Hán-Việt
   ↓
[Stage 3] Pre-call (LLM)
   - Extract entities (Scout)
   - Build chapter map
   ↓
[Stage 4] Trans-call (LLM main)
   - Build prompt with style + glossary + context
   - Call provider (with retry)
   - Output: polished translation
   ↓
[Stage 5] Post-process (deterministic)
   - Punctuation cleanup
   - Name lock validation
   - Strip AI preambles
   ↓
[Stage 6] Post-call (LLM audit, optional)
   - Quality score 1-5
   - Detect drift
   - Auto-retry if score < 3
   ↓
[Stage 7] Persist
   - Update cache (SQLite)
   - Write Obsidian vault (.md)
   - Update glossary if new terms found
   ↓
OUTPUT: Polished translation in vault
```

## 18. UX Principles (cho Streamlit)

1. **Always show progress** (cả block + chunk level)
2. **Cancelable operations** (Stop button mọi long-running task)
3. **Cost visibility** (show estimate trước, actual sau)
4. **Resume gracefully** (assume user close laptop)
5. **Side-by-side viewing** (Source | Convert | Polish columns)
6. **Inline edit** (click to edit, không reload page)
7. **Copy-to-clipboard** (mọi text output có button copy)

## 19. Performance Targets

- QT pass: < 100ms cho chương 1000 chars
- LLM call (Gemini Flash): < 5s
- LLM call (Claude Opus): < 15s
- Pipeline end-to-end: < 30s/chương (excluding LLM latency)
- UI page load: < 1s
- Database query: < 50ms
- Memory usage: < 500MB (excluding loaded dictionaries)

## 20. Common Pitfalls — Đừng phạm

1. **DON'T** parse QT dict naively — dùng `pyahocorasick`, không loop char-by-char
2. **DON'T** load dict mỗi lần — cache automaton (pickle), reuse across requests
3. **DON'T** send full chapter trong 1 request nếu > 4000 tokens — split + parallel
4. **DON'T** forget Gemini safety settings — sẽ refuse content liên tục
5. **DON'T** trust LLM output 100% — always validate name lock + format
6. **DON'T** mutate Pydantic models — dùng `.model_copy(update={...})`
7. **DON'T** block event loop — async cho mọi I/O (file read large file cũng async)
8. **DON'T** silent fail — log errors with context (chapter index, model, etc.)
9. **DON'T** create circular imports — `core/` không import từ `ui/`, `providers/`
10. **DON'T** hardcode "Vietnamese" — dùng enum `Language.VI`

## 21. When in Doubt

Khi không chắc design decision, theo thứ tự:

1. Đọc `BLUEPRINT.md` — vision có mention không?
2. Đọc `RESEARCH_BEST_PRACTICES.md` — repo nào đã giải quyết?
3. Default to **simplest solution** that works
4. Nếu still unsure → **HỎI USER**, đừng guess

User là vibe coder nhưng họ có instinct tốt về **product**. Hỏi họ về business/UX, không hỏi về code.

## 22. Out-of-Band Communication

User có thể paste:
- "STEP X.Y" → Tham chiếu ROADMAP_VIBE_CODER.md
- "BLUEPRINT mục N" → Tham chiếu BLUEPRINT.md section
- "Như GalTransl" → Tham chiếu RESEARCH_BEST_PRACTICES.md phần 1.1
- File path → đọc file đó trước khi action

Khi user paste error trace → format response theo Section 10 (Vấn đề → Tại sao → Fix → Verify).

---

## 🚨 Last Reminders

1. **Đây là MVP cho 1 user duy nhất**. Đừng over-engineer.
2. **Vibe coder không phải software architect**. Đừng đề xuất pattern phức tạp không cần thiết.
3. **Quality > Quantity**. Ít feature mà work tốt hơn nhiều feature buggy.
4. **Commit thường xuyên**. Mỗi step xong = 1 commit.
5. **Khi unsure → ask, don't assume**.

---

**END CLAUDE.md**

*File này là single source of truth cho mọi quyết định code. Cập nhật khi vision thay đổi.*