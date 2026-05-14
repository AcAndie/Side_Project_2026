"""Tests for the chapter-pipeline orchestrator + pre/post stages."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from trilex.core.models.project import ProjectConfig
from trilex.core.models.term import Term
from trilex.core.pipeline.orchestrator import (
    ChapterResult,
    translate_chapter,
)
from trilex.core.pipeline.stages.postprocess import postprocess
from trilex.core.pipeline.stages.preprocess import preprocess
from trilex.core.style_pack import get_style_pack
from trilex.providers.base import (
    DEFAULT_MAX_TOKENS,
    LLMProvider,
    ProviderResponse,
    QuotaExceededError,
)
from trilex.qt_dict.applier import QTApplier

# --------------------------------------------------------------------------- #
# Stage helpers                                                               #
# --------------------------------------------------------------------------- #


def test_preprocess_strips_ad_urls_and_normalizes() -> None:
    text = "李青走进青云宗。\r\n\r\n\r\nhttps://example.com/spam\n本章未完待续"
    out, warn = preprocess(text)
    assert "https://" not in out
    assert "本章未完" not in out
    assert "\r" not in out
    assert "\n\n\n" not in out
    assert any(w.startswith("stripped_junk") for w in warn)


def test_preprocess_empty_input() -> None:
    out, warn = preprocess("")
    assert out == ""
    assert "empty_input" in warn


def test_postprocess_normalizes_cjk_punctuation() -> None:
    text = "Lý Thanh đi vào Thanh Vân Tông ， trong lòng vừa hồi hộp 。"
    out, _ = postprocess(text)
    assert "，" not in out
    assert "。" not in out
    assert "Tông," in out
    assert "hồi hộp." in out


def test_postprocess_collapses_spaces() -> None:
    text = "Lý  Thanh   bước  vào   Thanh Vân."
    out, _ = postprocess(text)
    assert "  " not in out


def test_postprocess_dot_runs() -> None:
    out, _ = postprocess("Hắn nhìn ra xa....")
    assert "..." in out
    assert "...." not in out


# --------------------------------------------------------------------------- #
# Fake providers + applier                                                    #
# --------------------------------------------------------------------------- #


@dataclass
class _Recorded:
    prompt: str
    system: str | None


class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, reply: str, *, raise_error: Exception | None = None) -> None:
        self.reply = reply
        self.raise_error = raise_error
        self.calls: list[_Recorded] = []

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.calls.append(_Recorded(prompt=prompt, system=system))
        if self.raise_error is not None:
            raise self.raise_error
        return ProviderResponse(
            text=self.reply,
            tokens_used=128,
            model="fake-1",
            latency_ms=33.3,
            finish_reason="stop",
        )


@pytest.fixture
def tu_tien_pack():
    return get_style_pack("tu_tien", "vn")


@pytest.fixture
def real_applier() -> QTApplier:
    """Real applier against the project's data/dictionaries."""
    return QTApplier(Path("data/dictionaries"), cache_dir=Path("data/cache"))


@pytest.fixture
def fake_config() -> ProjectConfig:
    return ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")


# --------------------------------------------------------------------------- #
# ProjectConfig                                                               #
# --------------------------------------------------------------------------- #


def test_style_pack_id_default() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    assert cfg.style_pack_id() == ("tu_tien", "vn")


def test_style_pack_id_override() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", style_pack="litrpg.en")
    assert cfg.style_pack_id() == ("litrpg", "en")


def test_style_pack_id_malformed_raises() -> None:
    cfg = ProjectConfig(source_lang="zh", target_lang="vn", style_pack="bogus")
    with pytest.raises(ValueError):
        cfg.style_pack_id()


# --------------------------------------------------------------------------- #
# Orchestrator — mode=convert                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_convert_mode_does_not_call_provider(real_applier, fake_config, tu_tien_pack) -> None:
    provider = _FakeProvider(reply="never")
    r = await translate_chapter(
        "李青走进青云宗。",
        fake_config,
        mode="convert",
        provider=provider,
        applier=real_applier,
        style_pack=tu_tien_pack,
    )
    assert provider.calls == []
    assert r.mode == "convert"
    assert r.state == "postprocessed"
    assert r.convert_text is not None
    assert "Lý Thanh" in r.convert_text
    assert r.polished_text is None
    assert r.tokens_used == 0


