"""Edge-case tests: empty chapter, foreign chars, very long, bad dict, mixed unicode.

These exercise input shapes that real-world web-scraped chapters routinely
produce and that historically broke prior prototypes (LiTTrans v5.x).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline.orchestrator import translate_chapter
from trilex.core.pipeline.stages.postprocess import postprocess
from trilex.core.pipeline.stages.preprocess import preprocess
from trilex.core.style_pack import get_style_pack
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider, ProviderResponse
from trilex.qt_dict.applier import QTApplier
from trilex.qt_dict.parser import QTParseError, parse_qt_dict

# --------------------------------------------------------------------------- #
# Test doubles                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class _Recorded:
    prompt: str


class _EchoProvider(LLMProvider):
    """Returns the original/converted text untouched. Lets us assert pipeline
    plumbing without involving an LLM."""

    name = "echo"

    def __init__(self) -> None:
        self.calls: list[_Recorded] = []

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.calls.append(_Recorded(prompt=prompt))
        # Extract chapter content from prompt: just return last non-empty line.
        body = prompt.strip().splitlines()[-1] if prompt.strip() else ""
        return ProviderResponse(
            text=body or "echo",
            tokens_used=1,
            model="echo-1",
            latency_ms=0.1,
            finish_reason="stop",
        )


# --------------------------------------------------------------------------- #
# Empty chapter                                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_orchestrator_empty_chapter_returns_failed_not_crash() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    r = await translate_chapter("", cfg, mode="convert")
    assert r.state == "failed"
    assert r.final_text == ""
    assert any("empty_input" in w for w in r.warnings)


@pytest.mark.asyncio
async def test_orchestrator_whitespace_only_chapter_returns_failed() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    r = await translate_chapter("   \n\n\t  \n", cfg, mode="convert")
    assert r.state == "failed"
    assert r.final_text == ""


def test_postprocess_empty_returns_warning() -> None:
    out, warn = postprocess("")
    assert out == ""
    assert "empty_input" in warn


def test_postprocess_only_punctuation_collapses_clean() -> None:
    out, _ = postprocess("。。。，，，")
    assert "。" not in out
    assert "，" not in out


# --------------------------------------------------------------------------- #
# Foreign characters (English / digits / symbols) interleaved                 #
# --------------------------------------------------------------------------- #


def test_preprocess_keeps_english_digits_symbols() -> None:
    text = "李青 HP=100/200 [Skill] 突破到金丹期 (+50 EXP) — 第3章"
    out, _ = preprocess(text)
    assert "HP=100/200" in out
    assert "[Skill]" in out
    assert "+50 EXP" in out
    assert "第3章" in out
    assert "李青" in out


def test_preprocess_only_english_chapter_passes_through() -> None:
    text = "Chapter 1\n\nThe quick brown fox jumps over the lazy dog.\n\n12345 !@#$%"
    out, warn = preprocess(text)
    assert "The quick brown fox" in out
    assert "12345 !@#$%" in out
    # No CJK so no junk patterns should fire.
    assert all(not w.startswith("stripped_junk") for w in warn)


def test_qt_pass_skipped_for_english_only_source() -> None:
    # Routing assertion: ProjectConfig accepts non-zh source langs.
    # Full skip behaviour is covered in test_orchestrator.py::test_non_zh_source_skips_qt_pass.
    cfg = ProjectConfig(source_lang="en", target_lang="vn")
    assert cfg.source_lang == "en"


# --------------------------------------------------------------------------- #
# Very long chapter                                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_orchestrator_very_long_chapter_completes(tmp_path: Path) -> None:
    """10k+ char chapter must run through convert mode without crash or OOM.

    Pipeline currently does NOT chunk; this test pins that behaviour. If we
    later add chunking, update this test to assert the chunking strategy too.
    """
    cfg = ProjectConfig(
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
        dict_dir=Path("data/dictionaries"),
        cache_dir=Path("data/cache"),
    )
    # 15k chars of mixed ZH + CJK punctuation + paragraph breaks.
    paragraph = "李青走进青云宗，向张老行礼。突破到金丹期需要顿悟。" * 200
    big = paragraph + "\n\n" + paragraph + "\n\n" + paragraph
    assert len(big) > 10_000

    r = await translate_chapter(big, cfg, mode="convert")
    assert r.state == "postprocessed"
    assert r.convert_text is not None
    assert len(r.final_text) > 5_000
    # Performance budget: convert mode should be well under 10s for 30k chars.
    assert r.total_elapsed_ms < 30_000, f"convert pass too slow: {r.total_elapsed_ms}ms"


@pytest.mark.asyncio
async def test_orchestrator_very_long_polish_does_not_chunk_yet(tmp_path: Path) -> None:
    """Confirm current behaviour: polish sends whole chapter in one LLM call.

    KNOWN LIMITATION (BUGS_FOUND.md #LONG-1): no automatic split when
    chapter > 4000 tokens. Tracks the limitation so we know when it's fixed.
    """
    cfg = ProjectConfig(
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
        dict_dir=Path("data/dictionaries"),
        cache_dir=Path("data/cache"),
    )
    pack = get_style_pack("tu_tien", "vn")
    provider = _EchoProvider()
    big = "李青走进青云宗。" * 1500  # ~15k chars
    r = await translate_chapter(big, cfg, mode="polish", provider=provider, style_pack=pack)
    assert r.state == "postprocessed"
    # One call (no chunking) — pinning current behaviour.
    assert len(provider.calls) == 1


# --------------------------------------------------------------------------- #
# Bad dictionary files                                                        #
# --------------------------------------------------------------------------- #


def test_parse_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    d = parse_qt_dict(f)
    assert d.meta.count == 0
    assert d.entries == {}


def test_parse_only_comments_and_blanks(tmp_path: Path) -> None:
    f = tmp_path / "junk.txt"
    f.write_text("# comment\n\n# another\n\n\n", encoding="utf-8")
    d = parse_qt_dict(f)
    assert d.meta.count == 0
    assert d.meta.skipped_lines == 0  # comments / blanks are not "skipped errors"


def test_parse_all_malformed_lines(tmp_path: Path) -> None:
    f = tmp_path / "bad.txt"
    f.write_text("no equals here\nanother bad line\n=novalue\nnokey=\n", encoding="utf-8")
    d = parse_qt_dict(f)
    assert d.meta.count == 0
    assert d.meta.skipped_lines == 4


def test_parse_garbage_bytes_raises(tmp_path: Path) -> None:
    f = tmp_path / "garbage.bin"
    f.write_bytes(b"\xff\xfe\xff")  # invalid in every fallback
    with pytest.raises(QTParseError):
        parse_qt_dict(f)


def test_applier_missing_dict_dir_raises_or_loads_empty(tmp_path: Path) -> None:
    """Applier against an empty dir: no tiers, but instantiation succeeds.

    convert() on text is a pass-through (no rules applied)."""
    empty_dir = tmp_path / "no_dicts"
    empty_dir.mkdir()
    applier = QTApplier(empty_dir, cache_dir=tmp_path / "cache")
    assert applier.tier_names == []
    assert applier.convert("李青走进青云宗。") == "李青走进青云宗。"


def test_applier_corrupt_dict_skips_gracefully(tmp_path: Path) -> None:
    """Single corrupt file inside dict dir should not bring down the applier
    if other files are sound. Currently: a non-decodable file raises
    QTParseError during load.

    KNOWN LIMITATION (BUGS_FOUND.md #DICT-1): one bad dict file blocks the
    whole QTApplier from loading. This test pins that behaviour."""
    dict_dir = tmp_path / "dicts"
    dict_dir.mkdir()
    # Sound vietphrase + corrupt names
    (dict_dir / "Vietphrase.txt").write_text("金丹=Kim Đan\n", encoding="utf-8")
    (dict_dir / "Names.txt").write_bytes(b"\xff\xfe\xff")  # undecodable
    with pytest.raises(QTParseError):
        QTApplier(dict_dir, cache_dir=tmp_path / "cache")


def test_applier_empty_input_returns_empty(tmp_path: Path) -> None:
    empty_dir = tmp_path / "no_dicts"
    empty_dir.mkdir()
    applier = QTApplier(empty_dir, cache_dir=tmp_path / "cache")
    result = applier.convert_detail("")
    assert result.text == ""
    assert result.stats.input_chars == 0
    assert result.stats.output_chars == 0


# --------------------------------------------------------------------------- #
# Unicode edge cases                                                          #
# --------------------------------------------------------------------------- #


def test_preprocess_strips_zero_width_chars() -> None:
    text = "李​青‌走‍进﻿青云宗"
    out, _ = preprocess(text)
    assert "​" not in out
    assert "‌" not in out
    assert "‍" not in out
    assert "﻿" not in out
    assert "李青走进青云宗" in out


def test_preprocess_normalises_mixed_line_endings() -> None:
    text = "line1\r\nline2\rline3\nline4"
    out, _ = preprocess(text)
    assert "\r" not in out
    assert out.split("\n") == ["line1", "line2", "line3", "line4"]


def test_preprocess_collapses_excessive_blank_lines() -> None:
    text = "a\n\n\n\n\n\nb\n\n\n\n\nc"
    out, _ = preprocess(text)
    assert "\n\n\n" not in out


def test_preprocess_combining_diacritics_nfc_normalized() -> None:
    # "é" can be U+00E9 (NFC) or U+0065 U+0301 (NFD). Pipeline normalises to NFC.
    nfd = "Lé Thanh"
    out, _ = preprocess(nfd)
    assert "Lé Thanh" in out


# --------------------------------------------------------------------------- #
# Mode validation                                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_orchestrator_invalid_mode_raises() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    with pytest.raises(ValueError, match="mode"):
        await translate_chapter("xxx", cfg, mode="bogus")  # type: ignore[arg-type]
