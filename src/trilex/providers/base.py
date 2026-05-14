"""Abstract LLM provider contract.

Concrete adapters (Gemini, Claude, DeepSeek, OpenRouter, ...) implement
`LLMProvider.complete` and surface their failure modes via the shared
`ProviderError` hierarchy so callers can branch without importing SDKs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final

DEFAULT_MAX_TOKENS: Final[int] = 4000


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """One completion from an `LLMProvider`. Immutable."""

    text: str
    tokens_used: int
    model: str
    latency_ms: float
    finish_reason: str


class ProviderError(Exception):
    """Base for all provider failures."""


class QuotaExceededError(ProviderError):
    """API quota or per-minute rate limit exhausted."""


class SafetyBlockError(ProviderError):
    """Prompt or candidate was blocked by safety filters. Not retryable."""


class ProviderTimeoutError(ProviderError):
    """Request did not complete before the configured timeout."""


class EmptyResponseError(ProviderError):
    """Provider returned no candidates / empty text."""


class LLMProvider(ABC):
    """Abstract async LLM provider."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        """Return one completion. Raise `ProviderError` subclass on failure."""
