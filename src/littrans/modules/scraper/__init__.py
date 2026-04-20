"""
littrans.modules.scraper — Adapter cong khai cho web novel scraper.

Usage (CLI / tests):
    from littrans.modules.scraper import run_scraper_blocking, ScraperOptions

Usage (Streamlit UI — Phase 4):
    from littrans.modules.scraper import run_scraper, ScraperOptions
    # ScrapeRunner se duoc tao trong Phase 4 (ui/runner.py)
    # KHONG goi run_scraper_blocking tu Streamlit — freeze UI
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import queue
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class ScraperOptions:
    novel_name: str
    fast_learning: bool = False
    validation: bool = True
    max_pw_instances: int | None = None
    relearn_domains: list[str] = field(default_factory=list)


@dataclass
class ScraperResult:
    ok: bool
    chapters_written: int
    output_dir: Path
    errors: list[str]


def _valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def _progress_path(url: str, progress_dir: Path) -> str:
    p         = urlparse(url)
    domain    = p.netloc.replace(".", "_")
    parts     = [seg for seg in p.path.strip("/").split("/") if seg][:2]
    slug      = "_".join(parts) if parts else "unknown"
    out_str   = f"{domain}_{slug}"
    dir_hash  = hashlib.md5(out_str.encode()).hexdigest()[:8]
    return str(progress_dir / f"{domain}_{slug}_{dir_hash}.json")


async def run_scraper(
    urls: list[str],
    options: ScraperOptions,
    progress_queue: queue.Queue | None = None,
) -> ScraperResult:
    """Async entry point — dung tu ScrapeRunner (Streamlit) hoac CLI."""
    from littrans.config.settings import settings
    from littrans.modules.scraper.ai.client import AIRateLimiter
    from littrans.modules.scraper.core.session_pool import DomainSessionPool, PlaywrightPool
    from littrans.modules.scraper.core.scraper import run_novel_task, run_learning_only
    from littrans.modules.scraper.learning.profile_manager import ProfileManager
    from littrans.modules.scraper.utils.file_io import load_profiles, ensure_dirs
    from littrans.modules.scraper.utils.issue_reporter import write_session_header

    output_dir = settings.base_dir / "inputs" / options.novel_name
    progress_dir = settings.scraper_progress_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_dir.mkdir(parents=True, exist_ok=True)
    ensure_dirs()

    errors: list[str] = []
    chapters_written = 0

    def _log(msg: str) -> None:
        print(msg, flush=True)
        if progress_queue is not None:
            try:
                progress_queue.put_nowait(msg)
            except Exception:
                pass

    # Apply options to env
    if options.fast_learning:
        os.environ["CAO_FAST_LEARNING"] = "1"
    if not options.validation:
        os.environ["CAO_NO_VALIDATION"] = "1"

    valid_urls = [u for u in urls if _valid_url(u)]
    if not valid_urls:
        return ScraperResult(ok=False, chapters_written=0, output_dir=output_dir,
                             errors=["No valid URLs provided"])

    _log(f"[Scraper] Start: {len(valid_urls)} URL(s) -> inputs/{options.novel_name}/")

    pw_instances = options.max_pw_instances or settings.scraper_max_pw_instances
    ai_limiter   = AIRateLimiter()
    pw_pool      = PlaywrightPool()
    pool         = DomainSessionPool()

    if pw_instances > 0:
        pw_pool._semaphore = asyncio.Semaphore(pw_instances)

    profiles = await load_profiles()
    profiles_lock = asyncio.Lock()
    pm = ProfileManager(profiles, profiles_lock)

    # Apply relearn
    for domain in options.relearn_domains:
        keys_del = [k for k in profiles if k == domain or k == f"www.{domain}"]
        for k in keys_del:
            del profiles[k]
            _log(f"[Scraper] Re-learn: profile '{k}' xoa")

    write_session_header(len(valid_urls))

    # Phase 1: Sequential learning
    seen: set[str] = set()
    for url in valid_urls:
        domain = urlparse(url).netloc.lower()
        if domain in seen:
            continue
        seen.add(domain)
        try:
            await run_learning_only(
                start_url     = url,
                progress_path = _progress_path(url, progress_dir),
                pool          = pool,
                pw_pool       = pw_pool,
                pm            = pm,
                ai_limiter    = ai_limiter,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log(f"[Scraper] WARN Learning {url[:55]}: {e}")

    # Phase 2: Concurrent scraping
    async def _task(url: str, idx: int) -> None:
        await asyncio.sleep(idx * 2.0)
        await run_novel_task(
            start_url       = url,
            output_dir      = str(output_dir),
            progress_path   = _progress_path(url, progress_dir),
            pool            = pool,
            pw_pool         = pw_pool,
            pm              = pm,
            ai_limiter      = ai_limiter,
            on_chapter_done = None,
        )

    try:
        await asyncio.gather(*[_task(u, i) for i, u in enumerate(valid_urls)])
    except asyncio.CancelledError:
        _log("[Scraper] Cancelled by user")
        raise
    except Exception as exc:
        msg = f"[Scraper] FATAL: {exc}"
        _log(msg)
        errors.append(msg)
    finally:
        await pw_pool.close()

    # Count written chapters from output dir
    try:
        chapters_written = sum(1 for f in output_dir.iterdir() if f.suffix == ".md")
    except Exception:
        chapters_written = 0

    return ScraperResult(
        ok=len(errors) == 0,
        chapters_written=chapters_written,
        output_dir=output_dir,
        errors=errors,
    )


def run_scraper_blocking(
    urls: list[str],
    options: ScraperOptions,
    progress_queue: queue.Queue | None = None,
) -> ScraperResult:
    """BLOCKING wrapper — chi dung cho CLI/unit test.

    KHONG goi tu Streamlit — se freeze toan UI.
    UI phai dung ScrapeRunner (ui/runner.py) voi add_script_run_ctx + polling.
    """
    return asyncio.run(run_scraper(urls, options, progress_queue))
