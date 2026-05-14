"""Project repository — CRUD over the `projects` table.

Each method takes the injected `AsyncSession` from `__init__`. The repo
flushes (so the caller sees IDs / timestamps) but does NOT commit; commit
strategy belongs to the orchestrator / use case that owns the unit of work.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trilex.persistence.models import Project


class ProjectRepo:
    """CRUD on `Project`. Construct with an `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        source_lang: str,
        target_lang: str,
        genre: str = "other",
        vault_path: str | None = None,
        style_pack: str | None = None,
        provider_config: dict[str, Any] | None = None,
    ) -> Project:
        project = Project(
            name=name,
            slug=slug,
            source_lang=source_lang,
            target_lang=target_lang,
            genre=genre,
            vault_path=vault_path,
            style_pack=style_pack,
            provider_config=provider_config or {},
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def get(self, project_id: str) -> Project | None:
        return await self.session.get(Project, project_id)

    async def get_by_slug(self, slug: str) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.slug == slug))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        genre: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Project]:
        stmt = select(Project).order_by(Project.created_at.desc())
        if genre is not None:
            stmt = stmt.where(Project.genre == genre)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Project))
        return int(result.scalar_one())

    async def update(self, project_id: str, **fields: Any) -> Project | None:
        project = await self.get(project_id)
        if project is None:
            return None
        for key, value in fields.items():
            if not hasattr(project, key):
                raise AttributeError(f"Project has no attribute {key!r}")
            setattr(project, key, value)
        await self.session.flush()
        return project

    async def delete(self, project_id: str) -> bool:
        project = await self.get(project_id)
        if project is None:
            return False
        # Refresh relationships so ORM cascade emits child DELETEs (SQLite FK
        # cascade is off by default).
        await self.session.refresh(project, attribute_names=["chapters", "terms", "jobs"])
        await self.session.delete(project)
        await self.session.flush()
        return True
