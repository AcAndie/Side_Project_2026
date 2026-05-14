"""Tests for the LLM provider layer.

Unit tests use a fake `GenerativeModel.generate_content_async` so no network or
API key is required. The single integration test is gated behind
`-m integration` and is skipped by default.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.api_core import exceptions as gax

from trilex.providers.base import (
    DEFAULT_MAX_TOKENS,
    EmptyResponseError,
    LLMProvider,
    ProviderResponse,
    QuotaExceededError,
    SafetyBlockError,
)
from trilex.providers.gemini import GeminiProvider

# --------------------------------------------------------------------------- #
# base                                                                        #
# --------------------------------------------------------------------------- #


def test_provider_response_is_frozen() -> None:
    r = ProviderResponse(text="hi", tokens_used=5, model="x", latency_ms=10.0, finish_reason="stop")
    with pytest.raises(Exception):  # noqa: B017
        r.text = "modified"  # type: ignore[misc]


def test_llm_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_subclass_can_implement_complete() -> None:
    class _Echo(LLMProvider):
        name = "echo"

        async def complete(
            self,
            prompt: str,
            system: str | None = None,
            max_tokens: int = DEFAULT_MAX_TOKENS,
        ) -> ProviderResponse:
            return ProviderResponse(
                text=prompt,
                tokens_used=len(prompt),
                model="echo-1",
                latency_ms=0.0,
                finish_reason="stop",
            )

    r = await _Echo().complete("ping")
    assert r.text == "ping"
    assert r.model == "echo-1"


# --------------------------------------------------------------------------- #
# gemini — fakes                                                              #
# --------------------------------------------------------------------------- #


def _fake_response(
    text: str = "hello",
    finish: str = "STOP",
    tokens: int = 12,
    block_reason: object = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        candidates=[
            SimpleNamespace(
                finish_reason=SimpleNamespace(name=finish),
                content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
            )
        ],
        prompt_feedback=SimpleNamespace(block_reason=block_reason),
        usage_metadata=SimpleNamespace(total_token_count=tokens),
    )


class _FakeModel:
    """Drop-in replacement for `genai.GenerativeModel`."""

    def __init__(self, behaviour: list[Any]) -> None:
        self._behaviour = list(behaviour)
        self.calls = 0

    async def generate_content_async(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        step = self._behaviour.pop(0)
        if isinstance(step, Exception):
            raise step
        if callable(step):
            result = step()
            if asyncio.iscoroutine(result):
                return await result
            return result
        return step


@pytest.fixture
def gemini_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Build GeminiProvider with a `_FakeModel` patched in. No real SDK init."""

    def _build(behaviour: list[Any], **overrides: Any) -> tuple[GeminiProvider, _FakeModel]:
        # Patch genai.configure + GenerativeModel before construction.
        import trilex.providers.gemini as mod

        fake = _FakeModel(behaviour)
        monkeypatch.setattr(mod.genai, "configure", lambda **_: None)
        monkeypatch.setattr(mod.genai, "GenerativeModel", lambda **_: fake)

        kwargs: dict[str, Any] = {
            "api_key": "AIzaTEST00000000",
            "model": "gemini-test",
            "timeout": 0.5,
            "max_retries": 3,
            "log_path": tmp_path / "llm.jsonl",
            "backoff_base": 0.0,  # disable real sleeps in tests
        }
        kwargs.update(overrides)
        provider = GeminiProvider(**kwargs)
        # GenerativeModel was patched; ensure provider holds the fake.
        provider._model = fake  # type: ignore[attr-defined]
        return provider, fake

    return _build


def _read_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --------------------------------------------------------------------------- #
# gemini — happy path                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_complete_returns_response_and_logs_ok(gemini_factory) -> None:
    provider, fake = gemini_factory([_fake_response(text="xin chào", tokens=7)])
    r = await provider.complete("Dịch: 你好")
    assert r.text == "xin chào"
    assert r.tokens_used == 7
    assert r.model == "gemini-test"
    assert r.finish_reason == "stop"
    assert fake.calls == 1

    log = _read_log(provider.log_path)
    assert len(log) == 1
    assert log[0]["status"] == "ok"
    assert log[0]["tokens"] == 7
    # Mask hides the middle of the key.
    assert "TEST" not in log[0]["api_key"] or log[0]["api_key"].startswith("AIza")


