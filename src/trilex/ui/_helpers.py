"""Streamlit-side helpers: async bridge, sidebar project selector, DB session.

Streamlit pages run synchronously per rerun, so we wrap async calls with a
fresh `asyncio.run` each time. Per CLAUDE.md §8 ("async by default for I/O"),
the repos and pipeline are async; this thin shim keeps that invariant intact
without forcing the UI to grow its own event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, TypeVar

import streamlit as st
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from trilex.config import get_settings
from trilex.persistence.db import (
    DEFAULT_DB_PATH,
    make_session_maker,
    make_sync_engine,
)
from trilex.persistence.models import Project
from trilex.persistence.repos import ProjectRepo
from trilex.providers.gemini import GeminiProvider

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine to completion from sync Streamlit code."""
    return asyncio.run(coro)


@st.cache_resource
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Async session maker — cached across reruns so the engine isn't rebuilt."""
    from trilex.persistence.db import make_async_engine

    engine: AsyncEngine = make_async_engine(DEFAULT_DB_PATH)
    return make_session_maker(engine)


@st.cache_resource
def get_sync_session_factory() -> sessionmaker[Session]:
    """Sync SQLAlchemy session factory for simple read paths in the UI."""
    engine = make_sync_engine(DEFAULT_DB_PATH)
    return sessionmaker(engine, expire_on_commit=False, class_=Session)


@contextmanager
def sync_session() -> Iterator[Session]:
    factory = get_sync_session_factory()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


async def _list_projects_async() -> Sequence[Project]:
    maker = get_session_maker()
    async with maker() as s:
        repo = ProjectRepo(s)
        return await repo.list()


def list_projects() -> Sequence[Project]:
    return run_async(_list_projects_async())


def db_ready() -> bool:
    return DEFAULT_DB_PATH.exists()


def sidebar_project_selector() -> Project | None:
    """Render the active-project selector in the sidebar. Returns the chosen
    project (or None if the DB has no projects yet)."""
    st.sidebar.header("🌳 TriLex")
    if not db_ready():
        st.sidebar.warning(
            f"DB chưa init. Chạy `trilex db init` (file mong đợi: {DEFAULT_DB_PATH})."
        )
        return None

    try:
        projects = list_projects()
    except Exception as e:  # noqa: BLE001
        st.sidebar.error(f"Lỗi đọc DB: {e}")
        return None

    if not projects:
        st.sidebar.info("Chưa có project. Mở **Library** để tạo.")
        return None

    options = {f"{p.name} ({p.slug})": p for p in projects}
    current_id = st.session_state.get("active_project_id")
    current_index = 0
    if current_id is not None:
        for i, p in enumerate(projects):
            if p.id == current_id:
                current_index = i
                break
    label = st.sidebar.selectbox(
        "Project đang làm",
        list(options.keys()),
        index=current_index,
        key="active_project_label",
    )
    chosen = options[label]
    st.session_state["active_project_id"] = chosen.id
    return chosen


def gemini_provider_or_warn() -> GeminiProvider | None:
    """Return a configured `GeminiProvider`, or `None` after rendering a warning."""
    try:
        get_settings()
    except Exception as e:  # noqa: BLE001
        st.error(f"Config invalid — sửa `.env` rồi reload: {e}")
        return None
    try:
        return GeminiProvider.from_settings()
    except Exception as e:  # noqa: BLE001
        st.error(f"Không khởi tạo được Gemini: {e}")
        return None
