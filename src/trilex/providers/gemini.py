"""Google Gemini provider implementation.

Wraps `google.generativeai` with:
  - Async completion via `generate_content_async`
  - Exponential-backoff retry (configurable, default 3 attempts)
  - Hard timeout via `asyncio.wait_for`
  - Safety filters disabled (per CLAUDE.md §13: tu-tiên / võ-thuật content
    triggers Gemini's default safety blocks)
  - Per-call JSONL audit log (`data/logs/llm_calls.jsonl`) — never logs the
    prompt text, only metadata (status, tokens, latency, masked key)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import google.generativeai as genai
from google.api_core import exceptions as gax
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from trilex.config import get_settings, mask_key
from trilex.providers.base import (
    DEFAULT_MAX_TOKENS,
    EmptyResponseError,
    LLMProvider,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
    QuotaExceededError,
    SafetyBlockError,
)

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH: Final[Path] = Path("data/logs/llm_calls.jsonl")
DEFAULT_BACKOFF_BASE: Final[float] = 1.0  # seconds

SAFETY_SETTINGS: Final[dict[HarmCategory, HarmBlockThreshold]] = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}


class GeminiProvider(LLMProvider):
    """Async Gemini adapter with retry + JSONL audit log."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 3,
        log_path: Path | None = None,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")

        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.log_path = log_path if log_path is not None else DEFAULT_LOG_PATH
        self.backoff_base = backoff_base

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model,
            safety_settings=SAFETY_SETTINGS,
        )

    @classmethod
    def from_settings(cls, log_path: Path | None = None) -> GeminiProvider:
        """Build provider from cached `Settings` (env-driven)."""
        s = get_settings()
        return cls(
            api_key=s.gemini_api_key.get_secret_value(),
            model=s.gemini_model,
            timeout=float(s.request_timeout),
            max_retries=s.max_retries,
            log_path=log_path,
        )

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderResponse:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        generation_config = {"max_output_tokens": max_tokens}

        last_error: ProviderError | None = None
        for attempt in range(1, self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    self._model.generate_content_async(
                        full_prompt,
                        generation_config=generation_config,
                    ),
                    timeout=self.timeout,
                )
            except TimeoutError as e:
                last_error = ProviderTimeoutError(f"Gemini call exceeded {self.timeout}s")
                self._log("timeout", attempt, time.perf_counter() - t0, 0, None)
                logger.warning("Gemini timeout (attempt %d/%d): %s", attempt, self.max_retries, e)
            except gax.ResourceExhausted as e:
                last_error = QuotaExceededError(str(e))
                self._log("quota_exceeded", attempt, time.perf_counter() - t0, 0, None)
                logger.warning("Gemini quota exceeded (attempt %d/%d)", attempt, self.max_retries)
            except gax.DeadlineExceeded as e:
                last_error = ProviderTimeoutError(str(e))
                self._log("deadline", attempt, time.perf_counter() - t0, 0, None)
            except gax.GoogleAPIError as e:
                last_error = ProviderError(f"{type(e).__name__}: {e}")
                self._log("api_error", attempt, time.perf_counter() - t0, 0, None)
                logger.warning("Gemini API error (attempt %d): %s", attempt, e)
            else:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                try:
                    return self._build_response(response, latency_ms, attempt)
                except SafetyBlockError:
                    raise  # not retryable
                except EmptyResponseError as e:
                    last_error = e
                    # fall through to retry

            if attempt < self.max_retries:
                await asyncio.sleep(self.backoff_base * (2 ** (attempt - 1)))

        assert last_error is not None
        raise last_error

    def _build_response(
        self, response: object, latency_ms: float, attempt: int
    ) -> ProviderResponse:
        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
        if block_reason:
            self._log("safety_block_prompt", attempt, latency_ms / 1000.0, 0, str(block_reason))
            raise SafetyBlockError(f"Prompt blocked by safety filter: {block_reason}")

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            self._log("no_candidates", attempt, latency_ms / 1000.0, 0, None)
            raise EmptyResponseError("Gemini returned no candidates")

        cand = candidates[0]
        finish_reason = _finish_reason_label(getattr(cand, "finish_reason", None))
        text = _extract_text(response, cand)
        if not text:
            self._log("empty_text", attempt, latency_ms / 1000.0, 0, finish_reason)
            raise EmptyResponseError(f"Gemini returned empty text (finish={finish_reason})")

        tokens = _extract_token_count(response)
        self._log("ok", attempt, latency_ms / 1000.0, tokens, finish_reason)
        return ProviderResponse(
            text=text,
            tokens_used=tokens,
            model=self.model_name,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )

    def _log(
        self,
        status: str,
        attempt: int,
        elapsed_s: float,
        tokens: int,
        finish_reason: str | None,
    ) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "provider": self.name,
            "model": self.model_name,
            "status": status,
            "attempt": attempt,
            "latency_s": round(elapsed_s, 3),
            "tokens": tokens,
            "finish_reason": finish_reason,
            "api_key": mask_key(self.api_key),
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("Failed to write LLM log: %s", e)


def _finish_reason_label(raw: object) -> str:
    if raw is None:
        return "unknown"
    name = getattr(raw, "name", None)
    if isinstance(name, str):
        return name.lower()
    return str(raw).split(".")[-1].lower()


def _extract_text(response: object, candidate: object) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []
    pieces = [getattr(p, "text", "") for p in parts]
    return "".join(p for p in pieces if isinstance(p, str))


def _extract_token_count(response: object) -> int:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0
    return int(getattr(usage, "total_token_count", 0) or 0)
