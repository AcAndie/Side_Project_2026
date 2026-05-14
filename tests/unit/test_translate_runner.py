"""Tests for `ui/runners/translate_runner.py`.

The runner shells out work to background threads; we drive it inline by:
  1. Pointing `DEFAULT_DB_PATH` at a tmp SQLite file.
  2. Patching `GeminiProvider.from_settings` so no API key is required.
  3. Calling the worker functions directly (no threading) for deterministic tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trilex.persistence import db as db_mod
from trilex.persistence.db import sync_dsn
from trilex.persistence.models import Base, Chapter, Job, Project
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider, ProviderResponse
from trilex.ui.runners import translate_runner as runner_mod

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point runner + db_mod at a fresh tmp SQLite. Creates tables."""
    db_file = tmp_path / "runner.db"
    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", db_file)
    monkeypatch.setattr(runner_mod, "DEFAULT_DB_PATH", db_file)

    # Create schema synchronously.
    eng = create_engine(sync_dsn(db_file), future=True)
    Base.metadata.create_all(eng)
    eng.dispose()

    # Reset runner module-level cache.
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
            name="Test",
            slug="test",
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


@pytest.fixture
def fake_provider_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch GeminiProvider.from_settings to return a fake that always succeeds."""

    class _Fake(LLMProvider):
        name = "fake"

        async def complete(
            self,
            prompt: str,
            system: str | None = None,
            max_tokens: int = DEFAULT_MAX_TOKENS,
        ) -> ProviderResponse:
            return ProviderResponse(
                text="Đã dịch.",
                tokens_used=5,
                model="fake-1",
                latency_ms=1.0,
                finish_reason="stop",
            )

    monkeypatch.setattr(
        "trilex.providers.gemini.GeminiProvider.from_settings",
        classmethod(lambda cls: _Fake()),
    )


# --------------------------------------------------------------------------- #
# _get_factory + status helpers                                               #
# --------------------------------------------------------------------------- #


def test_get_factory_is_memoised(tmp_db: Path) -> None:
    f1 = runner_mod._get_factory()
    f2 = runner_mod._get_factory()
    assert f1 is f2


def test_update_job_noop_when_missing(tmp_db: Path) -> None:
    """_update_job on an unknown id silently returns (no crash)."""
    runner_mod._update_job("does-not-exist", status="completed")


def test_cancel_job_returns_false_when_missing(tmp_db: Path) -> None:
    assert runner_mod.cancel_job("nope") is False


def test_cancel_job_marks_cancelled(tmp_db: Path, project_id: str) -> None:
    job_id = runner_mod._create_job(project_id, job_type="translate", payload={})
    assert runner_mod.is_cancelled(job_id) is False
    assert runner_mod.cancel_job(job_id) is True
    assert runner_mod.is_cancelled(job_id) is True
    # Re-cancelling a cancelled job is a no-op.
    assert runner_mod.cancel_job(job_id) is False


def test_status_helpers_progress_then_complete(tmp_db: Path, project_id: str) -> None:
    job_id = runner_mod._create_job(project_id, job_type="translate", payload={})
    runner_mod._mark_running(job_id)
    runner_mod._mark_progress(job_id, 0.5)
    # Out-of-range clamps to [0, 1].
    runner_mod._mark_progress(job_id, 5.0)
    runner_mod._mark_complete(job_id)

    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.status == "completed"
        assert j.progress == 1.0


def test_mark_failed_truncates_long_message(tmp_db: Path, project_id: str) -> None:
    job_id = runner_mod._create_job(project_id, job_type="translate", payload={})
    huge = "x" * 5000
    runner_mod._mark_failed(job_id, huge)
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.status == "failed"
        assert j.error is not None and len(j.error) == 2000


# --------------------------------------------------------------------------- #
# persist_chapter_result                                                      #
# --------------------------------------------------------------------------- #


def test_persist_chapter_result_writes_db_and_vault(
    tmp_db: Path, project_id: str, tmp_path: Path
) -> None:
    from trilex.core.pipeline import ChapterResult

    res = ChapterResult(
        source_text="原文",
        preprocessed_text="原文",
        convert_text="convert",
        polished_text="polished",
        final_text="polished",
        mode="polish",
        state="postprocessed",
        warnings=[],
        stage_stats=[],
        tokens_used=10,
        total_elapsed_ms=12.3,
        model="fake-1",
    )
    chap_id, idx, vault_path = runner_mod.persist_chapter_result(
        project_id, res, title="Chương 1", write_to_vault=True
    )
    assert idx == 1
    assert vault_path is not None and vault_path.exists()

    # Second insert auto-increments index.
    chap_id2, idx2, _ = runner_mod.persist_chapter_result(
        project_id, res, title="Chương 2", write_to_vault=False
    )
    assert idx2 == 2 and chap_id2 != chap_id


def test_persist_chapter_result_no_vault_when_disabled(tmp_db: Path, project_id: str) -> None:
    from trilex.core.pipeline import ChapterResult

    res = ChapterResult(
        source_text="x",
        preprocessed_text="x",
        convert_text=None,
        polished_text="y",
        final_text="y",
        mode="polish",
        state="postprocessed",
        warnings=[],
        stage_stats=[],
        tokens_used=0,
        total_elapsed_ms=1.0,
        model=None,
    )
    _, _, vault_path = runner_mod.persist_chapter_result(project_id, res, write_to_vault=False)
    assert vault_path is None


def test_persist_chapter_result_failed_state_skips_translated_at(
    tmp_db: Path, project_id: str
) -> None:
    from trilex.core.pipeline import ChapterResult

    res = ChapterResult(
        source_text="x",
        preprocessed_text="x",
        convert_text=None,
        polished_text=None,
        final_text="",
        mode="polish",
        state="failed",
        warnings=["polish.boom"],
        stage_stats=[],
        tokens_used=0,
        total_elapsed_ms=0.5,
        model=None,
    )
    chap_id, _, _ = runner_mod.persist_chapter_result(project_id, res, write_to_vault=False)
    factory = runner_mod._get_factory()
    with factory() as s:
        ch = s.get(Chapter, chap_id)
        assert ch is not None
        assert ch.translated_at is None
        assert ch.state == "failed"


def test_persist_chapter_result_unknown_project_raises(tmp_db: Path) -> None:
    from trilex.core.pipeline import ChapterResult

    res = ChapterResult(
        source_text="x",
        preprocessed_text="x",
        convert_text=None,
        polished_text="y",
        final_text="y",
        mode="polish",
        state="postprocessed",
        warnings=[],
        stage_stats=[],
        tokens_used=0,
        total_elapsed_ms=1.0,
        model=None,
    )
    with pytest.raises(ValueError, match="not found"):
        runner_mod.persist_chapter_result("nope", res, write_to_vault=False)


# --------------------------------------------------------------------------- #
# _build_cfg_and_provider                                                     #
# --------------------------------------------------------------------------- #


def test_build_cfg_convert_mode_skips_provider(tmp_db: Path, project_id: str) -> None:
    cfg, provider = runner_mod._build_cfg_and_provider(project_id, "convert")
    assert provider is None
    assert cfg.source_lang == "zh"
    assert cfg.target_lang == "vn"


def test_build_cfg_polish_mode_creates_provider(
    tmp_db: Path, project_id: str, fake_provider_factory: None
) -> None:
    cfg, provider = runner_mod._build_cfg_and_provider(project_id, "polish")
    assert provider is not None
    assert cfg.genre == "tu_tien"


def test_build_cfg_unknown_project_raises(tmp_db: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        runner_mod._build_cfg_and_provider("nope", "polish")


# --------------------------------------------------------------------------- #
# Worker functions (inline, no threading)                                     #
# --------------------------------------------------------------------------- #


def test_worker_single_success(tmp_db: Path, project_id: str, fake_provider_factory: None) -> None:
    job_id = runner_mod._create_job(project_id, job_type="translate", payload={})
    runner_mod._worker_single(
        job_id,
        project_id,
        "李青走来。",
        title="Chương 1",
        mode="polish",
        write_to_vault=False,
    )
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None and j.status == "completed"


def test_worker_single_cancel_before_pipeline(
    tmp_db: Path,
    project_id: str,
    fake_provider_factory: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If is_cancelled returns True after setup, the worker bails out."""
    job_id = runner_mod._create_job(project_id, job_type="translate", payload={})
    monkeypatch.setattr(runner_mod, "is_cancelled", lambda jid: True)
    runner_mod._worker_single(
        job_id,
        project_id,
        "李青",
        title=None,
        mode="polish",
        write_to_vault=False,
    )
    factory = runner_mod._get_factory()
    with factory() as s:
        ch = s.query(Chapter).filter_by(project_id=project_id).all()
        assert ch == []


