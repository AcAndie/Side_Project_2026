"""Application configuration loaded from `.env` via pydantic-settings.

Secrets are wrapped in `SecretStr` so they cannot be accidentally leaked via
`repr()` or default `__str__`. Use `.get_secret_value()` only at the boundary
where the API call is made.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

DEFAULT_GEMINI_MODEL: Final[str] = "gemini-2.5-flash"
DEFAULT_REQUEST_TIMEOUT: Final[int] = 60
DEFAULT_MAX_RETRIES: Final[int] = 3


class Settings(BaseSettings):
    """Loads from `.env`. Use `get_settings()` for the cached singleton."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    gemini_api_key: SecretStr = Field(..., alias="GEMINI_API_KEY")
    fallback_key_1: SecretStr | None = Field(default=None, alias="FALLBACK_KEY_1")
    fallback_key_2: SecretStr | None = Field(default=None, alias="FALLBACK_KEY_2")

    gemini_model: str = Field(default=DEFAULT_GEMINI_MODEL, alias="GEMINI_MODEL")
    request_timeout: int = Field(default=DEFAULT_REQUEST_TIMEOUT)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES)

    @field_validator("fallback_key_1", "fallback_key_2", mode="before")
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("gemini_model", mode="before")
    @classmethod
    def _model_default_if_empty(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return DEFAULT_GEMINI_MODEL
        return v

    @field_validator("gemini_api_key", mode="after")
    @classmethod
    def _require_non_empty_primary(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("GEMINI_API_KEY must not be empty")
        return v

    def all_keys(self) -> list[SecretStr]:
        """Primary key first, then non-empty fallbacks in order."""
        keys: list[SecretStr] = [self.gemini_api_key]
        if self.fallback_key_1 is not None:
            keys.append(self.fallback_key_1)
        if self.fallback_key_2 is not None:
            keys.append(self.fallback_key_2)
        return keys


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton; loads `.env` once per process."""
    return Settings()  # type: ignore[call-arg]


def mask_key(key: str, head: int = 6, tail: int = 6) -> str:
    """Return `key` with its middle replaced by `...`. Never logs the full value."""
    if not key:
        return "(empty)"
    if len(key) <= head + tail:
        return "*" * len(key)
    return f"{key[:head]}...{key[-tail:]}"
