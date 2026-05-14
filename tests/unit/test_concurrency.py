"""Concurrency tests: parallel pipeline runs + SQLite write contention.

These pin the assumption that the orchestrator is stateless w.r.t. its inputs
(no shared mutable state between calls) and that the persistence layer can
absorb modest write fan-out without corrupting data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline.orchestrator import translate_chapter
from trilex.core.style_pack import get_style_pack
from trilex.persistence.db import create_all, make_async_engine, make_session_maker
from trilex.persistence.repos import ChapterRepo, ProjectRepo
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider, ProviderResponse
from trilex.qt_dict.applier import QTApplier


@dataclass
class _Slot:
    idx: int


class _SlowProvider(LLMProvider):
    """Returns a unique reply per call and sleeps briefly to force interleaving."""

    name = "slow"

    def __init__(self, delay_s: float = 0.05) -> None:
        self.delay_s = delay_s
        self.call_order: list[_Slot] = []
        self._counter = 0
        self._lock = asyncio.Lock()

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        async with self._lock:
            self._counter += 1
            n = self._counter
        self.call_order.append(_Slot(idx=n))
        await asyncio.sleep(self.delay_s)
        return ProviderResponse(
            text=f"output-{n}",
            tokens_used=10,
            model="slow-1",
            latency_ms=self.delay_s * 1000.0,
            finish_reason="stop",
        )


@pytest.fixture
def real_applier() -> QTApplier:
    return QTApplier(Path("data/dictionaries"), cache_dir=Path("data/cache"))


# --------------------------------------------------------------------------- #
# 5 parallel translate_chapter calls                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_five_parallel_translate_chapters_no_cross_contamination(
    real_applier: QTApplier,
) -> None:
    """5 chapters in flight at once: each result must reflect its own input.

    Catches: shared-state bugs in the applier (mutable instance attrs),
    style pack singletons, etc."""
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    pack = get_style_pack("tu_tien", "vn")
    provider = _SlowProvider(delay_s=0.05)

    sources = [f"李青走进青云宗。第{i}章" for i in range(5)]
    results = await asyncio.gather(
        *(
            translate_chapter(
                src,
                cfg,
                mode="polish",
                provider=provider,
                applier=real_applier,
                style_pack=pack,
            )
            for src in sources
        )
    )

    # All five completed.
    assert len(results) == 5
    assert all(r.state == "postprocessed" for r in results)

    # Each output is unique — proves replies weren't aliased.
    outputs = {r.final_text for r in results}
    assert len(outputs) == 5

    # Each result preserves its own source.
    for src, r in zip(sources, results, strict=True):
        assert r.source_text == src

    # Provider saw exactly 5 calls.
    assert len(provider.call_order) == 5


@pytest.mark.asyncio
async def test_parallel_convert_mode_shares_applier_safely(
    real_applier: QTApplier,
) -> None:
    """Convert mode bypasses LLM. 5 parallel calls sharing one applier must
    produce identical output for identical input and not corrupt the tier cache."""
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    text = "李青走进青云宗，向张老行礼。"

    results = await asyncio.gather(
        *(translate_chapter(text, cfg, mode="convert", applier=real_applier) for _ in range(5))
    )
    assert len({r.final_text for r in results}) == 1


# --------------------------------------------------------------------------- #
# SQLite write contention — 5 parallel inserts                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_parallel_chapter_inserts_no_loss(tmp_path: Path) -> None:
    """5 parallel sessions inserting different chapters into the same project.

    Each session must see its own write committed (no lost rows, no IntegrityError
    races on the (project_id, index) unique constraint when keys are disjoint)."""
    engine = make_async_engine(tmp_path / "concurrency.db")
    await create_all(engine)
    maker = make_session_maker(engine)

    # Bootstrap project.
    async with maker() as s:
        proj_repo = ProjectRepo(s)
        project = await proj_repo.create(
            name="Concurrency Test",
            slug="concurrency-test",
            source_lang="zh",
            target_lang="vn",
        )
        await s.commit()
        project_id = project.id

    async def insert_one(idx: int) -> str:
        async with maker() as s:
            repo = ChapterRepo(s)
            ch = await repo.create(
                project_id=project_id,
                index=idx,
                source_text=f"chapter {idx} body",
                title=f"Chapter {idx}",
            )
            await s.commit()
            return ch.id

    ids = await asyncio.gather(*(insert_one(i) for i in range(5)))
    assert len(set(ids)) == 5  # no duplicate IDs

    # Verify all 5 chapters readable.
    async with maker() as s:
        repo = ChapterRepo(s)
        rows = await repo.get_range(project_id, start=0, end=10)
        assert len(rows) == 5
        assert sorted(c.index for c in rows) == [0, 1, 2, 3, 4]

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_unique_constraint_blocks_dup_index(tmp_path: Path) -> None:
    """Two writers attempting the same (project_id, index) must not both succeed.

    Pins the schema-level guarantee against the (project_id, index) unique
    constraint. Catches: missing UniqueConstraint or accidental REPLACE."""
    from sqlalchemy.exc import IntegrityError

    engine = make_async_engine(tmp_path / "uniq.db")
    await create_all(engine)
    maker = make_session_maker(engine)

    async with maker() as s:
        proj_repo = ProjectRepo(s)
        proj = await proj_repo.create(name="Uniq", slug="uniq", source_lang="zh", target_lang="vn")
        await s.commit()
        pid = proj.id

    async with maker() as s:
        repo = ChapterRepo(s)
        await repo.create(project_id=pid, index=1, source_text="a")
        await s.commit()

    # Second insert with same index must raise.
    with pytest.raises(IntegrityError):
        async with maker() as s:
            repo = ChapterRepo(s)
            await repo.create(project_id=pid, index=1, source_text="b")
            await s.commit()

    await engine.dispose()
