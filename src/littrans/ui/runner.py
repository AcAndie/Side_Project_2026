"""
src/littrans/ui/runner.py — Background pipeline runner.
"""
from __future__ import annotations

import io
import sys
import threading
import queue
import traceback
from pathlib import Path

# ── Queue polling helper ──────────────────────────────────────────

DONE_SENTINEL = "__DONE__"


def poll_queue(
    q: queue.Queue,
    logs: list,
    *,
    extra_markers: tuple[str, ...] = (),
    max_drain: int = 300,
) -> tuple[bool, list[str]]:
    """Drain queue into logs list without blocking.

    Returns (done, extra_markers_seen). Replaces 5 duplicate drain loops.
    Messages matching extra_markers are collected separately (not appended to logs).
    """
    done = False
    extras: list[str] = []
    for _ in range(max_drain):
        try:
            msg = q.get_nowait()
        except queue.Empty:
            break
        if msg == DONE_SENTINEL:
            done = True
            break
        elif msg in extra_markers:
            extras.append(msg)
        else:
            logs.append(msg)
    return done, extras


class _StdoutCapture(io.TextIOBase):
    """Redirect stdout → Queue."""

    def __init__(self, log_queue: queue.Queue) -> None:
        self._q = log_queue

    def write(self, text: str) -> int:
        if text.strip():
            self._q.put(text.rstrip())
        return len(text)

    def flush(self) -> None:
        pass


def run_background(
    log_queue   : queue.Queue,
    mode        : str = "run",
    novel_name  : str = "",
    filename    : str = "",
    update_data : bool = False,
    force_scout : bool = False,
    all_files   : list[str] | None = None,
    chapter_index: int = 0,
    char_action : str = "",        # FIX: rỗng thay vì "merge" để tránh default âm thầm
) -> threading.Thread:
    """
    Chạy pipeline operation trong background thread.

    char_action: bắt buộc khi mode="clean_chars".
                 Nhận một trong: review|merge|fix|export|validate|archive|log|diff
    """

    def _worker() -> None:
        old_stdout = sys.stdout
        sys.stdout = _StdoutCapture(log_queue)
        try:
            root = Path(__file__).resolve().parents[3]
            for p in [str(root), str(root / "src")]:
                if p not in sys.path:
                    sys.path.insert(0, p)

            if novel_name:
                from littrans.config.settings import set_novel
                set_novel(novel_name)

            if mode == "run":
                from littrans.core.pipeline import Pipeline
                Pipeline().run()

            elif mode == "retranslate":
                if force_scout and all_files:
                    from littrans.core.scout import run as scout_run
                    print(f"🔭 Chạy Scout trước khi dịch lại ({len(all_files)} chương)...")
                    scout_run(all_files, chapter_index)

                from littrans.core.pipeline import Pipeline
                Pipeline().retranslate(filename, update_data=update_data)

            elif mode == "clean_glossary":
                from littrans.cli.tool_clean_glossary import clean_glossary
                clean_glossary()

            elif mode == "clean_chars":
                if not char_action:
                    raise ValueError("clean_chars: char_action là bắt buộc (review|merge|fix|export|validate|archive|log|diff)")
                from littrans.cli.tool_clean_chars import run_action
                run_action(char_action)

            else:
                raise ValueError(f"mode không hợp lệ: '{mode}'")

        except SystemExit as exc:
            if str(exc):
                log_queue.put(f"⚠️  {exc}")
        except Exception as exc:
            log_queue.put(f"❌ Lỗi: {exc}")
            for line in traceback.format_exc().splitlines()[-5:]:
                if line.strip():
                    log_queue.put(f"   {line}")
        finally:
            sys.stdout = old_stdout
            log_queue.put("__DONE__")

    thread = threading.Thread(target=_worker, daemon=True)
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        add_script_run_ctx(thread)
    except ImportError:
        pass
    thread.start()
    return thread


class ScrapeRunner:
    """Background scraper thread for Streamlit UI.

    CRITICAL: add_script_run_ctx ensures any st.session_state writes from
    the thread are visible to the Streamlit runtime. Without it, writes
    fail silently and the UI appears frozen.
    """

    def __init__(
        self,
        urls: list[str],
        options: object,
        progress_queue: queue.Queue,
        result_holder: list | None = None,
    ) -> None:
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx as _add_ctx
            self._add_ctx = _add_ctx
        except ImportError:
            self._add_ctx = None

        self._result_holder = result_holder if result_holder is not None else []
        self.thread = threading.Thread(
            target=self._run_wrapped,
            args=(urls, options, progress_queue),
            daemon=True,
        )
        if self._add_ctx is not None:
            self._add_ctx(self.thread)

    def _run_wrapped(self, urls: list[str], options: object, progress_queue: queue.Queue) -> None:
        import asyncio
        import traceback

        # Windows: Playwright subprocess needs ProactorEventLoop
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass

        try:
            from littrans.modules.scraper import run_scraper
            result = asyncio.run(run_scraper(urls, options, progress_queue))
            self._result_holder.append(result)
        except Exception as exc:
            progress_queue.put(f"__ERROR__:{type(exc).__name__}: {exc}")
            progress_queue.put(f"❌ Lỗi nghiêm trọng: {type(exc).__name__}: {exc}")
            for line in traceback.format_exc().splitlines()[-8:]:
                if line.strip():
                    progress_queue.put(f"   {line}")
        finally:
            progress_queue.put("__DONE__")

    def start(self) -> None:
        self.thread.start()

    def is_alive(self) -> bool:
        return self.thread.is_alive()


class PipelineRunner:
    """Sequential pipeline runner for Streamlit UI: source → translate.

    Stage markers sent to progress_queue:
      "__STAGE_2__"    — entering translate stage
      "__STAGE_DONE__" — all stages finished (before __DONE__)
      "__DONE__"       — thread finished (always last)
    """

    def __init__(
        self,
        mode           : str,
        urls           : list[str],
        epub_path      : str,
        novel_name     : str,
        max_pw         : int,
        progress_queue : queue.Queue,
        result_holder  : list | None = None,
    ) -> None:
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx as _add_ctx
            self._add_ctx = _add_ctx
        except ImportError:
            self._add_ctx = None

        self._result_holder = result_holder if result_holder is not None else []
        self.thread = threading.Thread(
            target=self._run_wrapped,
            args=(mode, urls, epub_path, novel_name, max_pw, progress_queue),
            daemon=True,
        )
        if self._add_ctx is not None:
            self._add_ctx(self.thread)

    def _run_wrapped(
        self,
        mode      : str,
        urls      : list[str],
        epub_path : str,
        novel_name: str,
        max_pw    : int,
        q         : queue.Queue,
    ) -> None:
        import asyncio
        import io
        import traceback

        class _Cap(io.TextIOBase):
            def write(self, t: str) -> int:
                if t.strip():
                    q.put(t.rstrip())
                return len(t)
            def flush(self) -> None:
                pass

        import sys
        # Windows: Playwright subprocess needs ProactorEventLoop
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass
        old_stdout = sys.stdout
        sys.stdout = _Cap()
        try:
            root = Path(__file__).resolve().parents[3]
            for p in [str(root), str(root / "src")]:
                if p not in sys.path:
                    sys.path.insert(0, p)

            if novel_name:
                from littrans.config.settings import set_novel
                set_novel(novel_name)

            # ── Stage 1: source → inputs/{novel_name}/ ───────────────
            if mode in ("web_only", "web_translate"):
                from littrans.modules.scraper import run_scraper, ScraperOptions
                opts = ScraperOptions(novel_name=novel_name, max_pw_instances=max_pw)
                result = asyncio.run(run_scraper(urls, opts, q))
                self._result_holder.append(("scrape", result))
                if not result.ok and mode == "web_only":
                    q.put(f"⚠️ Cào hoàn tất có {len(result.errors)} lỗi.")
                    return

            elif mode in ("epub_only", "epub_translate"):
                from littrans.tools.epub_processor import process_epub
                result = process_epub(
                    epub_path,
                    log_queue=q,
                    output_mode="per_chapter",
                    novel_name=novel_name,
                )
                self._result_holder.append(("epub", result))
                if mode == "epub_only":
                    return

            # ── Stage 2: translate ───────────────────────────────────
            if mode in ("web_translate", "epub_translate", "file_translate"):
                q.put("__STAGE_2__")
                from littrans.core.pipeline import Pipeline
                Pipeline().run()

            q.put("__STAGE_DONE__")

        except SystemExit as exc:
            if str(exc):
                q.put(f"⚠️  {exc}")
        except Exception as exc:
            q.put(f"❌ Lỗi: {exc}")
            for line in traceback.format_exc().splitlines()[-5:]:
                if line.strip():
                    q.put(f"   {line}")
        finally:
            sys.stdout = old_stdout
            q.put("__DONE__")

    def start(self) -> None:
        self.thread.start()

    def is_alive(self) -> bool:
        return self.thread.is_alive()