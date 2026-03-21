"""
src/littrans/llm/client.py — Gemini API client + Multi-Key Pool + Anthropic dispatcher.

ApiKeyPool quản lý nhiều Gemini API key.
Call functions:
  call_gemini()             → structured JSON (TranslationResult) — flow cũ
  call_translation()        → ★ MỚI: dispatcher tự chọn Gemini/Anthropic theo settings
  call_gemini_translation() → plain text — Gemini (vẫn giữ để backward compat)
  call_anthropic_translation() → plain text — Claude (mới v4.5)
  call_gemini_text()        → plain text tự do (Scout, Arc Memory)
  call_gemini_json()        → free JSON (Emotion, Glossary, Pre-call, Post-call)

[v4.5] Dual-Model support:
  - Anthropic SDK lazy-imported (không crash nếu chưa cài khi dùng gemini-only)
  - call_translation() là entry point duy nhất mà pipeline nên gọi
  - Retry logic và rate-limit handling nhất quán cho cả 2 provider
"""
from __future__ import annotations

import re
import json
import logging
import threading
from pydantic import ValidationError
from google import genai
from google.genai import types

from littrans.config.settings import settings
from littrans.llm.schemas import TranslationResult, GEMINI_SCHEMA


# ═══════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════

class AllKeysExhaustedError(Exception):
    """Tất cả API key đều hết quota."""


# ═══════════════════════════════════════════════════════════════════
# API KEY POOL (Gemini)
# ═══════════════════════════════════════════════════════════════════

class ApiKeyPool:
    """Thread-safe pool quản lý nhiều Gemini API key."""

    def __init__(self, api_keys: list[str], rotate_threshold: int = 3) -> None:
        if not api_keys:
            raise ValueError("Cần ít nhất 1 API key")
        self._keys      = api_keys
        self._threshold = rotate_threshold
        self._idx       = 0
        self._errors    = {k: 0 for k in api_keys}
        self._dead      = {k: False for k in api_keys}
        self._lock      = threading.Lock()
        self._clients   = {k: genai.Client(api_key=k) for k in api_keys}

    @property
    def current_key(self) -> str:
        return self._keys[self._idx]

    @property
    def current_client(self) -> genai.Client:
        return self._clients[self.current_key]

    def on_success(self) -> None:
        with self._lock:
            self._errors[self.current_key] = 0

    def on_rate_limit(self) -> None:
        with self._lock:
            key = self.current_key
            self._errors[key] += 1
            if self._errors[key] > self._threshold:
                self._dead[key] = True
                logging.warning(f"[ApiKeyPool] Key #{self._idx} đạt ngưỡng lỗi — rotate")
                self._rotate()

    def _rotate(self) -> None:
        n = len(self._keys)
        for _ in range(n):
            self._idx = (self._idx + 1) % n
            if not self._dead[self._keys[self._idx]]:
                print(f"  🔄 API Key rotate → key #{self._idx + 1}/{n}")
                return
        raise AllKeysExhaustedError(
            f"Tất cả {n} API key đều hết quota. "
            "Nghỉ rồi thử lại hoặc thêm key mới vào .env."
        )

    def stats(self) -> dict:
        return {
            "total_keys"  : len(self._keys),
            "active_idx"  : self._idx,
            "error_counts": dict(self._errors),
            "dead_keys"   : sum(1 for v in self._dead.values() if v),
        }


# Singleton Gemini pool
key_pool = ApiKeyPool(settings.gemini_api_keys, rotate_threshold=settings.key_rotate_threshold)


# ═══════════════════════════════════════════════════════════════════
# ANTHROPIC CLIENT (lazy init)
# ═══════════════════════════════════════════════════════════════════

_anthropic_client = None
_anthropic_lock   = threading.Lock()


def _get_anthropic_client():
    """
    Lazy-init Anthropic client.
    Không import lúc module load để tránh crash khi chưa cài anthropic SDK.
    """
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    with _anthropic_lock:
        if _anthropic_client is not None:
            return _anthropic_client
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "❌ Cần cài anthropic SDK: pip install anthropic\n"
                "   Hoặc: pip install 'littrans[anthropic]'"
            )
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return _anthropic_client


# ═══════════════════════════════════════════════════════════════════
# PUBLIC — DISPATCHER (entry point cho pipeline)
# ═══════════════════════════════════════════════════════════════════

def call_translation(system_prompt: str, chapter_text: str) -> str:
    """
    ★ Entry point chính cho Trans-call (3-call flow).

    Tự động dispatch sang Gemini hoặc Anthropic dựa trên
    settings.translation_provider và settings.translation_model.

    Pipeline LUÔN dùng hàm này thay vì gọi thẳng call_gemini_translation()
    hay call_anthropic_translation().
    """
    if settings.using_anthropic:
        return call_anthropic_translation(system_prompt, chapter_text)
    else:
        return call_gemini_translation(system_prompt, chapter_text)


def translation_model_info() -> str:
    """
    Trả về chuỗi mô tả model đang dùng để in ra log.
    VD: "claude-sonnet-4-6 (anthropic)" hoặc "gemini-2.0-flash-exp (gemini)"
    """
    return f"{settings.translation_model} ({settings.translation_provider})"


