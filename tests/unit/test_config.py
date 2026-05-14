"""Unit tests for trilex.config."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from trilex.config import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    Settings,
    mask_key,
)

ENV_VARS = ("GEMINI_API_KEY", "FALLBACK_KEY_1", "FALLBACK_KEY_2", "GEMINI_MODEL")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _write_env(path: Path, body: str) -> Path:
    env = path / ".env"
    env.write_text(body, encoding="utf-8")
    return env


def test_mask_key_normal_length() -> None:
    assert mask_key("AIzaSy1234567890abcdefXYZ") == "AIzaSy...defXYZ"


def test_mask_key_short_returns_stars() -> None:
    assert mask_key("short") == "*****"


def test_mask_key_empty_returns_placeholder() -> None:
    assert mask_key("") == "(empty)"


def test_settings_load_primary_and_one_fallback(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(
        tmp_path,
        "GEMINI_API_KEY=AIzaPRIMARY\nFALLBACK_KEY_1=AIzaFB1\n",
    )
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.gemini_api_key.get_secret_value() == "AIzaPRIMARY"
    assert s.fallback_key_1 is not None
    assert s.fallback_key_1.get_secret_value() == "AIzaFB1"
    assert s.fallback_key_2 is None
    assert s.gemini_model == DEFAULT_GEMINI_MODEL
    assert s.request_timeout == DEFAULT_REQUEST_TIMEOUT
    assert s.max_retries == DEFAULT_MAX_RETRIES


def test_empty_fallback_key_coerced_to_none(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(
        tmp_path,
        "GEMINI_API_KEY=primary\nFALLBACK_KEY_1=\nFALLBACK_KEY_2=   \n",
    )
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.fallback_key_1 is None
    assert s.fallback_key_2 is None


def test_empty_primary_raises(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(tmp_path, "GEMINI_API_KEY=\n")
    with pytest.raises(ValidationError):
        Settings(_env_file=env)  # type: ignore[call-arg]


def test_missing_primary_raises(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(tmp_path, "FALLBACK_KEY_1=fb1\n")
    with pytest.raises(ValidationError):
        Settings(_env_file=env)  # type: ignore[call-arg]


def test_empty_model_falls_back_to_default(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(tmp_path, "GEMINI_API_KEY=primary\nGEMINI_MODEL=\n")
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.gemini_model == DEFAULT_GEMINI_MODEL


def test_explicit_model_overrides_default(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(
        tmp_path,
        "GEMINI_API_KEY=primary\nGEMINI_MODEL=gemini-2.5-pro\n",
    )
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.gemini_model == "gemini-2.5-pro"


def test_all_keys_returns_primary_plus_fallbacks_in_order(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(
        tmp_path,
        "GEMINI_API_KEY=p\nFALLBACK_KEY_1=f1\nFALLBACK_KEY_2=f2\n",
    )
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    keys = [k.get_secret_value() for k in s.all_keys()]
    assert keys == ["p", "f1", "f2"]


def test_secret_str_repr_does_not_leak(tmp_path: Path, clean_env: None) -> None:
    env = _write_env(tmp_path, "GEMINI_API_KEY=AIzaSECRET12345\n")
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert "AIzaSECRET12345" not in repr(s)
    assert "AIzaSECRET12345" not in str(s.gemini_api_key)
