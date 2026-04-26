# CLAUDE.md — NovelPipeline Quick Reference

> Dự án: `C:\Users\FPT MONG CAI\Desktop\NovelPipeline\`
> Stack: Python 3.11+, Streamlit, Gemini/Claude API, Playwright, ebooklib

> **Open bug plan:** [BUGFIX_PLAN.md](BUGFIX_PLAN.md) — danh sách lỗi đang chờ fix
> (P0/P1/P2). Đọc trước khi sửa code trong working tree hiện tại.

## Project structure

```
NovelPipeline/
├── src/littrans/
│   ├── config/settings.py       ← Settings dataclass + all_gemini_keys
│   ├── llm/client.py            ← ApiKeyPool, Gemini + Claude clients
│   ├── core/pipeline.py         ← Translation orchestrator
│   ├── context/                 ← Glossary, Characters, NameLock, Memory, Bible
│   ├── modules/scraper/         ← Ported scraper (async, Playwright + curl_cffi)
│   ├── tools/
│   │   ├── epub_processor.py    ← EPUB → inputs/{novel}/*.md
│   │   └── epub_exporter.py     ← outputs/{novel}/*_VN.txt → .epub (BytesIO)
│   ├── utils/
│   │   ├── io_utils.py          ← load_text, atomic_write
│   │   └── bench.py             ← measure()/timed() → data/bench.jsonl
│   └── ui/                      ← Streamlit UI (Phase 3 — 5 tab)
│       ├── app.py               ← Entry point + router + global poll_all
│       ├── runner.py            ← ScrapeRunner, PipelineRunner, run_background
│       ├── bible_ui.py          ← (backing) re-exported via pages/bible_page
│       ├── epub_ui.py           ← (backing) re-exported via pages/export_page
│       ├── core/
│       │   ├── state.py         ← JOB_KEYS + init_all_jobs + reset_job
│       │   └── jobs.py          ← poll_all() — global queue drainer
│       └── pages/
│           ├── library_page.py  ← landing (novel grid)
│           ├── welcome_page.py  ← first-run setup
│           ├── scrape_page.py   ← 🌐 Cào
│           ├── translate_page.py← 🇻🇳 Dịch (run + reader + delete chapter)
│           ├── bible_page.py    ← 📖 Bible (no Export sub-tab)
│           ├── export_page.py   ← 📦 Export (EPUB / MD-zip / Bible export)
│           └── settings_page.py ← ⚙️ Cài đặt (+ Stats/Characters/Glossary expanders)
├── scripts/
│   ├── run_ui.py                ← Start Streamlit UI
│   └── main.py                  ← CLI entry point
├── inputs/{novel_name}/         ← Chapter files (không commit)
├── outputs/{novel_name}/        ← Bản dịch *_VN.txt (không commit)
├── data/                        ← Scraper profiles, context data (không commit)
├── progress/                    ← Scraper progress files (không commit)
└── .env                         ← API keys (KHÔNG BAO GIỜ commit)
```

---

## Phase 2 — Job session-state schema (added 2026-04-25)

Mọi background job dùng prefix-based keys (định nghĩa trong [src/littrans/ui/core/state.py](src/littrans/ui/core/state.py)):

| Prefix | Job |
|---|---|
| `tx` | Translate (full pipeline run) |
| `sc` | Scrape |
| `rt` | Retranslate one chapter |
| `bi` | Bible scan |
| `ep` | EPUB processor |
| `cg` | Clean glossary |
| `cc` | Clean characters |

7 keys per prefix: `{p}_running`, `{p}_q`, `{p}_logs`, `{p}_thread`, `{p}_last_log`, `{p}_result`, `{p}_error`.

**Polling rule**: chỉ `app.py` gọi `poll_all(S)` (từ [src/littrans/ui/core/jobs.py](src/littrans/ui/core/jobs.py)) trước khi dispatch page. Pages KHÔNG được tự gọi `poll_queue` hoặc `time.sleep + st.rerun` cho job của mình. Pages chỉ render log + dispatch start.

**Queue reuse**: trước khi tạo `queue.Queue()` mới phải check `S.{p}_thread` còn alive không. Nếu còn → block start, để job cũ chạy tiếp. Helper `reset_job(S, prefix)` chỉ gọi khi chắc chắn thread cũ đã chết.

---

## 4 pitfalls KHÔNG được quên

| # | Pitfall | Fix |
|---|---|---|
| 1 | Streamlit thread touch `st.session_state` → fail silently | `add_script_run_ctx(thread)` BẮT BUỘC |
| 2 | `def DATA_DIR() -> Path` → call site `DATA_DIR / "x"` TypeError | Option A (`settings.data_dir`) hoặc B (`_LazyPath`) — KHÔNG mix |
| 3 | `startswith("GEMINI_API_KEY")` nhặt nhầm `_DEV`, `_OLD`... | Strict regex `^GEMINI_API_KEY_\d+$` |
| 4 | `run_scraper_blocking` từ Streamlit → UI treo | CLI only; UI dùng `ScrapeRunner` + polling |
| 5 | Cache module-level (vd `_char_active_cache`) không invalidate sau write → stale reads | Sau mọi `save_json` / `atomic_write` phải reset cache về `None` |
| 6 | Scratch comments leak khi dán code (`# src/littrans/.../...`) | Trước commit grep `^# src/littrans/` để dọn |

---

## Key patterns

### Multi-key Gemini
`.env` hỗ trợ `GEMINI_API_KEY`, `FALLBACK_KEY_1/2`, và `GEMINI_API_KEY_N` (N = số).
`settings.all_gemini_keys` merge tất cả — strict regex `^GEMINI_API_KEY_\d+$`.

### Background thread (Streamlit)
```python
from streamlit.runtime.scriptrunner import add_script_run_ctx
thread = threading.Thread(target=..., daemon=True)
add_script_run_ctx(thread)  # BẮT BUỘC
thread.start()
```

### EPUB export (BytesIO)
```python
buf = io.BytesIO()
epub.write_epub(buf, book)
st.download_button("⬇️ Download", buf.getvalue(), mime="application/epub+zip")
```

### Pipeline queue markers
- `__DONE__` — thread finished (luôn là message cuối)
- `__STAGE_2__` — entering translate stage
- `__STAGE_DONE__` — all stages complete

---

## Conventions bắt buộc

1. **Không** store runtime objects trong SiteProfile (blocks dùng `BlockResult.metadata`)
2. **Không** mutate `ctx.profile` trong scraper blocks
3. **Không** dùng flat StepConfig v1 — chỉ dùng nested `params` v2
4. **Luôn** bắt `CancelledError` trước `Exception` trong async code
5. Config chỉ thay đổi qua `.env` — không hardcode
6. Mỗi background Streamlit thread → `add_script_run_ctx(thread)`
7. Path constants → Option A hoặc B nhất quán, KHÔNG `def DATA_DIR()`

---

## Startup

```bash
cd "C:\Users\FPT MONG CAI\Desktop\NovelPipeline"
python scripts/run_ui.py    # Web UI tại http://localhost:8501
python scripts/main.py translate   # CLI dịch
```

## Phase 7 — Dashboard, CLI & Polish (TODO)

- `src/littrans/ui/dashboard_page.py` — tổng quan novels, tiến độ, quick actions
- `scripts/main.py` — thêm commands: `scrape`, `pipeline`, `export-epub`
- Sidebar: 🏠 Dashboard ở đầu
- Settings tab mới: Scraper config (playwright concurrency, rate limit)