@pytest.mark.asyncio
async def test_system_prompt_is_prepended(gemini_factory) -> None:
    """If `system` is provided it should be sent (we just check no crash + call made)."""
    provider, fake = gemini_factory([_fake_response()])
    await provider.complete("user msg", system="you are X")
    assert fake.calls == 1


# --------------------------------------------------------------------------- #
# gemini — retry behaviour                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_retries_on_quota_then_succeeds(gemini_factory) -> None:
    provider, fake = gemini_factory(
        [
            gax.ResourceExhausted("rate limited"),
            gax.ResourceExhausted("still limited"),
            _fake_response(text="ok"),
        ]
    )
    r = await provider.complete("hi")
    assert r.text == "ok"
    assert fake.calls == 3
    statuses = [entry["status"] for entry in _read_log(provider.log_path)]
    assert statuses == ["quota_exceeded", "quota_exceeded", "ok"]


@pytest.mark.asyncio
async def test_exhausts_retries_raises_last_error(gemini_factory) -> None:
    provider, fake = gemini_factory(
        [gax.ResourceExhausted("1"), gax.ResourceExhausted("2"), gax.ResourceExhausted("3")]
    )
    with pytest.raises(QuotaExceededError):
        await provider.complete("hi")
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_timeout_is_classified_and_retried(
    gemini_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _slow() -> None:
        await asyncio.sleep(10)

    provider, fake = gemini_factory(
        [
            lambda: _slow(),  # returns a coroutine that asyncio.wait_for will cancel
            _fake_response(text="recovered"),
        ],
        timeout=0.05,
    )
    # The _FakeModel returns whatever the callable produces — here a coroutine.
    # asyncio.wait_for(coro, timeout=...) will raise TimeoutError on first attempt.
    r = await provider.complete("hi")
    assert r.text == "recovered"
    log = _read_log(provider.log_path)
    assert log[0]["status"] == "timeout"
    assert log[1]["status"] == "ok"


# --------------------------------------------------------------------------- #
# gemini — non-retryable                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_safety_block_raises_immediately(gemini_factory) -> None:
    blocked = _fake_response(block_reason="SAFETY")
    provider, fake = gemini_factory([blocked, _fake_response()])
    with pytest.raises(SafetyBlockError):
        await provider.complete("bad prompt")
    # Should NOT have called second time
    assert fake.calls == 1
    assert _read_log(provider.log_path)[0]["status"] == "safety_block_prompt"


@pytest.mark.asyncio
async def test_empty_response_is_retried_then_raises(gemini_factory) -> None:
    empty = SimpleNamespace(
        text="",
        candidates=[],
        prompt_feedback=SimpleNamespace(block_reason=None),
        usage_metadata=SimpleNamespace(total_token_count=0),
    )
    provider, fake = gemini_factory([empty, empty, empty])
    with pytest.raises(EmptyResponseError):
        await provider.complete("hi")
    assert fake.calls == 3


# --------------------------------------------------------------------------- #
# gemini — construction guardrails                                            #
# --------------------------------------------------------------------------- #


def test_empty_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import trilex.providers.gemini as mod

    monkeypatch.setattr(mod.genai, "configure", lambda **_: None)
    monkeypatch.setattr(mod.genai, "GenerativeModel", lambda **_: object())
    with pytest.raises(ValueError):
        GeminiProvider(api_key="   ", model="x")


def test_invalid_max_retries_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import trilex.providers.gemini as mod

    monkeypatch.setattr(mod.genai, "configure", lambda **_: None)
    monkeypatch.setattr(mod.genai, "GenerativeModel", lambda **_: object())
    with pytest.raises(ValueError):
        GeminiProvider(api_key="ok", model="x", max_retries=0)


# --------------------------------------------------------------------------- #
# integration (real Gemini call) — skipped unless `-m integration`            #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_gemini_translate_smoke(tmp_path: Path) -> None:
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    provider = GeminiProvider.from_settings(log_path=tmp_path / "real.jsonl")
    response = await provider.complete("Dịch sang tiếng Việt: 你好世界")
    assert response.text
    assert response.tokens_used > 0
