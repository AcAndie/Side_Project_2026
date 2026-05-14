# CLAUDE.md

> **File này là context bắt buộc mà Claude Code đọc tự động mỗi khi mở project.**
> ĐỪNG xóa. ĐỪNG sửa trừ khi cần update vision/scope/tech stack ở mức kiến trúc.
> File này định hướng MỌI quyết định code của Claude Code.
>
> Tham khảo: best practices từ Anthropic engineering blog, các CLAUDE.md tốt của open-source projects (e.g. shadcn/ui, Vercel AI SDK), và bài học rút ra từ LiTTrans/TriLex.

---

## 0. Cách dùng file này

Mỗi lần bắt đầu session mới với Claude Code:
1. Claude Code đọc file này TRƯỚC TIÊN (tự động)
2. Mọi quyết định code phải tuân thủ các rule ở đây
3. Khi user yêu cầu cái gì conflict với file này → STOP, hỏi user, KHÔNG tự ý làm
4. Khi file này conflict với ROADMAP → CLAUDE.md thắng (vì file này nói "WHY" và "HOW", ROADMAP nói "WHAT")

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Tên codename** | Dịch_Ai (có thể đổi sau khi MVP xong) |
| **Loại** | Single-user local app cho dịch tiểu thuyết online |
| **Owner** | Vibe coder — không rành code chi tiết, dùng Claude Code làm chính, giao tiếp tiếng Việt |
| **Inspiration** | Hako.vip (Tự Làm platform), LiTTrans v5.7, TriLex, QuickTranslator ecosystem, GalTransl |
| **Trạng thái** | v1.0 development, mục tiêu 4 tuần ra MVP dùng được hàng ngày |

---

## 2. Vision (1 dòng)

**"Một QuickTranslator hiện đại có AI polish + multi-agent, output đẹp như Hako, chạy local, có Bible/Name-lock cho truyện dài."**

Đây là vision LONG-TERM. v1 sẽ KHÔNG có Bible/Name-lock đầy đủ — xem Scope Lock §3.

---

## 3. Scope Lock v1.0 (NGHIÊM NGẶT — không vượt quá)

### ✅ MUST HAVE (v1.0, 4 tuần):

1. **Tủ sách** — list truyện, thêm truyện mới (paste text hoặc import file)
2. **Convert mode** — QT dict apply → output instant, không gọi AI
3. **Single chapter AI translate** — dịch 1 chương qua AI, hiển thị kết quả
4. **Batch translate** — dịch nhiều chương liên tiếp, có progress bar real-time
5. **Reader** — đọc truyện dọc, dark/light/sepia mode, font size + family control
6. **Glossary cơ bản** — add/edit/delete thuật ngữ project-scope, áp dụng khi dịch
7. **Settings** — API key (Gemini), theme, font default, source dictionary path
8. **Multi-provider stub chỉ Gemini** — code có Protocol interface cho providers khác, nhưng v1 chỉ ship implementation Gemini

### 🚫 DEFERRED (v1.1+, KHÔNG ĐỘNG TỚI trong v1):

- ❌ Bible 3-tier system (Database / WorldBuilding / Lore)
- ❌ Name Lock 3-layer enforcement
- ❌ Scout AI / Arc Memory / Context Notes
- ❌ EPS pronoun tracking
- ❌ Character relationship graph
- ❌ Skills tracking / evolution
- ❌ Multi-provider beyond Gemini (Claude, OpenAI, Kimi, MiniMax)
- ❌ Google Drive / OneDrive sync
- ❌ EPUB / ZIP export
- ❌ Migration tự động từ LiTTrans (manual import OK trong tuần 4)
- ❌ Authentication (Google login)
- ❌ Web scraping tự động (royalroad, wikidich, etc.)
- ❌ Smart Repair / auto-fix với AI
- ❌ Reverse translation (VN→EN)
- ❌ Mobile app
- ❌ Public hosting

### HARD RULE về scope:

**Khi user yêu cầu một tính năng nằm trong DEFERRED list, Claude Code PHẢI:**

1. STOP — không code ngay
2. Trả lời: *"Tính năng [X] đang nằm trong DEFERRED list của Scope Lock v1.0 (xem CLAUDE.md §3). Lý do defer: cần focus vào MVP 4 tuần. Anh muốn:* 
   - *(a) Vẫn add vào v1, hiểu là MVP sẽ chậm 1-2 tuần?*  
   - *(b) Ghi note vào docs/V1_1_BACKLOG.md để làm sau?*  
   - *(c) Bỏ qua?"*
