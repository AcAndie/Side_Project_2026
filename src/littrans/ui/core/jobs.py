"""
src/littrans/ui/core/jobs.py — Global poll_all drainer.

Runs once per Streamlit rerun (from app.py) BEFORE page dispatch.
Drains every job queue, marks done when sentinel arrives or thread dies,
emits stale-heartbeat warnings, surfaces __ERROR__ markers.

Returns True if any job is still active → caller must rerun to keep
polling alive even when the user has switched to a different tab.
"""
from __future__ import annotations

import time
from typing import Any

from littrans.ui.runner import poll_queue
from littrans.ui.core.state import JOB_KEYS

STALE_LOG_SEC = 180.0


def _thread_is_alive(thread: Any) -> bool:
    """Works for both threading.Thread and ScrapeRunner/PipelineRunner wrappers."""
    if thread is None:
        return False
    is_alive = getattr(thread, "is_alive", None)
    if callable(is_alive):
        try:
            return bool(is_alive())
        except Exception:
            return False
    return False


def poll_all(S: Any) -> bool:
    """Drain queues for every active job. Returns True if any job still active."""
    active = False

    for k in JOB_KEYS:
        if not S.get(f"{k}_running"):
            continue

        q      = S.get(f"{k}_q")
        logs   = S.setdefault(f"{k}_logs", [])
        thread = S.get(f"{k}_thread")

        if q is None:
            S[f"{k}_running"] = False
            continue

        prev_len = len(logs)
        done, _extras = poll_queue(q, logs)

        if len(logs) > prev_len:
            S[f"{k}_last_log"] = time.time()
            for i in range(prev_len, len(logs)):
                line = logs[i]
                if isinstance(line, str) and line.startswith("__ERROR__:"):
                    err = line.split(":", 1)[1].strip()
                    S[f"{k}_error"] = err
                    logs[i] = f"❌ {err}"

        # Watchdog: thread died but no __DONE__ sentinel arrived
        if not done and thread is not None and not _thread_is_alive(thread):
            logs.append("⚠ Thread terminated without __DONE__")
            done = True

        # Stale heartbeat warning (once per silent stretch)
        if not done:
            last = S.get(f"{k}_last_log") or 0.0
            if last and (time.time() - last) > STALE_LOG_SEC:
                flag = f"{k}_stale_warned"
                if not S.get(flag):
                    logs.append(
                        f"⏱ Không có log >{int(STALE_LOG_SEC)}s — "
                        "có thể đang AI call dài hoặc bị rate-limit."
                    )
                    S[flag] = True

        if done:
            S[f"{k}_running"] = False
            S.pop(f"{k}_stale_warned", None)
            logs.append("─" * 56)
            if S.get(f"{k}_error"):
                logs.append(f"⚠️ Job '{k}' kết thúc có lỗi.")
            else:
                logs.append(f"✅ Job '{k}' hoàn tất.")
        else:
            active = True

    return active