def test_worker_single_failure_marks_job_failed(tmp_db: Path, project_id: str) -> None:
    """Unknown project_id raised inside worker should mark the job failed."""
    job_id = runner_mod._create_job(project_id, job_type="translate", payload={})
    runner_mod._worker_single(
        job_id,
        "ghost-project",
        "x",
        title=None,
        mode="convert",
        write_to_vault=False,
    )
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None and j.status == "failed"


def test_worker_batch_runs_all_chapters(
    tmp_db: Path, project_id: str, fake_provider_factory: None
) -> None:
    chapters = [(f"Chương {i}", "李青走来。") for i in range(3)]
    job_id = runner_mod._create_job(project_id, job_type="batch_translate", payload={"count": 3})
    runner_mod._worker_batch(job_id, project_id, chapters, mode="polish", write_to_vault=False)
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.status == "completed"
        assert j.progress == 1.0
        ch_count = s.query(Chapter).filter_by(project_id=project_id).count()
        assert ch_count == 3


def test_worker_batch_continues_after_chapter_failure(
    tmp_db: Path, project_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One failing chapter should not stop the rest; final state still completed."""
    from trilex.core.pipeline import orchestrator as orch_mod

    call_count = {"n": 0}
    original = orch_mod.translate_chapter

    async def flaky(text: str, cfg: Any, **kw: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("boom")
        return await original(text, cfg, **kw)

    monkeypatch.setattr(runner_mod, "translate_chapter", flaky)

    chapters = [(None, "李青"), (None, "boom"), (None, "李青")]
    job_id = runner_mod._create_job(project_id, job_type="batch_translate", payload={})
    runner_mod._worker_batch(job_id, project_id, chapters, mode="convert", write_to_vault=False)
    factory = runner_mod._get_factory()
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None and j.status == "completed"
        # Two successful inserts, one skip.
        n = s.query(Chapter).filter_by(project_id=project_id).count()
        assert n == 2


def test_worker_batch_cancel_mid_run(
    tmp_db: Path,
    project_id: str,
    fake_provider_factory: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = runner_mod._create_job(project_id, job_type="batch_translate", payload={})
    # Patch is_cancelled → True so worker bails out after _mark_running.
    monkeypatch.setattr(runner_mod, "is_cancelled", lambda jid: True)
    runner_mod._worker_batch(
        job_id,
        project_id,
        [(None, "李青")],
        mode="polish",
        write_to_vault=False,
    )
    factory = runner_mod._get_factory()
    with factory() as s:
        ch = s.query(Chapter).filter_by(project_id=project_id).count()
        # Worker returned before any chapters were processed.
        assert ch == 0


def test_worker_batch_failure_in_setup(tmp_db: Path) -> None:
    """Unknown project → _build_cfg_and_provider raises → job marked failed."""
    # Need a job row with a real-looking project_id (FK).
    fake_proj = "00000000-0000-0000-0000-000000000000"
    factory = runner_mod._get_factory()
    with factory() as s:
        s.execute(
            Project.__table__.insert().values(
                id=fake_proj,
                name="ghost",
                slug="ghost",
                source_lang="zh",
                target_lang="vn",
                genre="tu_tien",
            )
        )
        s.commit()
    job_id = runner_mod._create_job(fake_proj, job_type="batch_translate", payload={})
    # Now delete the project so _build_cfg_and_provider fails.
    with factory() as s:
        # Cannot delete due to FK, just point worker at a different ghost id.
        pass
    runner_mod._worker_batch(
        job_id, "another-ghost", [(None, "x")], mode="convert", write_to_vault=False
    )
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None and j.status == "failed"


# --------------------------------------------------------------------------- #
# submit_* helpers (just ensure they spawn a job row)                         #
# --------------------------------------------------------------------------- #


def test_submit_single_chapter_creates_job(
    tmp_db: Path, project_id: str, fake_provider_factory: None
) -> None:
    job_id = runner_mod.submit_single_chapter(
        project_id, "李青", title=None, mode="convert", write_to_vault=False
    )
    factory = runner_mod._get_factory()
    import time as _t

    deadline = _t.time() + 30.0
    while _t.time() < deadline:
        with factory() as s:
            j = s.get(Job, job_id)
            if j is not None and j.status in ("completed", "failed"):
                break
        _t.sleep(0.2)
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None
        assert j.status == "completed"


def test_submit_batch_rejects_empty(tmp_db: Path, project_id: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        runner_mod.submit_batch(project_id, [], mode="convert")


def test_submit_batch_creates_job(
    tmp_db: Path, project_id: str, fake_provider_factory: None
) -> None:
    job_id = runner_mod.submit_batch(
        project_id,
        [(None, "李青") for _ in range(2)],
        mode="convert",
        write_to_vault=False,
    )
    factory = runner_mod._get_factory()
    import time as _t

    deadline = _t.time() + 30.0
    while _t.time() < deadline:
        with factory() as s:
            j = s.get(Job, job_id)
            if j is not None and j.status in ("completed", "failed", "cancelled"):
                break
        _t.sleep(0.2)
    with factory() as s:
        j = s.get(Job, job_id)
        assert j is not None and j.status == "completed"
