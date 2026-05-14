"""Chapter repository — CRUD + bulk insert + range queries + state counts."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trilex.persistence.models import Chapter


class ChapterRepo:
    """CRUD on `Chapter` scoped by `project_id`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: str,
        index: int,
        source_text: str,
        title: str | None = None,
        state: str = "raw",
    ) -> Chapter:
        chapter = Chapter(
            project_id=project_id,
            index=index,
            title=title,
            source_text=source_text,
            state=state,
        )
        self.session.add(chapter)
        await self.session.flush()
        return chapter

    async def bulk_insert(
        self,
        project_id: str,
        chapters: Iterable[dict[str, Any]],
    ) -> int:
        """Insert many chapters in one flush. `chapters` items need at least
        `index` and `source_text`. Returns inserted count."""
        rows = [
            Chapter(
                project_id=project_id,
                index=c["index"],
                source_text=c["source_text"],
                title=c.get("title"),
                state=c.get("state", "raw"),
            )
            for c in chapters
        ]
        if not rows:
            return 0
        self.session.add_all(rows)
        await self.session.flush()
        return len(rows)

    async def get(self, chapter_id: str) -> Chapter | None:
        return await self.session.get(Chapter, chapter_id)

    async def get_by_index(self, project_id: str, index: int) -> Chapter | None:
        result = await self.session.execute(
            select(Chapter).where(Chapter.project_id == project_id, Chapter.index == index)
        )
        return result.scalar_one_or_none()

    async def get_range(
        self,
        project_id: str,
        *,
        start: int,
        end: int,
    ) -> Sequence[Chapter]:
        """Return chapters with `start <= index <= end`, sorted by index."""
        if end < start:
            return []
        result = await self.session.execute(
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.index >= start,
                Chapter.index <= end,
            )
            .order_by(Chapter.index.asc())
        )
        return result.scalars().all()

    async def list_by_state(
        self,
        project_id: str,
        state: str,
        *,
        limit: int | None = None,
    ) -> Sequence[Chapter]:
        stmt = (
            select(Chapter)
            .where(Chapter.project_id == project_id, Chapter.state == state)
            .order_by(Chapter.index.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_state(self, project_id: str) -> dict[str, int]:
        """Return `{state: count}` for all chapters of `project_id`."""
        result = await self.session.execute(
            select(Chapter.state, func.count())
            .where(Chapter.project_id == project_id)
            .group_by(Chapter.state)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def update_translation(
        self,
        chapter_id: str,
        *,
        convert_text: str | None = None,
        polished_text: str | None = None,
        state: str | None = None,
        quality_score: float | None = None,
        tokens_used: int | None = None,
        provider_used: str | None = None,
        warnings: list[str] | None = None,
        mark_translated: bool = False,
    ) -> Chapter | None:
        chapter = await self.get(chapter_id)
        if chapter is None:
            return None
        if convert_text is not None:
            chapter.convert_text = convert_text
        if polished_text is not None:
            chapter.polished_text = polished_text
        if state is not None:
            chapter.state = state
        if quality_score is not None:
            chapter.quality_score = quality_score
        if tokens_used is not None:
            chapter.tokens_used = tokens_used
        if provider_used is not None:
            chapter.provider_used = provider_used
        if warnings is not None:
            chapter.warnings = list(warnings)
        if mark_translated:
            chapter.translated_at = datetime.now(UTC)
        await self.session.flush()
        return chapter

    async def delete(self, chapter_id: str) -> bool:
        chapter = await self.get(chapter_id)
        if chapter is None:
            return False
        await self.session.delete(chapter)
        await self.session.flush()
        return True
