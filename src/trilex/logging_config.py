"""Application logging configuration with rotation.

Default layout:
  - Console handler at the requested level (INFO by default).
  - ``RotatingFileHandler`` writing to ``data/logs/trilex.log``:
    10 MB per file, 10 backups → ~110 MB hard cap on disk usage.

Per CLAUDE.md §8 the project forbids ``print`` for diagnostics; this module is
the canonical entrypoint for wiring ``logging``.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Final

DEFAULT_LOG_PATH: Final[Path] = Path("data/logs/trilex.log")
DEFAULT_MAX_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT: Final[int] = 10  # → up to 11 files on disk
DEFAULT_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(
    level: int | str = logging.INFO,
    *,
    log_path: Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    console: bool = True,
) -> Path:
    """Install console + rotating-file handlers on the root logger.

    Safe to call multiple times: existing handlers attached by this function
    are removed before re-installation so reconfiguring during a long-running
    process doesn't duplicate output.

    Returns the resolved log path so callers can echo it back to the user.
    """
    path = log_path if log_path is not None else DEFAULT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    # Drop any previously-attached handlers tagged by us.
    for h in list(root.handlers):
        if getattr(h, "_trilex_managed", False):
            root.removeHandler(h)

    root.setLevel(level)

    formatter = logging.Formatter(DEFAULT_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,  # don't open the file until the first emit
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler._trilex_managed = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        stream_handler._trilex_managed = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)

    return path
