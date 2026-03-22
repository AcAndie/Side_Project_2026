"""
src/littrans/context/pipeline_bible_patch.py — Kết nối Bible System ↔ Pipeline.

[Refactor] bible/ → context/, managers/ → context/.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime


def _compile_name_pattern(name: str):
    try:
        return re.compile(rf"(?<![^\W_]){re.escape(name.lower())}(?![^\W_])", re.UNICODE)
    except re.error:
        return None


def _build_entity_patterns(bc: dict) -> list[tuple[dict, re.Pattern | None, str]]:
    entries = []
    for name in [bc.get("canonical_name",""), bc.get("en_name","")]:
        if not name or len(name) < 2: continue
        entries.append((bc, _compile_name_pattern(name), name.lower()))
    return entries


def _entity_matches(pattern, name_lower: str, text_lower: str) -> bool:
    if pattern is not None: return bool(pattern.search(text_lower))
    return name_lower in text_lower


# ═══════════════════════════════════════════════════════════════════
# 1. STARTUP SYNC: Bible → Characters_Active
# ═══════════════════════════════════════════════════════════════════

def init_characters_from_bible() -> int:
    from littrans.config.settings import settings
    from littrans.context.bible_store import BibleStore              # ← ĐỔI
    from littrans.context.characters import load_active              # ← ĐỔI
    from littrans.utils.io_utils import save_json

    store       = BibleStore(settings.bible_dir)
    bible_chars = store.get_all_characters()
    if not bible_chars: return 0

    active_data  = load_active()
    active_chars = active_data.setdefault("characters", {})
    added = 0

    for bc in bible_chars:
        name = (bc.get("canonical_name") or "").strip() or (bc.get("en_name") or "").strip()
        if not name or len(name) < 2: continue
        if name in active_chars: continue
        active_chars[name] = _bible_char_to_active_profile(bc)
        added += 1

    if added:
        active_data.setdefault("meta", {})["last_updated_chapter"] = (
            f"bible_sync_{datetime.now().strftime('%Y%m%d')}"
        )
        save_json(settings.characters_active_file, active_data)
        print(f"  📖 Bible sync: +{added} nhân vật → Characters_Active")

    return added


# ═══════════════════════════════════════════════════════════════════
# 2. PROMPT BUILDER WRAPPER
# ═══════════════════════════════════════════════════════════════════

def build_bible_system_prompt(
    instructions : str,
    text         : str,
    filename     : str,
    chapter_map  = None,
    name_lock    : dict | None = None,
    budget_limit : int = 0,
) -> str:
    from littrans.config.settings import settings
    from littrans.context.bible_store import BibleStore                    # ← ĐỔI
    from littrans.context.bible_prompt_builder import build_bible_translation_prompt  # ← ĐỔI

    store = BibleStore(settings.bible_dir)
    return build_bible_translation_prompt(
        instructions=instructions, chapter_text=text, chapter_filename=filename,
        store=store, chapter_map=chapter_map, name_lock_table=name_lock, budget_limit=budget_limit,
    )


# ═══════════════════════════════════════════════════════════════════
# 3. POST-CHAPTER UPDATE
# ═══════════════════════════════════════════════════════════════════

def update_bible_from_post(post_result, filename: str, chapter_text: str) -> None:
    from littrans.config.settings import settings
    from littrans.context.bible_store import BibleStore   # ← ĐỔI

    try:
        store      = BibleStore(settings.bible_dir)
        text_lower = chapter_text.lower()
        bible_chars = store.get_all_characters()
        if not bible_chars: return

        all_entries: list[tuple[dict, re.Pattern | None, str]] = []
        for bc in bible_chars:
            all_entries.extend(_build_entity_patterns(bc))

        updated_ids: set[str] = set()

        for bc, pattern, name_lower in all_entries:
            bc_id = bc.get("id","")
            if bc_id in updated_ids: continue
            if _entity_matches(pattern, name_lower, text_lower):
                updated_ids.add(bc_id)
                bc["last_seen"]     = filename
                bc["chapter_count"] = bc.get("chapter_count",0) + 1
                bc["last_updated"]  = datetime.now().strftime("%Y-%m-%d")
                try:
                    store.upsert_entity("character", bc)
                except Exception as e:
                    name = bc.get("canonical_name") or bc.get("en_name","?")
                    logging.warning(f"[BiblePatch] upsert last_seen [{name}]: {e}")

    except Exception as e:
        logging.error(f"[BiblePatch] update_bible_from_post {filename}: {e}")


# ── Helper ────────────────────────────────────────────────────────

def _bible_char_to_active_profile(bc: dict) -> dict:
    cult = bc.get("cultivation") or {}
    rels: dict = {}
    for r in bc.get("relationships", []):
        target = (r.get("target_name") or r.get("target_id","")).strip()
        if not target: continue
        rels[target] = {
            "type": r.get("rel_type","neutral"), "feeling": "", "dynamic": r.get("dynamic",""),
            "pronoun_status": "weak", "current_status": r.get("description",""),
            "tension_points": [], "history": [],
            "intimacy_level": r.get("eps_level",2), "eps_signals": [],
        }
    personality_traits = [bc["personality_summary"]] if bc.get("personality_summary") else []
    return {
        "identity"              : {"full_name": bc.get("en_name",""), "aliases": bc.get("aliases",[]),
                                   "current_title": "", "faction": bc.get("faction_id",""),
                                   "cultivation_path": cult.get("realm","")},
        "power"                 : {"current_level": cult.get("realm",""), "signature_skills": bc.get("skill_ids",[]),
                                   "combat_style": bc.get("combat_style","")},
        "canonical_name"        : bc.get("canonical_name",""),
        "alias_canonical_map"   : bc.get("alias_canonical_map",{}),
        "active_identity"       : bc.get("canonical_name",""),
        "known_aliases"         : bc.get("aliases",[]),
        "identity_context"      : "",
        "role"                  : bc.get("role","Unknown"),
        "archetype"             : bc.get("archetype","UNKNOWN"),
        "personality_traits"    : personality_traits,
        "speech"                : {"pronoun_self": bc.get("pronoun_self",""), "formality_level": "medium",
                                   "formality_note": "", "how_refers_to_others": {},
                                   "speech_quirks": bc.get("speech_quirks",[])},
        "habitual_behaviors"    : [],
        "relationships"         : rels,
        "arc_status"            : {"current_goal": bc.get("current_goal",""), "hidden_goal": "", "current_conflict": ""},
        "emotional_state"       : {"current": "normal", "intensity": "low", "reason": "", "last_chapter_index": 0},
        "first_seen"            : bc.get("first_appearance","bible_sync"),
        "last_seen_chapter_index": 0,
    }
