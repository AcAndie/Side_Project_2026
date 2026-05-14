"""Tests for the repository layer.

Each test runs against an isolated in-memory SQLite engine; `StaticPool` keeps
a single connection so all sessions see the same database (default behaviour
gives each connection its own ephemeral DB).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from trilex.persistence.db import create_all, make_session_maker
from trilex.persistence.repos import ChapterRepo, JobRepo, ProjectRepo, TermRepo


@pytest.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    await create_all(eng)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    maker = make_session_maker(engine)
    async with maker() as s:
        yield s


@pytest.fixture
async def project_id(session) -> str:
    repo = ProjectRepo(session)
    p = await repo.create(
        name="Test Project",
        slug="test-project",
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
    )
    await session.commit()
    return p.id


# --------------------------------------------------------------------------- #
# ProjectRepo                                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_project_create_and_get(session) -> None:
    repo = ProjectRepo(session)
    p = await repo.create(name="A", slug="a", source_lang="zh", target_lang="vn", genre="tu_tien")
    await session.commit()
    assert (await repo.get(p.id)).slug == "a"
    assert (await repo.get_by_slug("a")).id == p.id
    assert await repo.get("missing-id") is None
    assert await repo.get_by_slug("missing") is None


@pytest.mark.asyncio
async def test_project_list_and_count_filtered_by_genre(session) -> None:
    repo = ProjectRepo(session)
    await repo.create(name="A", slug="a", source_lang="zh", target_lang="vn", genre="tu_tien")
    await repo.create(name="B", slug="b", source_lang="zh", target_lang="vn", genre="litrpg")
    await repo.create(name="C", slug="c", source_lang="zh", target_lang="vn", genre="tu_tien")
    await session.commit()

    assert await repo.count() == 3
    tu_tien = await repo.list(genre="tu_tien")
    assert {p.slug for p in tu_tien} == {"a", "c"}
    page = await repo.list(limit=2)
    assert len(page) == 2


@pytest.mark.asyncio
async def test_project_update(session) -> None:
    repo = ProjectRepo(session)
    p = await repo.create(name="A", slug="a", source_lang="zh", target_lang="vn")
    await session.commit()
    updated = await repo.update(p.id, name="Renamed", genre="litrpg")
    assert updated.name == "Renamed"
    assert updated.genre == "litrpg"


@pytest.mark.asyncio
async def test_project_update_invalid_field_raises(session) -> None:
    repo = ProjectRepo(session)
    p = await repo.create(name="A", slug="a", source_lang="zh", target_lang="vn")
    with pytest.raises(AttributeError):
        await repo.update(p.id, bogus_field="x")


@pytest.mark.asyncio
async def test_project_delete_cascades(session, project_id: str) -> None:
    chapters = ChapterRepo(session)
    terms = TermRepo(session)
    jobs = JobRepo(session)

    await chapters.create(project_id=project_id, index=1, source_text="a")
    await terms.create(project_id=project_id, category="character", locked_zh="李青")
    await jobs.create(project_id=project_id, job_type="translate")
    await session.commit()

    projects = ProjectRepo(session)
    deleted = await projects.delete(project_id)
    assert deleted is True
    await session.commit()

    assert await projects.get(project_id) is None
    assert (await chapters.get_range(project_id, start=0, end=999)) == []
    assert (await terms.list_for_project(project_id)) == []
    assert (await jobs.list_for_project(project_id)) == []


# --------------------------------------------------------------------------- #
# ChapterRepo                                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_chapter_create_and_get_by_index(session, project_id) -> None:
    repo = ChapterRepo(session)
    ch = await repo.create(project_id=project_id, index=1, source_text="李青走进青云宗。")
    await session.commit()
    found = await repo.get_by_index(project_id, 1)
    assert found.id == ch.id
    assert await repo.get_by_index(project_id, 99) is None


@pytest.mark.asyncio
async def test_chapter_bulk_insert_and_range(session, project_id) -> None:
    repo = ChapterRepo(session)
    payload = [{"index": i, "source_text": f"chap {i}"} for i in range(1, 11)]
    n = await repo.bulk_insert(project_id, payload)
    await session.commit()
    assert n == 10

    rng = await repo.get_range(project_id, start=3, end=7)
    assert [c.index for c in rng] == [3, 4, 5, 6, 7]
    # Inverted range returns empty.
    assert await repo.get_range(project_id, start=10, end=5) == []


@pytest.mark.asyncio
async def test_chapter_bulk_insert_empty_returns_zero(session, project_id) -> None:
    repo = ChapterRepo(session)
    assert await repo.bulk_insert(project_id, []) == 0


@pytest.mark.asyncio
async def test_chapter_count_by_state(session, project_id) -> None:
    repo = ChapterRepo(session)
    await repo.bulk_insert(
        project_id,
        [
            {"index": 1, "source_text": "a", "state": "raw"},
            {"index": 2, "source_text": "b", "state": "raw"},
            {"index": 3, "source_text": "c", "state": "converted"},
            {"index": 4, "source_text": "d", "state": "polished"},
        ],
    )
    await session.commit()
    counts = await repo.count_by_state(project_id)
    assert counts == {"raw": 2, "converted": 1, "polished": 1}


@pytest.mark.asyncio
async def test_chapter_update_translation_sets_fields(session, project_id) -> None:
    repo = ChapterRepo(session)
    ch = await repo.create(project_id=project_id, index=1, source_text="李青走进青云宗。")
    await session.commit()
    updated = await repo.update_translation(
        ch.id,
        convert_text="Lý Thanh đi vào Thanh Vân Tông.",
        polished_text="Lý Thanh bước vào Thanh Vân Tông.",
        state="polished",
        tokens_used=123,
        provider_used="gemini",
        warnings=["none"],
        mark_translated=True,
    )
    assert updated.state == "polished"
    assert updated.tokens_used == 123
    assert updated.translated_at is not None
    assert updated.warnings == ["none"]


@pytest.mark.asyncio
async def test_chapter_list_by_state(session, project_id) -> None:
    repo = ChapterRepo(session)
    await repo.bulk_insert(
        project_id,
        [
            {"index": 1, "source_text": "a", "state": "raw"},
            {"index": 2, "source_text": "b", "state": "raw"},
            {"index": 3, "source_text": "c", "state": "converted"},
        ],
    )
    await session.commit()
    raws = await repo.list_by_state(project_id, "raw")
    assert [c.index for c in raws] == [1, 2]


# --------------------------------------------------------------------------- #
# TermRepo                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_term_search_by_zh_and_vn(session, project_id) -> None:
    repo = TermRepo(session)
    await repo.create(
        project_id=project_id, category="character", locked_zh="李青", locked_vn="Lý Thanh"
    )
    await repo.create(project_id=None, category="realm", locked_zh="金丹", locked_vn="Kim Đan")
    await session.commit()

    by_zh = await repo.search_by_zh("李青", project_id=project_id, exact=True)
    assert len(by_zh) == 1
    assert by_zh[0].locked_vn == "Lý Thanh"

    fuzzy = await repo.search_by_vn("Đan", exact=False)
    assert any(t.locked_zh == "金丹" for t in fuzzy)


@pytest.mark.asyncio
async def test_term_search_scope_includes_globals(session, project_id) -> None:
    repo = TermRepo(session)
    await repo.create(project_id=None, category="realm", locked_zh="金丹", locked_vn="Kim Đan")
    await session.commit()
    # Searching with a project_id should still find globals.
    hits = await repo.search_by_zh("金丹", project_id=project_id, exact=True)
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_term_find_conflicts(session, project_id) -> None:
    repo = TermRepo(session)
    await repo.create(project_id=project_id, locked_zh="李青", locked_vn="Lý Thanh")
    await repo.create(project_id=project_id, locked_zh="李青", locked_vn="Li Qing")
    await repo.create(project_id=project_id, locked_zh="金丹", locked_vn="Kim Đan")
    await session.commit()

    conflicts = await repo.find_conflicts(project_id=project_id)
    assert len(conflicts) == 1
    zh, group = conflicts[0]
    assert zh == "李青"
    assert {t.locked_vn for t in group} == {"Lý Thanh", "Li Qing"}


@pytest.mark.asyncio
async def test_term_insert_pending_default_pending_status(session, project_id) -> None:
    repo = TermRepo(session)
    n = await repo.insert_pending(
        [("李青", "Lý Thanh", "character", 0.9, "main char")],
        project_id=project_id,
    )
    await session.commit()
    assert n == 1
    rows = await repo.list_pending(project_id)
    assert len(rows) == 1
    assert rows[0].status == "pending"


@pytest.mark.asyncio
async def test_term_insert_pending_auto_accept(session, project_id) -> None:
    repo = TermRepo(session)
    n = await repo.insert_pending(
        [("张老", "Trương Lão", "character", 1.0, "")],
        project_id=project_id,
        status="accepted",
    )
    await session.commit()
    assert n == 1
    assert await repo.list_pending(project_id) == []
    accepted = await repo.list_for_project(project_id, status="accepted")
    assert len(accepted) == 1
    assert accepted[0].source == "scout_extracted"


@pytest.mark.asyncio
async def test_term_insert_pending_skips_existing_zh(session, project_id) -> None:
    repo = TermRepo(session)
    await repo.create(
        project_id=project_id, locked_zh="李青", locked_vn="Lý Thanh", category="character"
    )
    await session.commit()
    n = await repo.insert_pending(
        [("李青", "Li Qing", "character", 0.5, ""), ("张老", "Trương Lão", "character", 0.9, "")],
        project_id=project_id,
    )
    await session.commit()
    assert n == 1
    pending = await repo.list_pending(project_id)
    assert {t.locked_zh for t in pending} == {"张老"}


@pytest.mark.asyncio
async def test_term_accept_pending_flips_status(session, project_id) -> None:
    repo = TermRepo(session)
    await repo.insert_pending([("李青", "Lý Thanh", "character", 0.9, "")], project_id=project_id)
    await session.commit()
    pending = await repo.list_pending(project_id)
    accepted = await repo.accept_pending(pending[0].id)
    await session.commit()
    assert accepted.status == "accepted"
    assert await repo.list_pending(project_id) == []


@pytest.mark.asyncio
async def test_term_reject_pending_deletes(session, project_id) -> None:
    repo = TermRepo(session)
    await repo.insert_pending([("李青", "Lý Thanh", "character", 0.9, "")], project_id=project_id)
    await session.commit()
    pending = await repo.list_pending(project_id)
    ok = await repo.reject_pending(pending[0].id)
    await session.commit()
    assert ok is True
    assert await repo.list_pending(project_id) == []


@pytest.mark.asyncio
async def test_term_bulk_insert_from_qt_dict(session, project_id) -> None:
    repo = TermRepo(session)
    entries = [
        ("金丹", "Kim Đan"),
        ("元婴", "Nguyên Anh"),
        ("", "skip-empty-key"),  # filtered
        ("化神", ""),  # filtered
    ]
    n = await repo.bulk_insert_from_qt_dict(
        entries, project_id=project_id, category="realm", source="vietphrase"
    )
    await session.commit()
    assert n == 2
    rows = await repo.list_for_project(project_id, category="realm")
    assert {r.locked_zh for r in rows} == {"金丹", "元婴"}
    for r in rows:
        assert r.source == "vietphrase"


# --------------------------------------------------------------------------- #
# JobRepo                                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_job_queue_lifecycle(session, project_id) -> None:
    repo = JobRepo(session)
    job = await repo.create(project_id=project_id, job_type="translate", payload={"chapter": 1})
    await session.commit()

    pending = await repo.get_pending(project_id)
    assert [j.id for j in pending] == [job.id]

    running = await repo.mark_running(job.id)
    assert running.status == "running"
    assert running.started_at is not None

    progressed = await repo.update_progress(job.id, 0.5)
    assert progressed.progress == 0.5

    done = await repo.mark_complete(job.id)
    assert done.status == "completed"
    assert done.progress == 1.0
    assert done.completed_at is not None
    assert await repo.get_pending(project_id) == []


@pytest.mark.asyncio
async def test_job_mark_running_rejects_non_pending(session, project_id) -> None:
    repo = JobRepo(session)
    job = await repo.create(project_id=project_id, job_type="translate")
    await repo.mark_running(job.id)
    with pytest.raises(ValueError):
        await repo.mark_running(job.id)


@pytest.mark.asyncio
async def test_job_progress_out_of_range(session, project_id) -> None:
    repo = JobRepo(session)
    job = await repo.create(project_id=project_id, job_type="translate")
    with pytest.raises(ValueError):
        await repo.update_progress(job.id, 1.5)
    with pytest.raises(ValueError):
        await repo.update_progress(job.id, -0.1)


@pytest.mark.asyncio
async def test_job_mark_failed_records_error(session, project_id) -> None:
    repo = JobRepo(session)
    job = await repo.create(project_id=project_id, job_type="translate")
    failed = await repo.mark_failed(job.id, error="Gemini quota exceeded")
    assert failed.status == "failed"
    assert failed.error == "Gemini quota exceeded"
    assert failed.completed_at is not None


@pytest.mark.asyncio
async def test_job_cancel_is_idempotent(session, project_id) -> None:
    repo = JobRepo(session)
    job = await repo.create(project_id=project_id, job_type="translate")
    first = await repo.cancel(job.id)
    second = await repo.cancel(job.id)
    assert first.status == "cancelled"
    assert second.status == "cancelled"


@pytest.mark.asyncio
async def test_job_get_pending_filter_by_type(session, project_id) -> None:
    repo = JobRepo(session)
    await repo.create(project_id=project_id, job_type="translate")
    await repo.create(project_id=project_id, job_type="audit")
    await session.commit()
    translates = await repo.get_pending(project_id, job_type="translate")
    assert all(j.type == "translate" for j in translates)
    assert len(translates) == 1
