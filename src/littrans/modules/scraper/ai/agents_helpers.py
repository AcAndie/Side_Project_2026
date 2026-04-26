"""
ai/agents_helpers.py — Shared helpers extracted from agents.py (Batch 7).

Contains: retry infrastructure, JSON parser, HTML helpers,
          conflict resolution, JSON schemas, sanitization helpers.
All ai_* agent functions remain in agents.py.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from littrans.modules.scraper.config import GEMINI_MODEL, GEMINI_FALLBACK_MODEL, RE_NEXT_BTN
from littrans.modules.scraper.ai.client import ai_client, AIRateLimiter
from littrans.utils.retry_utils import is_retriable


# ── Retry infrastructure ───────────────────────────────────────────────────────

_MAX_RETRIES   = 5
_RETRY_BACKOFF = [30, 60, 120, 240]
_AI_CALL_TIMEOUT = 90.0  # seconds per single AI call — prevents UI hang


def _fmt(e: Exception) -> str:
    return (str(e) or repr(e)).strip()


async def _call(
    prompt: str,
    limiter: AIRateLimiter,
    schema: dict[str, Any] | None = None,
    *,
    _use_fallback: bool = False,
) -> str | None:
    await limiter.acquire()
    model = GEMINI_FALLBACK_MODEL if _use_fallback else GEMINI_MODEL
    last_retriable_err: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            if schema:
                from google.genai import types as T
                config = T.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                )
                resp = await asyncio.wait_for(
                    ai_client.aio.models.generate_content(
                        model=model, contents=prompt, config=config,
                    ),
                    timeout=_AI_CALL_TIMEOUT,
                )
            else:
                resp = await asyncio.wait_for(
                    ai_client.aio.models.generate_content(
                        model=model, contents=prompt,
                    ),
                    timeout=_AI_CALL_TIMEOUT,
                )
            return resp.text
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError as e:
            is_last = attempt >= _MAX_RETRIES - 1
            last_retriable_err = e
            if not is_last:
                wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                suffix = f" [{model}]" if _use_fallback else ""
                print(
                    f"  [AI] ⏱ Timeout {_AI_CALL_TIMEOUT:.0f}s (lần {attempt+1}/{_MAX_RETRIES}){suffix},"
                    f" thử lại sau {wait}s",
                    flush=True,
                )
                await asyncio.sleep(wait)
        except Exception as e:
            is_last  = attempt >= _MAX_RETRIES - 1
            err_str  = _fmt(e).lower()
            if schema and ("response_schema" in err_str or "mime_type" in err_str):
                try:
                    resp = await asyncio.wait_for(
                        ai_client.aio.models.generate_content(
                            model=model, contents=prompt,
                        ),
                        timeout=_AI_CALL_TIMEOUT,
                    )
                    return resp.text
                except Exception:
                    return None
            if is_retriable(e):
                last_retriable_err = e
                if not is_last:
                    wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                    suffix = f" [{model}]" if _use_fallback else ""
                    print(
                        f"  [AI] ⚠ Retriable error (lần {attempt+1}/{_MAX_RETRIES}){suffix},"
                        f" thử lại sau {wait}s: {_fmt(e)[:80]}",
                        flush=True,
                    )
                    await asyncio.sleep(wait)
            else:
                raise

    if last_retriable_err is not None and not _use_fallback and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        print(
            f"  [AI] 🔄 Model chính ({GEMINI_MODEL}) hết retry → thử fallback ({GEMINI_FALLBACK_MODEL})...",
            flush=True,
        )
        return await _call(prompt, limiter, schema, _use_fallback=True)

    return None


# ── JSON parser ────────────────────────────────────────────────────────────────

def _parse(text: str | None) -> dict | list | None:
    """
    Parse JSON từ AI response text.
    P2-C: thay greedy regex bằng json.JSONDecoder.raw_decode().
    """
    if not text:
        return None

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for start_char, search_start in (("{", 0), ("[", 0)):
        pos = 0
        while True:
            idx = text.find(start_char, pos)
            if idx == -1:
                break
            try:
                obj, _ = decoder.raw_decode(text, idx)
                return obj
            except json.JSONDecodeError:
                pos = idx + 1

    return None


# ── HTML helpers ───────────────────────────────────────────────────────────────

def snippet(html: str, max_len: int = 10000) -> str:
    """
    Cắt HTML xuống max_len chars để gửi cho AI.
    P2-B: early-exit nếu html đã nhỏ hơn max_len.
    """
    if len(html) <= max_len:
        return html

    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all(["script", "style", "noscript"]):
        t.decompose()

    cleaned = str(soup)
    if len(cleaned) <= max_len:
        return cleaned

    return soup.get_text(separator="\n", strip=True)[:max_len]


_snippet = snippet


def _nav_hints(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    hints = [
        f"{a.get_text(strip=True)!r} → {urljoin(base_url, a['href'])}"
        for a in soup.find_all("a", href=True)
        if RE_NEXT_BTN.search(a.get_text(strip=True))
    ]
    return "\n".join(hints[:10]) or "(không có)"


_RE_CHAP_LINK = re.compile(
    r"/(chapter|chuong|chap|/c/|/ch/|episode|ep)[_\-]?\d+"
    r"|/s/\d+/\d+",
    re.IGNORECASE,
)
_RE_TOC_PATH = re.compile(
    r"/(chapters|chapter-list|table-of-contents|toc|contents)[/?#]?$",
    re.IGNORECASE,
)


def _chapter_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if _RE_TOC_PATH.search(href):
            continue
        if not _RE_CHAP_LINK.search(href):
            continue
        full = urljoin(base_url, href)
        if full not in seen:
            seen.add(full)
            links.append(full)
    return links


# ── Conflict resolution ────────────────────────────────────────────────────────

def _resolve_selector_conflict(
    result1: dict | None,
    result2: dict | None,
    field: str,
) -> tuple[str | None, bool]:
    v1 = (result1 or {}).get(field)
    v2 = (result2 or {}).get(field)
    if v1 == v2:
        return v1, False
    if not v1 and v2:
        return v2, False
    if v1 and not v2:
        return v1, False
    c1 = float((result1 or {}).get("confidence", 0.5))
    c2 = float((result2 or {}).get("confidence", 0.5))
    if c1 >= c2:
        return v1, True
    return v2, True


def resolve_phase1_conflicts(
    ai1: dict | None,
    ai2: dict | None,
) -> tuple[dict, list[str]]:
    conflicts: list[str] = []
    consensus: dict = {}
    fields = ["content_selector", "chapter_title_selector", "next_selector",
              "nav_type", "chapter_url_pattern"]
    for field in fields:
        val, is_conflict = _resolve_selector_conflict(ai1, ai2, field)
        consensus[field] = val
        if is_conflict:
            conflicts.append(field)
            print(
                f"  [Learn] ⚠ Conflict on {field!r}: "
                f"AI#1={str((ai1 or {}).get(field))[:40]!r} vs "
                f"AI#2={str((ai2 or {}).get(field))[:40]!r}",
                flush=True,
            )
    rm1 = set((ai1 or {}).get("remove_selectors") or [])
    rm2 = set((ai2 or {}).get("remove_selectors") or [])
    if rm1 and rm2:
        consensus["remove_selectors"] = list(rm1 & rm2)
        only_in_1 = rm1 - rm2
        only_in_2 = rm2 - rm1
        if only_in_1 or only_in_2:
            print(
                f"  [Learn] ℹ Remove selectors: "
                f"{len(consensus['remove_selectors'])} agreed, "
                f"{len(only_in_1)} only-AI1, {len(only_in_2)} only-AI2 → intersection",
                flush=True,
            )
    elif rm1:
        consensus["remove_selectors"] = list(rm1)
    elif rm2:
        consensus["remove_selectors"] = list(rm2)
    else:
        consensus["remove_selectors"] = []
    consensus["requires_playwright"] = bool(
        (ai1 or {}).get("requires_playwright", False) or
        (ai2 or {}).get("requires_playwright", False)
    )
    return consensus, conflicts


# ── JSON Schemas ───────────────────────────────────────────────────────────────

_S_DOM_STRUCTURE = {
    "type": "object",
    "properties": {
        "chapter_title_selector"          : {"type": "string",  "nullable": True},
        "story_title_selector"            : {"type": "string",  "nullable": True},
        "author_selector"                 : {"type": "string",  "nullable": True},
        "content_selector"                : {"type": "string",  "nullable": True},
        "next_selector"                   : {"type": "string",  "nullable": True},
        "remove_selectors"                : {"type": "array",   "items": {"type": "string"}},
        "nav_type"                        : {"type": "string",  "nullable": True},
        "chapter_url_pattern"             : {"type": "string",  "nullable": True},
        "requires_playwright"             : {"type": "boolean"},
        "title_is_inside_remove_candidate": {"type": "boolean"},
        "title_container"                 : {"type": "string",  "nullable": True},
        "notes"                           : {"type": "string",  "nullable": True},
    },
}

_S_INDEPENDENT_CHECK = {
    "type": "object",
    "properties": {
        "chapter_title_selector": {"type": "string",  "nullable": True},
        "content_selector"      : {"type": "string",  "nullable": True},
        "next_selector"         : {"type": "string",  "nullable": True},
        "remove_selectors"      : {"type": "array",   "items": {"type": "string"}},
        "nav_type"              : {"type": "string",  "nullable": True},
        "chapter_url_pattern"   : {"type": "string",  "nullable": True},
        "author_selector"       : {"type": "string",  "nullable": True},
        "confidence"            : {"type": "number"},
        "uncertain_fields"      : {"type": "array",   "items": {"type": "string"}},
        "notes"                 : {"type": "string",  "nullable": True},
    },
    "required": ["confidence"],
}

_S_STABILITY = {
    "type": "object",
    "properties": {
        "content_valid_ch3"         : {"type": "boolean"},
        "content_valid_ch4"         : {"type": "boolean"},
        "content_fix"               : {"type": "string",  "nullable": True},
        "title_valid_ch3"           : {"type": "boolean"},
        "title_valid_ch4"           : {"type": "boolean"},
        "title_fix"                 : {"type": "string",  "nullable": True},
        "next_valid_ch3"            : {"type": "boolean"},
        "next_valid_ch4"            : {"type": "boolean"},
        "next_fix"                  : {"type": "string",  "nullable": True},
        "remove_selectors_safe"     : {"type": "array",   "items": {"type": "string"}},
        "remove_selectors_dangerous": {"type": "array",   "items": {"type": "string"}},
        "remove_add"                : {"type": "array",   "items": {"type": "string"}},
        "stability_score"           : {"type": "number"},
        "notes"                     : {"type": "string",  "nullable": True},
    },
    "required": ["stability_score"],
}

_S_REMOVE_AUDIT = {
    "type": "object",
    "properties": {
        "audit_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "selector"                 : {"type": "string"},
                    "is_ancestor_of_content"   : {"type": "boolean"},
                    "is_ancestor_of_title"     : {"type": "boolean"},
                    "contains_title_or_content": {"type": "boolean"},
                    "verdict"                  : {"type": "string"},
                    "reason"                   : {"type": "string", "nullable": True},
                },
            },
        },
        "safe_selectors"        : {"type": "array", "items": {"type": "string"}},
        "dangerous_selectors"   : {"type": "array", "items": {"type": "string"}},
        "suggested_replacements": {"type": "object"},
        "notes"                 : {"type": "string", "nullable": True},
    },
    "required": ["safe_selectors", "dangerous_selectors"],
}

_S_TITLE_DEEPDIVE = {
    "type": "object",
    "properties": {
        "best_title_selector"       : {"type": "string",  "nullable": True},
        "author_name_detected"      : {"type": "string",  "nullable": True},
        "author_contamination_risk" : {"type": "boolean"},
        "title_cleanup_needed"      : {"type": "boolean"},
        "title_cleanup_note"        : {"type": "string",  "nullable": True},
        "recommended_title_selector": {"type": "string",  "nullable": True},
        "notes"                     : {"type": "string",  "nullable": True},
    },
}

_S_SPECIAL_ELEMENT = {
    "type": "object",
    "properties": {
        "found"     : {"type": "boolean"},
        "selectors" : {"type": "array", "items": {"type": "string"}},
        "convert_to": {"type": "string"},
        "prefix"    : {"type": "string"},
    },
    "required": ["found"],
}

_S_SPECIAL_CONTENT = {
    "type": "object",
    "properties": {
        "has_tables"     : {"type": "boolean"},
        "table_evidence" : {"type": "string",  "nullable": True},
        "has_math"       : {"type": "boolean"},
        "math_format"    : {"type": "string",  "nullable": True},
        "math_evidence"  : {"type": "array",   "items": {"type": "string"}},
        "system_box"     : _S_SPECIAL_ELEMENT,
        "hidden_text"    : _S_SPECIAL_ELEMENT,
        "author_note"    : _S_SPECIAL_ELEMENT,
        "bold_italic"    : {"type": "boolean"},
        "hr_dividers"    : {"type": "boolean"},
        "image_alt_text" : {"type": "boolean"},
        "special_symbols": {"type": "array",   "items": {"type": "string"}},
        "notes"          : {"type": "string",  "nullable": True},
    },
    "required": ["has_tables", "has_math"],
}

_S_ADS_DEEPSCAN = {
    "type": "object",
    "properties": {
        "ads_keywords"       : {"type": "array", "items": {"type": "string"}},
        "ads_selectors"      : {"type": "array", "items": {"type": "string"}},
        "top_edge_pattern"   : {"type": "string", "nullable": True},
        "bottom_edge_pattern": {"type": "string", "nullable": True},
        "notes"              : {"type": "string", "nullable": True},
    },
    "required": ["ads_keywords"],
}

_S_NAV_STRESS = {
    "type": "object",
    "properties": {
        "next_selector_works"      : {"type": "boolean"},
        "next_url_found"           : {"type": "string",  "nullable": True},
        "best_next_selector"       : {"type": "string",  "nullable": True},
        "nav_type_confirmed"       : {"type": "string",  "nullable": True},
        "chapter_url_pattern_valid": {"type": "boolean"},
        "chapter_url_pattern_fix"  : {"type": "string",  "nullable": True},
        "fallback_methods"         : {"type": "array",   "items": {"type": "string"}},
        "notes"                    : {"type": "string",  "nullable": True},
    },
    "required": ["next_selector_works"],
}

_S_SIMULATION = {
    "type": "object",
    "properties": {
        "content_extracted" : {"type": "string",  "nullable": True},
        "content_char_count": {"type": "integer"},
        "content_quality"   : {"type": "string"},
        "title_extracted"   : {"type": "string",  "nullable": True},
        "title_quality"     : {"type": "string"},
        "next_url_found"    : {"type": "string",  "nullable": True},
        "nav_quality"       : {"type": "string"},
        "removed_elements"  : {"type": "array",   "items": {"type": "string"}},
        "removal_safe"      : {"type": "boolean"},
        "overall_score"     : {"type": "number"},
        "issues_found"      : {"type": "array",   "items": {"type": "string"}},
        "field_scores"      : {"type": "object"},
        "notes"             : {"type": "string",  "nullable": True},
    },
    "required": ["overall_score"],
}

_S_MASTER = {
    "type": "object",
    "properties": {
        "content_selector"      : {"type": "string",  "nullable": True},
        "next_selector"         : {"type": "string",  "nullable": True},
        "chapter_title_selector": {"type": "string",  "nullable": True},
        "remove_selectors"      : {"type": "array",   "items": {"type": "string"}},
        "nav_type"              : {"type": "string",  "nullable": True},
        "chapter_url_pattern"   : {"type": "string",  "nullable": True},
        "requires_playwright"   : {"type": "boolean"},
        "formatting_rules"      : {"type": "object"},
        "ads_keywords"          : {"type": "array",   "items": {"type": "string"}},
        "confidence"            : {"type": "number"},
        "uncertain_fields"      : {"type": "array",   "items": {"type": "string"}},
        "conflict_summary"      : {"type": "string",  "nullable": True},
        "notes"                 : {"type": "string",  "nullable": True},
    },
    "required": ["confidence"],
}

_S_NAMING_RULES = {
    "type": "object",
    "properties": {
        "story_name"           : {"type": "string"},
        "story_prefix_to_strip": {"type": "string"},
        "chapter_keyword"      : {"type": "string"},
        "has_chapter_subtitle" : {"type": "boolean"},
        "notes"                : {"type": "string", "nullable": True},
    },
    "required": ["story_name", "chapter_keyword", "has_chapter_subtitle"],
}

_S_FIRST_CHAPTER = {
    "type": "object",
    "properties": {"first_chapter_url": {"type": "string", "nullable": True}},
}

_S_CLASSIFY = {
    "type": "object",
    "properties": {
        "page_type"        : {"type": "string", "enum": ["chapter", "index", "other"]},
        "next_url"         : {"type": "string", "nullable": True},
        "first_chapter_url": {"type": "string", "nullable": True},
    },
    "required": ["page_type"],
}

_S_VERIFY_ADS = {
    "type": "object",
    "properties": {
        "confirmed_ads" : {"type": "array", "items": {"type": "string"}},
        "false_positives": {"type": "array", "items": {"type": "string"}},
        "notes"         : {"type": "string", "nullable": True},
    },
    "required": ["confirmed_ads"],
}

_S_EXTRACT_CONTENT = {
    "type": "object",
    "properties": {
        "content"   : {"type": "string"},
        "confidence": {"type": "number"},
        "notes"     : {"type": "string", "nullable": True},
    },
    "required": ["content", "confidence"],
}


# ── Sanitization helpers ───────────────────────────────────────────────────────

_REDUNDANT_REMOVE_TAGS = frozenset({"script", "style", "noscript", "iframe"})


def _sanitize_remove_selectors(result: dict) -> None:
    rm = result.get("remove_selectors")
    if not isinstance(rm, list):
        result["remove_selectors"] = []
    else:
        result["remove_selectors"] = [
            s for s in rm
            if isinstance(s, str)
            and s.strip()
            and s.strip().lower() not in _REDUNDANT_REMOVE_TAGS
        ]


def _validate_regex_field(result: dict, field: str) -> None:
    pat = result.get(field)
    if pat:
        try:
            re.compile(pat)
        except re.error:
            result[field] = None


def _sanitize_formatting_rules(fr: dict) -> None:
    fr.setdefault("tables",          False)
    fr.setdefault("math_support",    False)
    fr.setdefault("math_format",     None)
    fr.setdefault("special_symbols", [])
    fr.setdefault("bold_italic",     True)
    fr.setdefault("hr_dividers",     True)
    fr.setdefault("image_alt_text",  False)
    for key in ("system_box", "hidden_text", "author_note"):
        rule = fr.get(key)
        if not isinstance(rule, dict):
            fr[key] = {"found": False, "selectors": []}
        else:
            rule.setdefault("found",     False)
            rule.setdefault("selectors", [])
            if not isinstance(rule["selectors"], list):
                rule["selectors"] = []