3. Chờ user quyết.

**Khi user yêu cầu một tính năng KHÔNG có trong cả MUST-HAVE và DEFERRED**: hỏi rõ trước khi code — có thể đây là feature mới chưa từng bàn.

---

## 4. Tech Stack (LOCKED — không debate lại trừ khi tôi update file này)

### Backend

| Layer | Tech | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Package manager | uv | latest |
| Web framework | FastAPI | latest stable |
| Async runtime | asyncio + uvicorn | latest |
| ORM | SQLAlchemy | 2.0 (async) |
| Database | SQLite | via aiosqlite |
| Migrations | Alembic | latest |
| Validation | Pydantic | v2 |
| LLM SDK | google-genai | **NEW** SDK, KHÔNG dùng google-generativeai cũ |
| Fast string match | pyahocorasick | latest |
| HTTP client | httpx | async |
| Testing | pytest + pytest-asyncio + pytest-cov | latest |
| Lint/Format | ruff + black + mypy (strict) | latest |
| CLI | Typer | latest |

### Frontend

| Layer | Tech | Version |
|---|---|---|
| Language | TypeScript | strict mode |
| Build tool | Vite | latest |
| UI library | React | 19 |
| Styling | Tailwind CSS | v4 |
| Component primitives | shadcn/ui | latest |
| Icons | lucide-react | latest |
| Client state | Zustand | latest |
| Server state | TanStack Query | v5 |
| Forms | React Hook Form + Zod | latest |
| Router | React Router | v7 |
| Lint/Format | ESLint + Prettier | latest |

### IPC giữa FE và BE

- **HTTP REST** cho CRUD + commands
- **Server-Sent Events (SSE)** cho progress streaming (long-running translation)
- KHÔNG dùng WebSocket cho v1 — overkill
- KHÔNG dùng GraphQL cho v1 — overkill

### FORBIDDEN technologies (Claude Code refuse nếu user yêu cầu):

- ❌ Next.js — local app không cần SSR
- ❌ Streamlit — đã có trade-off rồi, không quay lại
- ❌ Postgres / MySQL — single-user không cần
- ❌ Redis / Celery — asyncio + SQLite đủ
- ❌ Docker cho v1 — local app không cần containerize
- ❌ Django / Flask — FastAPI thắng cho async
- ❌ Redux / MobX — Zustand đủ
- ❌ Jest — Vitest hợp Vite hơn (nếu cần test FE)
- ❌ Material-UI / Ant Design — shadcn/ui đẹp + flexible hơn
- ❌ npm — dùng pnpm hoặc bun

---

