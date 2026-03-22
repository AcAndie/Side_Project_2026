"""
src/littrans/context/bible_consolidator.py — Hợp nhất staging → 3 tầng chính.

[Refactor] bible/ → context/. Imports: bible.* → context.*.
"""
# Nội dung giống hệt bible/bible_consolidator.py
# CHỈ THAY ĐỔI 2 dòng import đầu:

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime

from filelock import FileLock, Timeout

from littrans.context.bible_store import BibleStore          # ← ĐỔI
from littrans.context.schemas import (                        # ← ĐỔI
    ScanOutput, ScanCandidate,
    BibleChapterSummary, BibleEvent, BiblePlotThread, BibleRevelation,
    ENTITY_MODELS,
)


# ── Result ────────────────────────────────────────────────────────

@dataclass
class ConsolidationResult:
    chars_added    : int = 0
    entities_added : int = 0
    entities_updated: int = 0
    wb_clues_added  : int = 0
    lore_chapters   : int = 0
    errors          : list[str] = field(default_factory=list)


# ── String Similarity ─────────────────────────────────────────────

def _levenshtein_ratio(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b: return 0.0
    if a == b: return 1.0
    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b))
    n, m = len(a), len(b)
    if abs(n - m) > max(n, m) * 0.5: return 0.0
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        new_dp = [i] + [0] * m
        for j in range(1, m + 1):
            if a[i-1] == b[j-1]: new_dp[j] = dp[j-1]
            else: new_dp[j] = 1 + min(dp[j], new_dp[j-1], dp[j-1])
        dp = new_dp
    return 1.0 - dp[m] / max(n, m)


def _name_similarity(candidate: ScanCandidate, existing: dict) -> float:
    c_names = [candidate.en_name.lower(), candidate.canonical_name.lower()]
    e_names = ([existing.get("en_name","").lower(), existing.get("canonical_name","").lower()]
               + [a.lower() for a in existing.get("aliases", [])])
    best = 0.0
    for cn in c_names:
        for en in e_names:
            if not cn or not en: continue
            best = max(best, _levenshtein_ratio(cn, en))
    return best


# ── Entity Resolver ───────────────────────────────────────────────

class EntityResolver:
    THRESH_SURE  = 0.95
    THRESH_MAYBE = 0.70

    def __init__(self, store: BibleStore) -> None:
        self._store = store

    def resolve(self, candidate: ScanCandidate) -> tuple[str, float]:
        if candidate.existing_id:
            entity = self._store.get_entity_by_id(candidate.existing_id)
            if entity: return candidate.existing_id, 0.97
        found = self._store._index_lookup(candidate.en_name)
        if not found: found = self._store._index_lookup(candidate.canonical_name)
        if found:
            etype = found.get("type","")
            if etype == candidate.entity_type:
                entity = self._store.get_entity_by_id(found["id"])
                if entity:
                    sim = _name_similarity(candidate, entity)
                    if sim >= self.THRESH_SURE: return found["id"], sim
                    elif sim >= self.THRESH_MAYBE:
                        logging.warning(f"[EntityResolver] Uncertain merge '{candidate.en_name}' → {found['id']} ({sim:.2f})")
                        return found["id"], sim
        results = self._store.search_entities(candidate.en_name or candidate.canonical_name, entity_type=candidate.entity_type)
        for entity in results[:3]:
            sim = _name_similarity(candidate, entity)
            if sim >= self.THRESH_SURE: return entity["id"], sim
            elif sim >= self.THRESH_MAYBE:
                logging.warning(f"[EntityResolver] Uncertain fuzzy merge '{candidate.en_name}' → {entity.get('id','?')} ({sim:.2f})")
                return entity["id"], sim
        return "", 0.0


# ── Bible Consolidator ────────────────────────────────────────────

