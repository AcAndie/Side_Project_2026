# CLAUDE.md — NovelPipeline Quick Reference

> Dự án: `C:\Users\FPT MONG CAI\Desktop\NovelPipeline\`
> Stack: Python 3.11+, Streamlit, Gemini/Claude API, Playwright, ebooklib

## Refactor Batch Plan (2026-04-22)

Kế hoạch: phát hiện 6 duplication hotspots + 5 perf bottlenecks → fix theo batch.
Chi tiết đầy đủ: `.claude/plans/review-to-n-b-codebase-iterative-treasure.md`

```
Batch 1 — Benchmark baseline          [x] DONE 2026-04-22
           bench.py + instrument pipeline.py + scraper.py
Batch 2 — Unified retry decorator     [x] DONE 2026-04-22
           retry_utils.py + epub_processor + bible_scanner + agents.py
Batch 3 — UI polling dedup            [x] DONE 2026-04-22
           poll_queue() → runner.py; replace 5 drain loops + fix epub add_script_run_ctx
Batch 4 — Cache glossary/characters   [x] DONE 2026-04-22
           glossary._load_all() cached by content-hash; chars cached by mtime_ns
Batch 5 — Scraper HTML parse reuse    [x] DONE 2026-04-22
           PipelineContext.get_soup() lazy cache; remove duplicate parse in find_start_chapter
Batch 6 — I/O helpers + misc dedup   [x] DONE 2026-04-22
           load_json_safe() → io_utils; parse_markdown public → glossary; ads_filter module-level cache
Batch 7 — Split oversized files       [x] DONE 2026-04-22
           app.py(1413→249) + pages/ package (7 pages); agents.py(955→~350) + agents_helpers.py;
           bible_scanner.py(781→~430) + bible_response_parser.py;
           loaders.py + env_utils.py + ui_utils.py extracted from app.py
```

**Sau Batch 1:** chạy translate + scrape để lấy `data/bench.jsonl` baseline trước khi làm Batch 4.

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
│   ├── utils/
│   │   ├── io_utils.py          ← load_text, atomic_write
│   │   └── bench.py             ← measure()/timed() → data/bench.jsonl [B1]
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
