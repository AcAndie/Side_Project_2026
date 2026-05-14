"""SQLAlchemy 2.0 declarative schema.

Single-user, single-DB. UUIDs stored as 36-char strings (SQLite has no native
UUID). `created_at` / `updated_at` are UTC datetimes set in Python so the DB
backend doesn't have to be timezone-aware.

Cascade rules: deleting a Project cascades to its Chapters, Terms, and Jobs.
Global terms (Term.project_id is NULL) survive project deletion.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base. Subclass to map tables."""


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    source_lang: Mapped[str] = mapped_column(String(8), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(8), nullable=False)
    genre: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    vault_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    style_pack: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    terms: Mapped[list[Term]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    jobs: Mapped[list[Job]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Project(id={self.id!r}, slug={self.slug!r})"


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("project_id", "index", name="uq_chapter_idx"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    convert_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    polished_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="raw")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    project: Mapped[Project] = relationship(back_populates="chapters")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Chapter(project={self.project_id!r}, index={self.index}, state={self.state!r})"


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="phrase")
    locked_zh: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    locked_vn: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    locked_en: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="accepted", index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    first_seen_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    locked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)

    project: Mapped[Project | None] = relationship(back_populates="terms")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Term(id={self.id!r}, zh={self.locked_zh!r}, "
            f"vn={self.locked_vn!r}, project={self.project_id!r})"
        )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_completed_index: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship(back_populates="jobs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Job(id={self.id!r}, type={self.type!r}, status={self.status!r})"
