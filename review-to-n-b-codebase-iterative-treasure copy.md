# NovelPipeline — Detailed Batch Fix Plan

## Context

Source: review trước đó phát hiện **6 duplication hotspots** + **5 perf bottlenecks**. User yêu cầu kế hoạch chi tiết fix hoàn chỉnh theo batch, tham khảo industry.

Codebase: 23,337 LOC / 99 files. Python 3.11 + Streamlit + Gemini/Claude + Playwright.

**Industry references used:**
- `tenacity` — Python retry lib (jd/tenacity) — model cho decorator API
- Scrapy `RetryMiddleware` — retry HTTP codes `[500, 502, 503, 504, 408, 429]` — dùng cho classifier
- Streamlit official doc — `add_script_run_ctx(thread, get_script_run_ctx())` pattern
- `pyahocorasick` — C-extension, pickle-able automaton — đang dùng ✓

---

## Batch Plan Overview

| Batch | Theme | Files | Effort | Risk | Order |
|-------|-------|-------|--------|------|-------|
| 1 | Benchmark baseline + feature flag | new `utils/bench.py` | S | LOW | FIRST |
| 2 | Retry decorator (`retry_utils`) | new + 5 sites | M | LOW | 2nd |
| 3 | UI polling dedup (`poll_queue`) | runner + 5 UI | S | LOW | 3rd |
| 4 | Cache glossary/characters per-novel | pipeline + context | M | **MED** | 4th |
| 5 | Scraper HTML parse reuse | scraper.py | S | LOW | 5th |
| 6 | I/O helpers + misc dedup | io_utils + many | S | LOW | 6th |
| 7 (opt) | Split oversized files | app.py, agents.py, bible_scanner.py | L | HIGH | LAST |

**Golden rule:** mỗi batch commit riêng, test ngay, rollback dễ. Không bundle.

---

## BATCH 1 — Benchmark Baseline (PREREQUISITE)

### Goal
Đo hiệu suất trước khi refactor → xác minh gain thật, không phải feeling.

### Files (new)
- `src/littrans/utils/bench.py`

### Implementation

```python
# src/littrans/utils/bench.py
from __future__ import annotations
import time, functools, json
from pathlib import Path
from contextlib import contextmanager

BENCH_LOG = Path(__file__).resolve().parents[3] / "data" / "bench.jsonl"

@contextmanager
def measure(label: str, **meta):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        BENCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with BENCH_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"label": label, "ms": round(dt*1000, 2), **meta}) + "\n")

def timed(label: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            with measure(label):
                return fn(*a, **kw)
        return wrap
    return deco
```

### Sites to instrument (temporary)
- `core/pipeline.py::translate_chapter()` — wrap với `measure("translate_chapter", ch=N)`
- `core/pipeline.py::filter_glossary()` + `filter_characters()` — `measure("ctx_filter")`
- `modules/scraper/core/scraper.py::scrape_one_chapter()` — `measure("scrape_chapter")`

### Verification
1. Chạy 10-chapter test novel translate → ghi `data/bench.jsonl`
2. Chạy 10-chapter scrape → ghi thêm
3. Lưu `bench.jsonl.baseline` snapshot

### Rollback
Xóa `measure(...)` calls. Giữ `bench.py` cho future use.

---

## BATCH 2 — Unified Retry Decorator

### Goal
Thay 5 retry implementations rải rác bằng 1 decorator. Pattern theo `tenacity` (không import tenacity — tự code để minimal dependency).

