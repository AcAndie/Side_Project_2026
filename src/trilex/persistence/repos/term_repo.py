"""Term (glossary) repository — search, conflicts, bulk import from QT dict."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trilex.persistence.models import Term

# A "conflict" is two project-scoped (or one project + one global) terms that
# share the same source text but disagree on the target. Useful for surfacing
# import collisions before they corrupt the glossary.


class TermRepo:
    """CRUD on `Term`. Supports per-project and global (`project_id=None`) terms."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: str | None,
        category: str = "phrase",
        locked_zh: str | None = None,
        locked_vn: str | None = None,
        locked_en: str | None = None,
        aliases: list[str] | None = None,
        source: str = "manual",
        confidence: float = 1.0,
        first_seen_chapter: int | None = None,
        notes: str = "",
    ) -> Term:
        term = Term(
            project_id=project_id,
            category=category,
            locked_zh=locked_zh,
            locked_vn=locked_vn,
            locked_en=locked_en,
            aliases=aliases or [],
            source=source,
            confidence=confidence,
            first_seen_chapter=first_seen_chapter,
            notes=notes,
        )
        self.session.add(term)
        await self.session.flush()
        return term

    async def get(self, term_id: str) -> Term | None:
        return await self.session.get(Term, term_id)

    async def search_by_zh(
        self, query: str, *, project_id: str | None = None, exact: bool = False
    ) -> Sequence[Term]:
        return await self._search(Term.locked_zh, query, project_id, exact)

    async def search_by_vn(
        self, query: str, *, project_id: str | None = None, exact: bool = False
    ) -> Sequence[Term]:
        return await self._search(Term.locked_vn, query, project_id, exact)

    async def search_by_en(
        self, query: str, *, project_id: str | None = None, exact: bool = False
    ) -> Sequence[Term]:
        return await self._search(Term.locked_en, query, project_id, exact)

    async def _search(
        self,
        column: Any,
        query: str,
        project_id: str | None,
        exact: bool,
    ) -> Sequence[Term]:
        stmt = select(Term)
        stmt = stmt.where(column == query) if exact else stmt.where(column.like(f"%{query}%"))
        if project_id is not None:
            # Include global (project_id IS NULL) terms alongside per-project hits.
            stmt = stmt.where(or_(Term.project_id == project_id, Term.project_id.is_(None)))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_conflicts(self, project_id: str | None = None) -> list[tuple[str, list[Term]]]:
        """Return list of `(source_text, [terms])` where multiple terms in the
        same scope share the same ZH source but differ on VN target."""
        stmt = select(Term).where(Term.locked_zh.isnot(None))
        if project_id is not None:
            stmt = stmt.where(or_(Term.project_id == project_id, Term.project_id.is_(None)))
        result = await self.session.execute(stmt)
        all_terms = result.scalars().all()

        groups: dict[str, list[Term]] = {}
        for t in all_terms:
            if t.locked_zh:
                groups.setdefault(t.locked_zh, []).append(t)

        conflicts: list[tuple[str, list[Term]]] = []
        for zh, terms in groups.items():
            distinct_vn = {t.locked_vn for t in terms if t.locked_vn}
            if len(distinct_vn) > 1:
                conflicts.append((zh, terms))
        return conflicts

    async def bulk_insert_from_qt_dict(
        self,
        entries: Iterable[tuple[str, str]],
        *,
        project_id: str | None = None,
        category: str = "phrase",
        source: str = "vietphrase",
        confidence: float = 1.0,
    ) -> int:
        """Insert `(zh, vn)` pairs as `Term` rows. Returns inserted count."""
        rows = [
            Term(
                project_id=project_id,
                category=category,
                locked_zh=zh,
                locked_vn=vn,
                source=source,
                confidence=confidence,
                aliases=[],
            )
            for zh, vn in entries
            if zh and vn
        ]
        if not rows:
            return 0
        self.session.add_all(rows)
        await self.session.flush()
        return len(rows)

    async def list_for_project(
        self,
        project_id: str,
        *,
        category: str | None = None,
        status: str | None = None,
    ) -> Sequence[Term]:
        stmt = select(Term).where(Term.project_id == project_id)
        if category is not None:
            stmt = stmt.where(Term.category == category)
        if status is not None:
            stmt = stmt.where(Term.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def insert_pending(
        self,
        proposals: Iterable[tuple[str, str, str, float, str]],
        *,
        project_id: str,
        source: str = "scout_extracted",
        status: str = "pending",
    ) -> int:
        """Insert NewTerm proposals as Term rows. Items are
        `(zh, vn, category, confidence, notes)`. `status` controls whether the
        rows land in pending review (`'pending'`) or are auto-locked
        (`'accepted'`). Returns inserted count.
        Skips entries whose `zh` is already locked or pending in this project."""
        proposals = list(proposals)
        if not proposals:
            return 0

        existing_zh = {t.locked_zh for t in await self.list_for_project(project_id) if t.locked_zh}

        rows = [
            Term(
                project_id=project_id,
                category=category,
                locked_zh=zh,
                locked_vn=vn,
                source=source,
                confidence=confidence,
                notes=notes,
                status=status,
                aliases=[],
            )
            for (zh, vn, category, confidence, notes) in proposals
            if zh and vn and zh not in existing_zh
        ]
        if not rows:
            return 0
        self.session.add_all(rows)
        await self.session.flush()
        return len(rows)

    async def list_pending(self, project_id: str) -> Sequence[Term]:
        return await self.list_for_project(project_id, status="pending")

    async def accept_pending(self, term_id: str) -> Term | None:
        term = await self.get(term_id)
        if term is None or term.status != "pending":
            return term
        term.status = "accepted"
        await self.session.flush()
        return term

    async def reject_pending(self, term_id: str) -> bool:
        term = await self.get(term_id)
        if term is None or term.status != "pending":
            return False
        await self.session.delete(term)
        await self.session.flush()
        return True

    async def delete(self, term_id: str) -> bool:
        term = await self.get(term_id)
        if term is None:
            return False
        await self.session.delete(term)
        await self.session.flush()
        return True
