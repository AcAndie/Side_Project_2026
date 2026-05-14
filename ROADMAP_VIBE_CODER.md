# ROADMAP_VIBE_CODER.md

> **Cho ai?** Người không rành code, dùng Claude Code làm gần như mọi việc, chỉ cần biết copy-paste prompt và kiểm tra kết quả.
>
> **Mục tiêu cuối:** Trong 4 tuần, có một app local giống Hako, dùng được hàng ngày để dịch truyện.

---

## Cách dùng file này

Đi tuần tự từ trên xuống. Mỗi PHASE có nhiều STEP. Mỗi STEP có 4 phần:

- 🎯 **Mục tiêu** — step này làm xong sẽ có gì
- 🗣️ **Bạn nói với Claude Code** — copy nguyên block này dán vào Claude Code
- 🙋 **Bạn cần làm tay** — việc con người, không thể automate
- ✅ **Kiểm tra** — cách verify step OK trước khi sang step tiếp

### Quy tắc vàng (KHÔNG bao giờ skip):

1. **Đừng bao giờ skip step.** Step 3 hỏng là step 4 sẽ vỡ.
2. **Mỗi step xong → commit git ngay.** Nếu Claude Code không tự commit, bảo nó.
3. **Step nào fail → STOP, debug.** Không chạy tiếp.
4. **Test pass + lint pass = mới được sang step kế.**
5. **Nếu Claude Code muốn làm thêm cái nằm ngoài step → bảo nó đọc lại CLAUDE.md §3 (Scope Lock).**

---

## 📋 Pre-flight Checklist (làm 1 lần duy nhất, trước Phase 0)

Trước khi bắt đầu, đảm bảo máy bạn có:

- [ ] **Python 3.11+** — gõ `python --version` trong terminal
- [ ] **Node.js 20+** — gõ `node --version`
- [ ] **pnpm** — gõ `pnpm --version`. Cài bằng `npm install -g pnpm` nếu chưa có.
- [ ] **uv** — gõ `uv --version`. Cài bằng:
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] **Claude Code** đã cài và login — gõ `claude` trong terminal phải mở được
- [ ] **Git** đã cài — gõ `git --version`
- [ ] **VS Code** (khuyến nghị)
- [ ] **Bộ QT dictionaries** (VietPhrase.txt, Names.txt, ...) — để sẵn 1 chỗ dễ tìm
- [ ] **Gemini API key** (free tier OK) — lấy ở [Google AI Studio](https://aistudio.google.com/apikey)
- [ ] **Quota internet ổn** — sẽ download nhiều package

Nếu thiếu cái nào, search Google "cài [tên cái thiếu] Windows/Mac" trước. Đừng nhờ Claude Code làm việc cài đặt hệ thống — dễ hỏng máy.

---

## 🌱 PHASE 0 — Setup môi trường (1 buổi tối, ~2 giờ)

### STEP 0.1 — Tạo folder dự án + cấu trúc monorepo

🎯 **Mục tiêu**: Có folder `dich-ai/` với cấu trúc monorepo (backend + frontend tách).

🙋 **Bạn cần làm tay**:
1. Chọn chỗ trên máy có >5GB free, ví dụ `D:\Projects\` hoặc `~/Projects/`
2. Tạo folder `dich-ai`
3. Mở terminal trong folder đó
4. Gõ `claude` để mở Claude Code session

🗣️ **Bạn nói với Claude Code**:

```
Tôi đang ở folder dich-ai/ trống. Hãy tạo cấu trúc monorepo:

dich-ai/
├── backend/                  ← Python FastAPI
├── frontend/                 ← React + Vite
├── docs/                     ← markdown docs
├── .gitignore                ← ignore .venv, node_modules, .env, data/, dist/
├── README.md                 ← skeleton
└── CHANGELOG.md              ← skeleton

Tạo .gitignore phù hợp (Python + Node + IDE + OS).
Tạo README.md skeleton chỉ có:
  # Dịch_Ai
  Local AI translation app cho tiểu thuyết.

Tạo CHANGELOG.md skeleton theo Keep a Changelog format.

KHÔNG init git ngay, tôi sẽ làm sau khi paste CLAUDE.md.
KHÔNG tạo file Python/JS nào trong backend/ và frontend/ ở step này, chỉ folder rỗng với .gitkeep.

Sau khi xong, hỏi tôi confirm trước step kế.
```

🙋 **Bạn cần làm tay**: Trả lời "yes" / "OK" khi Claude Code hỏi confirm.

✅ **Kiểm tra**:
- Folder có: `backend/`, `frontend/`, `docs/`, `.gitignore`, `README.md`, `CHANGELOG.md`
- Folder `backend/` và `frontend/` rỗng (chỉ có `.gitkeep`)
- Chưa có folder `.git/`

---

### STEP 0.2 — Paste CLAUDE.md + ROADMAP, init git

🎯 **Mục tiêu**: Claude Code biết governance rules trước khi code dòng đầu tiên.

🙋 **Bạn cần làm tay**:
1. Copy nội dung `CLAUDE.md` (file tôi đưa cho bạn) vào root `dich-ai/CLAUDE.md`
2. Copy nội dung `ROADMAP_VIBE_CODER.md` (file này) vào root `dich-ai/ROADMAP_VIBE_CODER.md`
3. Tạo folder `docs/` nếu chưa có
4. Trong `docs/`, tạo file `SCOPE_LOCK.md` chỉ chứa nội dung §3 của CLAUDE.md (copy phần "Scope Lock v1.0")

🗣️ **Bạn nói với Claude Code**:

```
Tôi vừa paste 3 file vào project:
- CLAUDE.md (root)
- ROADMAP_VIBE_CODER.md (root)
- docs/SCOPE_LOCK.md

Hãy đọc CẢ 3 file, tóm tắt cho tôi nghe trong 5 bullet points để xác nhận bạn hiểu đúng:
1. Project là gì
2. Tech stack đã lock những gì
3. v1 scope MUST-HAVE gồm những gì
4. v1 scope DEFERRED gồm những gì
5. Top 3 NEVER rules quan trọng nhất

ĐỪNG tạo code nào ở step này, chỉ đọc và confirm.

Sau khi tôi confirm, init git:
- git init
- git add .
- git commit -m "chore: initial project structure + governance docs"
```

🙋 **Bạn cần làm tay**:
- Đọc tóm tắt Claude Code đưa ra
- Nếu thiếu/sai chỗ nào → bảo nó đọc lại
- Nếu OK → bảo nó init git

✅ **Kiểm tra**:
- `git log` thấy 1 commit "initial project structure + governance docs"
- Claude Code tóm tắt đúng:
  - Project = Dịch_Ai, local app
  - Stack = FastAPI + React Vite + Tailwind + shadcn
  - v1 MUST = 8 items
  - v1 DEFERRED gồm Bible, Name Lock, Multi-provider beyond Gemini, etc.
  - NEVER: silent failure, `any`, deprecated SDK

---

### STEP 0.3 — Init backend Python

🎯 **Mục tiêu**: Backend có `pyproject.toml` chuẩn, `.venv` hoạt động, `uv` quản lý package.

🗣️ **Bạn nói với Claude Code**:

```
Init backend Python project trong folder backend/:

1. cd backend && uv init --python 3.11
2. Edit pyproject.toml với metadata:
   name = "dich-ai-backend"
   version = "0.1.0"
   description = "Local AI translation backend"
3. Add dependencies (uv add):
   - fastapi
   - uvicorn[standard]
   - sqlalchemy[asyncio]
   - aiosqlite
   - alembic
   - pydantic
   - pydantic-settings
   - google-genai            # NEW SDK, KHÔNG google-generativeai cũ
   - pyahocorasick
   - httpx
   - python-dotenv
   - typer

4. Add dev dependencies (uv add --dev):
   - pytest
   - pytest-asyncio
   - pytest-cov
   - mypy
   - ruff
   - black
   - httpx                   # dùng cho TestClient

5. Cấu hình pyproject.toml:
   [tool.ruff] line-length 100, target python 3.11
   [tool.mypy] strict mode
   [tool.black] line-length 100
   [tool.pytest.ini_options] asyncio_mode = "auto"

6. Tạo cấu trúc folder src/dich_ai/:
   src/dich_ai/
     ├── __init__.py
     ├── core/
     │   ├── __init__.py
     │   ├── models.py        ← rỗng, chỉ có docstring
     │   └── pipeline/
     │       ├── __init__.py
     │       └── stages/
     │           └── __init__.py
     ├── qt_dict/
     │   └── __init__.py
     ├── providers/
     │   └── __init__.py
     ├── persistence/
     │   ├── __init__.py
     │   ├── migrations/      ← cho Alembic
     │   └── repos/
     │       └── __init__.py
     ├── api/
     │   ├── __init__.py
     │   └── routes/
     │       └── __init__.py
     ├── config.py            ← rỗng, sẽ điền sau
     └── main.py              ← rỗng, sẽ điền sau

7. Tạo backend/tests/ với __init__.py
8. Tạo backend/.env.example với template:
   GEMINI_API_KEY=
   DATABASE_URL=sqlite+aiosqlite:///./data/dichai.db
   CORS_ORIGINS=http://localhost:5173
   LOG_LEVEL=INFO

9. Verify: cd backend && uv run python -c "import fastapi, sqlalchemy, google.genai; print('OK')"

Sau khi xong, run check:
- uv run ruff check src/
- uv run mypy src/dich_ai/ (sẽ không có error vì file đa số rỗng)
- uv run pytest (sẽ pass với 0 tests)

Commit: chore(backend): scaffold python project structure
```

🙋 **Bạn cần làm tay**:
- Trả lời "yes" khi Claude Code hỏi confirm install package
- Kiểm tra package install OK (không có lỗi đỏ)

✅ **Kiểm tra**:
- `backend/pyproject.toml` tồn tại với đủ dependencies
- `backend/.venv/` tồn tại
- `cd backend && uv run python -c "import fastapi"` không lỗi
- Cấu trúc folder đúng như spec
- `git log` thấy 2 commits

---

### STEP 0.4 — Init frontend React

🎯 **Mục tiêu**: Frontend có Vite + React + TS + Tailwind v4 + shadcn/ui ready.

🗣️ **Bạn nói với Claude Code**:

```
Init frontend trong folder frontend/:

1. cd frontend && pnpm create vite@latest . -- --template react-ts
   (Nếu hỏi overwrite, yes vì folder rỗng có .gitkeep)
2. pnpm install
3. Add Tailwind CSS v4:
   pnpm add tailwindcss @tailwindcss/vite
   Update vite.config.ts để dùng @tailwindcss/vite plugin
   Update src/index.css với @import "tailwindcss";
4. Setup shadcn/ui:
   pnpm dlx shadcn@latest init
   Khi hỏi:
   - Style: New York
   - Base color: Stone
   - CSS variables: yes
5. Add dependencies:
   pnpm add @tanstack/react-query zustand react-router-dom
   pnpm add react-hook-form zod @hookform/resolvers
   pnpm add lucide-react
6. Add dev dependencies:
   pnpm add -D @types/node prettier eslint-config-prettier
7. Cấu trúc folder src/:
   src/
     ├── features/
     │   ├── bookshelf/
     │   │   └── .gitkeep
     │   ├── reader/
     │   │   └── .gitkeep
     │   ├── translator/
     │   │   └── .gitkeep
     │   ├── glossary/
     │   │   └── .gitkeep
     │   └── settings/
     │       └── .gitkeep
     ├── components/
     │   └── ui/              ← shadcn primitives
     ├── lib/
     │   ├── api.ts           ← rỗng, sẽ điền
     │   └── utils.ts         ← shadcn tạo sẵn
     ├── stores/
     │   └── .gitkeep
     ├── App.tsx
     ├── main.tsx
     └── index.css

8. Add scripts vào package.json:
   "typecheck": "tsc --noEmit"
   "lint": "eslint . --max-warnings 0"
   "format": "prettier --write ."
   "format:check": "prettier --check ."

9. Create .prettierrc với:
   { "semi": true, "singleQuote": false, "trailingComma": "all", "printWidth": 100 }

10. Verify:
    - pnpm dev → server start ở http://localhost:5173
    - pnpm typecheck → no errors
    - pnpm lint → no errors

Commit: chore(frontend): scaffold vite + react + tailwind + shadcn
```

🙋 **Bạn cần làm tay**:
- Trả lời "yes" khi Claude Code hỏi overwrite/install
- Mở browser http://localhost:5173 xem Vite welcome page (tạm thời thôi, sẽ thay)
- Đóng dev server bằng Ctrl+C

✅ **Kiểm tra**:
- `frontend/package.json` có đủ dependencies
- `pnpm dev` start được, mở http://localhost:5173 không lỗi
- `pnpm typecheck` pass
- `pnpm lint` pass
- `git log` thấy 3 commits

---

### STEP 0.5 — Tạo docs cơ bản + V1_1_BACKLOG

🎯 **Mục tiêu**: Có chỗ chứa decisions, API contract, và backlog feature defer.

🗣️ **Bạn nói với Claude Code**:

```
Tạo các file docs sau:

1. docs/ARCHITECTURE.md
   - Copy phần §5 từ CLAUDE.md (Architecture Pillars)
   - Thêm section "Database Schema" placeholder (sẽ điền sau Step 1.2)
   - Thêm section "Layer Responsibilities" với 1-2 dòng cho mỗi layer

2. docs/API.md
   - Sketch endpoints planned:
     GET    /health
     GET    /projects
     POST   /projects
     GET    /projects/{id}
     DELETE /projects/{id}
     GET    /projects/{id}/chapters
     POST   /projects/{id}/chapters
     GET    /chapters/{id}
     PATCH  /chapters/{id}
     POST   /convert
     POST   /translate/chapter
     POST   /translate/batch
     GET    /jobs/{id}/stream (SSE)
     GET    /projects/{id}/glossary
     POST   /projects/{id}/glossary
     PATCH  /glossary/{id}
     DELETE /glossary/{id}
   - Mỗi endpoint: 1 dòng mô tả + request/response schema sketch
   - File này sẽ update dần khi code endpoints

3. docs/V1_1_BACKLOG.md
   - Header: "Features deferred khỏi v1.0, để làm sau MVP"
   - Copy đúng DEFERRED list từ CLAUDE.md §3
   - Mỗi item là checkbox - [ ]

4. CHANGELOG.md update với:
   ## [Unreleased]
   ### Added
   - Project structure scaffold
   - Governance docs (CLAUDE.md, ROADMAP_VIBE_CODER.md)
   - Architecture sketch
   - API contract sketch

Commit: docs: add architecture, API contract, v1.1 backlog
```

🙋 **Bạn cần làm tay**: Mở `docs/V1_1_BACKLOG.md` đọc qua, đảm bảo bạn nhớ những cái nào defer.

✅ **Kiểm tra**:
- `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/V1_1_BACKLOG.md` đều tồn tại và có content
- `git log` thấy 4 commits

---

## 🏗️ PHASE 1 — Backend Foundation (Tuần 1)

> **Mục tiêu cuối tuần 1**: Backend chạy localhost:8000, có 2 endpoint `/convert` và `/translate/chapter` work qua Postman/curl.

---

### STEP 1.1 — Domain models (Pydantic)

🎯 **Mục tiêu**: Định nghĩa core types: `Project`, `Chapter`, `Term`, `TranslationResult`, `Job`.

🗣️ **Bạn nói với Claude Code**:

```
Đọc CLAUDE.md §14 (Tech-specific Conventions). 

Tạo file src/dich_ai/core/models.py với Pydantic v2 models:

1. ChapterStatus: Literal["pending", "translating", "done", "failed"]
2. TranslationMode: Literal["convert", "polish"]
3. SourceLang: Literal["zh", "en", "vn"]
4. TargetLang: Literal["vn", "en"]

5. ProjectCreate(BaseModel):
   - title: str (min 1, max 200)
   - source_lang: SourceLang = "zh"
   - target_lang: TargetLang = "vn"
   - description: str | None = None

6. Project(ProjectCreate):
   - id: int
   - slug: str
   - created_at: datetime
   - updated_at: datetime
   - chapter_count: int = 0

7. ChapterCreate:
   - title: str
   - source_text: str
   - chapter_index: int | None = None  # auto-assign nếu None

8. Chapter(ChapterCreate):
   - id: int
   - project_id: int
   - chapter_index: int
   - convert_text: str | None = None
   - final_text: str | None = None
   - status: ChapterStatus = "pending"
   - mode: TranslationMode | None = None
   - tokens_used: int = 0
   - elapsed_ms: float = 0
   - error: str | None = None
   - created_at: datetime
   - updated_at: datetime

9. Term(BaseModel):
   - id: int
   - project_id: int
   - source: str
   - target: str
   - category: Literal["character", "place", "skill", "item", "term"] = "term"
   - locked: bool = False
   - notes: str | None = None

10. TranslationRequest(BaseModel):
    - chapter_id: int
    - mode: TranslationMode = "polish"
    - provider: str = "gemini"

11. JobStatus: Literal["queued", "running", "done", "failed", "cancelled"]
12. Job(BaseModel):
    - id: str  # UUID
    - type: Literal["translate_chapter", "translate_batch", "convert"]
    - status: JobStatus
    - progress: float = 0.0  # 0-1
    - total: int = 0
    - completed: int = 0
    - error: str | None = None
    - created_at: datetime
    - updated_at: datetime

Mỗi model có `model_config = ConfigDict(from_attributes=True)` để dùng với SQLAlchemy ORM.

Tạo file tests/unit/test_models.py với:
- Test validation: empty title → ValidationError
- Test default values
- Test invalid status → ValidationError
- Test from_attributes

Sau khi xong:
- uv run pytest tests/unit/test_models.py -v
- uv run mypy src/dich_ai/core/models.py
- uv run ruff check src/

Commit: feat(core): add domain models with pydantic v2
```

🙋 **Bạn cần làm tay**:
- Đọc output Claude Code: tests pass, mypy 0 errors
- Nếu fail → đọc error, bảo Claude Code fix

✅ **Kiểm tra**:
- File `src/dich_ai/core/models.py` có 12 models đúng spec
- Tests pass
- `uv run mypy src/` 0 errors

---

### STEP 1.2 — Database setup (SQLAlchemy + Alembic)

🎯 **Mục tiêu**: Có SQLite database, schema match với Pydantic models, migration system work.

🗣️ **Bạn nói với Claude Code**:

```
Setup database layer:

1. src/dich_ai/persistence/db.py:
   - Async engine từ DATABASE_URL trong .env
   - async_sessionmaker
   - get_session() async generator dùng cho FastAPI Depends

2. src/dich_ai/persistence/models.py — SQLAlchemy ORM (KHÔNG nhầm với Pydantic):
   - Base = declarative_base với async support
   - ProjectORM (table: projects)
     - id, slug (unique), title, source_lang, target_lang, description
     - created_at, updated_at (server default)
     - relationship to chapters
   - ChapterORM (table: chapters)
     - id, project_id (FK), chapter_index
     - source_text (Text), convert_text (Text null), final_text (Text null)
     - status, mode, tokens_used, elapsed_ms, error
     - created_at, updated_at
     - UniqueConstraint("uq_chapter_project_idx", project_id, chapter_index)
     - Index trên project_id
   - TermORM (table: terms)
     - id, project_id (FK), source, target, category, locked, notes
     - UniqueConstraint("uq_term_project_source", project_id, source)
     - Index trên project_id
   - JobORM (table: jobs)
     - id (str primary), type, status, progress, total, completed, error
     - payload (JSON), created_at, updated_at

3. src/dich_ai/persistence/repos/ — Repository pattern:
   - base.py: BaseRepo[T] generic
   - project_repo.py:
     - async def create(session, data: ProjectCreate) -> Project
     - async def get(session, id: int) -> Project | None
     - async def get_by_slug(session, slug: str) -> Project | None
     - async def list(session, limit=100, offset=0) -> list[Project]
     - async def delete(session, id: int) -> bool
   - chapter_repo.py:
     - create, get, list_by_project, update, delete, upsert_by_index
   - term_repo.py:
     - create, get, list_by_project, list_in_text (cho QT pass), update, delete
   - job_repo.py:
     - create, get, update_status, list_active

4. Setup Alembic:
   uv run alembic init -t async src/dich_ai/persistence/migrations
   Edit alembic.ini và env.py:
   - sqlalchemy.url từ env DATABASE_URL
   - target_metadata = Base.metadata
   - async support
   
5. Generate initial migration:
   uv run alembic revision --autogenerate -m "initial schema"

6. Apply migration:
   mkdir -p backend/data
   uv run alembic upgrade head

7. Tests tests/unit/test_repos.py:
   - Fixture: in-memory SQLite (sqlite+aiosqlite:///:memory:)
   - Test mỗi repo có create + get + list
   - Test unique constraint violation
   - Test cascade delete (project → chapters)

8. Verify:
   - uv run pytest tests/unit/test_repos.py -v
   - uv run mypy src/dich_ai/persistence/
   - sqlite3 data/dichai.db ".schema" → thấy tables

Commit: feat(persistence): add sqlalchemy models, repos, alembic migrations
```

🙋 **Bạn cần làm tay**:
- Tạo `.env` từ `.env.example`, điền `GEMINI_API_KEY=...` (lấy ở aistudio.google.com)
- Confirm install Alembic OK

✅ **Kiểm tra**:
- `backend/data/dichai.db` tồn tại
- `uv run pytest tests/unit/test_repos.py` pass tất cả
- `sqlite3 data/dichai.db ".tables"` → thấy 4 tables: projects, chapters, terms, jobs

---

### STEP 1.3 — QT Dict engine (port từ TriLex)

🎯 **Mục tiêu**: Convert mode work — paste text Trung → ra text Hán-Việt.

🗣️ **Bạn nói với Claude Code**:

```
Build QT Dictionary engine (Aho-Corasick based):

1. src/dich_ai/qt_dict/parser.py:
   - parse_vietphrase(path: Path) -> list[tuple[str, str]]
     Format mỗi dòng: "中文=越文" hoặc "中文\t越文"
     Skip lines: rỗng, bắt đầu //, bắt đầu #
   - parse_names(path: Path) -> list[tuple[str, str]]
   - parse_dict(path: Path, format: Literal["equal", "tab"]) -> list[tuple[str, str]]
   - Raise QTParseError(file, line, reason) nếu format sai
   - Encoding: UTF-8 với fallback UTF-8-sig (BOM)
   - Skip 1 entry bị lỗi, log warning, KHÔNG raise (theo CLAUDE.md §16 anti-pattern "silent failures" — phải log loud)

2. src/dich_ai/qt_dict/automaton.py:
   - Sử dụng pyahocorasick
   - class QTAutomaton:
     - __init__(entries: list[tuple[str, str]]) — build automaton
     - find_matches(text: str) -> list[tuple[int, int, str]] — return non-overlapping longest matches
   - Algorithm: longest-match wins khi overlap

3. src/dich_ai/qt_dict/applier.py:
   - class QTApplier:
     - __init__(dict_dir: Path)
     - load dictionaries theo priority (cao → thấp):
       1. project_glossary (cho từng project, set sau)
       2. names.txt + names2.txt
       3. vietphrase.txt
       4. luatnhan.txt (parameterized rules — skip cho v1, chỉ load file nếu có)
     - apply(text: str, project_glossary: list[Term] = []) -> str
     - Stats: số match, từ nào match
   - Cache automaton trong memory, rebuild khi project_glossary change
   - Wrap mỗi file load trong try/except QTParseError, log warning, skip file lỗi, KHÔNG block init (đây là KI-2 từ BUGS_FOUND.md cũ)

4. tests/unit/test_qt_dict.py:
   - parse: valid file, empty file, malformed lines, encoding edge cases (BOM, UTF-8-sig)
   - automaton: longest match, no match, overlap, empty input
   - applier: simple replace, priority order, missing dict file → graceful skip
   - 1 dict file corrupt → load các file khác bình thường

5. Verify:
   - uv run pytest tests/unit/test_qt_dict.py -v
   - uv run mypy src/dich_ai/qt_dict/

⚠️ LƯU Ý: KHÔNG hardcode đường dẫn dict files. Đọc từ env DICT_DIR (mặc định ./data/dicts/).

Commit: feat(qt_dict): port aho-corasick dictionary engine
```

🙋 **Bạn cần làm tay**:
- Tạo folder `backend/data/dicts/`
- Copy ít nhất `VietPhrase.txt` và `Names.txt` (từ bộ QT của bạn) vào đó
- Add `DICT_DIR=./data/dicts/` vào `.env`

✅ **Kiểm tra**:
- Tests pass
- Test manual: `uv run python -c "from dich_ai.qt_dict.applier import QTApplier; a = QTApplier(Path('./data/dicts')); print(a.apply('我是李青'))"` ra Hán-Việt

---

### STEP 1.4 — Gemini provider (NEW SDK)

🎯 **Mục tiêu**: Có wrapper gọi Gemini, dùng `google.genai` (KHÔNG `google.generativeai` deprecated).

🗣️ **Bạn nói với Claude Code**:

```
Build Gemini provider:

1. src/dich_ai/providers/base.py:
   - class TranslationProvider(Protocol):
     - async def translate(prompt: str, content: str, *, model: str | None = None) -> TranslationOutput
   - class TranslationOutput(BaseModel):
     - text: str
     - tokens_used: int
     - elapsed_ms: float
     - model: str
   - class ProviderError(Exception): pass
   - class QuotaExceededError(ProviderError): pass
   - class SafetyBlockedError(ProviderError): pass

2. src/dich_ai/providers/gemini.py:
   - import từ google.genai (KHÔNG google.generativeai)
   - class GeminiProvider:
     - __init__(api_key: str | list[str], default_model: str = "gemini-2.5-flash")
       Hỗ trợ list keys để rotate khi 429
     - async def translate(...) -> TranslationOutput
       - Safety settings: BLOCK_NONE cho 4 categories
       - Catch 429 → rotate key, retry (max 3 lần)
       - Catch safety block → raise SafetyBlockedError
       - Measure elapsed_ms
     - Internal state: _current_key_idx
   
3. src/dich_ai/config.py:
   - class Settings(BaseSettings):
     - gemini_api_key: str
     - gemini_fallback_keys: list[str] = []  # parse từ GEMINI_FALLBACK_KEYS comma-separated
     - default_model: str = "gemini-2.5-flash"
     - database_url: str = "sqlite+aiosqlite:///./data/dichai.db"
     - cors_origins: list[str] = ["http://localhost:5173"]
     - dict_dir: Path = Path("./data/dicts")
     - log_level: str = "INFO"
     - model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
   - @lru_cache def get_settings() -> Settings

4. tests/unit/test_providers.py:
   - Mock google.genai client
   - Test thành công → return TranslationOutput
   - Test 429 → rotate key + retry
   - Test 429 hết key → raise QuotaExceededError
   - Test safety block → raise SafetyBlockedError
   - Test timeout
   - Verify safety_settings được pass BLOCK_NONE

⚠️ QUAN TRỌNG (CLAUDE.md §16 anti-pattern):
- KHÔNG dùng "gemini-2.5-flash-lite-preview" hay bất kỳ flash-lite/preview model
- KHÔNG silent failure khi 429 — log loud
- KHÔNG hardcode API key trong code

Commit: feat(providers): add gemini provider with new google.genai sdk
```

🙋 **Bạn cần làm tay**:
- Đảm bảo `GEMINI_API_KEY` trong `.env` valid
- (Optional) thêm `GEMINI_FALLBACK_KEYS=key2,key3` nếu có nhiều key

✅ **Kiểm tra**:
- Tests pass
- Smoke test thật: `uv run python -c "import asyncio; from dich_ai.providers.gemini import GeminiProvider; from dich_ai.config import get_settings; s = get_settings(); p = GeminiProvider(s.gemini_api_key); print(asyncio.run(p.translate('Translate to Vietnamese:', 'Hello world')))"`

---

### STEP 1.5 — Translation pipeline (1 chương đơn)

🎯 **Mục tiêu**: Hàm `translate_chapter()` chạy: preprocess → QT pass → LLM → postprocess.

🗣️ **Bạn nói với Claude Code**:

```
Build pipeline orchestrator (SIMPLIFIED v1 — không có Scout, Bible, Name Lock):

1. src/dich_ai/core/pipeline/stages/preprocess.py:
   - def preprocess(text: str) -> str
     - Normalize encoding (NFC)
     - Strip zero-width chars (U+200B, U+200C, U+200D, U+FEFF, U+2060)
     - Normalize line endings → \n
     - Strip leading/trailing whitespace per line
     - KHÔNG strip empty lines (giữ đoạn văn)

2. src/dich_ai/core/pipeline/stages/qt_pass.py:
   - async def qt_pass(text: str, applier: QTApplier, glossary: list[Term]) -> str
   - Apply QT dict
   - Return convert_text

3. src/dich_ai/core/pipeline/stages/translate.py:
   - async def translate_stage(
       convert_text: str,
       source_text: str,
       provider: TranslationProvider,
       project: Project,
       glossary: list[Term],
       mode: TranslationMode = "polish",
     ) -> TranslationOutput
   - Build prompt theo format (mỗi route 1 prompt):
     - zh→vn: polish convert_text into natural Vietnamese
     - en→vn: full translation từ source
   - Inject MANDATORY GLOSSARY section với locked terms
   - Inject style guide cơ bản (1 paragraph generic, sẽ refine sau)
   - Call provider.translate()

4. src/dich_ai/core/pipeline/stages/postprocess.py:
   - def postprocess(text: str) -> str
   - Strip AI preambles ("Đây là bản dịch:", "Here is the translation:", etc.)
   - Normalize Vietnamese punctuation (—, …)
   - Strip excessive blank lines (>2 consecutive)
   - Validate: nếu trống → raise PipelineError

5. src/dich_ai/core/pipeline/orchestrator.py:
   - class PipelineResult(BaseModel):
     - convert_text: str
     - final_text: str | None
     - tokens_used: int
     - elapsed_ms: float
     - mode: TranslationMode
     - warnings: list[str] = []
   
   - async def translate_chapter(
       source_text: str,
       project: Project,
       glossary: list[Term],
       provider: TranslationProvider,
       applier: QTApplier,
       mode: TranslationMode = "polish",
     ) -> PipelineResult
   
   - Mode "convert": preprocess → qt_pass → return (final_text=None)
   - Mode "polish": preprocess → qt_pass → translate → postprocess → return

6. tests/unit/test_pipeline.py:
   - Mock provider trả output cố định
   - Test convert mode: chỉ có convert_text, final_text=None
   - Test polish mode: cả 2 đều có
   - Test empty input → PipelineError
   - Test very long input (15k chars) — TODO: log warning, không split (defer v1.1)
   - Test edge case: text full chữ Hán, text mix Anh-Trung
   - Test glossary applied

⚠️ LƯU Ý:
- CHƯA có chunking cho long input — log warning, để defer (xem V1_1_BACKLOG.md)
- CHƯA có Bible / Name Lock / Scout — defer
- Pipeline pure async, không side effects

Commit: feat(pipeline): add single-chapter translation orchestrator
```

🙋 **Bạn cần làm tay**: Đọc test output, đảm bảo pass.

✅ **Kiểm tra**: Tests pass, manual smoke test convert + polish mode work.

---

### STEP 1.6 — FastAPI skeleton + health check

🎯 **Mục tiêu**: Server start, `GET /health` trả `{"status":"ok"}`.

🗣️ **Bạn nói với Claude Code**:

```
Build FastAPI app skeleton:

1. src/dich_ai/main.py:
   - from fastapi import FastAPI
   - Lifespan context manager:
     - Startup: init DB engine, init QT applier, init provider
     - Shutdown: dispose engine
   - Add CORS middleware từ settings.cors_origins
   - Mount routers (sẽ thêm dần)
   - Register exception handlers:
     - ValidationError → 422
     - ProviderError → 502
     - QuotaExceededError → 429
     - SafetyBlockedError → 451

2. src/dich_ai/api/routes/health.py:
   - router = APIRouter()
   - @router.get("/health"): return {"status": "ok", "version": __version__}
   - @router.get("/health/deep"): check DB connection + return more info

3. src/dich_ai/api/dependencies.py:
   - get_db() session dependency
   - get_settings_dep() dependency
   - get_qt_applier() dependency (singleton)
   - get_provider() dependency (Gemini, dùng settings.gemini_api_key + fallback)

4. backend/scripts/run_dev.sh (và .bat cho Windows):
   - cd backend && uv run uvicorn dich_ai.main:app --reload --port 8000

5. tests/integration/test_health.py:
   - from fastapi.testclient import TestClient
   - test_health_returns_ok
   - test_deep_health_db_works

Verify:
- uv run uvicorn dich_ai.main:app --port 8000
- Mở http://localhost:8000/health trên browser → JSON {"status":"ok"}
- Mở http://localhost:8000/docs → Swagger UI hiển thị

Commit: feat(api): scaffold fastapi app with health check
```

🙋 **Bạn cần làm tay**:
- Start server (`uv run uvicorn dich_ai.main:app --reload --port 8000`)
- Mở browser http://localhost:8000/health → JSON
- Mở http://localhost:8000/docs → Swagger UI

✅ **Kiểm tra**: Cả 2 URL trên work. Test pass.

---

### STEP 1.7 — Endpoint `/convert`

🎯 **Mục tiêu**: POST `/convert` với raw text → trả convert_text (Hán-Việt).

🗣️ **Bạn nói với Claude Code**:

```
Add /convert endpoint:

1. src/dich_ai/api/routes/translate.py:
   - POST /convert
   - Request body:
     class ConvertRequest(BaseModel):
       text: str = Field(min_length=1, max_length=200_000)
       source_lang: SourceLang = "zh"
       project_id: int | None = None  # nếu có, dùng glossary của project
   - Response:
     class ConvertResponse(BaseModel):
       convert_text: str
       stats: ConvertStats
     class ConvertStats(BaseModel):
       chars_in: int
       chars_out: int
       elapsed_ms: float
       terms_matched: int
   - Handler:
     - Lấy glossary của project (nếu có)
     - Gọi pipeline preprocess + qt_pass
     - Return convert_text + stats

2. Mount router vào main.py

3. tests/integration/test_convert_endpoint.py:
   - POST /convert với text TRung → 200, có convert_text
   - POST /convert text rỗng → 422
   - POST /convert text >200k → 422
   - POST /convert với project_id không tồn tại → 404
   - POST /convert với glossary có term → term được apply

Verify thủ công bằng curl:
curl -X POST http://localhost:8000/convert -H "Content-Type: application/json" -d '{"text":"我是李青"}'

Commit: feat(api): add /convert endpoint
```

✅ **Kiểm tra**: curl ra Hán-Việt. Test pass.

---

### STEP 1.8 — Endpoint `/translate/chapter`

🎯 **Mục tiêu**: POST `/translate/chapter` → dịch full bằng AI.

🗣️ **Bạn nói với Claude Code**:

```
Add /translate/chapter endpoint:

1. src/dich_ai/api/routes/translate.py thêm:
   - POST /translate/chapter
   - Request:
     class TranslateChapterRequest(BaseModel):
       text: str = Field(min_length=1, max_length=200_000)
       source_lang: SourceLang = "zh"
       target_lang: TargetLang = "vn"
       project_id: int | None = None
       mode: TranslationMode = "polish"
   - Response:
     class TranslateChapterResponse(BaseModel):
       convert_text: str
       final_text: str | None  # None if mode=convert
       stats: TranslateStats
       warnings: list[str]
   - Handler:
     - Lấy project (nếu có) và glossary
     - Gọi pipeline.translate_chapter()
     - Return result + stats

2. tests/integration/test_translate_endpoint.py:
   - Mock provider
   - POST với mode=polish → có final_text
   - POST với mode=convert → final_text None
   - POST với text rỗng → 422
   - POST khi provider 429 → 429 response
   - POST khi provider safety block → 451 response

⚠️ KHÔNG dùng real API trong test — chỉ mock. Real API smoke test làm thủ công.

Verify thủ công:
curl -X POST http://localhost:8000/translate/chapter \
  -H "Content-Type: application/json" \
  -d '{"text":"我是李青，今年十八岁。","mode":"polish"}'

Commit: feat(api): add /translate/chapter endpoint
```

✅ **Kiểm tra**: curl ra bản dịch tiếng Việt mượt. Test pass.

---

### STEP 1.9 — Tuần 1 Retro + buffer

🎯 **Mục tiêu**: Tổng kết, fix bugs nhỏ, đảm bảo backend solid trước tuần 2.

🗣️ **Bạn nói với Claude Code**:

```
Tuần 1 retrospective:

1. Run full test suite: uv run pytest -v --cov=dich_ai --cov-report=term-missing
2. Run mypy strict: uv run mypy src/
3. Run ruff: uv run ruff check src/
4. Run black: uv run black --check src/
5. Báo cáo:
   - Tổng tests pass/fail
   - Coverage tổng
   - Coverage cho mỗi module (core, qt_dict, providers, persistence, api)
   - Tech debt list (nếu có)

6. Nếu coverage <80% cho bất kỳ module nào trong core/, qt_dict/, providers/, persistence/ → add tests
7. Fix mọi mypy/ruff issues
8. Update CHANGELOG.md

9. Tạo file docs/WEEK1_RETRO.md:
   - Tổng thời gian thật vs plan
   - Cái gì làm tốt
   - Cái gì cần cải thiện tuần 2
   - Tech debt
   - Decision đã thay đổi (nếu có)

Commit: chore: week 1 retrospective + test coverage
```

🙋 **Bạn cần làm tay**:
- Đọc `docs/WEEK1_RETRO.md`
- Nếu thấy quá tải / cần điều chỉnh → bàn lại với Claude (chat), không phải Claude Code

✅ **Kiểm tra**:
- Coverage `core/`, `qt_dict/`, `providers/`, `persistence/` đều >80%
- 0 mypy errors, 0 ruff errors
- Smoke test thủ công: convert + translate qua curl đều work với truyện thật

---

## ⚙️ PHASE 2 — Backend Complete + Frontend Bootstrap (Tuần 2)

> **Mục tiêu cuối tuần 2**: Backend có thêm batch + SSE + project CRUD. Frontend init xong, có Tủ sách page list được data từ backend.

---

### STEP 2.1 — Job queue (async tasks in-process)

🎯 **Mục tiêu**: Có cơ chế chạy long-running task in background, track progress.

🗣️ **Bạn nói với Claude Code**:

```
Build in-process job queue:

1. src/dich_ai/core/jobs.py:
   - class JobManager:
     - _jobs: dict[str, JobInfo]
     - async def submit(job_type, coro_factory) -> str (returns job_id)
     - async def get(job_id) -> JobInfo | None
     - async def list_active() -> list[JobInfo]
     - async def cancel(job_id) -> bool
     - subscribe(job_id) -> AsyncIterator[JobInfo]  # for SSE
   - Singleton pattern (1 instance trong app lifecycle)
   - Persist tới SQLite qua JobORM khi state changes

2. JobInfo extends Job (pydantic):
   - task: asyncio.Task  # internal, không expose qua API
   - subscribers: list[asyncio.Queue]  # for SSE fanout

3. tests/unit/test_jobs.py:
   - submit task → state queued → running → done
   - cancel running task → state cancelled
   - failed task → state failed với error message
   - subscribe → receive updates → unsubscribe
   - 10 jobs concurrent

⚠️ LƯU Ý:
- KHÔNG dùng Celery/Redis (forbidden tech)
- Jobs lost khi app restart — OK cho v1, sẽ defer persistent queue v1.1
- Limit max concurrent jobs = 3 (config) để tránh overload Gemini quota

Commit: feat(core): add in-process async job manager
```

✅ **Kiểm tra**: Tests pass. mypy clean.

---

### STEP 2.2 — SSE endpoint cho progress

🎯 **Mục tiêu**: GET `/jobs/{id}/stream` → server push progress updates qua SSE.

🗣️ **Bạn nói với Claude Code**:

```
Add SSE for job progress:

1. src/dich_ai/api/routes/jobs.py:
   - GET /jobs/{id} → return JobInfo (không kèm task)
   - GET /jobs/{id}/stream → SSE
     - Stream events định dạng SSE:
       event: progress
       data: {"completed": 5, "total": 100, "progress": 0.05}
       
       event: done
       data: {"result": ...}
       
       event: error
       data: {"error": "..."}
   - DELETE /jobs/{id} → cancel job

2. Dùng sse-starlette library (uv add sse-starlette)

3. tests/integration/test_sse.py:
   - Submit fake long job
   - Connect SSE
   - Receive progress events
   - Receive done event

Verify thủ công:
- Submit 1 batch job (sẽ test sau Step 2.3)
- curl -N http://localhost:8000/jobs/{id}/stream → thấy events stream

Commit: feat(api): add sse endpoint for job progress
```

✅ **Kiểm tra**: Test pass. Manual SSE test work.

---

### STEP 2.3 — Endpoint `/translate/batch`

🎯 **Mục tiêu**: POST `/translate/batch` với array chapters → trả job_id, dịch background.

🗣️ **Bạn nói với Claude Code**:

```
Add /translate/batch:

1. src/dich_ai/api/routes/translate.py thêm:
   - POST /translate/batch
   - Request:
     class BatchTranslateRequest(BaseModel):
       project_id: int
       chapter_ids: list[int]
       mode: TranslationMode = "polish"
   - Response:
     class BatchTranslateResponse(BaseModel):
       job_id: str
   - Handler:
     - Validate project + chapters tồn tại
     - Submit job to JobManager
     - Background coro:
       - Lặp chapter_ids
       - Mỗi chapter: gọi pipeline.translate_chapter()
       - Update chapter trong DB (status, final_text)
       - Update job progress
       - Catch error per chapter → mark chapter failed, continue
     - Return job_id ngay

2. tests/integration/test_batch.py:
   - 5 chapters → submit batch → poll job → done
   - 1 chapter fail → batch vẫn xong, chapter đó status=failed
   - Cancel mid-batch → các chapter chưa run = pending

⚠️ Concurrency: batch dịch TUẦN TỰ trong v1 (theo CLAUDE.md anti-pattern §16 — parallel dễ overload quota). Defer parallel v1.1.

Commit: feat(api): add /translate/batch with background job
```

✅ **Kiểm tra**: Test pass. Manual: submit batch 3 chương, xem progress qua SSE.

---

### STEP 2.4 — Projects + Chapters CRUD

🎯 **Mục tiêu**: Full CRUD cho project và chapter.

🗣️ **Bạn nói với Claude Code**:

```
Implement project + chapter CRUD:

1. src/dich_ai/api/routes/projects.py:
   - GET /projects → list
   - POST /projects → create (auto-generate slug from title)
   - GET /projects/{id} → detail (include chapter_count)
   - PATCH /projects/{id} → update title, description, langs
   - DELETE /projects/{id} → cascade delete chapters + terms

2. src/dich_ai/api/routes/chapters.py:
   - GET /projects/{id}/chapters → list (with pagination ?skip=0&limit=50)
   - POST /projects/{id}/chapters → create (auto chapter_index nếu None)
   - GET /chapters/{id} → detail (full text)
   - PATCH /chapters/{id} → update title, source_text, final_text
   - DELETE /chapters/{id}

3. Add slug generator: unicodedata + regex để slugify Vietnamese title

4. tests/integration/test_projects_crud.py + test_chapters_crud.py:
   - Full CRUD flow
   - Cascade delete
   - Unique constraint violations → 409
   - 404 cho id không tồn tại

5. Update docs/API.md với schema thật.

Commit: feat(api): add projects + chapters crud
```

✅ **Kiểm tra**: Test pass. Manual curl create project + chapter work.

---

### STEP 2.5 — Frontend setup + API client

🎯 **Mục tiêu**: Frontend init Tailwind + shadcn theo Hako-style + API client TanStack Query.

🗣️ **Bạn nói với Claude Code**:

```
Setup frontend foundation:

1. src/lib/api.ts:
   - Base URL từ VITE_API_URL env (default http://localhost:8000)
   - apiClient với fetch wrapper
   - Type-safe endpoints:
     - api.health.check()
     - api.projects.list(), create, get, update, delete
     - api.chapters.list(projectId), create, get, update, delete
     - api.translate.convert(req), chapter(req), batch(req)
     - api.glossary.list(projectId), create, update, delete
   - Mỗi function trả Promise<T> với type rõ ràng
   - Throw ApiError với status + message

2. src/lib/sse.ts:
   - Hook useJobStream(jobId) dùng EventSource
   - Return { status, progress, completed, total, error }

3. src/main.tsx:
   - Wrap App với QueryClientProvider (TanStack Query)
   - BrowserRouter
   - Default queryClient config: retry 1, staleTime 5min

4. src/components/ui/ (shadcn install primitives cần ngay):
   - pnpm dlx shadcn@latest add button card dialog input label sonner tabs textarea
   
5. src/App.tsx:
   - Layout shell:
     - Top nav (logo "Dịch Ai" + breadcrumb)
     - Sidebar trái: nav items (Tủ sách, Settings)
     - Main content area
   - Routes:
     - / → BookshelfPage (placeholder)
     - /settings → SettingsPage (placeholder)
     - /book/:slug → BookDetailPage (placeholder)
     - /book/:slug/chapter/:idx → ReaderPage (placeholder)
   - Theme provider (light/dark/sepia) — use shadcn theme provider

6. Tailwind theme tokens trong src/index.css:
   - Light theme: bg #f4f2ee (cream — như Hako), text #1a1a1a
   - Dark theme: bg #1a1a1a, text #e8e6e2
   - Sepia theme: bg #f4ecd8, text #3a2f25
   - Font: serif (Lora hoặc Source Serif Pro) cho reading, sans (Inter) cho UI

7. Verify:
   - pnpm dev → http://localhost:5173 thấy shell layout
   - pnpm typecheck → 0 errors
   - pnpm lint → 0 errors

⚠️ LƯU Ý:
- KHÔNG dùng `any` type
- KHÔNG inline style, dùng Tailwind utility
- Form sẽ luôn dùng react-hook-form + zod (setup sau)

Commit: feat(frontend): scaffold app shell + api client + theme
```

✅ **Kiểm tra**: 
- Dev server start, layout shell hiển thị
- Cream theme đẹp, có dark mode toggle work
- Click nav items đổi route (page rỗng OK)

---

### STEP 2.6 — Bookshelf page (Tủ sách)

🎯 **Mục tiêu**: Trang home liệt kê truyện từ backend, có button "Truyện mới".

🗣️ **Bạn nói với Claude Code**:

```
Build Bookshelf page:

1. src/features/bookshelf/BookCard.tsx:
   - Props: project: Project
   - Display: title, chapter_count, description preview, last updated
   - Click → navigate /book/{slug}
   - Hover effect

2. src/features/bookshelf/AddBookDialog.tsx:
   - Dialog với form (react-hook-form + zod):
     - title (required, max 200)
     - source_lang (select: zh/en/vn, default zh)
     - target_lang (select: vn/en, default vn)
     - description (optional)
   - On submit → api.projects.create() → close dialog + refetch list
   - Loading state, error state

3. src/features/bookshelf/BookshelfPage.tsx:
   - useQuery api.projects.list()
   - Render grid 3-cột (responsive: 1 mobile, 2 tablet, 3 desktop)
   - Empty state: "Tủ sách trống. Thêm truyện đầu tiên?"
   - Button "+ Truyện mới" mở AddBookDialog
   - Skeleton loading
   - Error state với retry button

4. src/App.tsx update route / → BookshelfPage

5. Tests (Vitest + React Testing Library):
   - pnpm add -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom jsdom
   - Setup vitest config
   - Test: render BookshelfPage with mock API → list books
   - Test: empty state hiển thị
   - Test: error state hiển thị retry

Verify:
- Start backend (port 8000)
- Start frontend (port 5173)
- Mở http://localhost:5173 → thấy "Tủ sách trống" (vì DB rỗng)
- Click "+ Truyện mới" → fill form → submit → thấy book card
- Refresh → vẫn còn (vì persisted)

Commit: feat(bookshelf): add bookshelf page + add book dialog
```

✅ **Kiểm tra**: 
- Tạo được truyện qua UI
- Truyện hiển thị trong list
- F5 refresh truyện vẫn còn

---

### STEP 2.7 — Book detail + chapter import

🎯 **Mục tiêu**: Click vào truyện → thấy chapter list, có button add chapter.

🗣️ **Bạn nói với Claude Code**:

```
Build BookDetailPage:

1. src/features/bookshelf/BookDetailPage.tsx:
   - Route: /book/:slug
   - useQuery: api.projects.get(slug) + api.chapters.list(projectId)
   - Layout:
     - Header: title, description, edit button (mở dialog edit project)
     - Tab "Chương" | "Glossary" | "Cài đặt"  (Glossary và Cài đặt placeholder)
     - Chương tab:
       - Toolbar: button "Thêm chương" + "Dịch hàng loạt" (disabled khi chưa có chương)
       - Chapter list: index | title | status badge | actions (view, translate, delete)
       - Empty state

2. src/features/translator/AddChapterDialog.tsx:
   - 2 modes: paste text | upload file (.txt)
   - Form:
     - title (auto từ first line hoặc manual)
     - chapter_index (auto next)
     - source_text (textarea hoặc dropped file content)
   - On submit → api.chapters.create() → refetch

3. src/features/translator/ImportTextFromURLDialog.tsx (DEFER v1.1):
   - Placeholder button, click → toast "Sẽ có ở v1.1"

4. Tests:
   - BookDetailPage render với 0 chapters → empty state
   - BookDetailPage render với 3 chapters → list
   - AddChapterDialog: submit → call API
   - Delete chapter → confirm dialog → API call

Verify:
- Click 1 truyện → vào detail page
- Click "Thêm chương" → paste text → submit → thấy trong list
- Refresh vẫn còn

Commit: feat(bookshelf): add book detail page + add chapter dialog
```

✅ **Kiểm tra**: Add chapter qua UI work. Chapter list hiển thị.

---

### STEP 2.8 — Tuần 2 Retro

🎯 **Mục tiêu**: Tổng kết tuần 2.

🗣️ **Bạn nói với Claude Code**:

```
Tuần 2 retrospective:

1. Run all tests: BE + FE
2. Coverage check (BE >80% cho core modules)
3. mypy + ruff + tsc + eslint clean
4. Update CHANGELOG.md
5. Tạo docs/WEEK2_RETRO.md với:
   - Done vs planned
   - Issues found
   - Tech debt
   - Decisions changed (nếu có)
6. Smoke test e2e:
   - Tạo project mới qua UI
   - Add 1 chương qua UI
   - Verify chapter persist sau F5

Commit: chore: week 2 retrospective
```

✅ **Kiểm tra**:
- E2E smoke test pass
- Mọi test/lint clean
- Đọc retro doc, lên dây cót cho tuần 3

---

## 📖 PHASE 3 — Reader + Translator UI (Tuần 3)

> **Mục tiêu cuối tuần 3**: Đọc được chương đã dịch trong reader đẹp. Dịch được chương qua UI. Batch dịch có progress bar.

---

### STEP 3.1 — Reader component (đọc dọc)

🎯 **Mục tiêu**: Trang reader hiển thị chương đẹp như Hako: serif font, line-height rộng, max-width center.

🗣️ **Bạn nói với Claude Code**:

```
Build Reader page:

1. src/features/reader/ReaderPage.tsx:
   - Route: /book/:slug/chapter/:idx
   - useQuery: api.chapters.get(id)
   - Layout:
     - Header sticky top (hiện khi scroll up, ẩn khi scroll down):
       - Back button → book detail
       - Chapter title
       - Chapter index navigation (← prev | "5 / 100" | next →)
     - Main content:
       - max-width: 720px center
       - padding: 32px responsive
       - Display final_text với:
         - font-family serif
         - font-size: 18px (configurable)
         - line-height: 1.8
         - paragraph spacing: 1.5em
         - text-align: justify
       - Mỗi đoạn = <p>, split by \n\n
     - Footer:
       - Prev | Next buttons
       - "Mục lục" button → drawer hiển thị toàn bộ chapter list

2. src/features/reader/useReaderSettings.ts (Zustand store):
   - fontSize: 14 | 16 | 18 | 20 | 24
   - fontFamily: "serif" | "sans" | "mono"
   - theme: "light" | "dark" | "sepia"
   - maxWidth: 640 | 720 | 840 | 960
   - lineHeight: 1.6 | 1.8 | 2.0
   - persist tới localStorage

3. src/features/reader/ReaderToolbar.tsx:
   - Floating button bottom-right
   - Click → popover với controls cho font size, family, theme, max-width, line-height
   - Preview live

4. src/features/reader/ChapterDrawer.tsx:
   - Sheet/drawer slide từ phải
   - List chapters với scroll, highlight chương đang đọc
   - Click → navigate

5. Keyboard shortcuts (chỉ trong ReaderPage):
   - ← : prev chapter
   - → : next chapter
   - j / down: scroll down
   - k / up: scroll up
   - g : open chapter drawer
   - ?: show shortcuts help

6. Tests: render chapter content, navigate prev/next, change font size

Verify:
- Mở 1 chapter đã có final_text
- Reader đẹp, dễ đọc
- Đổi font size live
- Nav prev/next work
- F5 giữ reader settings

Commit: feat(reader): add reader page with toolbar + chapter drawer
```

✅ **Kiểm tra**: Reader đẹp, controls work, persist setting.

---

### STEP 3.2 — Single chapter translate UI

🎯 **Mục tiêu**: Trong reader, có button "Dịch chương này" → gọi API → hiển thị kết quả.

🗣️ **Bạn nói với Claude Code**:

```
Add translation controls:

1. src/features/translator/TranslateButton.tsx:
   - Props: chapterId, currentStatus, mode
   - States:
     - Idle: button "Dịch" + dropdown mode (Convert / Polish)
     - Translating: spinner + "Đang dịch... (00:23)"
     - Done: checkmark + "Đã dịch"
     - Failed: red icon + "Lỗi" + retry button
   - On click "Dịch":
     - useMutation api.translate.chapter()
     - Show progress với toast
     - On success → invalidate chapter query → reader hiển thị final_text

2. src/features/reader/ReaderPage.tsx update:
   - Nếu chapter chưa có final_text:
     - Hiển thị placeholder "Chương này chưa được dịch."
     - Hiển thị TranslateButton lớn ở giữa
     - Show source_text bên dưới (collapsible)
   - Nếu có final_text:
     - Hiển thị final_text như cũ
     - Top-right có button "Dịch lại" (đỏ, double-confirm)
     - Button toggle "Xem bản gốc" → split view

3. src/features/translator/SplitView.tsx:
   - 2 cột: source bên trái, final bên phải
   - Đồng bộ scroll
   - Highlight đoạn tương ứng khi hover

4. Tests: translate flow happy path, error case, retry

Verify:
- Mở 1 chapter chưa dịch → thấy Translate button
- Click → spinner → 10-30s sau → final_text hiện
- F5 → final_text vẫn còn
- Toggle split view work

Commit: feat(translator): add translate button + split view
```

✅ **Kiểm tra**: Dịch 1 chương qua UI work end-to-end.

---

### STEP 3.3 — Batch translate UI với SSE progress

🎯 **Mục tiêu**: Trong BookDetailPage, click "Dịch hàng loạt" → modal chọn chapters → progress bar real-time.

🗣️ **Bạn nói với Claude Code**:

```
Add batch translate UI:

1. src/features/translator/BatchTranslateDialog.tsx:
   - Trigger: button "Dịch hàng loạt" trong BookDetailPage
   - Body:
     - List chapters với checkbox (select all / select pending only)
     - Mode selector (Convert / Polish)
     - Estimated tokens + time (cảnh báo nếu >1000 chapters)
     - Button "Bắt đầu"
   - On submit:
     - api.translate.batch() → nhận job_id
     - Đóng dialog, mở BatchProgressDialog

2. src/features/translator/BatchProgressDialog.tsx:
   - useJobStream(jobId)
   - Display:
     - Overall progress bar (completed / total)
     - Current chapter title
     - Tokens used
     - Time elapsed
     - Chapter list với status badge updated live
     - Errors list (nếu có chapter fail)
   - Buttons:
     - "Dừng" → DELETE /jobs/{id}
     - "Đóng" (chỉ khi done) — không close khi running
   - Khi done: toast "Đã dịch xong X/Y chương"
   - Khi cancel: confirm dialog

3. src/features/bookshelf/BookDetailPage.tsx update:
   - Disable "Dịch hàng loạt" khi không có chapter pending
   - Show batch progress nếu có job đang chạy cho project này

4. Tests: 
   - Open dialog → select chapters → submit → progress updates → done
   - Cancel mid-way
   - SSE disconnect → reconnect

Verify:
- Add 5 chapters
- Click "Dịch hàng loạt" → select all → mode polish → start
- Thấy progress bar updates real-time
- Done → tất cả chapters có final_text

Commit: feat(translator): add batch translate dialog with sse progress
```

✅ **Kiểm tra**: Batch translate 5+ chapters work, progress smooth.

---

### STEP 3.4 — Glossary UI

🎯 **Mục tiêu**: Tab Glossary trong BookDetailPage cho add/edit/delete thuật ngữ, áp dụng khi dịch.

🗣️ **Bạn nói với Claude Code**:

```
Build Glossary UI:

1. src/features/glossary/GlossaryTab.tsx:
   - Trong BookDetailPage tab "Glossary"
   - Toolbar: button "Thêm term" + search input + filter category
   - Table:
     - Columns: Source | Target | Category | Locked | Notes | Actions
     - Sortable
     - Pagination 50/page
   - Actions: edit (inline) | delete (confirm)
   - Bulk select + bulk delete

2. src/features/glossary/AddTermDialog.tsx:
   - Form:
     - source (required)
     - target (required)
     - category (select: character/place/skill/item/term, default term)
     - locked (checkbox, default false)
     - notes (textarea optional)
   - Submit → api.glossary.create()

3. src/features/glossary/EditTermInline.tsx:
   - Double-click row để edit inline
   - Press Enter save, Esc cancel

4. Backend: ensure glossary áp dụng khi /convert và /translate (đã có từ Step 1.7-1.8, verify lại)

5. Tests: CRUD glossary terms, bulk delete, search filter

Verify:
- Thêm 5 term: e.g. 李青 → Lý Thanh (character, locked)
- Re-translate 1 chapter có chữ 李青 → output có "Lý Thanh"
- Edit term → re-translate → output đổi
- Delete term → re-translate → revert về QT default

Commit: feat(glossary): add glossary management ui
```

✅ **Kiểm tra**: Glossary CRUD work, áp dụng khi dịch.

---

### STEP 3.5 — Tuần 3 Retro

🎯 **Mục tiêu**: Tổng kết tuần 3, tới đây app đã usable cho dịch.

🗣️ **Bạn nói với Claude Code**:

```
Tuần 3 retrospective:

1. Full test BE + FE
2. Smoke test e2e:
   - Tạo project
   - Add 5 chapters
   - Add 5 glossary terms (mix locked + unlocked)
   - Single translate 1 chapter → verify final_text
   - Batch translate 4 còn lại → verify all done
   - Đọc 1 chapter trong reader
   - Đổi theme, font → persist
3. Đo: thời gian dịch 1 chapter trung bình (target <30s với Gemini Flash)
4. Tạo docs/WEEK3_RETRO.md
5. Update CHANGELOG.md

Commit: chore: week 3 retrospective
```

✅ **Kiểm tra**:
- App dùng được end-to-end cho 1 use case thực
- Quyết định features cho tuần 4 (polish vs add small feature)

---

## 🎨 PHASE 4 — Settings + Polish + Migrate (Tuần 4)

> **Mục tiêu cuối tuần 4**: App dùng được hàng ngày, migrate được 1 truyện thực từ LiTTrans, có README + setup guide cho user khác.

---

### STEP 4.1 — Settings page

🎯 **Mục tiêu**: Settings page cho API key, default theme, font, dict path.

🗣️ **Bạn nói với Claude Code**:

```
Build Settings page:

1. src/features/settings/SettingsPage.tsx:
   - Tabs: "Chung" | "API Keys" | "Convert" | "Giao diện" | "Đồng bộ" (disabled, sẽ ghi "Sắp có" cho v1.1)

2. Tab "Chung":
   - Language (Tiếng Việt / English) — chỉ stub, full i18n v1.1
   - Default source/target lang
   - Default mode (convert/polish)

3. Tab "API Keys":
   - Gemini API Key input (password type, có toggle show/hide)
   - Test button → call /health/deep với key → ✅ hoặc ❌
   - Fallback keys (multiple, +/- buttons)
   - Lưu local trong backend settings (PATCH /settings hoặc UPDATE .env via API endpoint riêng — cẩn thận security, chỉ accept từ localhost)

4. Tab "Convert":
   - Dictionary directory path input
   - Stats: số dict files loaded, tổng entries
   - Reload button → trigger backend reload applier

5. Tab "Giao diện":
   - Default theme (light/dark/sepia)
   - Default font size, family, line-height
   - Reader max-width
   - All persist tới localStorage (frontend) + có thể sync settings global qua backend (chỉ cho v1, simple)

6. Backend cần endpoint:
   - GET /settings → return current settings (sanitize: hide API keys, only show last 4 chars)
   - PATCH /settings → update non-secret fields
   - POST /settings/test-api-key → verify

7. Tests: tabs render, test API key flow, update settings

⚠️ Security: 
- API key chỉ accept update từ localhost (check origin)
- KHÔNG return API key đầy đủ trong GET (chỉ "AIza...xxx1234")
- KHÔNG log API key

Commit: feat(settings): add settings page with api keys + theme
```

✅ **Kiểm tra**: Đổi API key qua UI work. Theme default applied khi mở mới.

---

### STEP 4.2 — Error boundaries + loading states polish

🎯 **Mục tiêu**: App không crash khi gặp error, loading states đẹp, không có "flicker".

🗣️ **Bạn nói với Claude Code**:

```
Polish error handling + loading:

1. src/components/ErrorBoundary.tsx:
   - React error boundary
   - Fallback UI: "Đã xảy ra lỗi 😅 [Tải lại trang] [Báo cáo]"
   - Log error tới console + send tới backend /errors/report (best-effort, không block)

2. src/components/AppErrorBoundary.tsx:
   - Wrap App với ErrorBoundary
   - Đặt cũng wrap mỗi route page

3. Loading states audit:
   - Mỗi useQuery: skeleton thay vì spinner
   - Mỗi useMutation: button có loading state (spinner inside button, disabled)
   - Mỗi page có suspense fallback

4. Toast notifications (sonner — đã cài):
   - Success: green, 3s
   - Error: red, 5s
   - Loading: với promise

5. Empty states audit:
   - Tủ sách trống: illustration + CTA
   - Chapter list trống: illustration + CTA
   - Glossary trống: illustration + CTA
   - Search no result: text + suggestion

6. Network error global handler:
   - Backend down (port 8000 không response) → toast "Backend không kết nối được. Đảm bảo backend đang chạy."

Commit: chore(ui): polish error boundaries, loading, empty states
```

✅ **Kiểm tra**:
- Stop backend → UI hiển thị error thân thiện
- Mọi loading state có skeleton/spinner
- Mọi empty state có guidance

---

### STEP 4.3 — Accessibility (a11y) pass

🎯 **Mục tiêu**: Keyboard navigation work, screen reader friendly, focus visible.

🗣️ **Bạn nói với Claude Code**:

```
A11y pass:

1. Audit với axe-core:
   - pnpm add -D @axe-core/react
   - Setup trong dev mode chỉ
   - Fix issues reported

2. Keyboard navigation:
   - Mọi interactive element tab-able
   - Esc đóng dialogs/popovers
   - Focus visible (Tailwind focus-visible classes)
   - Focus trap trong dialog (shadcn lo)

3. ARIA labels:
   - Icon-only buttons có aria-label
   - Loading có aria-busy
   - Error có role="alert"

4. Color contrast:
   - Check WCAG AA cho text trong 3 themes
   - Đặc biệt sepia, có thể cần adjust

5. Skip to content link cho keyboard users

Commit: chore(a11y): improve keyboard nav, aria labels, focus
```

✅ **Kiểm tra**: Tab navigate được toàn app. Axe report ít/0 violations.

---

### STEP 4.4 — Migrate 1 truyện từ LiTTrans

🎯 **Mục tiêu**: Import truyện 50+ chương từ LiTTrans data sang app mới.

🗣️ **Bạn nói với Claude Code**:

```
Build migration script:

1. backend/scripts/migrate_from_littrans.py (Typer CLI):
   - Args:
     - --from PATH (LiTTrans novel directory)
     - --title STR
     - --slug STR
   - Steps:
     1. Đọc inputs/*.txt → source_text per chapter
     2. Đọc outputs/*_VN.txt → final_text (nếu có)
     3. Đọc Glossary.json → import terms với category="term"
     4. Đọc Characters_Active.json → import character names → terms với category="character", locked=True
     5. Create project + chapters + terms qua repos
   - Idempotent: dùng upsert (project slug + chapter index)
   - Progress: tqdm bar
   - Dry-run mode: --dry-run (chỉ in ra plan)

2. tests/unit/test_migration.py:
   - Mock LiTTrans dir
   - Test full migration → DB has expected data
   - Test re-run = idempotent (không duplicate)

3. CLI usage:
   uv run python scripts/migrate_from_littrans.py \
     --from /path/to/littrans/data/royalroad_com_fiction_66455 \
     --title "Tên Truyện" \
     --slug "ten-truyen"

⚠️ KHÔNG modify LiTTrans data — chỉ đọc.

Commit: feat(migration): add script to import from littrans
```

🙋 **Bạn cần làm tay**:
- Backup LiTTrans data trước khi chạy (safety)
- Chạy migration với --dry-run trước
- Verify số chapter + term import đúng
- Run real migration

✅ **Kiểm tra**: Mở app, thấy truyện migrate, đọc được trong reader.

---

### STEP 4.5 — E2E smoke test + README

🎯 **Mục tiêu**: Có hướng dẫn setup từ đầu cho người khác (hoặc bản thân 6 tháng sau).

🗣️ **Bạn nói với Claude Code**:

```
Final docs:

1. README.md update:
   - Description
   - Screenshots (placeholder, sẽ thêm thật sau)
   - Tech stack
   - Setup instructions:
     - Prerequisites (Python 3.11+, Node 20+, pnpm, uv)
     - Clone repo
     - Backend: cd backend && uv sync && cp .env.example .env && edit GEMINI_API_KEY
     - Backend: alembic upgrade head
     - Backend: uv run uvicorn dich_ai.main:app --port 8000
     - Frontend: cd frontend && pnpm install
     - Frontend: pnpm dev
     - Open http://localhost:5173
   - First use:
     - Settings → add Gemini API key
     - Settings → set dict path
     - Tủ sách → tạo project mới
     - Add chapter → dịch
   - Troubleshooting section (5-10 common issues)
   - License (chọn MIT hoặc tương tự)

2. docs/TROUBLESHOOTING.md:
   - Port 8000 đã dùng
   - Backend không connect được
   - Gemini API key invalid
   - QT dict không apply
   - Migration fail
   - SSE disconnect

3. docs/ARCHITECTURE.md update với final state

4. CHANGELOG.md update version 1.0.0 - 2026-XX-XX với full feature list

5. End-to-end smoke test:
   - Clean install: rm -rf backend/.venv frontend/node_modules
   - Follow README chính xác
   - Phải work từ zero → dịch được chapter đầu

Commit: docs: finalize readme, troubleshooting, changelog v1.0.0
```

🙋 **Bạn cần làm tay**:
- Follow README như người mới hoàn toàn
- Note mỗi step không clear/sai → bảo Claude Code fix README

✅ **Kiểm tra**: README đủ để clean install + dùng.

---

### STEP 4.6 — Final retro + v1.0 tag

🎯 **Mục tiêu**: Tag version 1.0.0, planning v1.1.

🗣️ **Bạn nói với Claude Code**:

```
Final tasks:

1. Run all tests + lint final time, 0 errors
2. Bump version: backend pyproject.toml 0.1.0 → 1.0.0
3. Bump version: frontend package.json 0.0.0 → 1.0.0
4. Tag: git tag v1.0.0 -m "Initial release"
5. Tạo docs/PROJECT_RETROSPECTIVE.md:
   - 4 tuần đã làm gì
   - Plan vs Actual (timeline)
   - Cái gì hoạt động tốt
   - Cái gì khó / mất nhiều thời gian
   - Tech debt accumulate
   - Top 3 ưu tiên cho v1.1
6. Update docs/V1_1_BACKLOG.md với:
   - Priority order
   - Estimated effort

Commit: chore: release v1.0.0
```

✅ **Kiểm tra**:
- `git tag` thấy v1.0.0
- App dùng được hàng ngày
- Đọc retro doc, plan v1.1 với head clear

---

## 📊 Quy tắc Vàng cho Vibe Coder (tổng hợp)

### Khi nào commit git?

**Sau MỖI step xong + test pass.** Nếu Claude Code không tự commit, bảo nó.

### Khi nào revert?

Step phá hỏng cái trước:
```
git log --oneline    # xem commits
git revert HEAD       # an toàn, tạo revert commit
# hoặc CẨN THẬN:
git reset --hard HEAD~1   # xóa commit cuối, không thể undo dễ
```

### Cách yêu cầu Claude Code fix bug

KHÔNG nói: "Code không chạy, fix đi"
NÓI:
```
Khi tôi chạy lệnh: <lệnh chính xác>
Tôi gặp lỗi này: <paste full error/traceback>

File liên quan: src/dich_ai/...
Tôi expect: <kết quả mong đợi>
Thực tế: <kết quả thực tế>

Hãy debug và fix theo CLAUDE.md §6 (THINK-FIRST) và §7 (VERIFY).
```

### Khi Claude Code suggest gì lạ

- "Cài thêm package X" → STOP, kiểm tra có trong CLAUDE.md §4 không. Nếu không → hỏi tại sao.
- "Refactor toàn bộ module Y" → STOP, hỏi tại sao trước. Scope creep nguy hiểm.
- "Xóa file Z" → CONFIRM 2 lần, có git backup chưa.
- "Sửa file ngoài project" → TUYỆT ĐỐI KHÔNG.
- "Skip test này tạm thời" → KHÔNG, fix code thay vì skip test.

### Quản lý expectation

| Tuần | % done | Cảm xúc dự kiến |
|---|---|---|
| 1 | 25% | "Mới có backend, chưa có UI, nản 1 chút" |
| 2 | 50% | "Có UI rồi, dù đơn giản. Có hi vọng." |
| 3 | 75% | "Đọc được truyện đã dịch trong UI mình tự build. Wow." |
| 4 | 100% | "Mình có hako-local thật rồi." |

**Đừng so sánh tốc độ với người khác.** Vibe coding khác. Skill của bạn là **biết yêu cầu cái gì + biết verify**, không phải gõ code.

---

## 🆘 Khi nào bí, hỏi Claude (chat) thay vì Claude Code

Claude Code giỏi: implement code, fix bug cụ thể, refactor file
Claude (chat) giỏi: design decision, debate kiến trúc, giải thích concept

**Hỏi chat khi:**
- "Step này có nhất thiết không?"
- "Tại sao dùng FastAPI mà không Flask?"
- "Tôi đang mất hứng, có nên dừng không?"
- "Tự Làm họ vừa ship feature X, mình có cần follow không?"
- Bí kỹ thuật mà Code không hiểu yêu cầu

**Đừng hỏi chat:**
- "Viết code cho tôi" → việc của Code
- "Tại sao file này lỗi?" → Code thấy file, chat không

---

## ✅ Definition of Done (project-level)

Dự án v1.0 "xong" khi:

- [ ] Backend chạy localhost:8000, có đủ endpoints trong docs/API.md
- [ ] Frontend chạy localhost:5173, đủ 5 pages: Bookshelf, BookDetail, Reader, Glossary, Settings
- [ ] Convert mode work (QT dict apply, không AI)
- [ ] Single chapter translate work với Gemini
- [ ] Batch translate work với SSE progress
- [ ] Glossary áp dụng khi dịch
- [ ] Reader đẹp: 3 themes, font controls, keyboard shortcuts
- [ ] Migrate được 1 truyện thực từ LiTTrans
- [ ] 0 mypy errors, 0 ruff errors, 0 ESLint warnings
- [ ] Coverage core modules >80%
- [ ] README đủ để clean install + dùng
- [ ] Dùng app hàng ngày để dịch truyện ít nhất 1 tuần liền không crash
- [ ] git tag v1.0.0

---

## 🚀 Sau v1.0 — định hướng v1.1

Xem `docs/V1_1_BACKLOG.md`. Top candidates:

1. **Bible system (3-tier)** — Database/WorldBuilding/Lore
2. **Name Lock 3-layer enforcement** — đảm bảo consistency tuyệt đối
3. **Multi-provider** — Claude, OpenAI, Kimi, MiniMax
4. **Scout AI / Arc Memory** — long-form context cho truyện 500+ chương
5. **Chunking cho long chapters** — split + parallel khi >4k tokens

**Đừng động vào v1.1 trước khi v1.0 dùng đủ stable 1 tuần.**

---

**END ROADMAP**

*Mỗi step là 1 win nhỏ. Mỗi commit là 1 thắng lợi nhỏ. 4 tuần sau, anh sẽ có hako-local thật sự.*

*Khi gặp khó khăn, quay lại file này. Khi mất hứng, đọc lại retro tuần trước — anh đã làm được nhiều hơn anh nghĩ.* 🚀