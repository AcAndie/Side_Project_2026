"""
src/littrans/ui/env_utils.py — .env helpers and novel selector utilities.
Extracted from app.py (Batch 7).
"""
from __future__ import annotations

from pathlib import Path

_ROOT     = Path(__file__).resolve().parents[3]
_ENV_PATH = _ROOT / ".env"


def _load_env() -> dict[str, str]:
    try:
        from dotenv import dotenv_values
        return {k: (v or "") for k, v in dotenv_values(str(_ENV_PATH)).items()}
    except Exception:
        return {}


def _save_env(updates: dict[str, str]) -> None:
    try:
        from dotenv import set_key
        if not _ENV_PATH.exists():
            _ENV_PATH.write_text("")
        for k, v in updates.items():
            set_key(str(_ENV_PATH), k, v)
    except Exception as exc:
        raise RuntimeError(f"Không thể lưu .env: {exc}") from exc


def _has_api_key() -> bool:
    return bool(_load_env().get("GEMINI_API_KEY", "").strip())


def _get_available_novels() -> list[str]:
    try:
        from littrans.config.settings import get_available_novels
        return get_available_novels()
    except Exception:
        inp = _ROOT / "inputs"
        if not inp.exists():
            return []
        return sorted([
            d.name for d in inp.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            and any(f.suffix in (".txt", ".md") for f in d.iterdir())
        ])


def _apply_novel(name: str) -> None:
    from littrans.config.settings import set_novel
    from littrans.ui.loaders import load_chapters, load_stats, load_characters, load_glossary_data
    set_novel(name)
    for fn in [load_chapters, load_stats, load_characters, load_glossary_data]:
        fn.clear()
