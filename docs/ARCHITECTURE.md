# TriLex — Architecture

> Tóm tắt technical cho developer. Vision đầy đủ xem `BLUEPRINT.md`.

---

## Tổng quan

TriLex là single-user translation tool dùng kiến trúc **QT-first**: apply QuickTranslator dictionaries (deterministic) trước, rồi dùng LLM chỉ để polish output. Khác biệt cốt lõi so với AI translator thông thường.

```
Source text
    │
    ▼
[Pre-process]          Normalize encoding, strip junk, detect language
    │
    ▼
[QT Pass]              Aho-Corasick dictionary lookup (ZH source only)
    │                  ~1.14M entries, <100ms/chapter
    ▼
[Scout / Entity Extract]   Gemini Flash extract characters, places, skills
    │
    ▼
[LLM Polish]           Build prompt (style + glossary + context + convert)
    │                  Call provider (retry + fallback keys)
    ▼
[Post-process]         Name lock validation, punctuation cleanup, strip AI preambles
    │
    ▼
[Persist]              SQLite cache + Obsidian vault write
```

---

## Layer 1: QT Dictionary Engine (`qt_dict/`)

### Tại sao Aho-Corasick?

Dictionary có 1.14M+ entries. Naive loop-per-char là O(n × m). Aho-Corasick build automaton một lần → match tất cả patterns trong O(n) — nhanh hơn ~100×.

### Files

| File | Nhiệm vụ |
|---|---|
| [qt_dict/parser.py](../src/trilex/qt_dict/parser.py) | Parse `VietPhrase.txt`, `Names.txt`, ... → list of `(source, target)` |
| [qt_dict/automaton.py](../src/trilex/qt_dict/automaton.py) | Build Aho-Corasick automaton, pickle cache, load from cache |
| [qt_dict/applier.py](../src/trilex/qt_dict/applier.py) | Apply automaton to text, handle priority tiers |

### 4-tier dictionary priority

```
Tier 1: Project glossary (highest — per-novel locked terms)
Tier 2: Names.txt (proper nouns)
Tier 3: VietPhrase.txt (general vocabulary)
Tier 4: LuatNhan.txt (pronoun rules — lowest)
```

Higher tier wins on conflict. Project glossary luôn override QT dictionary.

### Automaton cache

Pickle file lưu tại `data/cache/automaton_{hash}.pkl` — hash của dict files. Nếu dict thay đổi → hash khác → rebuild tự động.

---

## Layer 2: LLM Polish (`providers/` + `core/pipeline/stages/polish.py`)

### Provider abstraction

```python
class LLMProvider(Protocol):
    async def polish(self, prompt: str) -> str: ...
    async def scout(self, prompt: str) -> str: ...
```

Hiện tại chỉ có `GeminiProvider`. Thêm Claude/DeepSeek thì implement Protocol này.

### Multi-key rotation

`GeminiProvider` nhận list keys từ `Settings.all_keys()`. Khi gặp 429 (quota exceeded) → rotate sang key tiếp theo. Retry 3 lần với exponential backoff.

### Prompt structure (Gemini format)

```
TASK: Polish Vietnamese translation
INSTRUCTIONS:
1. ...

STYLE PACK:
{genre-specific style rules from packs/style/*.yaml}

MANDATORY GLOSSARY (you MUST use these EXACT translations):
- 李青 → Lý Thanh (NEVER: Lý Xanh, Li Qing)

CONVERT (QT pass output — use as translation base):
{convert_text}

SOURCE (original ZH — context only):
{source_text}

OUTPUT FORMAT: ...
```

### Name lock (3 layers)

1. **Pre-translation**: project glossary applied qua QT automaton
2. **Prompt injection**: glossary inject vào prompt với constraint cứng
3. **Post-validation** (`postprocess.py`): regex scan output, auto-fix violations

---

## Layer 3: Pipeline Orchestrator (`core/pipeline/`)

### Stages

```python
# core/pipeline/orchestrator.py
stages = [
    PreprocessStage(),      # normalize, detect lang
    QTPassStage(),          # Aho-Corasick apply
    ScoutStage(),           # entity extraction
    TranslateStage(),       # LLM polish
    PostprocessStage(),     # name lock + cleanup
    PersistStage(),         # SQLite + vault write
]
```

Mỗi stage nhận `PipelineState` (Pydantic model), transform, trả về state mới. Pure function — không có side effects ngoài `PersistStage`.

### Resume logic

`PipelineState.final` là `None` nếu chưa xong. `PersistStage` check trước khi ghi. CLI `trilex translate` detect state hiện tại và skip stages đã done.

### Mode

| Mode | Stages chạy |
|---|---|
| `convert` | Preprocess → QT Pass → Persist |
| `polish` | Tất cả stages |
| `side-by-side` | Polish → xuất 3-column markdown |

---

## Layer 4: Persistence (`persistence/`)

