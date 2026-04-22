"""
ai/agents.py — AI agent functions for scraper learning + scraping phases.

Helpers (retry, parse, schemas, HTML, sanitize) live in agents_helpers.py.
This file contains only the ai_* public functions.

P2-B: snippet() early-exit nếu raw html đã <= max_len.
P2-C: _parse() thay greedy regex bằng json.JSONDecoder.raw_decode().
Fix ADS-B: ai_ads_deepscan() thêm validation guard lọc garbage keywords.
"""
from __future__ import annotations

import asyncio

from littrans.modules.scraper.ai.agents_helpers import (
    _fmt, _call, _parse,
    snippet, _snippet, _nav_hints, _chapter_links,
    _sanitize_remove_selectors, _validate_regex_field, _sanitize_formatting_rules,
    resolve_phase1_conflicts,
    _S_DOM_STRUCTURE, _S_INDEPENDENT_CHECK, _S_STABILITY, _S_REMOVE_AUDIT,
    _S_TITLE_DEEPDIVE, _S_SPECIAL_CONTENT, _S_ADS_DEEPSCAN,
    _S_MASTER, _S_NAMING_RULES, _S_FIRST_CHAPTER,
    _S_CLASSIFY, _S_VERIFY_ADS, _S_EXTRACT_CONTENT,
)
from littrans.modules.scraper.ai.client import AIRateLimiter


# ══════════════════════════════════════════════════════════════════════════════
# LEARNING PHASE AGENTS
# P0-A: KHÔNG gọi snippet() — caller (phase_ai.py) đã cắt HTML trước.
# ══════════════════════════════════════════════════════════════════════════════

