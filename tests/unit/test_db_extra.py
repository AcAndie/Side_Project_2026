"""Extra coverage for `persistence/db.py` — engine caching, session lifecycle,
drop_all, reset_default_engine.

Existing test_persistence.py exercises schemas + repos; here we focus on the
engine/factory helpers that were uncovered (lines 52–53, 62, 67, 72, 76, 82–89).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from trilex.persistence import db as db_mod
from trilex.persistence.db import (
    create_all,
    default_engine,
    default_session_maker,
    drop_all,
    get_session,
    make_async_engine,
    make_session_maker,
    make_sync_engine,
    reset_default_engine,
    sync_dsn,
)
from trilex.persistence.models import Project


@pytest.fixture
def patched_default_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point DEFAULT_DB_PATH at a tmp file + clear the engine cache so the
    default_engine() helper builds against the tmp path."""
    tmp_db = tmp_path / "default.db"
    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", tmp_db)
    db_mod._cached_default_engine.cache_clear()
    db_mod._cached_default_session_maker.cache_clear()
    yield tmp_db
    db_mod._cached_default_engine.cache_clear()
    db_mod._cached_default_session_maker.cache_clear()


def test_make_sync_engine_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "x.db"
    eng = make_sync_engine(nested)
    assert nested.parent.exists()
    assert sync_dsn(nested) in str(eng.url) or eng.url.database == nested.as_posix()
    eng.dispose()


def test_make_async_engine_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "x" / "y" / "db.sqlite"
    eng = make_async_engine(nested)
    assert nested.parent.exists()
    eng.sync_engine.dispose()


@pytest.mark.asyncio
async def test_default_engine_returns_same_instance(patched_default_db: Path) -> None:
    a = default_engine()
    b = default_engine()
    assert a is b
    # Session maker is also memoised against the cached engine.
    m1 = default_session_maker()
    m2 = default_session_maker()
    assert m1 is m2
    await a.dispose()
    db_mod._cached_default_engine.cache_clear()
    db_mod._cached_default_session_maker.cache_clear()


@pytest.mark.asyncio
async def test_reset_default_engine_disposes_and_clears(patched_default_db: Path) -> None:
    default_engine()
    assert db_mod._cached_default_engine.cache_info().currsize == 1
    await reset_default_engine()
    assert db_mod._cached_default_engine.cache_info().currsize == 0
    # Second reset is a no-op (no cached engine).
    await reset_default_engine()


@pytest.mark.asyncio
async def test_reset_default_engine_noop_when_uncached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", tmp_path / "noop.db")
    db_mod._cached_default_engine.cache_clear()
    # No call to default_engine → nothing cached.
    await reset_default_engine()  # should not raise


@pytest.mark.asyncio
async def test_get_session_commits_on_success(patched_default_db: Path) -> None:
    """get_session() commit branch: write inside the context, see it after."""
    engine = default_engine()
    await create_all(engine)

    async with get_session() as s:
        s.add(
            Project(
                name="ok",
                slug="ok-slug",
                source_lang="zh",
                target_lang="vn",
            )
        )
    # New session should see committed row.
    async with get_session() as s:
        result = await s.execute(text("SELECT name FROM projects WHERE slug='ok-slug'"))
        assert result.scalar_one() == "ok"

    await engine.dispose()
    db_mod._cached_default_engine.cache_clear()


@pytest.mark.asyncio
async def test_get_session_rolls_back_on_exception(patched_default_db: Path) -> None:
    engine = default_engine()
    await create_all(engine)

    with pytest.raises(RuntimeError, match="boom"):
        async with get_session() as s:
            s.add(
                Project(
                    name="bad",
                    slug="bad-slug",
                    source_lang="zh",
                    target_lang="vn",
                )
            )
            raise RuntimeError("boom")

    async with get_session() as s:
        result = await s.execute(text("SELECT name FROM projects WHERE slug='bad-slug'"))
        assert result.first() is None

    await engine.dispose()
    db_mod._cached_default_engine.cache_clear()


@pytest.mark.asyncio
async def test_drop_all_removes_tables(tmp_path: Path) -> None:
    eng = make_async_engine(tmp_path / "drop.db")
    await create_all(eng)
    # Insert then drop — table should disappear.
    async with make_session_maker(eng)() as s:
        s.add(Project(name="x", slug="x", source_lang="zh", target_lang="vn"))
        await s.commit()
    await drop_all(eng)
    from sqlalchemy.exc import OperationalError

    with pytest.raises(OperationalError):
        async with make_session_maker(eng)() as s:
            await s.execute(text("SELECT * FROM projects"))
    await eng.dispose()
