"""Tests for the polish stage. Uses a fake LLMProvider; no network."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import pytest

from trilex.core.models.term import Term
from trilex.core.pipeline.stages.polish import (
    LENGTH_MAX_RATIO,
    PolishResult,
    polish,
)
from trilex.core.style_pack import get_style_pack
from trilex.providers.base import (
    DEFAULT_MAX_TOKENS,
    LLMProvider,
    ProviderResponse,
)


@pytest.fixture(scope="module")
def tu_tien():
    return get_style_pack("tu_tien", "vn")


@dataclass
class _CapturedCall:
    prompt: str
    system: str | None
    max_tokens: int


class _FakeProvider(LLMProvider):
    """Records the last prompt and returns a scripted reply."""

    name = "fake"

    def __init__(
        self,
        reply: str = "ok",
        tokens: int = 42,
        latency_ms: float = 12.0,
        finish_reason: str = "stop",
    ) -> None:
        self.reply = reply
        self.tokens = tokens
        self.latency_ms = latency_ms
        self.finish_reason = finish_reason
        self.calls: list[_CapturedCall] = []

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.calls.append(_CapturedCall(prompt=prompt, system=system, max_tokens=max_tokens))
        return ProviderResponse(
            text=self.reply,
            tokens_used=self.tokens,
            model="fake-1",
            latency_ms=self.latency_ms,
            finish_reason=self.finish_reason,
        )


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_polish_returns_result_with_no_warnings(tu_tien) -> None:
    provider = _FakeProvider(reply="Lý Thanh bước vào Thanh Vân Tông.")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert isinstance(r, PolishResult)
    assert "Lý Thanh" in r.text
    assert r.tokens_used == 42
    assert r.model == "fake-1"
    assert r.warnings == []
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_provider_receives_glossary_and_style(tu_tien) -> None:
    provider = _FakeProvider(reply="Lý Thanh đi tới Thanh Vân Tông.")
    glossary = [Term(source="李青", target="Lý Thanh", category="character")]
    await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
        glossary=glossary,
    )
    call = provider.calls[0]
    # System prompt mentions role.
    assert call.system is not None
    assert "dịch giả" in call.system
    # User prompt carries glossary line and realm ladder.
    assert "李青 -> Lý Thanh" in call.prompt
    assert "Kim Đan" in call.prompt
    # Few-shot section included.
    assert "VÍ DỤ DỊCH MẪU" in call.prompt


@pytest.mark.asyncio
async def test_glossary_terms_not_in_source_are_filtered(tu_tien) -> None:
    """Terms whose `source` isn't in the chapter shouldn't appear in the prompt."""
    provider = _FakeProvider(reply="Lý Thanh đi vào Thanh Vân Tông.")
    glossary = [
        Term(source="李青", target="Lý Thanh"),
        Term(source="王五", target="Vương Ngũ"),  # not in original
    ]
    await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
        glossary=glossary,
    )
    prompt = provider.calls[0].prompt
    assert "李青 -> Lý Thanh" in prompt
    assert "王五" not in prompt


# --------------------------------------------------------------------------- #
# Preamble stripping                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_preamble_is_stripped(tu_tien) -> None:
    provider = _FakeProvider(reply="Đây là bản dịch:\nLý Thanh bước vào Thanh Vân Tông.")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert not r.text.lower().startswith("đây là")
    assert r.text.startswith("Lý Thanh")


# --------------------------------------------------------------------------- #
# Warnings                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_warning_on_residual_cjk(tu_tien) -> None:
    provider = _FakeProvider(reply="Lý Thanh 走进 Thanh Vân Tông.")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert any(w.startswith("residual_cjk") for w in r.warnings)


@pytest.mark.asyncio
async def test_warning_on_name_violation(tu_tien) -> None:
    provider = _FakeProvider(reply="Một nhân vật đi vào tông môn.")
    glossary = [Term(source="李青", target="Lý Thanh", category="character")]
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
        glossary=glossary,
    )
    assert any("name_violation" in w for w in r.warnings)


@pytest.mark.asyncio
async def test_warning_on_markdown_noise(tu_tien) -> None:
    provider = _FakeProvider(reply="```\nLý Thanh đi vào Thanh Vân Tông.\n```")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert "markdown_or_html_garbage" in r.warnings


@pytest.mark.asyncio
async def test_warning_on_banned_phrase(tu_tien) -> None:
    provider = _FakeProvider(reply="Lý Thanh đi vào tông môn một cách nhanh chóng.")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert any(w.startswith("banned_phrases") for w in r.warnings)


@pytest.mark.asyncio
async def test_warning_on_too_short(tu_tien) -> None:
    provider = _FakeProvider(reply="Lý Thanh.")
    r = await polish(
        original="李青走进了青云宗，他抬头看着山门。",
        converted="Lý Thanh đi vào Thanh Vân Tông, hắn ngẩng đầu nhìn sơn môn.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert any(w.startswith("too_short") for w in r.warnings)


@pytest.mark.asyncio
async def test_warning_on_too_long(tu_tien) -> None:
    converted = "Lý Thanh đi vào Thanh Vân Tông."
    bloated = "Lý Thanh đi vào Thanh Vân Tông. " * 4
    provider = _FakeProvider(reply=bloated)
    r = await polish(
        original="李青走进了青云宗。",
        converted=converted,
        style_pack=tu_tien,
        provider=provider,
    )
    assert any(w.startswith("too_long") for w in r.warnings)
    # Sanity: bloated text is well over the ceiling.
    assert len(bloated) / len(converted) > LENGTH_MAX_RATIO


@pytest.mark.asyncio
async def test_warning_on_empty_output(tu_tien) -> None:
    provider = _FakeProvider(reply="")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert r.warnings == ["empty_output"]


@pytest.mark.asyncio
async def test_warning_on_forbidden_in_output(tu_tien) -> None:
    provider = _FakeProvider(reply="Lý Thanh dùng phép thuật vào Thanh Vân Tông.")
    r = await polish(
        original="李青走进了青云宗。",
        converted="Lý Thanh đi vào Thanh Vân Tông.",
        style_pack=tu_tien,
        provider=provider,
    )
    assert any(w.startswith("forbidden_in_output") for w in r.warnings)


# --------------------------------------------------------------------------- #
# Integration                                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_gemini_polish() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    from trilex.providers.gemini import GeminiProvider

    pack = get_style_pack("tu_tien", "vn")
    provider = GeminiProvider.from_settings()
    r = await asyncio.wait_for(
        polish(
            original="李青走进了青云宗，心中既紧张又兴奋。",
            converted="Lý Thanh đi vào Thanh Vân Tông , trong lòng vừa căng thẳng vừa hưng phấn 。",
            style_pack=pack,
            provider=provider,
        ),
        timeout=120,
    )
    assert r.text
    assert r.tokens_used > 0
