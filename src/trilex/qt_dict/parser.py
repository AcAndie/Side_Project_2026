"""QuickTranslator dictionary parser.

Reads QT-format .txt dictionaries (VietPhrase, Names, LuatNhan, ChinesePhienAm,
Pronouns, ...) into typed QTDictionary objects. Read-only; never modifies sources.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

ENCODING_FALLBACKS: Final[tuple[str, ...]] = ("utf-8-sig", "utf-16", "gbk")
SEPARATOR_CANDIDATES: Final[tuple[str, ...]] = (";", "/")
DEFAULT_SEPARATOR: Final[str] = ";"
SEPARATOR_SAMPLE_SIZE: Final[int] = 1000
COMMENT_PREFIX: Final[str] = "#"


class QTParseError(Exception):
    """Raised when a QT dictionary file cannot be decoded with any fallback."""


class QTDictMeta(BaseModel):
    """Metadata about a parsed QT dictionary."""

    model_config = ConfigDict(frozen=True)

    source: Path
    count: int
    separator: str
    encoding: str
    skipped_lines: int


class QTDictionary(BaseModel):
    """Parsed QT dictionary.

    `entries` maps a Chinese (or pattern) key to one or more Vietnamese meanings.
    Order of meanings preserved from source file.
    """

    model_config = ConfigDict(frozen=True)

    entries: dict[str, list[str]]
    meta: QTDictMeta

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, key: object) -> bool:
        return key in self.entries


def _read_text(path: Path) -> tuple[str, str]:
    """Read file, trying encodings in fallback order. Returns (text, encoding)."""
    raw = path.read_bytes()
    for enc in ENCODING_FALLBACKS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise QTParseError(f"Cannot decode {path} with any of {ENCODING_FALLBACKS}")


def _detect_separator(lines: list[str]) -> str:
    """Pick whichever of `;` or `/` appears most in value-side of sample lines."""
    counts = dict.fromkeys(SEPARATOR_CANDIDATES, 0)
    sampled = 0
    for raw in lines:
        if sampled >= SEPARATOR_SAMPLE_SIZE:
            break
        line = raw.strip()
        if not line or line.startswith(COMMENT_PREFIX) or "=" not in line:
            continue
        _, _, value = line.partition("=")
        for sep in SEPARATOR_CANDIDATES:
            counts[sep] += value.count(sep)
        sampled += 1
    winner = max(counts, key=lambda s: counts[s])
    return winner if counts[winner] > 0 else DEFAULT_SEPARATOR


def parse_qt_dict(path: Path | str) -> QTDictionary:
    """Parse a QT-format dictionary file into a QTDictionary.

    Skips blank lines and comments (lines starting with `#`).
    Logs WARNING for malformed entries (no `=`, empty key/value) and continues.
    Auto-detects separator (`;` vs `/`) from the file's own content.
    """
    path = Path(path)
    text, encoding = _read_text(path)
    lines = text.splitlines()
    separator = _detect_separator(lines)

    entries: dict[str, list[str]] = {}
    skipped = 0

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith(COMMENT_PREFIX):
            continue

        if "=" not in line:
            logger.warning("%s:%d skipped (no '='): %r", path.name, lineno, line[:80])
            skipped += 1
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if not key or not value:
            logger.warning(
                "%s:%d skipped (empty key/value): %r",
                path.name,
                lineno,
                line[:80],
            )
            skipped += 1
            continue

        meanings = [m.strip() for m in value.split(separator) if m.strip()]
        if not meanings:
            skipped += 1
            continue
        entries[key] = meanings

    meta = QTDictMeta(
        source=path,
        count=len(entries),
        separator=separator,
        encoding=encoding,
        skipped_lines=skipped,
    )
    return QTDictionary(entries=entries, meta=meta)
