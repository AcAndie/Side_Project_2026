"""
src/littrans/ui/core/state.py — Unified session-state schema for jobs.

Each long-running background job uses prefix-based keys:
    {prefix}_running   bool
    {prefix}_q         queue.Queue | None
    {prefix}_logs      list[str]
    {prefix}_thread    Thread | runner | None
    {prefix}_last_log  float (epoch seconds)
    {prefix}_result    list (artifact holder)
    {prefix}_error     str | None

Prefixes:
    tx = translate (full pipeline run)
    sc = scrape
    rt = retranslate one chapter
    bi = bible scan
    ep = epub processor
    cg = clean glossary
    cc = clean characters
    cr = bible cross-reference / consistency validate
"""
from __future__ import annotations

from typing import Any

JOB_KEYS: tuple[str, ...] = ("tx", "sc", "rt", "bi", "ep", "cg", "cc", "cr")


def init_job_state(S: Any, prefix: str) -> None:
    """Initialize all 7 keys for one job prefix (idempotent)."""
    S.setdefault(f"{prefix}_running",  False)
    S.setdefault(f"{prefix}_q",        None)
    S.setdefault(f"{prefix}_logs",     [])
    S.setdefault(f"{prefix}_thread",   None)
    S.setdefault(f"{prefix}_last_log", 0.0)
    S.setdefault(f"{prefix}_result",   [])
    S.setdefault(f"{prefix}_error",    None)


def init_all_jobs(S: Any) -> None:
    for k in JOB_KEYS:
        init_job_state(S, k)


def reset_job(S: Any, prefix: str) -> None:
    """Wipe job state — call before starting a fresh run."""
    S[f"{prefix}_running"]  = False
    S[f"{prefix}_q"]        = None
    S[f"{prefix}_logs"]     = []
    S[f"{prefix}_thread"]   = None
    S[f"{prefix}_last_log"] = 0.0
    S[f"{prefix}_result"]   = []
    S[f"{prefix}_error"]    = None
    S.pop(f"{prefix}_stale_warned", None)
