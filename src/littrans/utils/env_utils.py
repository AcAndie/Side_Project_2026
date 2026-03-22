"""
src/littrans/utils/env_utils.py — Đọc/ghi file .env.

Tách ra từ app.py để dùng chung nếu cần từ nhiều module.

[v1.0] Phase 5.2 refactor
"""
from __future__ import annotations

from pathlib import Path

# Đường dẫn mặc định — root của project
_DEFAULT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def load_env(env_path: Path | None = None) -> dict[str, str]:
    """Đọc file .env → dict. Trả về {} nếu file không tồn tại hoặc lỗi."""
    path = env_path or _DEFAULT_ENV_PATH
    try:
        from dotenv import dotenv_values
        return {k: (v or "") for k, v in dotenv_values(str(path)).items()}
    except Exception:
        return {}


def save_env(updates: dict[str, str], env_path: Path | None = None) -> None:
    """
    Ghi/cập nhật các key vào file .env.
    Tạo file mới nếu chưa tồn tại.
    Raise RuntimeError nếu không ghi được.
    """
    path = env_path or _DEFAULT_ENV_PATH
    try:
        from dotenv import set_key
        if not path.exists():
            path.write_text("")
        for k, v in updates.items():
            set_key(str(path), k, v)
    except Exception as exc:
        raise RuntimeError(f"Không thể lưu .env ({path}): {exc}") from exc