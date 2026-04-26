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
# 2b. CONTEXT AUGMENT (Bible = ENHANCE, không REPLACE)
# ═══════════════════════════════════════════════════════════════════

# Map bible entity_type → glossary category (settings.glossary_files key)
_ENTITY_TO_CATEGORY = {
    "item"    : "items",
    "location": "locations",
    "faction" : "organizations",
    "concept" : "general",
}


def _format_bible_term_line(entity: dict) -> str | None:
    en  = (entity.get("en_name") or "").strip()
    vn  = (entity.get("canonical_name") or "").strip()
    if not en or not vn:
        return None
    desc = (entity.get("description") or "").strip()
    if desc:
        # Cắt mô tả dài để tiết kiệm token prompt
        if len(desc) > 120:
            desc = desc[:117] + "..."
        return f"- {en}: {vn} — {desc}"
    return f"- {en}: {vn}"


def augment_ctx_from_bible(
    glossary_ctx : dict[str, list[str]],
    char_profiles: dict[str, str],
    chapter_text : str,
) -> tuple[int, int]:
    """
    Bổ sung (KHÔNG overwrite) glossary_ctx và char_profiles từ Bible Store
    cho các entity xuất hiện trong chapter_text.

    Returns: (n_glossary_added, n_chars_added).
    """
    from littrans.config.settings import settings
    from littrans.context.bible_store import BibleStore
    from littrans.core.patterns import word_boundary_search

    if not settings.bible_available:
        return 0, 0

    store = BibleStore(settings.bible_dir)

    # ── Glossary augment ────────────────────────────────────────
    n_g = 0
    for entity_type, cat in _ENTITY_TO_CATEGORY.items():
        try:
            entities = store.get_all_entities(entity_type)
        except Exception as _e:
            logging.exception(f"[BiblePatch] get_all_entities({entity_type}): {_e}")
            continue
        for ent in entities:
            en  = (ent.get("en_name") or "").strip()
            vn  = (ent.get("canonical_name") or "").strip()
            if not en or not vn:
                continue
            if not (word_boundary_search(en, chapter_text) or
                    word_boundary_search(vn.strip("[]"), chapter_text)):
                continue
            line = _format_bible_term_line(ent)
            if line is None:
                continue
            cat_lines = glossary_ctx.setdefault(cat, [])
            # Skip nếu en_name đã có trong category (tránh duplicate)
            key_lc = en.lower()
            if any(key_lc in (l or "").lower() for l in cat_lines):
                continue
            cat_lines.append(line)
            n_g += 1

    # ── Characters augment ──────────────────────────────────────
    n_c = 0
    try:
        bible_chars = store.get_all_characters()
    except Exception as _e:
        logging.exception(f"[BiblePatch] get_all_characters: {_e}")
        bible_chars = []

    for bc in bible_chars:
        name = (bc.get("canonical_name") or "").strip() \
            or (bc.get("en_name") or "").strip()
        if not name or len(name) < 2 or name in char_profiles:
            continue
        # Match trên en_name + canonical + aliases
        candidates = [bc.get("en_name", ""), bc.get("canonical_name", "")]
        candidates.extend(bc.get("aliases") or [])
        if not any(c and word_boundary_search(c, chapter_text) for c in candidates):
            continue
        # Mini stub profile (Pre-call chỉ cần biết name; Bible prompt builder
        # tự fetch full profile từ store)
        stub_lines = [
            f"### {name}  [BIBLE] [{bc.get('role','?')}]",
            f"**Pronoun_self:** {bc.get('pronoun_self','—')}",
        ]
        personality = bc.get("personality_summary", "")
        if personality:
            stub_lines.append(f"**Personality:** {personality}")
        char_profiles[name] = "\n".join(stub_lines)
        n_c += 1

    return n_g, n_c


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