class BibleConsolidator:
    def __init__(self, store: BibleStore) -> None:
        self._store    = store
        self._resolver = EntityResolver(store)

    def run(self, staging: list[ScanOutput]) -> ConsolidationResult:
        lock_path = self._store._dir / ".consolidate.lock"
        try:
            with FileLock(str(lock_path), timeout=30):
                return self._run_locked(staging)
        except Timeout:
            msg = "Không thể lấy consolidation lock sau 30s"
            logging.error(f"[Consolidator] {msg}")
            print(f"  ⚠️  {msg}")
            return ConsolidationResult(errors=[msg])

    def _run_locked(self, staging: list[ScanOutput]) -> ConsolidationResult:
        result = ConsolidationResult()
        for scan_output in staging:
            try:
                self._consolidate_one(scan_output, result)
                self._store.mark_chapter_scanned(scan_output.source_chapter)
            except Exception as e:
                msg = f"{scan_output.source_chapter}: {e}"
                logging.error(f"[Consolidator] {msg}")
                result.errors.append(msg)
        return result

    def _consolidate_one(self, scan: ScanOutput, result: ConsolidationResult) -> None:
        self._consolidate_database(scan, result)
        if scan.worldbuilding_clues: self._consolidate_worldbuilding(scan, result)
        self._consolidate_lore(scan, result)

    def _consolidate_database(self, scan: ScanOutput, result: ConsolidationResult) -> None:
        for candidate in scan.database_candidates:
            if not candidate.en_name and not candidate.canonical_name: continue
            if candidate.entity_type not in ENTITY_MODELS: candidate.entity_type = "concept"
            try:
                entity_id, action = self._resolve_and_upsert(candidate, scan.source_chapter)
                if action == "added":
                    result.entities_added += 1
                    if candidate.entity_type == "character": result.chars_added += 1
                elif action == "updated": result.entities_updated += 1
            except Exception as e:
                logging.warning(f"[Consolidator] {candidate.en_name} | {candidate.entity_type} | {e}")

    def _resolve_and_upsert(self, candidate: ScanCandidate, source_chapter: str) -> tuple[str, str]:
        existing_id, confidence = self._resolver.resolve(candidate)
        if existing_id and EntityResolver.THRESH_MAYBE <= confidence < EntityResolver.THRESH_SURE:
            existing_id = self._llm_arbitration(candidate, existing_id, confidence)
        entity_data = self._candidate_to_entity(candidate, source_chapter)
        if existing_id:
            entity_data["id"] = existing_id
            entity_id = self._store.upsert_entity(candidate.entity_type, entity_data)
            return entity_id, "updated"
        else:
            entity_id = self._store.upsert_entity(candidate.entity_type, entity_data)
            return entity_id, "added"

    def _candidate_to_entity(self, c: ScanCandidate, source_chapter: str) -> dict:
        base = {"en_name": c.en_name, "canonical_name": c.canonical_name, "type": c.entity_type,
                "description": c.description, "first_appearance": source_chapter,
                "confidence": c.confidence, "last_updated": datetime.now().strftime("%Y-%m-%d")}
        raw = c.raw_data or {}
        if c.entity_type == "character":
            base.update({"status": raw.get("status","alive"), "role": raw.get("role","Unknown"),
                         "archetype": raw.get("archetype","UNKNOWN"), "faction_id": "",
                         "cultivation": {"realm": raw.get("cultivation_realm","")},
                         "personality_summary": raw.get("personality_summary",""),
                         "pronoun_self": raw.get("pronoun_self",""), "current_goal": raw.get("current_goal",""),
                         "aliases": raw.get("aliases",[])})
        elif c.entity_type == "item":
            base.update({"item_type": raw.get("item_type","other"), "rarity": raw.get("rarity",""), "effects": raw.get("effects",[])})
        elif c.entity_type == "location":
            base.update({"location_type": raw.get("location_type","other"), "notable_features": raw.get("notable_features",[])})
        elif c.entity_type == "skill":
            base.update({"skill_type": raw.get("skill_type","active"), "effects": raw.get("effects",[]),
                         "evolution_chain": [c.canonical_name] if c.canonical_name else []})
        elif c.entity_type == "faction":
            base.update({"faction_type": raw.get("faction_type","other"), "power_level": raw.get("power_level","")})
        return base

    def _llm_arbitration(self, candidate: ScanCandidate, existing_id: str, confidence: float) -> str:
        existing = self._store.get_entity_by_id(existing_id)
        if not existing: return ""
        system = ("Bạn là AI chuyên phán xét entity resolution. Câu hỏi: A và B có phải cùng entity không? "
                  'Trả về JSON: {"same": true/false, "reason": "lý do ngắn"}')
        user = (f"Entity A: {candidate.en_name} → {candidate.canonical_name}\n"
                f"  Loại: {candidate.entity_type}\n  Mô tả: {candidate.description}\n"
                f"  Context: {candidate.context_snippet[:150]}\n\n"
                f"Entity B [{existing_id}]: {existing.get('en_name','')} → {existing.get('canonical_name','')}\n"
                f"  Mô tả: {existing.get('description','')}")
        try:
            from littrans.llm.client import call_gemini_json
            result = call_gemini_json(system, user)
            if result.get("same"): return existing_id
        except Exception as e:
            logging.warning(f"[Consolidator] LLM arbitration lỗi: {e}")
        return ""

    def _consolidate_worldbuilding(self, scan: ScanOutput, result: ConsolidationResult) -> None:
        cfg = _get_wb_updates(scan)
        if not cfg: return
        try:
            self._store.update_worldbuilding(cfg)
            result.wb_clues_added += len(scan.worldbuilding_clues)
        except Exception as e:
            logging.warning(f"[Consolidator] WorldBuilding update lỗi: {e}")

    def _consolidate_lore(self, scan: ScanOutput, result: ConsolidationResult) -> None:
        lore = scan.lore_entry
        if not lore.chapter_summary: return
        summary = BibleChapterSummary(
            chapter=scan.source_chapter, chapter_index=scan.chapter_index, summary=lore.chapter_summary,
            tone=lore.tone, pov_char_id="", location_id="",
            key_events=[e.get("title","") for e in lore.key_events],
            new_entity_ids=[], scanned_at=scan.scanned_at,
        )
        self._store.append_chapter_summary(summary)
        result.lore_chapters += 1
        for ev_raw in lore.key_events:
            if not isinstance(ev_raw, dict): continue
            event = BibleEvent(chapter=scan.source_chapter, event_type=ev_raw.get("type","other"),
                               title=ev_raw.get("title",""), description=ev_raw.get("description",""),
                               participants=ev_raw.get("participants",[]), consequence=ev_raw.get("consequence",""))
            if event.title: self._store.append_event(event)
        for t_raw in lore.plot_threads_opened:
            if not isinstance(t_raw, dict) or not t_raw.get("name"): continue
            self._store.append_plot_thread(BiblePlotThread(
                name=t_raw["name"], opened_chapter=scan.source_chapter, status="open",
                summary=t_raw.get("summary",""), key_chapters=[scan.source_chapter]))
        for t_raw in lore.plot_threads_closed:
            if not isinstance(t_raw, dict): continue
            self._store.update_plot_thread_status(
                thread_name=t_raw.get("thread_name",""), status="closed",
                closed_chapter=scan.source_chapter, resolution=t_raw.get("resolution",""))
        for r_raw in lore.revelations:
            if not isinstance(r_raw, dict) or not r_raw.get("title"): continue
            self._store.append_revelation(BibleRevelation(
                chapter=scan.source_chapter, title=r_raw["title"],
                description=r_raw.get("description",""),
                foreshadowed_in=r_raw.get("foreshadowed_in",[])))


def _get_wb_updates(scan: ScanOutput) -> dict:
    if not scan.worldbuilding_clues: return {}
    updates: dict = {"confirmed_rules": [], "history_notes": [], "economy_notes": [], "cosmology_notes": []}
    CAT_MAP = {"rule": "confirmed_rules", "history": "history_notes",
               "economy": "economy_notes", "cosmological": "cosmology_notes", "cosmology": "cosmology_notes"}
    has_any = False
    for clue in scan.worldbuilding_clues:
        key = CAT_MAP.get(clue.category.lower())
        if key:
            if key == "confirmed_rules":
                updates["confirmed_rules"].append({"description": clue.description, "source_chapter": scan.source_chapter,
                                                   "category": clue.category.lower(), "confidence": clue.confidence})
            else: updates[key].append(f"[{scan.source_chapter}] {clue.description}")
            has_any = True
    return updates if has_any else {}
