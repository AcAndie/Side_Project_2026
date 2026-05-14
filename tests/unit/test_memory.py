"""Memory-leak smoke test: 100 chapters through the pipeline must not grow
heap allocations unboundedly.

This is a regression guard. The pipeline holds: applier (with cached
automatons), style pack, glossary. None of those should accumulate per-call
state.

Strategy: warm up (so caches stabilise), capture tracemalloc baseline,
run N more chapters, compare. Allow generous headroom because Python's
allocator + asyncio internals fluctuate; we just want to catch *unbounded*
growth, not a few KB of noise.
"""

from __future__ import annotations

import asyncio
import gc
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

import pytest

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline.orchestrator import translate_chapter
from trilex.core.style_pack import get_style_pack
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider, ProviderResponse
from trilex.qt_dict.applier import QTApplier


@dataclass
class _Slot:
    n: int


class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self) -> None:
        self.n = 0

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.n += 1
        return ProviderResponse(
            text="Lý Thanh bước vào tông môn.",
            tokens_used=10,
            model="fake-1",
            latency_ms=0.1,
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_memory_does_not_grow_unbounded_over_100_chapters() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    pack = get_style_pack("tu_tien", "vn")
    applier = QTApplier(Path("data/dictionaries"), cache_dir=Path("data/cache"))
    provider = _FakeProvider()
    chapter = "李青走进青云宗，向张老行礼。突破到金丹期需要顿悟。" * 20

    # Warm up — fill any one-off caches.
    for _ in range(10):
        await translate_chapter(
            chapter,
            cfg,
            mode="polish",
            provider=provider,
            applier=applier,
            style_pack=pack,
        )
    gc.collect()
    await asyncio.sleep(0)

    tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()

    for _ in range(100):
        await translate_chapter(
            chapter,
            cfg,
            mode="polish",
            provider=provider,
            applier=applier,
            style_pack=pack,
        )

    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    grew_bytes = current - baseline
    # 100 small chapters; growth should be well under 10 MB. A leak that
    # retains the chapter (or convert text) every call would balloon past this.
    assert grew_bytes < 10 * 1024 * 1024, (
        f"memory grew {grew_bytes / 1024 / 1024:.1f} MB over 100 chapters "
        f"(baseline {baseline}, current {current}, peak {peak})"
    )


@pytest.mark.asyncio
async def test_convert_mode_memory_stable_100_chapters() -> None:
    """Convert-only path (no LLM) — even tighter budget since no async stack."""
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    applier = QTApplier(Path("data/dictionaries"), cache_dir=Path("data/cache"))
    chapter = "李青走进青云宗，向张老行礼。" * 50

    for _ in range(10):
        await translate_chapter(chapter, cfg, mode="convert", applier=applier)
    gc.collect()

    tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()

    for _ in range(100):
        await translate_chapter(chapter, cfg, mode="convert", applier=applier)

    gc.collect()
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    grew_bytes = current - baseline
    assert (
        grew_bytes < 5 * 1024 * 1024
    ), f"convert-mode memory grew {grew_bytes / 1024 / 1024:.1f} MB"
