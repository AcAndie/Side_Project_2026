"""
src/littrans/context/base.py — BaseManager: skeleton chung cho JSON-backed managers.

Cung cấp:
  - Thread-safe load/save qua self._lock
  - atomic write thông qua save_json (đã dùng atomic_write bên trong)
  - ensure_dir() tạo thư mục cha nếu cần
  - Interface abstract _empty_db() và stats()

Subclasses hiện tại:
  SkillsManager   → managers/skills.py
  (GlossaryManager, CharacterManager — tương lai nếu cần)

Public API của mỗi manager vẫn là module-level functions →
  call-sites trong pipeline.py, scout.py, prompt_builder.py KHÔNG đổi.

[v1.0] Phase 4 refactor
"""
from __future__ import annotations

import threading
from pathlib import Path

from littrans.utils.io_utils import load_json, save_json


class BaseManager:
    """
    Skeleton thread-safe cho managers dùng single-file JSON storage.

    Subclass chỉ cần:
      1. Gọi super().__init__(filepath) trong __init__
      2. Implement _empty_db() → dict
      3. Implement stats() → dict[str, int]
      4. Viết domain logic dùng self._lock, self._load_locked(), self._save()
    """

    def __init__(self, filepath: Path) -> None:
        self._path = filepath
        self._lock = threading.Lock()

    # ── Storage ───────────────────────────────────────────────────

    def _load(self) -> dict:
        """Load từ disk (không cần lock). Dùng khi chỉ đọc."""
        data = load_json(self._path)
        return data if data else self._empty_db()

    def _load_locked(self) -> dict:
        """
        Load từ disk bên trong lock đang giữ.
        Dùng trong pattern read-modify-write:

            with self._lock:
                data = self._load_locked()
                data["key"] = value
                self._save(data)
        """
        data = load_json(self._path)
        return data if data else self._empty_db()

    def _save(self, data: dict) -> None:
        """Ghi nguyên tử xuống disk (gọi save_json → atomic_write bên trong)."""
        save_json(self._path, data)

    def ensure_dir(self) -> None:
        """Tạo thư mục cha nếu chưa tồn tại."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ── Interface buộc subclass implement ────────────────────────

    def _empty_db(self) -> dict:
        """Trả về dict mặc định khi file chưa tồn tại hoặc rỗng."""
        raise NotImplementedError(
            f"{type(self).__name__} phải implement _empty_db()"
        )

    def stats(self) -> dict[str, int]:
        """Thống kê nhanh — dùng bởi CLI `stats` và UI sidebar."""
        raise NotImplementedError(
            f"{type(self).__name__} phải implement stats()"
        )