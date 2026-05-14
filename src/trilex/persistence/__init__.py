"""Persistence layer — SQLAlchemy 2.0 models + async session factories."""

from trilex.persistence.db import (
    DEFAULT_DB_PATH,
    async_dsn,
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
from trilex.persistence.models import Base, Chapter, Job, Project, Term

__all__ = [
    "Base",
    "Chapter",
    "DEFAULT_DB_PATH",
    "Job",
    "Project",
    "Term",
    "async_dsn",
    "create_all",
    "default_engine",
    "default_session_maker",
    "drop_all",
    "get_session",
    "make_async_engine",
    "make_session_maker",
    "make_sync_engine",
    "reset_default_engine",
    "sync_dsn",
]