### Database schema (SQLite)

```
projects      → id, slug, title, source_lang, target_lang, genre
chapters      → id, project_id, chapter_index, source, convert, final, state, ...
terms         → id, project_id, source, target, term_type, locked
jobs          → id, project_id, type, state, started_at, finished_at, ...
```

`UniqueConstraint("uq_chapter_idx")` trên `(project_id, chapter_index)` — không thể trùng.

### Repository pattern

```python
# persistence/repos/chapter_repo.py
class ChapterRepo:
    async def upsert(self, chapter: ChapterCreate) -> Chapter: ...
    async def get_by_index(self, project_id: int, index: int) -> Chapter | None: ...
    async def list_pending(self, project_id: int) -> list[Chapter]: ...
```

Không gọi SQLAlchemy trực tiếp từ UI/pipeline — luôn qua repo.

### Async sessions

```python
# persistence/db.py
engine = create_async_engine("sqlite+aiosqlite:///data/trilex.db")
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
```

`aiosqlite` serialise qua một worker thread → không có real concurrency trong SQLite nhưng không block event loop.

---

## Layer 5: Output (`output/`)

| Module | Output |
|---|---|
| `obsidian.py` | Write `data/vault/{slug}/Chapter_XXXX.md` với YAML frontmatter |
| `plain_text.py` | Strip markdown, continuous text block cho copy-paste |
| `epub.py` | EbookLib EPUB3 generation |

---

## Layer 6: UI (`ui/`)

### Multipage Streamlit

```
ui/app.py              # Entrypoint, config, sidebar
ui/pages/
  01_Library.py        # Project CRUD
  02_Translate.py      # Main translation UI
  03_Jobs.py           # Job monitoring
  04_Dictionary.py     # Dict management
  05_Glossary.py       # Term management
  06_Settings.py       # Config viewer
  07_Export.py         # Export chapter/epub
```

### AsyncIO trong Streamlit

Streamlit là sync. Bridge qua `ui/_helpers.py::run_async()`:
```python
def run_async(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)
```

Pipeline calls (async) được wrap trong `run_async` khi gọi từ UI.

---

## Layer 7: Memory (`memory/`)

### Scout

`memory/scout.py` — Gemini Flash call sau mỗi chapter để extract:
- Tên nhân vật mới
- Địa danh
- Kỹ năng / skill
- Vật phẩm

Kết quả merge vào glossary (nếu user approve qua UI).

---

## Configuration (`config.py`)

```python
class Settings(BaseSettings):
    gemini_api_key: SecretStr      # GEMINI_API_KEY in .env
    fallback_key_1: SecretStr | None
    fallback_key_2: SecretStr | None
    gemini_model: str = "gemini-2.5-flash"
    request_timeout: int = 60
    max_retries: int = 3
```

Load từ `.env` qua `pydantic-settings`. Secrets dùng `SecretStr` — không leak qua `repr()`.

---

## Style Packs (`packs/`)

YAML files định nghĩa vocabulary rules per genre × target lang:

```yaml
# packs/style/tu_tien.vn.yaml
vocabulary_rules:
  - source: "修仙"
    preferred: "tu tiên"
    forbidden: ["sửa tiên", "tu thiên"]
  ...
tone:
  - formal
  - literary
```

Loaded qua `core/style_pack.py` → inject vào LLM prompt.

---

## Dependency Rules

```
core/       ← không import từ ui/, providers/, persistence/
qt_dict/    ← không import từ core/, ui/
providers/  ← không import từ ui/, persistence/
ui/         ← có thể import tất cả
cli/        ← có thể import tất cả
```

Enforce qua mypy + code review. Circular imports là bug.

---

## Test Strategy

```
tests/
├── unit/
│   ├── test_qt_dict.py         # Parser + automaton + applier
│   ├── test_pipeline.py        # Orchestrator stages (mocked provider)
│   ├── test_providers.py       # GeminiProvider (mocked SDK)
│   ├── test_repos.py           # SQLite repos (in-memory DB)
│   ├── test_edge_cases.py      # Empty/corrupt input, edge scenarios
│   ├── test_concurrency.py     # Parallel chapter processing
│   └── test_memory.py          # Memory leak checks
└── integration/                # Live API tests (skipped by default)
    └── test_live_gemini.py     # Run với: pytest -m integration
```

213 tests passing, 56% coverage (UI excluded).

---

## Known Limitations

| ID | Issue | Workaround |
|---|---|---|
| KI-1 | No auto-chunking cho chapter >4000 tokens | Chia chapter thủ công |
| KI-2 | Một corrupt dict file block toàn bộ QT pass | Fix/remove corrupt file |
| KI-3 | `google.generativeai` SDK deprecated | Migrate sang `google.genai` (planned) |
| KI-4 | UI pages 0% test coverage | Streamlit AppTest (planned) |