### Files
- **new** `src/littrans/utils/retry_utils.py`
- **edit** [tools/epub_processor.py](src/littrans/tools/epub_processor.py) (replace `_parse_retry_delay` flow)
- **edit** [context/bible_scanner.py:71](src/littrans/context/bible_scanner.py#L71) (`_call_json`)
- **edit** [context/bible_consolidator.py:95](src/littrans/context/bible_consolidator.py#L95) (`_acquire_lock_with_retry`)
- **edit** [modules/scraper/ai/agents.py:36-52](src/littrans/modules/scraper/ai/agents.py#L36) (`_is_retriable`, `_call`)
- **edit** [llm/client.py](src/littrans/llm/client.py) (consolidate `is_rate_limit`, `handle_api_error`)

### Implementation

```python
# src/littrans/utils/retry_utils.py
from __future__ import annotations
import asyncio, time, random, functools, re
from dataclasses import dataclass
from typing import Callable, Iterable

# Scrapy-inspired retriable HTTP codes + Gemini-specific
RETRIABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 522, 524})
RATE_LIMIT_MARKERS = ("429", "rate_limit", "RATE_LIMIT", "RESOURCE_EXHAUSTED",
                      "quota", "too many requests", "overloaded")
NETWORK_MARKERS = ("connection", "timeout", "reset by peer", "timed out",
                   "SSL", "EOF", "dns", "network")

_RETRY_DELAY_RE = re.compile(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)", re.I)

def parse_retry_after(err: BaseException) -> float | None:
    """Gemini 429 response embeds 'retry_delay { seconds: N }'. Extract N."""
    m = _RETRY_DELAY_RE.search(str(err))
    return float(m.group(1)) if m else None

def is_rate_limit(err: BaseException) -> bool:
    s = str(err).lower()
    return any(m.lower() in s for m in RATE_LIMIT_MARKERS)

def is_network(err: BaseException) -> bool:
    s = str(err).lower()
    return any(m.lower() in s for m in NETWORK_MARKERS)

def is_retriable(err: BaseException) -> bool:
    return is_rate_limit(err) or is_network(err)

@dataclass
class Backoff:
    base: float = 1.0       # initial wait
    cap: float = 60.0       # max wait
    factor: float = 2.0     # exponential multiplier
    jitter: float = 0.2     # ±20% jitter

    def wait(self, attempt: int, hint: float | None = None) -> float:
        if hint is not None:
            return max(hint, 0.5)
        raw = min(self.cap, self.base * (self.factor ** attempt))
        j = raw * self.jitter * (random.random() * 2 - 1)
        return max(0.5, raw + j)

def with_retry(
    *,
    max_attempts: int = 5,
    retry_on: Callable[[BaseException], bool] = is_retriable,
    backoff: Backoff | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
):
    bo = backoff or Backoff()

    def deco(fn):
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrap(*a, **kw):
                for attempt in range(max_attempts):
                    try:
                        return await fn(*a, **kw)
                    except BaseException as e:
                        if isinstance(e, asyncio.CancelledError):
                            raise
                        if attempt == max_attempts - 1 or not retry_on(e):
                            raise
                        wait = bo.wait(attempt, parse_retry_after(e))
                        if on_retry: on_retry(attempt, e, wait)
                        await asyncio.sleep(wait)
            return awrap
        @functools.wraps(fn)
        def swrap(*a, **kw):
            for attempt in range(max_attempts):
                try:
                    return fn(*a, **kw)
                except BaseException as e:
                    if attempt == max_attempts - 1 or not retry_on(e):
                        raise
                    wait = bo.wait(attempt, parse_retry_after(e))
                    if on_retry: on_retry(attempt, e, wait)
                    time.sleep(wait)
        return swrap
    return deco
```

### Migration examples

**epub_processor.py:**
```python
from littrans.utils.retry_utils import with_retry, Backoff, is_rate_limit

@with_retry(max_attempts=6, backoff=Backoff(base=2.0, cap=120.0),
            on_retry=lambda a,e,w: print(f"[epub] retry {a+1} in {w:.1f}s: {e}"))
def _epub_call_json(prompt, schema, key):
    ...
```

**bible_scanner.py:**
```python
@with_retry(max_attempts=5, backoff=Backoff(base=1.5, cap=90.0))
def _call_json(self, prompt, schema):
    ...
```

**agents.py** (async):
```python
@with_retry(max_attempts=4, backoff=Backoff(cap=30.0))
async def _call(self, ...):
    ...
```

### Verification
1. Unit test: `tests/test_retry_utils.py` — mock rate_limit exception, verify retry count + backoff time
2. Run full bible scan on test novel — confirm retry logs appear on throttle
3. Compare `data/bench.jsonl` — retry time không tăng

### Rollback
Git revert commit. `retry_utils.py` xóa an toàn (no other consumers).

---

## BATCH 3 — UI Polling Dedup

### Goal
Xóa 5 copies của `_handle_log()`. Pattern Streamlit chính thức: custom thread + queue + `add_script_run_ctx`.

### Files
- **edit** [ui/runner.py](src/littrans/ui/runner.py) — thêm `poll_queue()` + `launch_with_queue()`
- **edit** [ui/app.py:348](src/littrans/ui/app.py#L348) — replace `_poll()`
- **edit** [ui/pipeline_page.py:236](src/littrans/ui/pipeline_page.py#L236)
- **edit** [ui/scraper_page.py:138](src/littrans/ui/scraper_page.py#L138)
- **edit** [ui/epub_ui.py:178](src/littrans/ui/epub_ui.py#L178)
- **edit** [ui/bible_ui.py:241, 604](src/littrans/ui/bible_ui.py#L241)

### Implementation

```python
# src/littrans/ui/runner.py (add)
import queue, threading, time
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

DONE_SENTINEL = "__DONE__"

def poll_queue(
    q_key: str,
    logs_key: str,
    thread_key: str,
    *,
    poll_interval: float = 1.0,
    max_drain: int = 200,
    on_done: callable = None,
) -> bool:
    """Drain queue into session_state[logs_key]. Return True when __DONE__ seen.

    Replaces 5 duplicate _handle_log() impls.
    """
    q: queue.Queue = st.session_state.get(q_key)
    if q is None:
        return False
    logs: list = st.session_state.setdefault(logs_key, [])
    done = False
    for _ in range(max_drain):
        try:
            msg = q.get_nowait()
        except queue.Empty:
            break
        if msg == DONE_SENTINEL:
            done = True
            break
        logs.append(msg)
    if done:
        st.session_state[thread_key] = None
        if on_done: on_done()
        return True
    # Still running → schedule rerun
    time.sleep(poll_interval)
    st.rerun()

def launch_with_queue(
    target: callable,
    *,
    q_key: str,
    thread_key: str,
    logs_key: str,
    args: tuple = (),
    kwargs: dict | None = None,
) -> None:
    """Start background thread with queue. Replaces 3 _launch() copies."""
    if st.session_state.get(thread_key):
        return  # already running
    q = queue.Queue()
    st.session_state[q_key] = q
    st.session_state[logs_key] = []
    kwargs = dict(kwargs or {}, log_queue=q)
    th = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    add_script_run_ctx(th)
    th.start()
    st.session_state[thread_key] = th
```

### Migration pattern (per UI page)

Before (pipeline_page.py):
```python
def _handle_log():
    q = st.session_state.get("pipeline_queue")
    ...
    while True:
        try: msg = q.get_nowait()
        except: break
        if msg == "__DONE__": done=True; break
        logs.append(msg)
    ...
```

After:
```python
from littrans.ui.runner import poll_queue
poll_queue("pipeline_queue", "pipeline_logs", "pipeline_thread",
           on_done=lambda: _render_result())
```

### Verification
1. UI smoke: start scrape → confirm logs stream, __DONE__ triggers result render
2. Repeat for pipeline / epub / bible scan / bible crossref
3. Test no duplicate log entries, no stuck state

### Rollback
Per-file revert possible (decoupled).

---

## BATCH 4 — Cache Glossary/Characters Per-Novel ⚠️ HIGH IMPACT

### Goal
Fix N+1 file reads. `filter_glossary()` + `filter_characters()` đọc **mỗi chapter** → cache 1 lần tại `Pipeline.__init__()`.

### Files
- **edit** [core/pipeline.py:243-244](src/littrans/core/pipeline.py#L243)
- **edit** [context/glossary.py:41](src/littrans/context/glossary.py#L41) — add `GlossaryCache` class
- **edit** [context/characters.py](src/littrans/context/characters.py) — add `CharacterCache`
- **edit** [context/base.py](src/littrans/context/base.py) — add `mtime_invalidate()` helper

### Implementation

```python
# src/littrans/context/glossary.py (add)
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class GlossaryCache:
    """Per-novel cache. Built once at Pipeline.__init__, invalidated on merge."""
    _data: dict[str, list[dict]] = field(default_factory=dict)
    _mtimes: dict[str, float] = field(default_factory=dict)
    _automaton: object | None = None  # Aho-Corasick

    def load(self, force: bool = False) -> None:
        files = settings.glossary_files + [settings.staging_chars_file]
        if not force and self._is_fresh(files):
            return
        self._data.clear()
        self._mtimes.clear()
        for fp in files:
            if fp.exists():
                self._data[fp.name] = _parse(fp.read_text(encoding="utf-8"))
                self._mtimes[fp.name] = fp.stat().st_mtime
        self._automaton = _build_automaton(self._data)

    def _is_fresh(self, files: list[Path]) -> bool:
        for fp in files:
            if not fp.exists(): continue
            if self._mtimes.get(fp.name, 0) < fp.stat().st_mtime:
                return False
        return True

    def filter_for_chapter(self, text: str) -> list[dict]:
        self.load()  # no-op if fresh
        return _ac_match(self._automaton, text)

    def invalidate(self) -> None:
        self._data.clear()
        self._mtimes.clear()
        self._automaton = None

# Module-level singleton (per-process)
_CACHE = GlossaryCache()

def filter_glossary(chapter_text: str) -> list[dict]:
    """Public API — unchanged signature, now cached."""
    return _CACHE.filter_for_chapter(chapter_text)

def invalidate_glossary_cache() -> None:
    _CACHE.invalidate()
```

**Characters cache** — similar pattern:

```python
# src/littrans/context/characters.py (add)
@dataclass
class CharacterCache:
    _active: list[dict] = field(default_factory=list)
    _archive: list[dict] = field(default_factory=list)
    _mtime_active: float = 0.0
    _mtime_archive: float = 0.0

    def load(self) -> None:
        af = settings.characters_active_file
        if af.exists() and af.stat().st_mtime > self._mtime_active:
            self._active = json.loads(af.read_text("utf-8"))
            self._mtime_active = af.stat().st_mtime
        # same for archive
        ...

    def filter_for_chapter(self, text: str) -> tuple[list, list]:
        self.load()
        return _score_relevance(self._active, self._archive, text)

_CHAR_CACHE = CharacterCache()
```

### Pipeline integration

```python
# core/pipeline.py
from littrans.context.glossary import invalidate_glossary_cache
from littrans.context.characters import invalidate_character_cache

class Pipeline:
    def __init__(self, ...):
        ...
        # Pre-warm caches
        from littrans.context import glossary, characters
        glossary._CACHE.load()
        characters._CHAR_CACHE.load()

    def after_merge(self):
        """Call after Scout writes new Characters/Glossary entries."""
        invalidate_glossary_cache()
        invalidate_character_cache()
```

**Invalidation hooks** — tìm các chỗ ghi vào Characters_Active.json / Glossary.md:
- `characters.save_active()` → call `invalidate_character_cache()`
- `glossary._append_to_file()` → call `invalidate_glossary_cache()`
- Bible enricher updates → invalidate chars

### Edge cases ⚠️
1. **Staging writes giữa chapters** — mtime check tự handle
2. **Multi-process** — cache per-process, Streamlit restart reload → OK
3. **Big glossary (5000+ entries)** — automaton build ~100ms, 1 lần/novel → chấp nhận được
4. **Concurrent translate + scout** — scout có thể ghi glossary. Lock: `threading.RLock` quanh `load()`

### Verification
1. Translate 10 chapters → compare `bench.jsonl` — `ctx_filter` time giảm ≥80%
2. Trigger Scout → add new term → chapter sau phải thấy term mới (invalidation work)
3. Bible enricher chạy → characters cache refresh
4. Edge: xóa Characters_Active.json giữa chừng → không crash, reload empty

### Rollback
Git revert. Cache is additive (không thay signature public). Có thể disable bằng env flag:
```python
USE_CONTEXT_CACHE = os.getenv("LITTRANS_CACHE_CTX", "1") == "1"
```

---

## BATCH 5 — Scraper HTML Parse Reuse

### Goal
[scraper.py:141, 178, 390](src/littrans/modules/scraper/core/scraper.py#L141) parse cùng HTML 2-3 lần. Cache first parse.

### Files
- **edit** [modules/scraper/core/scraper.py](src/littrans/modules/scraper/core/scraper.py)
- **edit** [modules/scraper/pipeline/base.py](src/littrans/modules/scraper/pipeline/base.py) — `BlockContext.soup_cache`

### Implementation

```python
# modules/scraper/pipeline/base.py (add to BlockContext)
@dataclass
class BlockContext:
    html: str = ""
    url: str = ""
    ...
    _soup_cache: "BeautifulSoup | None" = None

    def get_soup(self):
        from bs4 import BeautifulSoup
        if self._soup_cache is None and self.html:
            self._soup_cache = BeautifulSoup(self.html, "html.parser")
        return self._soup_cache

    def invalidate_soup(self):
        """Call when html field mutated."""
        self._soup_cache = None
```

### Migration
- scraper.py line 141: `soup = BeautifulSoup(html, "html.parser")` → `soup = ctx.get_soup()`
- Line 178: same
- Line 390: same
- Mọi block trong `pipeline/extractor.py` dùng `ctx.get_soup()` thay `BeautifulSoup(ctx.html, ...)`

### Verification
1. Scrape 20 chapters → compare `scrape_chapter` ms giảm 200-500ms/chapter
2. Diff output .md trước/sau — byte-identical

### Rollback
Low risk — soup cache transparent.

---

## BATCH 6 — I/O Helpers + Misc Dedup

### Goal
Cleanup nhỏ nhưng rộng: UTF-8 helper, glossary._parse() export, ads_filter load-once, JSON consolidation.

### Files
- **edit** [utils/io_utils.py](src/littrans/utils/io_utils.py) — add `read_utf8()`, `write_utf8()`, `load_json_safe()`
- **edit** [context/name_lock.py:99](src/littrans/context/name_lock.py#L99) — dùng `glossary.parse_markdown()`
- **edit** [context/glossary.py](src/littrans/context/glossary.py) — rename `_parse` → `parse_markdown` (public)
- **edit** [modules/scraper/utils/ads_filter.py](src/littrans/modules/scraper/utils/ads_filter.py) — module-level load
- **edit** 13 sites `open(..., encoding="utf-8")` → `read_utf8()` / `write_utf8()`

### Implementation

```python
# utils/io_utils.py (add)
from pathlib import Path
import json

def read_utf8(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")

def write_utf8(path: Path | str, text: str, *, atomic: bool = False) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if atomic:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(p)
    else:
        p.write_text(text, encoding="utf-8")

def load_json_safe(path: Path | str, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
```

```python
# modules/scraper/utils/ads_filter.py (fix N+1)
_ADS_DB_CACHE: dict | None = None

def _get_ads_db() -> dict:
    global _ADS_DB_CACHE
    if _ADS_DB_CACHE is None:
        _ADS_DB_CACHE = load_json_safe(ADS_DB_FILE, default={})
    return _ADS_DB_CACHE
```

### Verification
- Grep `open(.*encoding="utf-8"` — còn 0 matches (trừ retry_utils test mocks)
- Scraper 10-chapter run — identical output
- name_lock test — populate giống trước

### Rollback
Each change isolated. Per-file revert.

---

## BATCH 7 (OPTIONAL) — Split Oversized Files

⚠️ User chưa approve. Skip unless explicit go.

Plan outline only:
- [ui/app.py](src/littrans/ui/app.py) (1413) → `ui/pages/` folder, 1 file/page, app.py = router only (~200 LOC)
- [scraper/ai/agents.py](src/littrans/modules/scraper/ai/agents.py) (955) → `agents/retry.py`, `agents/parse.py`, `agents/nav_hints.py`
- [context/bible_scanner.py](src/littrans/context/bible_scanner.py) (781) → `scanner.py` (orchestration) + `response_parser.py` (JSON → entities)

Risk HIGH — import surface thay đổi. Cần full regression test.

---

## Global Verification Plan

Sau mỗi batch chạy:

```bash
# 1. Syntax check
python -c "from littrans.core.pipeline import Pipeline; from littrans.ui import app"

# 2. Translate 5-chapter smoke test
python scripts/main.py translate  # on test_novel/

# 3. Scrape smoke (1 chapter)
# Via UI: 🌐 Cào Truyện → known URL → verify .md output

# 4. Bible scan (small novel)
# Via UI: 📚 Bible → Scan → verify JSON DB updated

# 5. Diff bench.jsonl vs baseline
python -c "
import json
lines = [json.loads(l) for l in open('data/bench.jsonl')]
from collections import defaultdict
agg = defaultdict(list)
for l in lines: agg[l['label']].append(l['ms'])
for k,v in agg.items(): print(f'{k}: avg={sum(v)/len(v):.1f}ms n={len(v)}')
"
```

### Expected gains post-Batch 4

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| `ctx_filter` per chapter | ~200ms | <20ms | -90% |
| `translate_chapter` | baseline | -3-5% | mildly |
| `scrape_chapter` startup | baseline | -200-500ms | -10% |
| UI log stream latency | 1s | 1s (unchanged) | — |
| LOC total | 23337 | ~22800 | -500 |

---

## Commit Strategy

One commit per batch, Conventional Commits:

```
batch 1: add bench.py, instrument pipeline + scraper hot paths
batch 2: add retry_utils; replace 5 retry sites with @with_retry decorator
batch 3: dedup UI polling — extract poll_queue/launch_with_queue to runner
batch 4: cache glossary+characters per-novel; fix N+1 file reads per chapter
batch 5: reuse BeautifulSoup parse in scraper via BlockContext.get_soup()
batch 6: add io_utils helpers; load ads_db once; export glossary.parse_markdown
```

Không push until user review từng commit.

---

## Critical Files — Full List

### New files
- [src/littrans/utils/bench.py](src/littrans/utils/bench.py) *(B1)*
- [src/littrans/utils/retry_utils.py](src/littrans/utils/retry_utils.py) *(B2)*
- [tests/test_retry_utils.py](tests/test_retry_utils.py) *(B2)*

### Modified files
| Path | Batch |
|------|-------|
| [src/littrans/core/pipeline.py](src/littrans/core/pipeline.py) | 1,4 |
| [src/littrans/tools/epub_processor.py](src/littrans/tools/epub_processor.py) | 2 |
| [src/littrans/context/bible_scanner.py](src/littrans/context/bible_scanner.py) | 2 |
| [src/littrans/context/bible_consolidator.py](src/littrans/context/bible_consolidator.py) | 2 |
| [src/littrans/modules/scraper/ai/agents.py](src/littrans/modules/scraper/ai/agents.py) | 2 |
| [src/littrans/llm/client.py](src/littrans/llm/client.py) | 2 |
| [src/littrans/ui/runner.py](src/littrans/ui/runner.py) | 3 |
| [src/littrans/ui/app.py](src/littrans/ui/app.py) | 3 |
| [src/littrans/ui/pipeline_page.py](src/littrans/ui/pipeline_page.py) | 3 |
| [src/littrans/ui/scraper_page.py](src/littrans/ui/scraper_page.py) | 3 |
| [src/littrans/ui/epub_ui.py](src/littrans/ui/epub_ui.py) | 3 |
| [src/littrans/ui/bible_ui.py](src/littrans/ui/bible_ui.py) | 3 |
| [src/littrans/context/glossary.py](src/littrans/context/glossary.py) | 4,6 |
| [src/littrans/context/characters.py](src/littrans/context/characters.py) | 4 |
| [src/littrans/context/base.py](src/littrans/context/base.py) | 4 |
| [src/littrans/context/name_lock.py](src/littrans/context/name_lock.py) | 6 |
| [src/littrans/modules/scraper/core/scraper.py](src/littrans/modules/scraper/core/scraper.py) | 1,5 |
| [src/littrans/modules/scraper/pipeline/base.py](src/littrans/modules/scraper/pipeline/base.py) | 5 |
| [src/littrans/modules/scraper/utils/ads_filter.py](src/littrans/modules/scraper/utils/ads_filter.py) | 6 |
| [src/littrans/utils/io_utils.py](src/littrans/utils/io_utils.py) | 6 |

---

## Sources (industry reference)

- [Tenacity — Python retry lib](https://github.com/jd/tenacity) — decorator API model
- [Scrapy RetryMiddleware](https://docs.scrapy.org/en/latest/_modules/scrapy/downloadermiddlewares/retry.html) — HTTP code list
- [Streamlit Threading docs](https://docs.streamlit.io/develop/concepts/design/multithreading) — `add_script_run_ctx` pattern
- [pyahocorasick](https://pypi.org/project/pyahocorasick/) — C-extension, pickle-able automaton