@pytest.mark.asyncio
async def test_convert_mode_postprocesses_cjk_punct(
    real_applier, fake_config, tu_tien_pack
) -> None:
    r = await translate_chapter(
        "李青走进青云宗。",
        fake_config,
        mode="convert",
        applier=real_applier,
        style_pack=tu_tien_pack,
    )
    assert "。" not in r.final_text
    assert r.final_text.rstrip().endswith(".")


# --------------------------------------------------------------------------- #
# Orchestrator — mode=polish                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_polish_mode_full_pipeline(real_applier, fake_config, tu_tien_pack) -> None:
    provider = _FakeProvider(reply="Lý Thanh bước vào Thanh Vân Tông.")
    r = await translate_chapter(
        "李青走进青云宗。",
        fake_config,
        mode="polish",
        provider=provider,
        applier=real_applier,
        style_pack=tu_tien_pack,
    )
    assert len(provider.calls) == 1
    assert r.state == "postprocessed"
    assert r.convert_text is not None
    assert r.polished_text is not None
    assert "Lý Thanh" in r.final_text
    assert r.tokens_used == 128
    assert r.model == "fake-1"
    # All four stages ran.
    stage_names = [s.name for s in r.stage_stats]
    assert stage_names == ["preprocess", "qt_pass", "polish", "postprocess"]


@pytest.mark.asyncio
async def test_polish_mode_passes_glossary_into_prompt(real_applier, tu_tien_pack) -> None:
    cfg = ProjectConfig(
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
        custom_glossary=(Term(source="李青", target="Lý Thanh", category="character"),),
    )
    provider = _FakeProvider(reply="Lý Thanh bước vào Thanh Vân Tông.")
    await translate_chapter(
        "李青走进青云宗。",
        cfg,
        mode="polish",
        provider=provider,
        applier=real_applier,
        style_pack=tu_tien_pack,
    )
    assert "李青 -> Lý Thanh" in provider.calls[0].prompt


@pytest.mark.asyncio
async def test_polish_mode_requires_provider(real_applier, fake_config) -> None:
    with pytest.raises(ValueError, match="provider"):
        await translate_chapter(
            "李青走进青云宗。",
            fake_config,
            mode="polish",
            applier=real_applier,
        )


@pytest.mark.asyncio
async def test_polish_failure_returns_failed_state(real_applier, fake_config, tu_tien_pack) -> None:
    """With ``fallback_to_convert=False`` a ProviderError still terminates the
    pipeline in ``state="failed"``."""
    provider = _FakeProvider(reply="", raise_error=QuotaExceededError("rate limit"))
    r = await translate_chapter(
        "李青走进青云宗。",
        fake_config,
        mode="polish",
        provider=provider,
        applier=real_applier,
        style_pack=tu_tien_pack,
        fallback_to_convert=False,
    )
    assert r.state == "failed"
    assert r.polished_text is None
    assert any("provider_error" in w for w in r.warnings)
    # convert_text should still be populated (QT pass already ran).
    assert r.convert_text is not None


@pytest.mark.asyncio
async def test_polish_failure_falls_back_to_convert(
    real_applier, fake_config, tu_tien_pack
) -> None:
    """Default ``fallback_to_convert=True``: ProviderError degrades to convert
    output instead of failing the chapter."""
    provider = _FakeProvider(reply="", raise_error=QuotaExceededError("rate limit"))
    r = await translate_chapter(
        "李青走进青云宗。",
        fake_config,
        mode="polish",
        provider=provider,
        applier=real_applier,
        style_pack=tu_tien_pack,
    )
    assert r.state == "postprocessed"
    assert r.polished_text is None
    assert r.convert_text is not None
    assert r.final_text
    assert any("fallback_to_convert" in w for w in r.warnings)
    assert any("provider_error" in w for w in r.warnings)
    assert r.tokens_used == 0
    assert r.model is None


# --------------------------------------------------------------------------- #
# Orchestrator — source != zh skips QT                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_non_zh_source_skips_qt_pass(tu_tien_pack) -> None:
    cfg = ProjectConfig(source_lang="en", target_lang="vn")
    provider = _FakeProvider(reply="Lý Thanh bước vào tông môn.")
    r = await translate_chapter(
        "Li Qing entered the Qingyun Sect.",
        cfg,
        mode="polish",
        provider=provider,
        style_pack=tu_tien_pack,
    )
    assert r.convert_text is None
    assert any("qt_pass.skipped" in w for w in r.warnings)
    assert "Lý Thanh" in r.final_text


