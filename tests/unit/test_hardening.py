"""Hardening regression tests: retry, resume, fallback, log rotation,
quota/network/crash scenarios.

Maps to BUGS_FOUND.md follow-ups:
  - Resume after crash mid-batch (Job.last_completed_index)
  - Graceful degradation: ProviderError → convert-mode fallback
  - Log rotation: RotatingFileHandler at 10 MB × 10 files
  - Quota / safety / network errors handled per provider contract
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline.orchestrator import translate_chapter
from trilex.logging_config import setup_logging
from trilex.persistence import db as db_mod
from trilex.persistence.db import sync_dsn
from trilex.persistence.models import Base, Chapter, Job, Project
from trilex.providers.base import (
    DEFAULT_MAX_TOKENS,
    EmptyResponseError,
    LLMProvider,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
    QuotaExceededError,
)
from trilex.qt_dict.applier import QTApplier
from trilex.ui.runners import translate_runner as runner_mod

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_path / "hard.db"
    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", db_file)
    monkeypatch.setattr(runner_mod, "DEFAULT_DB_PATH", db_file)

    eng = create_engine(sync_dsn(db_file), future=True)
    Base.metadata.create_all(eng)
    eng.dispose()

    runner_mod._engine = None
    runner_mod._factory = None
    yield db_file
    runner_mod._engine = None
    runner_mod._factory = None


@pytest.fixture
def project_id(tmp_db: Path, tmp_path: Path) -> str:
    eng = create_engine(sync_dsn(tmp_db), future=True)
    session_factory = sessionmaker(eng, expire_on_commit=False)
    with session_factory() as s:
        p = Project(
            name="Hard",
            slug="hard",
            source_lang="zh",
            target_lang="vn",
            genre="tu_tien",
            vault_path=str(tmp_path / "vault"),
        )
        s.add(p)
        s.commit()
        pid = p.id
    eng.dispose()
    return pid


class _FlakyProvider(LLMProvider):
    """Succeeds for the first ``ok_count`` calls then raises ``error`` forever."""

    name = "flaky"

    def __init__(self, ok_count: int = 0, error: ProviderError | None = None) -> None:
        self.ok_count = ok_count
        self.error = error or QuotaExceededError("quota exhausted")
        self.calls = 0

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.calls += 1
        if self.calls > self.ok_count:
            raise self.error
        return ProviderResponse(
            text="đã dịch.",
            tokens_used=1,
            model="flaky-1",
            latency_ms=0.1,
            finish_reason="stop",
        )


# --------------------------------------------------------------------------- #
# Resume                                                                      #
# --------------------------------------------------------------------------- #


def test_resume_after_partial_crash(tmp_db: Path, project_id: str) -> None:
    """Simulate a crash mid-batch: process the first 3 chapters then have the
    worker raise. Restart with resume_job_id and verify chapters 4–10 run."""

    fake_provider = _FlakyProvider(ok_count=999)

    def _stub_build(pid: str, mode: str):
        cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
        return cfg, fake_provider

    # Avoid touching real config/env.
    import unittest.mock as mock

    chapters = [(f"Ch{i}", f"李青 {i}") for i in range(10)]
    with mock.patch.object(runner_mod, "_build_cfg_and_provider", _stub_build):
        # First run — abort after 3 by raising inside translate_chapter.
        crash_after = {"n": 0}
        original = runner_mod.translate_chapter

        async def crash_after_3(text, cfg, **kw):
            crash_after["n"] += 1
            if crash_after["n"] > 3:
                # Hard exit out of the worker loop.
                raise SystemExit("simulated crash")
            return await original(text, cfg, **kw)

        with mock.patch.object(runner_mod, "translate_chapter", crash_after_3):
            job_id = runner_mod._create_job(
                project_id,
                job_type="batch_translate",
                payload={"mode": "convert"},
                total_count=len(chapters),
            )
            with pytest.raises(SystemExit):
                runner_mod._worker_batch(
                    job_id, project_id, chapters, mode="convert", write_to_vault=False
                )

        # State check: 3 chapters persisted, last_completed_index == 2.
        factory = runner_mod._get_factory()
        with factory() as s:
            j = s.get(Job, job_id)
            assert j is not None
            assert j.completed_count == 3
            assert j.last_completed_index == 2
            n_chapters = s.query(Chapter).filter_by(project_id=project_id).count()
            assert n_chapters == 3

        # Restart: resume picks up at index 3.
        runner_mod._reset_job_for_resume(job_id, total=len(chapters))
        runner_mod._worker_batch(job_id, project_id, chapters, mode="convert", write_to_vault=False)

        with factory() as s:
            j = s.get(Job, job_id)
            assert j is not None
            assert j.status == "completed"
            assert j.completed_count == 10
            assert j.last_completed_index == 9
            n_chapters = s.query(Chapter).filter_by(project_id=project_id).count()
            assert n_chapters == 10


def test_resume_skips_completed_chapters(tmp_db: Path, project_id: str) -> None:
    """Pre-seed last_completed_index=4 and verify the worker starts at 5."""

    fake_provider = _FlakyProvider(ok_count=999)

    def _stub_build(pid: str, mode: str):
        cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
        return cfg, fake_provider

    import unittest.mock as mock

    chapters = [(f"Ch{i}", f"李青 {i}") for i in range(10)]
    job_id = runner_mod._create_job(
        project_id,
        job_type="batch_translate",
        payload={},
        total_count=len(chapters),
    )
    # Manually seed prior progress.
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        j.completed_count = 5
        j.last_completed_index = 4
        s.commit()

    seen_texts: list[str] = []
    original = runner_mod.translate_chapter

    async def spy(text, cfg, **kw):
        seen_texts.append(text)
        return await original(text, cfg, **kw)

    with (
        mock.patch.object(runner_mod, "_build_cfg_and_provider", _stub_build),
        mock.patch.object(runner_mod, "translate_chapter", spy),
    ):
        runner_mod._worker_batch(job_id, project_id, chapters, mode="convert", write_to_vault=False)

    # Only chapters 5..9 should have been processed.
    assert seen_texts == [f"李青 {i}" for i in range(5, 10)]
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.completed_count == 10
        assert j.last_completed_index == 9


def test_resume_via_submit_batch_resume_job_id(
    tmp_db: Path, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``submit_batch(resume_job_id=...)`` keeps the old job row and re-arms it."""
    chapters = [(None, "李青") for _ in range(2)]
    job_id = runner_mod._create_job(
        project_id, job_type="batch_translate", payload={}, total_count=10
    )

    # Patch worker so we don't actually run the pipeline; just assert the
    # function was given the same job_id.
    captured: dict[str, str] = {}

    def _fake_worker(jid, pid, chs, mode, write):
        captured["job_id"] = jid

    monkeypatch.setattr(runner_mod, "_worker_batch", _fake_worker)
    # The Thread is started before our patched fn runs — give the worker time.
    monkeypatch.setattr(
        runner_mod.threading,
        "Thread",
        lambda target, args, daemon, name: type("T", (), {"start": lambda self: target(*args)})(),
    )

    out_id = runner_mod.submit_batch(project_id, chapters, mode="convert", resume_job_id=job_id)
    assert out_id == job_id
    assert captured.get("job_id") == job_id


