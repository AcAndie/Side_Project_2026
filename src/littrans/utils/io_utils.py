"""
src/littrans/utils/io_utils.py — Đọc/ghi file an toàn.

Atomic write (tempfile → os.replace) tránh corrupt khi bị kill giữa chừng.

Helpers:
  safe_list(v)  → v nếu là list, ngược lại []
  safe_dict(v)  → v nếu là dict, ngược lại {}
"""
from __future__ import annotations

import os
import json
import logging
import tempfile
from pathlib import Path


def load_text(filepath: str | Path) -> str:
    fp = str(filepath)
    if not os.path.exists(fp):
        return ""
    with open(fp, "r", encoding="utf-8") as f:
        return f.read()


def load_json(filepath: str | Path) -> dict:
    raw = load_text(filepath)
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logging.error(f"JSON lỗi '{filepath}': {e}")
        return {}


def load_json_safe(filepath: str | Path, default=None):
    """Load JSON with explicit default on missing file or parse error."""
    p = Path(filepath)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save_json(filepath: str | Path, data: dict) -> None:
    atomic_write(str(filepath), json.dumps(data, ensure_ascii=False, indent=2))


def safe_list(v) -> list:
    """Trả về v nếu là list, ngược lại trả về []."""
    return v if isinstance(v, list) else []


def safe_dict(v) -> dict:
    """Trả về v nếu là dict, ngược lại trả về {}."""
    return v if isinstance(v, dict) else {}


def atomic_write(filepath: str | Path, content: str) -> None:
    """Ghi file nguyên tử — không bao giờ để file ở trạng thái không đầy đủ."""
    fp      = str(filepath)
    dir_name = os.path.dirname(fp) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, fp)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise