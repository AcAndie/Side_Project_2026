"""
src/littrans/ui/runner.py — Background pipeline runner.

Captures stdout (tất cả print() trong pipeline) và đẩy vào Queue
để UI có thể stream log theo thời gian thực.
"""
from __future__ import annotations

import io
import sys
import threading
import queue
import traceback
from pathlib import Path


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
    log_queue: queue.Queue,
    mode: str = "run",
    filename: str = "",
    update_data: bool = False,
    force_scout: bool = False,
    all_files: list[str] | None = None,
    chapter_index: int = 0,
    char_action: str = "merge",
) -> threading.Thread:
    """
    Chạy pipeline operation trong background thread.

    mode:
        "run"            — Pipeline().run()   (dịch tất cả chương chưa dịch)
        "retranslate"    — Pipeline().retranslate(filename, update_data)
        "clean_glossary" — clean_glossary()
        "clean_chars"    — run_action(char_action)
    """

    def _worker() -> None:
        old_stdout = sys.stdout
        sys.stdout = _StdoutCapture(log_queue)
        try:
            # Đảm bảo project root trên sys.path
            root = Path(__file__).resolve().parents[3]
            for p in [str(root), str(root / "src")]:
                if p not in sys.path:
                    sys.path.insert(0, p)

            if mode == "run":
                from littrans.engine.pipeline import Pipeline
                Pipeline().run()

            elif mode == "retranslate":
                # Optional: chạy Scout trước
                if force_scout and all_files:
                    from littrans.engine.scout import run as scout_run
                    print(f"🔭 Chạy Scout trước khi dịch lại ({len(all_files)} chương)...")
                    scout_run(all_files, chapter_index)

                from littrans.engine.pipeline import Pipeline
                Pipeline().retranslate(filename, update_data=update_data)

            elif mode == "clean_glossary":
                from littrans.tools.clean_glossary import clean_glossary
                clean_glossary()

            elif mode == "clean_chars":
                from littrans.tools.clean_characters import run_action
                run_action(char_action)

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
    thread.start()
    return thread