def test_record_helpers_clamp_progress(tmp_db: Path, project_id: str) -> None:
    job_id = runner_mod._create_job(project_id, job_type="batch_translate", payload={})
    runner_mod._record_chapter_done(job_id, index=0, progress=2.0)  # > 1.0
    runner_mod._record_chapter_failed(job_id, index=1, progress=-0.5)  # < 0
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.progress == 0.0
        assert j.completed_count == 1
        assert j.failed_count == 1
        assert j.last_completed_index == 1


def test_record_helpers_noop_on_missing_job(tmp_db: Path) -> None:
    """Defensive: missing job id must not raise."""
    runner_mod._record_chapter_done("ghost", index=0, progress=0.5)
    runner_mod._record_chapter_failed("ghost", index=0, progress=0.5)
    runner_mod._reset_job_for_resume("ghost", total=10)
    assert runner_mod._last_completed_index("ghost") == -1


# --------------------------------------------------------------------------- #
# Fallback to convert                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fallback_keeps_pipeline_alive_on_quota(tmp_path: Path) -> None:
    cfg = ProjectConfig(
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
        dict_dir=Path("data/dictionaries"),
        cache_dir=Path("data/cache"),
    )
    provider = _FlakyProvider(ok_count=0, error=QuotaExceededError("quota"))
    applier = QTApplier(Path("data/dictionaries"), cache_dir=Path("data/cache"))
    result = await translate_chapter(
        "李青走进青云宗。",
        cfg,
        mode="polish",
        provider=provider,
        applier=applier,
    )
    assert result.state == "postprocessed"
    assert result.polished_text is None
    assert result.convert_text is not None
    assert any("fallback_to_convert:QuotaExceededError" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_fallback_disabled_marks_failed(tmp_path: Path) -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    provider = _FlakyProvider(ok_count=0, error=ProviderTimeoutError("net timeout"))
    applier = QTApplier(Path("data/dictionaries"), cache_dir=Path("data/cache"))
    result = await translate_chapter(
        "李青。",
        cfg,
        mode="polish",
        provider=provider,
        applier=applier,
        fallback_to_convert=False,
    )
    assert result.state == "failed"
    assert any("provider_error:ProviderTimeoutError" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_fallback_with_non_zh_source_skips_qt_but_returns_preprocessed(
    tmp_path: Path,
) -> None:
    """VN→EN with ProviderError → fallback uses preprocessed text since QT
    pass was skipped (source != zh)."""
    cfg = ProjectConfig(source_lang="vn", target_lang="en", genre="tu_tien")
    provider = _FlakyProvider(ok_count=0, error=EmptyResponseError("empty"))
    result = await translate_chapter("Lý Thanh.", cfg, mode="polish", provider=provider)
    assert result.state == "postprocessed"
    assert result.convert_text is None
    assert "Lý Thanh" in result.final_text  # preprocessed fallback


# --------------------------------------------------------------------------- #
# Quota / network behaviour at the worker level                               #
# --------------------------------------------------------------------------- #


def test_quota_exhausted_marks_chapters_failed_then_continues(
    tmp_db: Path, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider raises QuotaExceeded on every call. Worker keeps going thanks to
    per-chapter except, marking each chapter failed."""
    provider = _FlakyProvider(ok_count=0, error=QuotaExceededError("over quota"))

    def _stub_build(pid: str, mode: str):
        cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
        return cfg, provider

    monkeypatch.setattr(runner_mod, "_build_cfg_and_provider", _stub_build)

    # The orchestrator-level fallback returns state="postprocessed", not
    # state="failed", so all 5 chapters still get persisted (just without
    # polished text). Validates: even on quota exhaustion, no data loss.
    chapters = [(None, "李青") for _ in range(5)]
    job_id = runner_mod._create_job(
        project_id, job_type="batch_translate", payload={}, total_count=5
    )
    runner_mod._worker_batch(job_id, project_id, chapters, mode="polish", write_to_vault=False)
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.status == "completed"
        assert j.completed_count == 5
        n = s.query(Chapter).filter_by(project_id=project_id).count()
        assert n == 5
        for ch in s.query(Chapter).filter_by(project_id=project_id).all():
            assert ch.polished_text is None
            assert ch.state == "postprocessed"


# --------------------------------------------------------------------------- #
# Log rotation                                                                #
# --------------------------------------------------------------------------- #


@pytest.fixture
def isolated_root_logger() -> None:
    """Snapshot the root logger and restore it after the test.

    Keeps log-rotation tests from polluting global state — without this, a
    DEBUG-level root logger leaks into later tests and slows them via
    SQLAlchemy/aiosqlite chatter, which destabilises threaded tests that race
    against fixed timeouts (e.g. ``test_submit_batch_creates_job``).
    """
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    yield
    for h in list(root.handlers):
        if getattr(h, "_trilex_managed", False):
            root.removeHandler(h)
            h.close()
    # Restore exactly what was there before.
    root.handlers = saved_handlers
    root.setLevel(saved_level)


def test_setup_logging_creates_rotating_handler(tmp_path: Path, isolated_root_logger: None) -> None:
    log_path = tmp_path / "logs" / "trilex.log"
    out = setup_logging(level=logging.INFO, log_path=log_path, console=False)
    assert out == log_path
    root = logging.getLogger()
    rotating = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(rotating) == 1
    rh = rotating[0]
    assert rh.maxBytes == 10 * 1024 * 1024
    assert rh.backupCount == 10


def test_log_rotation_actually_rolls(tmp_path: Path, isolated_root_logger: None) -> None:
    """Force a rotation by setting maxBytes tiny and flooding the handler.
    After enough writes the .1 backup should exist."""
    log_path = tmp_path / "trilex.log"
    setup_logging(
        level=logging.DEBUG,
        log_path=log_path,
        max_bytes=512,
        backup_count=3,
        console=False,
    )
    logger = logging.getLogger("trilex.test.rotation")
    for i in range(200):
        logger.info("rotation line %d %s", i, "x" * 32)
    for h in logging.getLogger().handlers:
        h.flush()
    assert log_path.exists()
    rotated = list(tmp_path.glob("trilex.log.*"))
    assert len(rotated) >= 1
    assert len(rotated) <= 3  # bounded by backup_count


def test_setup_logging_idempotent(tmp_path: Path, isolated_root_logger: None) -> None:
    """Calling setup_logging twice must not duplicate handlers."""
    log_path = tmp_path / "trilex.log"
    setup_logging(level=logging.INFO, log_path=log_path, console=False)
    setup_logging(level=logging.INFO, log_path=log_path, console=False)
    managed = [h for h in logging.getLogger().handlers if getattr(h, "_trilex_managed", False)]
    assert len(managed) == 1


# --------------------------------------------------------------------------- #
# Provider-level retry already exists; assert it fires correctly              #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_gemini_provider_retries_on_quota_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject a flaky underlying SDK that quota-errors twice then returns a
    valid response. The provider must retry and succeed on the 3rd attempt."""
    from google.api_core import exceptions as gax

    from trilex.providers.gemini import GeminiProvider

    p = GeminiProvider(
        api_key="AIzaSyTESTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        model="gemini-test",
        timeout=2.0,
        max_retries=3,
        backoff_base=0.0,
    )

    class _Resp:
        prompt_feedback = None

        class _Cand:
            finish_reason = type("FR", (), {"name": "STOP"})()

            class _Content:
                parts = [type("P", (), {"text": "ok"})()]

            content = _Content()

        candidates = [_Cand()]
        text = "ok"

        class _Usage:
            total_token_count = 3

        usage_metadata = _Usage()

    attempts = {"n": 0}

    async def fake_generate(*args, **kw):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise gax.ResourceExhausted("rate limit")
        return _Resp()

    monkeypatch.setattr(p._model, "generate_content_async", fake_generate)

    resp = await p.complete("hello")
    assert resp.text == "ok"
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_gemini_provider_raises_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from google.api_core import exceptions as gax

    from trilex.providers.gemini import GeminiProvider

    p = GeminiProvider(
        api_key="AIzaSyTESTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        model="gemini-test",
        timeout=2.0,
        max_retries=2,
        backoff_base=0.0,
    )

    async def always_quota(*args, **kw):
        raise gax.ResourceExhausted("nope")

    monkeypatch.setattr(p._model, "generate_content_async", always_quota)

    with pytest.raises(QuotaExceededError):
        await p.complete("hi")
