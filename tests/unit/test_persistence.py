"""Tests for the persistence layer: engine wiring, schema, FK cascade.

Each test gets a fresh on-disk SQLite under `tmp_path` so they are isolated.
We exercise the *async* engine since that's the runtime path; Alembic is
covered separately via a CLI smoke test in test_orchestrator-style runs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trilex.persistence.db import (
    async_dsn,
    create_all,
    make_async_engine,
    make_session_maker,
    sync_dsn,
)
from trilex.persistence.models import Chapter, Job, Project, Term


@pytest.fixture
async def engine(tmp_path: Path):
    eng = make_async_engine(tmp_path / "test.db")
    await create_all(eng)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    maker = make_session_maker(engine)
    async with maker() as s:
        yield s


# --------------------------------------------------------------------------- #
# DSN helpers                                                                 #
# --------------------------------------------------------------------------- #


def test_async_dsn_uses_aiosqlite(tmp_path: Path) -> None:
    assert async_dsn(tmp_path / "x.db").startswith("sqlite+aiosqlite:///")


def test_sync_dsn_is_plain_sqlite(tmp_path: Path) -> None:
    assert sync_dsn(tmp_path / "x.db").startswith("sqlite:///")
    assert "aiosqlite" not in sync_dsn(tmp_path / "x.db")


# --------------------------------------------------------------------------- #
# Schema smoke                                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_all_makes_tables(engine) -> None:
    async with engine.connect() as conn:
        rows = await conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = [r[0] for r in rows.fetchall()]
    # alembic_version may or may not be present (only when alembic ran).
    expected = {"projects", "chapters", "terms", "jobs"}
    assert expected.issubset(set(names))


# --------------------------------------------------------------------------- #
# Project CRUD                                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_insert_and_query_project(session) -> None:
    p = Project(
        name="Đại Đạo Tu Tiên",
        slug="dai-dao-tu-tien",
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
    )
    session.add(p)
    await session.commit()

    result = await session.execute(select(Project).where(Project.slug == "dai-dao-tu-tien"))
    fetched = result.scalar_one()
    assert fetched.name == "Đại Đạo Tu Tiên"
    assert fetched.genre == "tu_tien"
    assert isinstance(fetched.created_at, datetime)


@pytest.mark.asyncio
async def test_project_slug_unique(session) -> None:
    session.add(Project(name="A", slug="dup", source_lang="zh", target_lang="vn"))
    await session.commit()
    session.add(Project(name="B", slug="dup", source_lang="zh", target_lang="vn"))
    with pytest.raises(IntegrityError):
        await session.commit()


# --------------------------------------------------------------------------- #
# Chapter                                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_chapter_state_lifecycle(session) -> None:
    p = Project(name="X", slug="x", source_lang="zh", target_lang="vn")
    session.add(p)
    await session.flush()
    ch = Chapter(
        project_id=p.id,
        index=1,
        source_text="李青走进青云宗。",
        state="raw",
    )
    session.add(ch)
    await session.commit()

    ch.convert_text = "Lý Thanh đi vào Thanh Vân Tông."
    ch.state = "converted"
    await session.commit()

    fetched = (await session.execute(select(Chapter).where(Chapter.id == ch.id))).scalar_one()
    assert fetched.state == "converted"
    assert "Lý Thanh" in (fetched.convert_text or "")


@pytest.mark.asyncio
async def test_chapter_index_unique_per_project(session) -> None:
    p = Project(name="X", slug="x", source_lang="zh", target_lang="vn")
    session.add(p)
    await session.flush()
    session.add(Chapter(project_id=p.id, index=1, source_text="a"))
    session.add(Chapter(project_id=p.id, index=1, source_text="b"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_chapter_index_can_repeat_across_projects(session) -> None:
    p1 = Project(name="A", slug="a", source_lang="zh", target_lang="vn")
    p2 = Project(name="B", slug="b", source_lang="zh", target_lang="vn")
    session.add_all([p1, p2])
    await session.flush()
    session.add(Chapter(project_id=p1.id, index=1, source_text="a"))
    session.add(Chapter(project_id=p2.id, index=1, source_text="b"))
    await session.commit()  # no exception


# --------------------------------------------------------------------------- #
# Term                                                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_term_with_project_and_global_term(session) -> None:
    p = Project(name="X", slug="x", source_lang="zh", target_lang="vn")
    session.add(p)
    await session.flush()
    session.add(
        Term(
            project_id=p.id,
            category="character",
            locked_zh="李青",
            locked_vn="Lý Thanh",
            aliases=["小李"],
        )
    )
    session.add(
        Term(
            project_id=None,
            category="realm",
            locked_zh="金丹",
            locked_vn="Kim Đan",
            locked_en="Golden Core",
        )
    )
    await session.commit()

    rows = (await session.execute(select(Term).where(Term.locked_zh == "李青"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].aliases == ["小李"]

    globals_only = (
        (await session.execute(select(Term).where(Term.project_id.is_(None)))).scalars().all()
    )
    assert len(globals_only) == 1
    assert globals_only[0].locked_en == "Golden Core"


# --------------------------------------------------------------------------- #
# Job                                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_job_status_transition(session) -> None:
    p = Project(name="X", slug="x", source_lang="zh", target_lang="vn")
    session.add(p)
    await session.flush()
    job = Job(project_id=p.id, type="translate", status="pending")
    session.add(job)
    await session.commit()

    job.status = "running"
    job.started_at = datetime.now(UTC)
    job.progress = 0.5
    await session.commit()

    job.status = "completed"
    job.progress = 1.0
    job.completed_at = datetime.now(UTC)
    await session.commit()

    fetched = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
    assert fetched.status == "completed"
    assert fetched.progress == 1.0


# --------------------------------------------------------------------------- #
# Cascade delete                                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_deleting_project_cascades(session) -> None:
    p = Project(name="X", slug="x", source_lang="zh", target_lang="vn")
    session.add(p)
    await session.flush()
    session.add(Chapter(project_id=p.id, index=1, source_text="a"))
    session.add(Term(project_id=p.id, category="character", locked_zh="A"))
    session.add(Job(project_id=p.id, type="translate"))
    await session.commit()

    # Re-fetch the project so its relationships are populated, then delete via ORM
    # cascade so SQLAlchemy emits the dependent DELETEs (SQLite FK cascade is off
    # by default, and async sessions don't expire across the boundary).
    fetched = (await session.execute(select(Project).where(Project.id == p.id))).scalar_one()
    await session.refresh(fetched, attribute_names=["chapters", "terms", "jobs"])
    await session.delete(fetched)
    await session.commit()

    chapters = (await session.execute(select(Chapter))).scalars().all()
    terms = (await session.execute(select(Term))).scalars().all()
    jobs = (await session.execute(select(Job))).scalars().all()
    assert chapters == []
    assert terms == []
    assert jobs == []
