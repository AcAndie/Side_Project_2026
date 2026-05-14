"""Post-process stage — punctuation + whitespace cleanup after LLM polish.

Run AFTER the polish stage (or after QT pass in convert-only mode). Handles:
  - Convert CJK punctuation to Latin equivalents (LLM sometimes echoes 「」 from
    examples).
  - Collapse runs of spaces.
  - Remove spaces before sentence-final punctuation (`, .`).
  - Normalize ellipsis variants → `…` or `...` consistently.
"""

from __future__ import annotations

import re
from typing import Final

_CJK_PUNCT_MAP: Final[dict[int, str]] = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "「": '"',
        "」": '"',
        "『": '"',
        "』": '"',
        "、": ",",
        "～": "~",
    }
)

_SPACE_BEFORE_PUNCT: Final[re.Pattern[str]] = re.compile(r"[ \t]+([,.;:!?…])")
_MULTI_SPACE: Final[re.Pattern[str]] = re.compile(r"[ \t]{2,}")
_MULTI_BLANK_LINE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")
_DOT_RUN: Final[re.Pattern[str]] = re.compile(r"\.{4,}")


def postprocess(text: str) -> tuple[str, list[str]]:
    """Return cleaned text and a list of warning tags."""
    if not text:
        return "", ["empty_input"]

    warnings: list[str] = []
    out = text.translate(_CJK_PUNCT_MAP)
    out = _DOT_RUN.sub("...", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = _MULTI_SPACE.sub(" ", out)
    out = _MULTI_BLANK_LINE.sub("\n\n", out)
    out = "\n".join(line.rstrip() for line in out.split("\n"))
    out = out.strip()

    if not out:
        warnings.append("empty_after_postprocess")
    return out, warnings
