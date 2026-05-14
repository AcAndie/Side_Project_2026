"""Background-threaded translation runner.

Single-user assumption ⇒ `threading.Thread` is sufficient (no executor pool,
no Celery). Each worker:
  1. Reads project metadata from a fresh sync SQLAlchemy session.
  2. Runs the async pipeline via `asyncio.run` inside the thread.
  3. Persists `Chapter` + writes the vault file.
  4. Updates Job status / progress in DB between steps.

The UI never talks to the worker directly — DB rows are the only sync point,
which keeps Streamlit's session-state model intact (worker threads can't safely
touch `st.session_state`).

Cancellation is best-effort: the worker polls `Job.status` between chapters; a
mid-pipeline cancel waits for the current chapter to finish.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline import ChapterResult, translate_chapter
from trilex.output.obsidian import write_chapter as vault_write_chapter
from trilex.persistence.db import DEFAULT_DB_PATH, sync_dsn
from trilex.persistence.models import Chapter, Job, Project
from trilex.providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

_engine = None
_factory: sessionmaker[Session] | None = None


def _get_factory() -> sessionmaker[Session]:
    """Lazy sync sessionmaker. `check_same_thread=False` + `NullPool` so each
    worker thread gets its own connection without poisoning the next caller."""
    global _engine, _factory
    if _factory is None:
        _engine = create_engine(
            sync_dsn(DEFAULT_DB_PATH),
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        _factory = sessionmaker(_engine, expire_on_commit=False, class_=Session)
    return _factory


# --------------------------------------------------------------------------- #
# Job status helpers (sync)                                                   #
# --------------------------------------------------------------------------- #


def _update_job(job_id: str, **fields: object) -> None:
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        if j is None:
            return
        for k, v in fields.items():
            setattr(j, k, v)
        s.commit()


def _mark_running(job_id: str) -> None:
    _update_job(job_id, status="running", started_at=datetime.now(UTC), progress=0.0)


def _mark_progress(job_id: str, progress: float) -> None:
    _update_job(job_id, progress=max(0.0, min(1.0, progress)))


def _mark_complete(job_id: str) -> None:
    _update_job(
        job_id,
        status="completed",
        progress=1.0,
        completed_at=datetime.now(UTC),
        error=None,
    )


def _mark_failed(job_id: str, err: str) -> None:
    _update_job(
        job_id,
        status="failed",
        completed_at=datetime.now(UTC),
        error=err[:2000],
    )


def is_cancelled(job_id: str) -> bool:
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        return j is not None and j.status == "cancelled"


def cancel_job(job_id: str) -> bool:
    """Mark a job cancelled. Worker honors this between chapters."""
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        if j is None or j.status in ("completed", "failed", "cancelled"):
            return False
        j.status = "cancelled"
        j.completed_at = datetime.now(UTC)
        s.commit()
        return True


# --------------------------------------------------------------------------- #
# Chapter persistence                                                          #
# --------------------------------------------------------------------------- #


def _next_chapter_index(s: Session, project_id: str) -> int:
    max_idx = s.execute(
        select(func.coalesce(func.max(Chapter.index), 0)).where(Chapter.project_id == project_id)
    ).scalar_one()
    return int(max_idx) + 1


def persist_chapter_result(
    project_id: str,
    result: ChapterResult,
    *,
    title: str | None = None,
    write_to_vault: bool = True,
) -> tuple[str, int, Path | None]:
    """Insert a `Chapter` row + (optionally) write the vault file.

    Returns `(chapter_id, index, vault_path_or_None)`.
    """
    factory = _get_factory()
    with factory() as s:
        project = s.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        index = _next_chapter_index(s, project_id)
        ch = Chapter(
            project_id=project_id,
            index=index,
            title=title,
            source_text=result.source_text,
            convert_text=result.convert_text,
            polished_text=result.polished_text,
            state=result.state,
            tokens_used=result.tokens_used,
            provider_used=result.model,
            warnings=list(result.warnings),
            translated_at=datetime.now(UTC) if result.state != "failed" else None,
        )
        s.add(ch)
        s.commit()
        chapter_id = ch.id

        vault_path: Path | None = None
        if write_to_vault:
            vault_root = Path(project.vault_path) if project.vault_path else Path("data/vault")
            # Re-fetch in same session so ch is bound for the write helper.
            s.refresh(ch)
            vault_path = vault_write_chapter(vault_root, project.slug, ch)

        return chapter_id, index, vault_path


# --------------------------------------------------------------------------- #
# Single-chapter background job                                                #
# --------------------------------------------------------------------------- #


def submit_single_chapter(
    project_id: str,
    source_text: str,
    *,
    title: str | None = None,
    mode: str = "polish",
    write_to_vault: bool = True,
) -> str:
    job_id = _create_job(
        project_id,
        job_type="translate",
        payload={"mode": mode, "title": title, "write_to_vault": write_to_vault},
    )
    threading.Thread(
        target=_worker_single,
        args=(job_id, project_id, source_text, title, mode, write_to_vault),
        daemon=True,
        name=f"trilex-translate-{job_id[:8]}",
    ).start()
    return job_id


def _worker_single(
    job_id: str,
    project_id: str,
    source_text: str,
    title: str | None,
    mode: str,
    write_to_vault: bool,
) -> None:
    try:
        _mark_running(job_id)
        cfg, provider = _build_cfg_and_provider(project_id, mode)
        _mark_progress(job_id, 0.1)
        if is_cancelled(job_id):
            return
        result = asyncio.run(
            translate_chapter(source_text, cfg, mode=mode, provider=provider)  # type: ignore[arg-type]
        )
        _mark_progress(job_id, 0.85)
        if is_cancelled(job_id):
            return
        persist_chapter_result(project_id, result, title=title, write_to_vault=write_to_vault)
        _mark_complete(job_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("single-chapter worker failed (job=%s)", job_id)
        _mark_failed(job_id, f"{type(e).__name__}: {e}")


# --------------------------------------------------------------------------- #
# Batch background job                                                         #
# --------------------------------------------------------------------------- #


def submit_batch(
    project_id: str,
    chapters: list[tuple[str | None, str]],
    *,
    mode: str = "polish",
    write_to_vault: bool = True,
    resume_job_id: str | None = None,
) -> str:
    """Spawn a batch translation job.

    If ``resume_job_id`` points to an existing batch job, the worker picks up
    from ``last_completed_index + 1`` and reuses the existing job row instead
    of creating a new one.
    """
    if not chapters:
        raise ValueError("chapters list is empty")
    if resume_job_id is not None:
        job_id = resume_job_id
        _reset_job_for_resume(job_id, total=len(chapters))
    else:
        job_id = _create_job(
            project_id,
            job_type="batch_translate",
            payload={
                "mode": mode,
                "count": len(chapters),
                "write_to_vault": write_to_vault,
            },
            total_count=len(chapters),
        )
    threading.Thread(
        target=_worker_batch,
        args=(job_id, project_id, list(chapters), mode, write_to_vault),
        daemon=True,
        name=f"trilex-batch-{job_id[:8]}",
    ).start()
    return job_id


def _worker_batch(
    job_id: str,
    project_id: str,
    chapters: list[tuple[str | None, str]],
    mode: str,
    write_to_vault: bool,
) -> None:
    try:
        _mark_running(job_id)
        cfg, provider = _build_cfg_and_provider(project_id, mode)

        total = len(chapters)
        # Resume: skip chapters whose index is <= last_completed_index.
        start_index = _last_completed_index(job_id) + 1
        if start_index > 0:
            logger.info("resuming batch job=%s from index %d/%d", job_id, start_index, total)

        for i in range(start_index, total):
            title, text = chapters[i]
            if is_cancelled(job_id):
                return
            try:
                result = asyncio.run(
                    translate_chapter(text, cfg, mode=mode, provider=provider)  # type: ignore[arg-type]
                )
                persist_chapter_result(
                    project_id, result, title=title, write_to_vault=write_to_vault
                )
                _record_chapter_done(job_id, index=i, progress=(i + 1) / total)
            except Exception:  # noqa: BLE001
                logger.exception("batch chapter %d failed", i)
                _record_chapter_failed(job_id, index=i, progress=(i + 1) / total)
        if not is_cancelled(job_id):
            _mark_complete(job_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("batch worker failed (job=%s)", job_id)
        _mark_failed(job_id, f"{type(e).__name__}: {e}")


# --------------------------------------------------------------------------- #
# Shared helpers                                                               #
# --------------------------------------------------------------------------- #


def _create_job(
    project_id: str,
    *,
    job_type: str,
    payload: dict[str, object],
    total_count: int = 0,
) -> str:
    factory = _get_factory()
    with factory() as s:
        job = Job(
            project_id=project_id,
            type=job_type,
            status="pending",
            progress=0.0,
            payload=payload,
            total_count=total_count,
        )
        s.add(job)
        s.commit()
        return job.id


def _reset_job_for_resume(job_id: str, *, total: int) -> None:
    """Re-arm a job row for a resume run.

    Keeps ``completed_count`` / ``last_completed_index`` so the worker knows
    where to pick up, but clears terminal status + error so the worker can run.
    """
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        if j is None:
            return
        j.status = "pending"
        j.error = None
        j.completed_at = None
        j.total_count = total
        s.commit()


def _last_completed_index(job_id: str) -> int:
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        if j is None:
            return -1
        return int(j.last_completed_index)


def _record_chapter_done(job_id: str, *, index: int, progress: float) -> None:
    """Atomically bump completed_count + advance last_completed_index."""
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        if j is None:
            return
        j.completed_count = int(j.completed_count) + 1
        j.last_completed_index = index
        j.progress = max(0.0, min(1.0, progress))
        s.commit()


def _record_chapter_failed(job_id: str, *, index: int, progress: float) -> None:
    """Bump failed_count and advance last_completed_index so the next run skips
    past the bad chapter (rather than retrying it forever)."""
    factory = _get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        if j is None:
            return
        j.failed_count = int(j.failed_count) + 1
        j.last_completed_index = index
        j.progress = max(0.0, min(1.0, progress))
        s.commit()


def _build_cfg_and_provider(
    project_id: str, mode: str
) -> tuple[ProjectConfig, GeminiProvider | None]:
    factory = _get_factory()
    with factory() as s:
        project = s.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        cfg = ProjectConfig(
            source_lang=project.source_lang,  # type: ignore[arg-type]
            target_lang=project.target_lang,  # type: ignore[arg-type]
            genre=project.genre,
        )
    provider: GeminiProvider | None = None
    if mode != "convert":
        provider = GeminiProvider.from_settings()
    return cfg, provider
