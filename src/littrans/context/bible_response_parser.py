"""
src/littrans/context/bible_response_parser.py — Parse AI scan response → typed dataclasses.

Extracted from bible_scanner.py (Batch 7) to reduce file size.
Public API: _parse_scan_response, _merge_scan_outputs.
"""
from __future__ import annotations

import logging
from datetime import datetime

from littrans.context.schemas import (
    ScanOutput, ScanCandidate, ScanWorldBuildingClue, ScanLoreEntry,
)


def _normalize_list_of_dicts(items: list, string_key: str = "title") -> list[dict]:
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, str) and item.strip():
            result.append({string_key: item.strip()})
    return result


def _parse_scan_response(
    raw_data,
    source_chapter: str,
    chapter_index: int,
    depth: str,
    model_used: str,
) -> ScanOutput:
    # [FIX v1] Guard khi AI trả về JSON array hoặc kiểu khác thay vì dict
    if isinstance(raw_data, list):
        logging.warning(
            f"[BibleScanner] raw_data là list (size={len(raw_data)}) "
            f"cho '{source_chapter}' — wrap thành database_candidates"
        )
        raw_data = {"database_candidates": raw_data}
    elif not isinstance(raw_data, dict):
        logging.warning(
            f"[BibleScanner] raw_data là {type(raw_data).__name__} "
            f"(không phải dict) cho '{source_chapter}' — bỏ qua"
        )
        raw_data = {}

    candidates = []
    for c in raw_data.get("database_candidates", []):
        if not isinstance(c, dict):
            continue
        if "entity_type" not in c and "type" in c:
            c = dict(c)
            c["entity_type"] = c.pop("type")
        if "en_name" not in c:
            c = dict(c)
            c["en_name"] = (c.get("full_name") or c.get("name") or "").strip()
        en = c.get("en_name", "").strip()
        if not en:
            continue
        try:
            conf = float(c.get("confidence", 0.9))
        except Exception:
            conf = 0.9
        candidates.append(ScanCandidate(
            entity_type=c.get("entity_type", "concept"),
            en_name=en,
            canonical_name=c.get("canonical_name", "").strip(),
            existing_id=c.get("existing_id", "").strip(),
            is_new=bool(c.get("is_new", True)),
            description=c.get("description", "").strip(),
            raw_data=c.get("raw_data", {}),
            confidence=min(1.0, max(0.0, conf)),
            context_snippet=c.get("context_snippet", "").strip()[:200],
        ))

    clues = []
    for w in raw_data.get("worldbuilding_clues", []):
        if not isinstance(w, dict):
            continue
        try:
            conf = float(w.get("confidence", 0.8))
        except Exception:
            conf = 0.8
        clues.append(ScanWorldBuildingClue(
            category=w.get("category", "other"),
            description=w.get("description", "").strip(),
            raw_text=w.get("raw_text", "").strip()[:300],
            confidence=min(1.0, max(0.0, conf)),
        ))

    lr = raw_data.get("lore_entry", {})
    if not isinstance(lr, dict):
        lr = {}
    lore = ScanLoreEntry(
        chapter_summary=lr.get("chapter_summary", "").strip(),
        tone=lr.get("tone", "").strip(),
        pov_char=lr.get("pov_char", "").strip(),
        location=lr.get("location", "").strip(),
        key_events=_normalize_list_of_dicts(
            lr.get("key_events", []) if isinstance(lr.get("key_events"), list) else [],
            string_key="title"),
        plot_threads_opened=_normalize_list_of_dicts(
            lr.get("plot_threads_opened", []) if isinstance(lr.get("plot_threads_opened"), list) else [],
            string_key="name"),
        plot_threads_closed=_normalize_list_of_dicts(
            lr.get("plot_threads_closed", []) if isinstance(lr.get("plot_threads_closed"), list) else [],
            string_key="thread_name"),
        revelations=_normalize_list_of_dicts(
            lr.get("revelations", []) if isinstance(lr.get("revelations"), list) else [],
            string_key="title"),
        relationship_changes=_normalize_list_of_dicts(
            lr.get("relationship_changes", []) if isinstance(lr.get("relationship_changes"), list) else [],
            string_key="event"),
    )
    return ScanOutput(
        source_chapter=source_chapter,
        chapter_index=chapter_index,
        scan_depth=depth,
        database_candidates=candidates,
        worldbuilding_clues=clues,
        lore_entry=lore,
        scanned_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        model_used=model_used,
        raw_response=raw_data,
    )


def _merge_scan_outputs(
    outputs: list[ScanOutput],
    source_chapter: str,
    chapter_index: int,
    depth: str,
    model_used: str,
) -> ScanOutput:
    if len(outputs) == 1:
        return outputs[0]

    seen_entities: dict[str, ScanCandidate] = {}
    for out in outputs:
        for c in out.database_candidates:
            key = c.en_name.lower().strip()
            if key not in seen_entities or c.confidence > seen_entities[key].confidence:
                seen_entities[key] = c
    merged_candidates = list(seen_entities.values())

    seen_clues: dict[str, ScanWorldBuildingClue] = {}
    for out in outputs:
        for w in out.worldbuilding_clues:
            key = w.description.lower().strip()[:80]
            if key and key not in seen_clues:
                seen_clues[key] = w
    merged_clues = list(seen_clues.values())

    summaries = [o.lore_entry.chapter_summary for o in outputs if o.lore_entry.chapter_summary]
    if len(summaries) > 1:
        merged_summary = " | ".join(summaries)
    elif summaries:
        merged_summary = summaries[0]
    else:
        merged_summary = ""

    def _first(attr: str) -> str:
        for o in outputs:
            v = getattr(o.lore_entry, attr, "")
            if v:
                return v
        return ""

    def _merge_list_by_key(items_list: list[list[dict]], key: str) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for items in items_list:
            for item in items:
                if not isinstance(item, dict):
                    continue
                k = str(item.get(key, "")).lower().strip()
                if k and k not in seen:
                    seen.add(k)
                    result.append(item)
        return result

    merged_lore = ScanLoreEntry(
        chapter_summary=merged_summary,
        tone=_first("tone"),
        pov_char=_first("pov_char"),
        location=_first("location"),
        key_events=_merge_list_by_key(
            [o.lore_entry.key_events for o in outputs], "title"
        ),
        plot_threads_opened=_merge_list_by_key(
            [o.lore_entry.plot_threads_opened for o in outputs], "name"
        ),
        plot_threads_closed=_merge_list_by_key(
            [o.lore_entry.plot_threads_closed for o in outputs], "thread_name"
        ),
        revelations=_merge_list_by_key(
            [o.lore_entry.revelations for o in outputs], "title"
        ),
        relationship_changes=_merge_list_by_key(
            [o.lore_entry.relationship_changes for o in outputs], "event"
        ),
    )

    return ScanOutput(
        source_chapter=source_chapter,
        chapter_index=chapter_index,
        scan_depth=depth,
        database_candidates=merged_candidates,
        worldbuilding_clues=merged_clues,
        lore_entry=merged_lore,
        scanned_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        model_used=model_used,
        raw_response={},
    )
