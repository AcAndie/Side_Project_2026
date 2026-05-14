"""Tests for the scout (new-term extractor)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pytest

from trilex.core.models.term import Term
from trilex.memory.scout import NewTerm, scout_terms
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider, ProviderResponse


@dataclass
class _Call:
    prompt: str
    system: str | None


class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[_Call] = []

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        self.calls.append(_Call(prompt=prompt, system=system))
        return ProviderResponse(
            text=self.reply,
            tokens_used=64,
            model="fake-1",
            latency_ms=10.0,
            finish_reason="stop",
        )


CHAPTER = "李青走进青云宗，遇见了张老。张老传授了《青云剑诀》。"
TRANSLATION = (
    "Lý Thanh bước vào Thanh Vân Tông, gặp Trương Lão. "
    "Trương Lão truyền thụ «Thanh Vân Kiếm Quyết»."
)


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_scout_returns_validated_new_terms() -> None:
    reply = json.dumps(
        [
            {"zh": "李青", "vn": "Lý Thanh", "category": "character", "confidence": 0.95},
            {"zh": "青云宗", "vn": "Thanh Vân Tông", "category": "sect", "confidence": 0.9},
            {"zh": "张老", "vn": "Trương Lão", "category": "character", "confidence": 0.8},
            {
                "zh": "青云剑诀",
                "vn": "Thanh Vân Kiếm Quyết",
                "category": "skill",
                "confidence": 0.7,
            },
        ]
    )
    provider = _FakeProvider(reply)
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=provider, glossary=[]
    )
    assert len(out) == 4
    assert {t.zh for t in out} == {"李青", "青云宗", "张老", "青云剑诀"}
    assert all(isinstance(t, NewTerm) for t in out)
    assert all(0.0 <= t.confidence <= 1.0 for t in out)


@pytest.mark.asyncio
async def test_scout_skips_already_glossed_zh() -> None:
    reply = json.dumps(
        [
            {"zh": "李青", "vn": "Lý Thanh", "category": "character"},
            {"zh": "青云宗", "vn": "Thanh Vân Tông", "category": "sect"},
        ]
    )
    provider = _FakeProvider(reply)
    existing = [Term(source="李青", target="Lý Thanh", category="character")]
    out = await scout_terms(
        original=CHAPTER,
        translation=TRANSLATION,
        provider=provider,
        glossary=existing,
    )
    assert {t.zh for t in out} == {"青云宗"}


@pytest.mark.asyncio
async def test_scout_dedupes_within_response() -> None:
    reply = json.dumps(
        [
            {"zh": "张老", "vn": "Trương Lão", "category": "character"},
            {"zh": "张老", "vn": "Trương Lão Gia", "category": "character"},
        ]
    )
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=_FakeProvider(reply)
    )
    assert len(out) == 1


# --------------------------------------------------------------------------- #
# Robustness — malformed / wrapped responses                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_scout_strips_json_code_fence() -> None:
    inner = json.dumps([{"zh": "张老", "vn": "Trương Lão", "category": "character"}])
    reply = f"```json\n{inner}\n```"
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=_FakeProvider(reply)
    )
    assert len(out) == 1
    assert out[0].zh == "张老"


@pytest.mark.asyncio
async def test_scout_strips_leading_label() -> None:
    inner = json.dumps([{"zh": "张老", "vn": "Trương Lão", "category": "character"}])
    reply = f"JSON: {inner}"
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=_FakeProvider(reply)
    )
    assert len(out) == 1


@pytest.mark.asyncio
async def test_scout_recovers_array_from_surrounding_noise() -> None:
    inner = json.dumps([{"zh": "张老", "vn": "Trương Lão", "category": "character"}])
    reply = f"Đây là kết quả:\n{inner}\nKết thúc."
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=_FakeProvider(reply)
    )
    assert len(out) == 1


@pytest.mark.asyncio
async def test_scout_returns_empty_on_invalid_json() -> None:
    out = await scout_terms(
        original=CHAPTER,
        translation=TRANSLATION,
        provider=_FakeProvider("not json at all"),
    )
    assert out == []


@pytest.mark.asyncio
async def test_scout_skips_hallucinated_term_not_in_source() -> None:
    # LLM proposes a term that never appears in CHAPTER.
    reply = json.dumps(
        [
            {"zh": "张老", "vn": "Trương Lão", "category": "character"},
            {"zh": "妖魔界", "vn": "Yêu Ma Giới", "category": "place"},  # not in CHAPTER
        ]
    )
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=_FakeProvider(reply)
    )
    assert {t.zh for t in out} == {"张老"}


@pytest.mark.asyncio
async def test_scout_skips_malformed_rows() -> None:
    reply = json.dumps(
        [
            {"zh": "张老"},  # missing vn
            {"vn": "Trương Lão"},  # missing zh
            {"zh": "张老", "vn": "Trương Lão", "category": "character"},  # ok
            "not-an-object",  # garbage
        ]
    )
    out = await scout_terms(
        original=CHAPTER, translation=TRANSLATION, provider=_FakeProvider(reply)
    )
    assert len(out) == 1
    assert out[0].zh == "张老"


# --------------------------------------------------------------------------- #
# Prompt construction                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_prompt_includes_existing_glossary_for_chapter() -> None:
    provider = _FakeProvider("[]")
    existing = [
        Term(source="李青", target="Lý Thanh", category="character"),
        Term(source="王五", target="Vương Ngũ", category="character"),  # NOT in chapter
    ]
    await scout_terms(
        original=CHAPTER,
        translation=TRANSLATION,
        provider=provider,
        glossary=existing,
    )
    prompt = provider.calls[0].prompt
    assert "李青 -> Lý Thanh" in prompt
    assert "王五" not in prompt
    assert "TASK: Extract NEW terms" in prompt
    assert provider.calls[0].system is not None
    assert "scout" in provider.calls[0].system.lower()


# --------------------------------------------------------------------------- #
# Integration (real Gemini, skipped by default)                               #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_gemini_scout_finds_character_names() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    from trilex.providers.gemini import GeminiProvider

    provider = GeminiProvider.from_settings()
    out = await scout_terms(
        original=CHAPTER,
        translation=TRANSLATION,
        provider=provider,
        glossary=[],
    )
    # At minimum scout should surface the protagonist + sect.
    surfaces = {t.zh for t in out}
    assert "李青" in surfaces or "青云宗" in surfaces