@pytest.mark.asyncio
async def test_zh_to_en_skips_qt_pass_with_target_not_vn_warning() -> None:
    from trilex.core.style_pack import get_style_pack

    pack = get_style_pack("tu_tien", "en")
    cfg = ProjectConfig(source_lang="zh", target_lang="en", genre="tu_tien")
    provider = _FakeProvider(reply="Li Qing stepped into the Qingyun Sect.")
    r = await translate_chapter(
        "李青走进青云宗。",
        cfg,
        mode="polish",
        provider=provider,
        style_pack=pack,
    )
    assert r.convert_text is None
    assert any("qt_pass.skipped:target_not_vn" in w for w in r.warnings)
    prompt = provider.calls[0].prompt
    assert "Dịch văn bản tiếng Trung" in prompt
    assert "BẢN CONVERT QT" not in prompt
    assert "Li Qing" in r.final_text


@pytest.mark.asyncio
async def test_vn_to_en_full_translation_with_general_pack() -> None:
    from trilex.core.style_pack import get_style_pack

    pack = get_style_pack("general", "en")
    cfg = ProjectConfig(source_lang="vn", target_lang="en", genre="general")
    provider = _FakeProvider(reply='"Brother, where are you going?" asked Little Li.')
    r = await translate_chapter(
        '"Đại ca, anh đi đâu thế?" Tiểu Lý lo lắng hỏi.',
        cfg,
        mode="polish",
        provider=provider,
        style_pack=pack,
    )
    assert r.convert_text is None
    assert any("qt_pass.skipped:source_not_zh" in w for w in r.warnings)
    prompt = provider.calls[0].prompt
    assert "Dịch văn bản tiếng Việt" in prompt
    # General pack honorific "đại ca" present in original → must appear in prompt slice
    assert "đại ca" in prompt
    assert "elder brother" in prompt


@pytest.mark.asyncio
async def test_en_to_vn_uses_full_translation_prompt() -> None:
    """EN→VN should hit polish with `is_full_translation=True` ⇒ task block
    says 'Dịch ... đầy đủ' instead of 'Polish'."""
    from trilex.core.style_pack import get_style_pack

    litrpg = get_style_pack("litrpg", "vn")
    cfg = ProjectConfig(source_lang="en", target_lang="vn", genre="litrpg")
    provider = _FakeProvider(reply="Cấp 5 → Cấp 6. +5 STR.")
    r = await translate_chapter(
        "Level 5 → Level 6. +5 STR.",
        cfg,
        mode="polish",
        provider=provider,
        style_pack=litrpg,
    )
    assert r.convert_text is None
    assert len(provider.calls) == 1
    prompt = provider.calls[0].prompt
    assert "Dịch văn bản tiếng Anh" in prompt
    assert "[NGUYÊN BẢN TIẾNG ANH" in prompt
    assert "BẢN CONVERT QT" not in prompt
    assert "Cấp 5" in r.final_text


# --------------------------------------------------------------------------- #
# Orchestrator — invalid input                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_invalid_mode_raises(fake_config) -> None:
    with pytest.raises(ValueError):
        await translate_chapter(
            "x",
            fake_config,
            mode="weird",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_empty_input_returns_failed(real_applier, fake_config, tu_tien_pack) -> None:
    provider = _FakeProvider(reply="should not be called")
    r = await translate_chapter(
        "",
        fake_config,
        mode="polish",
        provider=provider,
        applier=real_applier,
        style_pack=tu_tien_pack,
    )
    assert r.state == "failed"
    assert provider.calls == []
    assert any("empty_input" in w for w in r.warnings)


# --------------------------------------------------------------------------- #
# Integration                                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_gemini_full_chapter() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    from trilex.providers.gemini import GeminiProvider

    cfg = ProjectConfig(source_lang="zh", target_lang="vn", genre="tu_tien")
    provider = GeminiProvider.from_settings()
    r = await translate_chapter(
        "李青走进青云宗，心中既紧张又兴奋。",
        cfg,
        mode="polish",
        provider=provider,
    )
    assert isinstance(r, ChapterResult)
    assert r.state == "postprocessed"
    assert r.final_text
    assert r.tokens_used > 0