# ═══════════════════════════════════════════════════════════════════
# PUBLIC CALL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def call_gemini(system_prompt: str, chapter_text: str) -> TranslationResult:
    """
    Flow cũ — Gọi Gemini với structured output → TranslationResult.
    Giữ nguyên để backward compatible khi USE_THREE_CALL=false.
    """
    response = key_pool.current_client.models.generate_content(
        model=settings.gemini_model,
        contents=chapter_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
            response_schema=GEMINI_SCHEMA,
            response_mime_type="application/json",
        ),
    )

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        u = response.usage_metadata
        _log_tokens(
            getattr(u, "prompt_token_count", "?"),
            getattr(u, "candidates_token_count", "?"),
            getattr(u, "total_token_count", "?"),
        )

    result = _parse_response(response)
    key_pool.on_success()
    return result


def call_gemini_translation(system_prompt: str, chapter_text: str) -> str:
    """
    Gemini Trans-call — plain text output.
    Dùng settings.translation_model nếu provider là gemini,
    fallback về settings.gemini_model nếu không.
    """
    model = (
        settings.translation_model
        if settings.translation_provider == "gemini"
        else settings.gemini_model
    )
    response = key_pool.current_client.models.generate_content(
        model=model,
        contents=chapter_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
        ),
    )

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        u = response.usage_metadata
        _log_tokens(
            getattr(u, "prompt_token_count", "?"),
            getattr(u, "candidates_token_count", "?"),
            getattr(u, "total_token_count", "?"),
        )

    text = response.text or ""
    if not text.strip():
        raise ValueError("Translation call trả về text rỗng.")

    key_pool.on_success()
    return text


def call_anthropic_translation(system_prompt: str, chapter_text: str) -> str:
    """
    Anthropic (Claude) Trans-call — plain text output.

    Đặc điểm so với Gemini:
      - system_prompt đi vào `system` param (không phải system_instruction)
      - chapter_text đi vào messages[user]
      - Temperature mặc định 1.0 cho Claude (khuyến nghị của Anthropic)
      - Không dùng structured output — plain text như Gemini translation call

    Raise exception khi thất bại — caller quyết định retry.
    """
    client = _get_anthropic_client()
    model  = settings.translation_model

    response = client.messages.create(
        model=model,
        max_tokens=8096,
        temperature=1,          # Anthropic khuyến nghị temp=1 cho Claude 3+
        system=system_prompt,
        messages=[
            {"role": "user", "content": chapter_text}
        ],
    )

    # Log token usage
    if hasattr(response, "usage") and response.usage:
        u = response.usage
        _log_tokens(
            getattr(u, "input_tokens", "?"),
            getattr(u, "output_tokens", "?"),
            "—",                # Anthropic không trả total riêng
        )

    # Extract text từ content blocks
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    if not text.strip():
        raise ValueError("Anthropic translation call trả về text rỗng.")

    return text


def call_gemini_text(system_prompt: str, user_text: str) -> str:
    """Scout, Arc Memory — plain text, luôn dùng Gemini."""
    response = key_pool.current_client.models.generate_content(
        model=settings.gemini_model,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )
    key_pool.on_success()
    return response.text or ""


def call_gemini_json(system_prompt: str, user_text: str) -> dict:
    """
    Emotion Tracker, clean_glossary, Pre-call, Post-call — JSON tự do.
    Luôn dùng Gemini (không dispatch sang Anthropic).
    """
    response = key_pool.current_client.models.generate_content(
        model=settings.gemini_model,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    key_pool.on_success()
    raw   = response.text or "{}"
    clean = re.sub(r"^```json\s*|```\s*$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(clean)


# ═══════════════════════════════════════════════════════════════════
# ERROR HELPERS
# ═══════════════════════════════════════════════════════════════════

def is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in ("429", "rate limit", "quota", "resource_exhausted",
                                   "overloaded", "529"))  # 529 = Anthropic overload


def handle_api_error(exc: Exception) -> None:
    """Gọi từ pipeline khi gặp exception."""
    if is_rate_limit(exc):
        # Chỉ rotate Gemini key pool — Anthropic dùng key đơn, không có pool
        if not settings.using_anthropic:
            key_pool.on_rate_limit()


# ═══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════

def _parse_response(response) -> TranslationResult:
    if response.parsed is not None:
        p = response.parsed
        if isinstance(p, TranslationResult) and p.translation.strip():
            return p

    raw  = response.text or ""
    text = re.sub(r"^```json\s*|```\s*$", "", raw.strip(), flags=re.MULTILINE)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON không hợp lệ: {e}\n[300 ký đầu]: {raw[:300]}")

    try:
        result = TranslationResult.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Response không khớp schema: {e}")

    if not result.translation.strip():
        raise ValueError("Bản dịch rỗng sau parse.")

    return result


def _log_tokens(inp, out, total) -> None:
    try:
        from tqdm import tqdm
        tqdm.write(f"  📊 Tokens — input: {inp} | output: {out} | total: {total}")
    except Exception:
        print(f"  📊 Tokens — input: {inp} | output: {out} | total: {total}")