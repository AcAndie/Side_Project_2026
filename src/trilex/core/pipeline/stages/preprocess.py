"""Pre-process stage — clean junk + normalize whitespace before QT pass.

Web-scraped chapters routinely carry: site footers, ad links, anti-scraper
markers (`本章未完`, `更多精彩内容`), zero-width chars, BOMs, and inconsistent
line endings. Strip them once here so downstream stages see clean text.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

_JUNK_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"https?://\S+"),
    re.compile(r"www\.[\w.-]+\.(?:com|net|org|cn|vn)\S*", re.IGNORECASE),
    re.compile(r"(?:本章未完|未完待续|更多精彩内容|本小章还未完|页继续阅读)[^\n]*"),
    re.compile(r"〔[^〕]*〕"),
    re.compile(r"［[^］]*］"),
    re.compile(r"^[\s　]*[\*]{3,}[\s　]*$", re.MULTILINE),
)

_ZERO_WIDTH_RE: Final[re.Pattern[str]] = re.compile(r"[​‌‍﻿⁠]")


def preprocess(text: str) -> tuple[str, list[str]]:
    """Return cleaned text and a list of warning tags."""
    warnings: list[str] = []
    if not text:
        return "", ["empty_input"]

    out = unicodedata.normalize("NFC", text)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    out = _ZERO_WIDTH_RE.sub("", out)

    junk_count = 0
    for pat in _JUNK_PATTERNS:
        out, n = pat.subn("", out)
        junk_count += n
    if junk_count:
        warnings.append(f"stripped_junk:{junk_count}")

    # collapse 3+ blank lines, trim trailing whitespace per line
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.strip()

    if not out:
        warnings.append("empty_after_preprocess")
    return out, warnings
