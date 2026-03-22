"""
src/littrans/managers/glossary.py — Glossary phân category + Aho-Corasick filter.

5 file category + 1 staging:
  Glossary_Pathways.md      Glossary_Organizations.md   Glossary_Items.md
  Glossary_Locations.md     Glossary_General.md          Staging_Terms.md

[v4 FIX] Aho-Corasick cache key bao gồm max_mtime → tự invalidate khi file thay đổi.
[v4.3 FIX] Không làm tròn mtime — tránh cache stale khi file được ghi trong cùng 1 giây.
[v4.4] Thêm existing_terms_set() public — dùng bởi Scout Glossary Suggest.
[v4.5 FIX] _append_staging dùng atomic_write thay vì open("a") → tránh corrupt file khi crash.
[v4.5 FIX] _get_automaton dùng content hash (size + mtime_ns) thay vì mtime float
           → đáng tin hơn trên Docker/Windows mount và filesystem độ phân giải thấp.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import logging

from littrans.config.settings import settings
from littrans.utils.io_utils import load_text, atomic_write

try:
    import ahocorasick
    _AHO = True
except ImportError:
    _AHO = False

_lock         = threading.Lock()
_aho_cache: dict = {}
_aho_lock     = threading.Lock()
_AHO_CACHE_MAX = 5
_NEW_SECTION  = "Mới — chờ phân loại"


# ── Parse ────────────────────────────────────────────────────────

def _parse(text: str) -> dict[str, str]:
    """text → {term_lower: original_line}"""
    terms: dict[str, str] = {}
    for line in text.splitlines():
        clean = re.sub(r"^[\*\-\+]\s*", "", line.strip())
        if ":" in clean and not clean.startswith("#"):
            eng = clean.split(":", 1)[0].strip()
            if eng:
                terms[eng.lower()] = line
    return terms


def _load_all() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for cat, path in settings.glossary_files.items():
        result[cat] = _parse(load_text(path))
    result["staging"] = _parse(load_text(settings.staging_terms_file))
    return result


# ── Filter ───────────────────────────────────────────────────────

def filter_glossary(chapter_text: str) -> dict[str, list[str]]:
    """
    Trả về {category: [lines]} chỉ gồm term XUẤT HIỆN trong chapter_text.
    """
    all_terms  = _load_all()
    text_lower = chapter_text.lower()

    flat: dict[str, tuple[str, str]] = {}
    for cat, terms in all_terms.items():
        for t, line in terms.items():
            if t not in flat:
                flat[t] = (cat, line)

    if not flat:
        return {}

    matched: dict[str, list[str]] = {}

    if _AHO:
        auto = _get_automaton(flat)
        for end_idx, (term, (cat, line)) in auto.iter(text_lower):
            start  = end_idx - len(term) + 1
            before = text_lower[start - 1] if start > 0 else " "
            after  = text_lower[end_idx + 1] if end_idx + 1 < len(text_lower) else " "
            if len(term) <= 1 or (not before.isalnum() and not after.isalnum()):
                _add(matched, cat, line)
    else:
        for term, (cat, line) in flat.items():
            try:
                hit = bool(re.search(rf"\b{re.escape(term)}\b", text_lower))
            except re.error:
                hit = term in text_lower
            if hit:
                _add(matched, cat, line)

    return matched


def _add(d: dict, cat: str, line: str) -> None:
    d.setdefault(cat, [])
    if line not in d[cat]:
        d[cat].append(line)


# ── Content hash cho cache invalidation ──────────────────────────

def _get_content_hash() -> str:
    """
    Hash dựa trên (file_size + mtime_ns) của tất cả glossary files.
    Nhanh hơn đọc toàn bộ nội dung, nhưng đáng tin hơn mtime float đơn thuần.
    Chỉ khi cả size lẫn mtime_ns đều không đổi thì mới có thể false-positive,
    xác suất gần như bằng 0 trong thực tế.
    """
    all_paths = list(settings.glossary_files.values()) + [settings.staging_terms_file]
    hasher    = hashlib.md5()
    for p in sorted(all_paths, key=str):
        try:
            if p.exists():
                stat = p.stat()
                hasher.update(
                    f"{p.name}:{stat.st_size}:{stat.st_mtime_ns}".encode()
                )
            else:
                hasher.update(f"{p.name}:missing".encode())
        except OSError:
            hasher.update(f"{p.name}:error".encode())
    return hasher.hexdigest()


def _get_automaton(flat: dict):
    # [FIX v4.5] Dùng content hash thay vì mtime float.
    # mtime float không đáng tin trên Docker volume, Windows mount, hoặc
    # khi file được ghi và đọc trong cùng một phần nhỏ của giây.
    cache_key = hash((frozenset(flat.keys()), _get_content_hash()))

    with _aho_lock:
        if cache_key in _aho_cache:
            return _aho_cache[cache_key]

        A = ahocorasick.Automaton()
        for t, payload in flat.items():
            A.add_word(t, (t, payload))
        A.make_automaton()

        if len(_aho_cache) >= _AHO_CACHE_MAX:
            oldest_key = next(iter(_aho_cache))
            del _aho_cache[oldest_key]

        _aho_cache[cache_key] = A
        return A


# ── Public helper for Scout Glossary Suggest ─────────────────────

def existing_terms_set() -> set[str]:
    """
    Trả về set tất cả terms đã có (lowercase) từ mọi glossary file + staging.
    Dùng bởi Scout Glossary Suggest để dedup trước khi đề xuất.
    """
    found: set[str] = set()
    for terms in _load_all().values():
        found.update(terms.keys())  # keys đã là lowercase từ _parse()
    return found


# ── Write ────────────────────────────────────────────────────────

def add_new_terms(new_terms: list, source_chapter: str) -> int:
    """
    Ghi thuật ngữ mới (thread-safe).
    IMMEDIATE_MERGE=true  → ghi thẳng vào category file
    IMMEDIATE_MERGE=false → ghi vào Staging_Terms.md
    """
    if not new_terms:
        return 0

    with _lock:
        existing: set[str] = set()
        for terms in _load_all().values():
            existing.update(terms.keys())

        by_cat: dict[str, list[str]] = {}
        for term in new_terms:
            eng = term.english.strip()
            vie = term.vietnamese.strip()
            cat = getattr(term, "category", "general")
            if cat not in settings.glossary_files:
                cat = "general"
            if eng and eng.lower() not in existing:
                by_cat.setdefault(cat, []).append(f"- {eng}: {vie}")
                existing.add(eng.lower())

        if not by_cat:
            return 0

        total = 0
        if settings.immediate_merge:
            for cat, lines in by_cat.items():
                _append_to_file(settings.glossary_files[cat], lines)
                total += len(lines)
        else:
            all_lines = [l for lines in by_cat.values() for l in lines]
            _append_staging(all_lines, source_chapter)
            total = len(all_lines)

    return total


def _append_to_file(path, lines: list[str]) -> None:
    content = load_text(path)
    block   = "\n".join(lines)
    if f"## {_NEW_SECTION}" in content:
        content = content.rstrip("\n") + f"\n{block}\n"
    else:
        content = content.rstrip("\n") + f"\n\n## {_NEW_SECTION}\n{block}\n"
    atomic_write(path, content)


def _append_staging(lines: list[str], source: str) -> None:
    """
    [FIX v4.5] Dùng atomic_write thay vì open("a").
    Tránh corrupt file nếu process bị kill giữa chừng.
    Pattern: đọc toàn bộ → nối chuỗi → ghi nguyên tử.
    """
    existing = load_text(settings.staging_terms_file)
    block    = f"\n## Từ chương: {source}\n" + "".join(l + "\n" for l in lines)
    if not existing.strip():
        block = "# Staging Terms\n\n" + block
    atomic_write(settings.staging_terms_file, existing + block)


# ── Stats ────────────────────────────────────────────────────────

def has_pending_terms() -> bool:
    return bool(load_text(settings.staging_terms_file).strip())


def count_pending_terms() -> int:
    return load_text(settings.staging_terms_file).count("\n- ")


def glossary_stats() -> dict[str, int]:
    return {cat: len(terms) for cat, terms in _load_all().items()}