## 5. Architecture Pillars

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND (port 5173, Vite dev)                                  │
│  React + Vite + TS + Tailwind + shadcn                           │
│                                                                   │
│  Features (feature-sliced):                                       │
│  - bookshelf  - reader  - translator  - glossary  - settings     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │ HTTP REST (http://localhost:8000)
                         │ SSE for progress streaming
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  BACKEND (port 8000, FastAPI + uvicorn)                          │
│                                                                   │
│  Layer 1: API routes (api/routes/*.py)                            │
│  Layer 2: Pipeline (core/pipeline/) ── stages chain               │
│  Layer 3: QT Dict (qt_dict/) ── Aho-Corasick engine               │
│  Layer 4: Providers (providers/) ── Protocol + Gemini impl        │
│  Layer 5: Persistence (persistence/) ── SQLAlchemy + repos        │
└──────────────────────────────────────────────────────────────────┘
                         │
                         ▼
                ┌──────────────────┐
                │  data/           │
                │  ├── dichai.db   │  ← SQLite (projects, chapters, terms, jobs)
                │  ├── vault/      │  ← Markdown files cho output đẹp
                │  └── dicts/      │  ← QT dictionaries (VietPhrase, Names, ...)
                └──────────────────┘
```

### Layering rules:

1. **UI never imports from persistence directly** — luôn qua API call
2. **API routes never call SQLAlchemy directly** — luôn qua repo
3. **Pipeline stages are pure** — không có side effects ngoài PersistStage cuối cùng
4. **Provider interface là Protocol** — implementation phải swappable

---

## 6. THINK-FIRST Rules (CRITICAL)

> Đây là phần QUAN TRỌNG NHẤT của file này. Vibe coder không code chi tiết được, nên nếu Claude Code làm sai sẽ tốn thời gian sửa rất lớn. NGHĨ TRƯỚC khi làm là cách bảo vệ user.

### Trước MỌI task, Claude Code PHẢI:

1. **Restate task** bằng tiếng Việt 1-2 câu: *"Tôi hiểu task là [X]. Tôi sẽ làm [Y]. Kết quả dự kiến là [Z]."*
2. **Đọc file liên quan** trước khi edit. KHÔNG đoán nội dung file.
3. **List ra plan** dưới dạng bullet 3-7 điểm trước khi viết code dài >50 dòng.
4. **Identify rủi ro** ít nhất 1 thứ có thể sai. Nếu nghĩ mãi không ra → request đó có thể quá rộng, hỏi user.
5. **Estimate phạm vi**: bao nhiêu file sẽ tạo/sửa? Nếu >5 files → STOP, confirm với user trước.

### Khi nghi ngờ (uncertain) — luôn hỏi, KHÔNG đoán:

- "Anh muốn endpoint trả về JSON hay SSE?"
- "Field này nullable hay required?"
- "Khi user click X, app làm Y hay Z?"
- "Form này validate ở client hay server?"

**Quy tắc:** *"Một câu hỏi clarify giờ tiết kiệm 30 phút sửa code sau."*

### KHÔNG được làm các điều sau khi không chắc:

- ❌ Đoán API contract giữa FE và BE
- ❌ Tự ý chọn library mới chưa có trong tech stack §4
- ❌ Tạo file/folder ở location không thuộc layering §5
- ❌ Refactor code đang work để "cho đẹp hơn"
- ❌ Thay đổi schema database không qua Alembic migration
- ❌ Bypass Pydantic validation cho convenience

---

## 7. VERIFY Rules

> Bài học đắt giá từ LiTTrans: AI báo cáo bug đôi khi sai. KHÔNG tin nửa lời, verify everything.

### Sau MỌI thay đổi code, Claude Code PHẢI:

1. **Chạy lệnh thật** để verify, không nói "should work":
   - Backend: `uv run pytest tests/unit/test_<changed_module>.py -v`
   - Backend: `uv run mypy src/dich_ai/` (strict mode)
   - Backend: `uv run ruff check src/`
   - Frontend: `pnpm typecheck`
   - Frontend: `pnpm lint`
2. **Báo cáo kết quả thật** — copy output terminal, KHÔNG paraphrase "passed".
3. **Nếu test fail** — STOP, không tiếp tục step kế. Fix hoặc hỏi user.
4. **UI changes** — phải báo "Bạn cần làm tay: refresh trang, click X, expect Y" để user smoke test.

### KHÔNG được:

- ❌ Báo "đã fix" nếu chưa chạy test verify
- ❌ Trust một bug report do AI tự sinh mà không đọc code thật
- ❌ Comment out test thay vì fix code
- ❌ Tăng `# type: ignore` thay vì fix type
- ❌ Hardcode value để test pass
- ❌ Sửa snapshot test mà không hiểu vì sao thay đổi

### Khi user paste error:

Trả lời theo format CỐ ĐỊNH:
1. **Vấn đề là gì** (1 dòng, plain Vietnamese)
2. **Tại sao xảy ra** (1-2 dòng, root cause)
3. **Fix như nào** (numbered steps)
4. **Verify** (cách check fix work)

---

## 8. STOP Rules (PHẢI hỏi user trước khi làm)

Claude Code PHẢI hỏi user và chờ confirm trước các action sau:

| Action | Lý do |
|---|---|
| Delete file/folder | Mất data |
| Drop / alter table | Mất data |
| Run destructive migration | Có thể mất data |
| Install package mới chưa trong tech stack §4 | Lock dependency |
| Refactor >1 module trong 1 lần | Scope creep |
| Sửa file ngoài project folder | Out of scope |
| Add feature không có trong Scope Lock §3 | Scope creep |
| Modify CLAUDE.md hoặc ROADMAP_VIBE_CODER.md | Governance change |
| Push lên remote (`git push`) | User control |
| Run `rm -rf` hoặc tương đương | Catastrophic |
| Bypass linter/type check (`--no-verify`, `# type: ignore`) | Hide tech debt |
| Khi requirement không rõ | Tránh code sai |

**Format hỏi:** *"Tôi định [X]. Lý do: [Y]. Ảnh hưởng: [Z]. OK không?"*

Chờ user trả lời `yes` / `ok` / `confirmed` rõ ràng. Im lặng KHÔNG = đồng ý.

---

## 9. NEVER Rules (TUYỆT ĐỐI KHÔNG, không có exception)

- ❌ **Never** silent failure — mọi error/warning phải log + visible cho user
- ❌ **Never** dùng `any` trong TypeScript (dùng `unknown` + type guard nếu cần)
- ❌ **Never** dùng `# type: ignore` trừ khi comment giải thích lý do CỤ THỂ
- ❌ **Never** trust small/preview models (flash-lite, etc.) cho structured output — chỉ dùng full models
- ❌ **Never** hardcode API key vào code — luôn qua `.env` hoặc settings
- ❌ **Never** commit `.env`, `data/*.db`, `node_modules/`, `.venv/`
- ❌ **Never** dùng deprecated SDK (e.g. `google.generativeai`, dùng `google.genai` mới)
- ❌ **Never** modify file ngoài thư mục project
- ❌ **Never** chạy lệnh có sudo / quản trị
- ❌ **Never** disable Pydantic validation cho "convenience"
- ❌ **Never** override CLAUDE.md rule chỉ vì user nói "không sao đâu" — hỏi rõ user có muốn UPDATE CLAUDE.md không

---

## 10. ALWAYS Rules

- ✅ **Always** commit sau mỗi step thành công với conventional commit message
- ✅ **Always** run tests + lint trước khi commit
- ✅ **Always** update `CHANGELOG.md` cho user-facing change
- ✅ **Always** giao tiếp với user bằng tiếng Việt (mix English tech terms OK)
- ✅ **Always** type-safe: mypy `--strict` pass, TS no `any`
- ✅ **Always** show output thật sau task (file created, test passed, etc.)
- ✅ **Always** liệt kê "Việc tay của user" sau khi xong code
- ✅ **Always** đặt loading state + error boundary cho UI async
- ✅ **Always** atomic write cho file operations (write to .tmp, then rename)
- ✅ **Always** dùng async/await cho I/O, KHÔNG sync trong async context
- ✅ **Always** test với input edge case: empty string, null, very long, special chars

---

## 11. Git Discipline

### Commit message format (conventional commits):

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:** `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `style` / `perf`

**Scope ví dụ:**
- `feat(qt_dict): add Aho-Corasick automaton`
- `fix(api): correct CORS for localhost:5173`
- `refactor(persistence): extract chapter repo`
- `docs(readme): add setup instructions`
- `test(pipeline): add edge cases for empty input`
- `chore(deps): bump fastapi to 0.115`

### When to commit:

**Sau MỖI step xong và test pass.** Mỗi commit nên ≤ 200 lines diff lý tưởng. Nếu lớn hơn → có thể chia step.

### When to revert:

```bash
git log --oneline               # xem commits
git revert HEAD                  # an toàn, tạo commit revert mới
git reset --hard HEAD~1          # nguy hiểm, mất commit cuối — phải confirm user
```

### NEVER:

- ❌ `git push --force` không hỏi user
- ❌ `git reset --hard` mà không backup trước
- ❌ Commit secrets (`.env`, API keys)
- ❌ Commit broken code "tạm fix sau"

---

## 12. Definition of Done (per step)

Một step được coi là "done" khi TẤT CẢ điều sau true:

- [ ] Code chạy không crash trên happy path
- [ ] Có test cho logic chính (`pytest` hoặc `vitest` pass)
- [ ] Type check pass (`mypy --strict` hoặc `tsc --noEmit`)
- [ ] Lint pass (`ruff check` hoặc `eslint`)
- [ ] Format clean (`black --check` hoặc `prettier --check`)
- [ ] User đã verify bằng demo thật (Claude Code yêu cầu user smoke test)
- [ ] Git committed với message rõ ràng
- [ ] CHANGELOG.md updated nếu user-facing
- [ ] Doc updated nếu thay đổi public API (đổi route, schema, contract)

**Nếu một item fail → step CHƯA done. Không skip sang step kế.**

---

## 13. Communication Style với Vibe Coder

User là **vibe coder** — không rành code chi tiết. Khi communicate:

### DO:

- ✅ Giải thích bằng tiếng Việt (mix English tech terms OK)
- ✅ Show output/result sau khi xong (file đã tạo, test passed, etc.)
- ✅ Hỏi confirm trước action lớn (delete, refactor, install package)
- ✅ Đề xuất commit message rõ ràng cho mỗi step
- ✅ Demo bằng cách run real example, không chỉ unit test
- ✅ Liệt kê "Bạn cần làm gì tay" sau khi xong code
- ✅ Khi không hiểu code user paste, hỏi rõ context

### DON'T:

- ❌ KHÔNG bắt user hiểu code chi tiết — show high-level
- ❌ KHÔNG refactor toàn bộ module mà không hỏi
- ❌ KHÔNG cài package mới mà không giải thích lý do
- ❌ KHÔNG tạo file ngoài project folder
- ❌ KHÔNG assume user biết debug — show full error
- ❌ KHÔNG skip confirm cho destructive ops
- ❌ KHÔNG dùng jargon không cần thiết (e.g. nói "MapReduce" khi chỉ là forEach + push)

### Khi user paste error/traceback, response format:

```markdown
**Vấn đề:** [1 dòng plain Vietnamese]

**Tại sao xảy ra:** [1-2 dòng root cause, không kỹ thuật quá]

**Fix:**
1. [step 1]
2. [step 2]
3. [step 3]

**Verify:** [cách check fix work, e.g. "Refresh trang, click button X, expect Y"]
```

---

## 14. Tech-specific Conventions

### Python Backend

```python
# Imports: stdlib → 3rd party → local, mỗi nhóm cách 1 dòng
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dich_ai.core.pipeline import Pipeline


# Pydantic models: dùng BaseModel, không dataclass
class ChapterCreate(BaseModel):
    title: str
    content: str
    source_lang: str = "zh"


# Async-first cho I/O
async def get_chapter(chapter_id: int) -> Chapter:
    async with session_factory() as session:
        return await chapter_repo.get(session, chapter_id)


# Type hints BẮT BUỘC, không Optional[X], dùng X | None
def parse(text: str) -> list[Term] | None:
    ...
```

**Rules:**
- Python 3.11+ syntax (`X | None`, không `Optional[X]`)
- Pydantic v2 syntax (`model_config`, không `Config` class)
- SQLAlchemy 2.0 syntax (`select()`, không `Query`)
- mypy `--strict` PHẢI pass
- Mọi public function có docstring (1-2 dòng đủ)
- Type hints CHO MỌI parameter và return value

### Frontend TypeScript

```typescript
// strict types, không any
interface Chapter {
  id: number;
  title: string;
  content: string;
  status: "pending" | "translating" | "done" | "failed";
}

// Component: function component, không class
export function ChapterCard({ chapter }: { chapter: Chapter }) {
  // ...
}

// Async với try/catch
const { data, error, isLoading } = useQuery({
  queryKey: ["chapters", projectId],
  queryFn: () => api.chapters.list(projectId),
});
```

**Rules:**
- TS `strict: true`, KHÔNG `any`
- Named exports preferred over default exports (trừ pages/routes)
- shadcn/ui primitives qua `components/ui/`
- Tailwind utility-first, KHÔNG inline `style={{}}`
- Mỗi component file <300 dòng — chia nhỏ nếu hơn
- Mỗi component có loading state + error state
- Form luôn qua React Hook Form + Zod schema

---

## 15. Decision Log (LOCKED — không debate)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Scope | Single-user local app | Confirmed by user |
| 2 | Backend framework | FastAPI | Async, modern, type-safe |
| 3 | Frontend framework | React + Vite | Đơn giản, hot reload nhanh, tận dụng v7.0 |
| 4 | Database | SQLite + Alembic | Single user, transactional, file-based |
| 5 | UI components | shadcn/ui + Tailwind v4 | Đẹp, flexible, không lock vào design system |
| 6 | State (client) | Zustand | Minimal, no boilerplate |
| 7 | State (server) | TanStack Query v5 | Cache, retry, sync built-in |
| 8 | Streaming | SSE | Đơn giản hơn WebSocket, 1-way đủ |
| 9 | Python version | 3.11+ | `X \| None`, performance, modern type hints |
| 10 | Package manager (Python) | uv | Nhanh hơn pip 10x |
| 11 | Package manager (JS) | pnpm | Disk-efficient, monorepo-friendly |
| 12 | LLM SDK (Gemini) | google-genai (NEW) | google-generativeai bị deprecated |
| 13 | Provider v1 | Gemini only | Free tier, đủ cho MVP |
| 14 | Auth | None cho v1 | Local-only, không cần |
| 15 | Cloud sync | None cho v1 | Defer v1.1+ |
| 16 | Test framework | pytest + vitest | Standard cho stack |

---

## 16. Anti-patterns (bài học từ LiTTrans/TriLex — TRÁNH)

> Đây là pattern đã đốt thời gian thật. KHÔNG lặp lại.

1. **Silent failures** — code path fail nhưng không có warning hiển thị. Mọi error PHẢI log + visible.
2. **Trusting small/preview models cho structured output** — flash-lite truncate chapters, mislabel severity. CHỈ dùng full models (Gemini 2.5 Flash trở lên, KHÔNG flash-lite preview) cho structured task.
3. **Trusting AI bug reports without verification** — đã có report sai về LiTTrans bugs. Luôn đọc code thật trước khi accept claim.
4. **Environment config override code logic silently** — `.env` `BIBLE_DIR` overrode per-novel path → bug ẩn. Settings phải explicit, log khi override.
5. **Full retranslate cho lỗi nhỏ** — đốt token. Dùng targeted auto-fix trước, full retry sau.
6. **Schema validation fail làm data trống không có warning** — luôn raise hoặc log loud khi schema fail.
7. **Cache singleton thread-safety** — Streamlit cache có race condition. Dùng async lock hoặc tránh shared mutable state.
8. **Truncated translations metadata silently fail** — luôn validate metadata save thành công, không assume.

---

## 17. When to ask Claude (chat) vs Claude Code

Claude Code giỏi: implement code, fix bug cụ thể, refactor file
Claude (chat) giỏi: design decision, debate kiến trúc, giải thích concept

**Hỏi chat khi:**
- "Step này có nhất thiết không?"
- "Tại sao dùng FastAPI mà không Flask?"
- "Schema này nên có những field nào?"
- "Dự án mình có vấn đề gì không?"
- Bí kỹ thuật mà Code không hiểu yêu cầu

**Đừng hỏi chat:**
- "Viết code cho tôi" → việc của Code
- "Tại sao file này lỗi?" → Code thấy file, chat không

---

## 18. Reference Documents

Trong root folder:

- `CLAUDE.md` — file này, governance + rules
- `ROADMAP_VIBE_CODER.md` — lộ trình 4 tuần, step-by-step
- `docs/ARCHITECTURE.md` — chi tiết architecture, schema, layers
- `docs/API.md` — API contract giữa FE và BE
- `docs/SCOPE_LOCK.md` — copy phần §3 ở đây, treo nổi bật
- `docs/V1_1_BACKLOG.md` — feature defer, để làm sau MVP
- `CHANGELOG.md` — user-facing changes

**Khi user hỏi về vision/architecture → tham chiếu file này (§2, §5)**
**Khi user paste step number → tham chiếu ROADMAP_VIBE_CODER.md**
**Khi gặp design decision khó → hỏi Claude chat trước, đừng tự ý**

---

## 19. Self-check trước MỌI response của Claude Code

Trước khi gửi response cho user, internally check:

- [ ] Tôi đã đọc CLAUDE.md chưa? (file này)
- [ ] Task này có trong Scope Lock §3 không? Nếu nằm DEFERRED → STOP rule §8
- [ ] Tôi đã restate task chưa? §6.1
- [ ] Tôi có cần hỏi clarify không? §6
- [ ] Plan có >5 file changes không? Nếu có → STOP rule §8
- [ ] Có destructive op không? Nếu có → STOP rule §8
- [ ] Sau khi code: tôi đã chạy test thật chưa? §7
- [ ] Commit message format đúng chưa? §11
- [ ] Có items trong Definition of Done bị skip không? §12
- [ ] Tôi có dùng `any`, `# type: ignore`, hoặc bypass linter không? §9

**Nếu bất kỳ check nào FAIL → fix trước khi send.**

---

## 20. Phiên bản

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-05-14 | Initial, lock scope v1 |

**END CLAUDE.md**

> *"Một câu hỏi clarify giờ tiết kiệm 30 phút sửa code sau."*