async def ai_dom_structure(
    html1: str, url1: str,
    html2: str, url2: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_1_dom_structure(html1, url1, html2, url2)
    try:
        text   = await _call(prompt, limiter, _S_DOM_STRUCTURE)
        result = _parse(text)
        if isinstance(result, dict):
            _sanitize_remove_selectors(result)
            _validate_regex_field(result, "chapter_url_pattern")
            result.setdefault("requires_playwright", False)
            result.setdefault("title_is_inside_remove_candidate", False)
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#1] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_independent_check(
    html1: str, url1: str,
    html2: str, url2: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_2_independent_check(html1, url1, html2, url2)
    try:
        text   = await _call(prompt, limiter, _S_INDEPENDENT_CHECK)
        result = _parse(text)
        if isinstance(result, dict):
            _sanitize_remove_selectors(result)
            _validate_regex_field(result, "chapter_url_pattern")
            try:
                result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.7))))
            except (TypeError, ValueError):
                result["confidence"] = 0.7
            result.setdefault("uncertain_fields", [])
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#2] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_stability_check(
    html3: str, url3: str,
    html4: str, url4: str,
    consensus: dict,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_3_stability_check(html3, url3, html4, url4, consensus)
    try:
        text   = await _call(prompt, limiter, _S_STABILITY)
        result = _parse(text)
        if isinstance(result, dict):
            result.setdefault("remove_selectors_safe",      [])
            result.setdefault("remove_selectors_dangerous", [])
            result.setdefault("remove_add",                 [])
            try:
                result["stability_score"] = max(0.0, min(1.0, float(result.get("stability_score", 0.8))))
            except (TypeError, ValueError):
                result["stability_score"] = 0.8
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#3] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_remove_audit(
    html5: str, url5: str,
    remove_selectors: list[str],
    content_selector: str | None,
    title_selector: str | None,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_4_remove_audit(html5, url5, remove_selectors, content_selector, title_selector)
    try:
        text   = await _call(prompt, limiter, _S_REMOVE_AUDIT)
        result = _parse(text)
        if isinstance(result, dict):
            result.setdefault("safe_selectors",      [])
            result.setdefault("dangerous_selectors", [])
            result.setdefault("audit_results",       [])
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#4] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_title_deepdive(
    html6: str, url6: str,
    title_selector: str | None,
    author_selector: str | None,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_5_title_deepdive(html6, url6, title_selector, author_selector)
    try:
        text   = await _call(prompt, limiter, _S_TITLE_DEEPDIVE)
        result = _parse(text)
        if isinstance(result, dict):
            result.setdefault("author_contamination_risk", False)
            result.setdefault("title_cleanup_needed",      False)
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#5] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_special_content(
    html7: str, url7: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_6_special_content(html7, url7)
    try:
        text   = await _call(prompt, limiter, _S_SPECIAL_CONTENT)
        result = _parse(text)
        if isinstance(result, dict):
            result.setdefault("math_evidence",   [])
            result.setdefault("special_symbols", [])
            result.setdefault("bold_italic",     True)
            result.setdefault("hr_dividers",     True)
            result.setdefault("image_alt_text",  False)
            for key in ("system_box", "hidden_text", "author_note"):
                rule = result.get(key)
                if not isinstance(rule, dict):
                    result[key] = {"found": False, "selectors": []}
                else:
                    rule.setdefault("found",     False)
                    rule.setdefault("selectors", [])
                    if not isinstance(rule["selectors"], list):
                        rule["selectors"] = []
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#6] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_ads_deepscan(
    html8: str, url8: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_7_ads_deepscan(html8, url8)
    try:
        text   = await _call(prompt, limiter, _S_ADS_DEEPSCAN)
        result = _parse(text)
        if isinstance(result, dict):
            result.setdefault("ads_keywords",  [])
            result.setdefault("ads_selectors", [])
            from littrans.modules.scraper.utils.string_helpers import is_valid_ads_keyword as _kw_ok
            result["ads_keywords"] = [
                kw.lower().strip() for kw in result["ads_keywords"]
                if isinstance(kw, str) and _kw_ok(kw.strip())
            ]
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#7] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_nav_stress(
    html9: str, url9: str,
    next_selector: str | None,
    nav_type: str | None,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    from littrans.modules.scraper.ai.agents_helpers import _S_NAV_STRESS
    prompt = Prompts.learning_8_nav_stress(html9, url9, next_selector, nav_type)
    try:
        text   = await _call(prompt, limiter, _S_NAV_STRESS)
        result = _parse(text)
        if isinstance(result, dict):
            result.setdefault("next_selector_works", False)
            result.setdefault("fallback_methods",    [])
            _validate_regex_field(result, "chapter_url_pattern_fix")
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#8] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_full_simulation(
    html10: str, url10: str,
    profile_so_far: dict,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    from littrans.modules.scraper.ai.agents_helpers import _S_SIMULATION
    prompt = Prompts.learning_9_full_simulation(html10, url10, profile_so_far)
    try:
        text   = await _call(prompt, limiter, _S_SIMULATION)
        result = _parse(text)
        if isinstance(result, dict):
            try:
                result["overall_score"] = max(0.0, min(1.0, float(result.get("overall_score", 0.7))))
            except (TypeError, ValueError):
                result["overall_score"] = 0.7
            result.setdefault("issues_found",     [])
            result.setdefault("removed_elements", [])
            result.setdefault("removal_safe",     True)
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#9] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY AGENTS
# ══════════════════════════════════════════════════════════════════════════════

