# CLAUDE.md — NovelPipeline Quick Reference

> Dự án: `C:\Users\FPT MONG CAI\Desktop\NovelPipeline\`
> Stack: Python 3.11+, Streamlit, Gemini/Claude API, Playwright, ebooklib

---

## Phase checklist

```
Phase 0 — Tách Repo & Chuẩn Bị         [x] DONE 2026-04-20
Phase 1 — Unified Config & Multi-Key   [x] DONE 2026-04-20
Phase 2 — Port Scraper Thành Module    [x] DONE 2026-04-20 — live test PASS (resume verified)
Phase 3 — Audit & Enhance EPUB         [x] DONE 2026-04-20
Phase 4 — UI: Scraper Page             [x] DONE 2026-04-20 — scraper_page.py, ScrapeRunner
Phase 5 — UI: Pipeline Page            [x] DONE 2026-04-20 — pipeline_page.py, PipelineRunner
Phase 6 — EPUB Export                  [x] DONE 2026-04-20 — epub_exporter.py, BytesIO download
Phase 7 — Dashboard, CLI & Polish      [ ] not started
```

---

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
│   └── ui/
│       ├── app.py               ← Streamlit entry point (v5.6)
│       ├── pipeline_page.py     ← 1-click pipeline: scrape/epub → translate
│       ├── scraper_page.py      ← Standalone scraper UI
│       ├── runner.py            ← ScrapeRunner, PipelineRunner, run_background()
│       ├── epub_ui.py           ← EPUB processor UI
│       └── bible_ui.py          ← Bible System UI
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

## 4 pitfalls KHÔNG được quên

| # | Pitfall | Fix |
|---|---|---|
| 1 | Streamlit thread touch `st.session_state` → fail silently | `add_script_run_ctx(thread)` BẮT BUỘC |
| 2 | `def DATA_DIR() -> Path` → call site `DATA_DIR / "x"` TypeError | Option A (`settings.data_dir`) hoặc B (`_LazyPath`) — KHÔNG mix |
| 3 | `startswith("GEMINI_API_KEY")` nhặt nhầm `_DEV`, `_OLD`... | Strict regex `^GEMINI_API_KEY_\d+$` |
| 4 | `run_scraper_blocking` từ Streamlit → UI treo | CLI only; UI dùng `ScrapeRunner` + polling |

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
