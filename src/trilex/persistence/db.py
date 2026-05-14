"""Database engine + session factories for the persistence layer.

Two engines:
  - **Async** (`aiosqlite`) — used by repos and the application runtime. Async
    sessions are the project default per CLAUDE.md §8 ("async by default for I/O").
  - **Sync** — used only by Alembic migrations. Alembic's `env.py` reaches for
    this directly via the `alembic.ini` URL.

Engine instances are cached per `(path)` so production code shares one engine,
but tests can build isolated engines against a tmp file.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Final

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trilex.persistence.models import Base

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH: Final[Path] = Path("data/trilex.db")


def async_dsn(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def sync_dsn(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def make_async_engine(path: Path) -> AsyncEngine:
    """Build (do NOT cache) an async engine for `path`. Use in tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(async_dsn(path), future=True)


def make_sync_engine(path: Path) -> Engine:
    """Build a sync engine — only meant for Alembic migrations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(sync_dsn(path), future=True)


def make_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def _cached_default_engine() -> AsyncEngine:
    return make_async_engine(DEFAULT_DB_PATH)


def default_engine() -> AsyncEngine:
    """The shared application engine bound to `DEFAULT_DB_PATH`."""
    return _cached_default_engine()


@lru_cache(maxsize=1)
def _cached_default_session_maker() -> async_sessionmaker[AsyncSession]:
    return make_session_maker(default_engine())


def default_session_maker() -> async_sessionmaker[AsyncSession]:
    return _cached_default_session_maker()


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an `AsyncSession` bound to the default engine, with commit/rollback."""
    maker = default_session_maker()
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all(engine: AsyncEngine) -> None:
    """Create every table defined on `Base.metadata` against `engine`. Tests / first-run."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def reset_default_engine() -> None:
    """Dispose the cached default engine. Call after changing DEFAULT_DB_PATH in tests."""
    engine = _cached_default_engine() if _cached_default_engine.cache_info().currsize else None
    if engine is not None:
        await engine.dispose()
    _cached_default_engine.cache_clear()
    _cached_default_session_maker.cache_clear()