async def ai_master_synthesis(
    synthesis_summary: str,
    domain: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    prompt = Prompts.learning_10_master_synthesis(synthesis_summary, domain)
    try:
        text   = await _call(prompt, limiter, _S_MASTER)
        result = _parse(text)
        if isinstance(result, dict):
            try:
                result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.7))))
            except (TypeError, ValueError):
                result["confidence"] = 0.7
            _sanitize_remove_selectors(result)
            _validate_regex_field(result, "chapter_url_pattern")
            result.setdefault("uncertain_fields", [])
            result.setdefault("ads_keywords",     [])
            from littrans.modules.scraper.utils.string_helpers import is_valid_ads_keyword as _kw_ok
            result["ads_keywords"] = [
                kw.lower().strip() for kw in result["ads_keywords"]
                if isinstance(kw, str) and _kw_ok(kw.strip())
            ]
            fr = result.get("formatting_rules")
            if not isinstance(fr, dict):
                result["formatting_rules"] = {}
            _sanitize_formatting_rules(result["formatting_rules"])
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI#10] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_extract_naming_rules(
    raw_titles: list[str],
    base_url: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    if not raw_titles:
        return None
    prompt = Prompts.naming_rules(raw_titles, base_url)
    try:
        text   = await _call(prompt, limiter, _S_NAMING_RULES)
        result = _parse(text)
        if isinstance(result, dict) and result.get("story_name", "").strip():
            result["story_name"]            = result["story_name"].strip()
            result["story_prefix_to_strip"] = (result.get("story_prefix_to_strip") or "").strip()
            result["chapter_keyword"]       = (result.get("chapter_keyword") or "Chapter").strip()
            result["has_chapter_subtitle"]  = bool(result.get("has_chapter_subtitle", False))
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI naming] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_find_first_chapter(
    html: str,
    base_url: str,
    limiter: AIRateLimiter,
) -> str | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    links = await asyncio.to_thread(_chapter_links, html, base_url)
    if not links:
        return None
    if len(links) == 1:
        return links[0]
    candidates = "\n".join(links[:15])
    prompt = Prompts.find_first_chapter(candidates, base_url)
    try:
        text   = await _call(prompt, limiter, _S_FIRST_CHAPTER)
        result = _parse(text)
        if isinstance(result, dict) and result.get("first_chapter_url"):
            return result["first_chapter_url"]
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI find_first] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return links[0]


async def ai_classify_and_find(
    html: str,
    base_url: str,
    limiter: AIRateLimiter,
) -> dict | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    hints   = await asyncio.to_thread(_nav_hints, html, base_url)
    snip    = await asyncio.to_thread(snippet, html, 5000)
    prompt  = Prompts.classify_and_find(hints, snip, base_url)
    try:
        text   = await _call(prompt, limiter, _S_CLASSIFY)
        result = _parse(text)
        if isinstance(result, dict):
            return result
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI classify] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None


async def ai_verify_ads(
    candidates: list[str],
    domain: str,
    limiter: AIRateLimiter,
) -> list[str]:
    from littrans.modules.scraper.ai.prompts import Prompts
    if not candidates:
        return []
    prompt = Prompts.verify_ads(candidates, domain)
    try:
        text   = await _call(prompt, limiter, _S_VERIFY_ADS)
        result = _parse(text)
        if isinstance(result, dict):
            confirmed = result.get("confirmed_ads") or []
            fp        = result.get("false_positives") or []
            if fp:
                print(
                    f"  [Ads] ℹ️  {len(fp)} false positive: "
                    + ", ".join(repr(x[:40]) for x in fp[:3]),
                    flush=True,
                )
            return [line for line in confirmed if isinstance(line, str) and line.strip()]
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI verify_ads] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return []


async def ai_extract_content(
    html: str,
    url: str,
    limiter: AIRateLimiter,
) -> str | None:
    from littrans.modules.scraper.ai.prompts import Prompts
    _MIN_CHARS      = 150
    _MIN_CONFIDENCE = 0.3
    prompt = Prompts.extract_content(snippet(html, 8000), url)
    try:
        text   = await _call(prompt, limiter, _S_EXTRACT_CONTENT)
        result = _parse(text)
        if isinstance(result, dict):
            content = (result.get("content") or "").strip()
            conf    = float(result.get("confidence", 0.0))
            if len(content) >= _MIN_CHARS and conf >= _MIN_CONFIDENCE:
                return content
            if content and len(content) < _MIN_CHARS:
                print(f"  [AI extract] ⚠ Từ chối: content quá ngắn ({len(content)}c < {_MIN_CHARS}c)", flush=True)
            elif content:
                print(f"  [AI extract] ⚠ Từ chối: confidence quá thấp ({conf:.2f} < {_MIN_CONFIDENCE})", flush=True)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"  [AI extract] ⚠ Thất bại: {_fmt(e)}", flush=True)
    return None
