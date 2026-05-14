"""100-chapter smoke test against the bundled `137239_thieu-nien-di.epub`.

Per the user's spec (BUGS_FOUND.md §Recommended fix when addressed):
  - Pull real chapter content from a Vietnamese-language EPUB.
  - Run the full pipeline VN→EN in `polish` mode with a fake provider.
  - Verify 100 chapters complete without crash and without unbounded growth.

The QT pass is skipped (`source_lang != "zh"`) so the pipeline goes
preprocess → polish → postprocess. We assert no chapter ends in `state="failed"`
and that the fake provider was invoked exactly N times.
"""

from __future__ import annotations

import gc
import re
import tracemalloc
from pathlib import Path

import pytest
from ebooklib import ITEM_DOCUMENT, epub

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline.orchestrator import translate_chapter
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider, ProviderResponse

EPUB_PATH = Path(__file__).resolve().parents[2] / "137239_thieu-nien-di.epub"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class _CountingProvider(LLMProvider):
    """Counts calls + returns a short English translation for any input."""

    name = "fake-en"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(
            text="The young man went forth into the city.",
            tokens_used=12,
            model="fake-en-1",
            latency_ms=0.1,
            finish_reason="stop",
        )


def _extract_chapters(epub_path: Path, limit: int) -> list[str]:
    """Pull plain-text chapter bodies from the EPUB until we have `limit` of them."""
    book = epub.read_epub(str(epub_path))
    chapters: list[str] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="ignore")
        text = _TAG_RE.sub("", html)
        text = _WS_RE.sub(" ", text).strip()
        if len(text) < 200:  # skip toc / titlepage / acks
            continue
        chapters.append(text)
        if len(chapters) >= limit:
            break
    return chapters


@pytest.fixture(scope="module")
def epub_chapters() -> list[str]:
    if not EPUB_PATH.exists():
        pytest.skip(f"EPUB fixture missing: {EPUB_PATH}")
    return _extract_chapters(EPUB_PATH, limit=110)  # tiny buffer


@pytest.mark.asyncio
async def test_100_chapters_vn_to_en_no_crash(epub_chapters: list[str]) -> None:
    assert len(epub_chapters) >= 100, f"only {len(epub_chapters)} chapters extracted"
    chapters = epub_chapters[:100]

    cfg = ProjectConfig(source_lang="vn", target_lang="en", genre="tu_tien")
    provider = _CountingProvider()

    failed: list[int] = []
    for i, body in enumerate(chapters):
        result = await translate_chapter(body, cfg, mode="polish", provider=provider)
        if result.state == "failed":
            failed.append(i)
        # Every result must carry the QT skip warning since source != zh.
        assert any("qt_pass.skipped" in w for w in result.warnings), result.warnings
        # Polish ran → polished text non-empty.
        assert result.polished_text == "The young man went forth into the city."
        assert result.final_text  # postprocess must not blank it out

    assert failed == [], f"chapters failed: {failed[:5]}…"
    assert provider.calls == 100


@pytest.mark.asyncio
async def test_100_chapters_memory_bounded(epub_chapters: list[str]) -> None:
    """Heap growth across 100 real chapters must stay under 15 MB."""
    chapters = epub_chapters[:100]
    cfg = ProjectConfig(source_lang="vn", target_lang="en", genre="tu_tien")
    provider = _CountingProvider()

    # Warm-up.
    for body in chapters[:5]:
        await translate_chapter(body, cfg, mode="polish", provider=provider)
    gc.collect()

    tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()
    for body in chapters:
        await translate_chapter(body, cfg, mode="polish", provider=provider)
    gc.collect()
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    grew = current - baseline
    # Real chapters are ~5–10 KB each so the pipeline keeps copies in
    # ChapterResult; 15 MB still proves nothing leaks per call.
    assert (
        grew < 15 * 1024 * 1024
    ), f"VN→EN pipeline grew {grew / 1024 / 1024:.1f} MB over 100 real chapters"
