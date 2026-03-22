"""
src/littrans/bible/pipeline_bible_patch.py — Kết nối Bible System ↔ Pipeline.

3 hàm được gọi trực tiếp từ pipeline.py khi BIBLE_MODE=true:

  init_characters_from_bible()   — startup: sync Bible chars → Characters_Active
                                   Chỉ ADD nhân vật chưa có, KHÔNG overwrite profile cũ.

  build_bible_system_prompt()    — wrapper gọi build_bible_translation_prompt()
                                   với BibleStore hiện tại.

  update_bible_from_post()       — sau mỗi chương dịch xong:
                                   cập nhật last_seen + chapter_count trong Bible DB.
                                   KHÔNG tạo entity mới (đó là việc của BibleScanner).

[v1.0] Initial implementation.
[v1.1] Phase 5.1: pre-compile regex patterns thay vì compile lại trong vòng lặp.
       Với Bible DB lớn (100+ nhân vật) tránh compile O(n) lần mỗi chapter.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime


# ── Regex helper ──────────────────────────────────────────────────

def _compile_name_pattern(name: str):
    """Compile word-boundary pattern cho tên nhân vật/entity."""
    try:
        return re.compile(
            rf"(?<![^\W_]){re.escape(name.lower())}(?![^\W_])",
            re.UNICODE,
        )
    except re.error:
        return None   # tên có ký tự đặc biệt → fallback plain search


def _build_entity_patterns(bc: dict) -> list[tuple[dict, re.Pattern | None, str]]:
    """
    Trả về list[(bc, pattern, name_lower)] cho canonical_name và en_name.
    pattern=None → fallback plain contains.
    """
    entries = []
    for name in [bc.get("canonical_name", ""), bc.get("en_name", "")]:
        if not name or len(name) < 2:
            continue
        entries.append((bc, _compile_name_pattern(name), name.lower()))
    return entries


def _entity_matches(pattern, name_lower: str, text_lower: str) -> bool:
    """Kiểm tra entity có xuất hiện trong text_lower không."""
    if pattern is not None:
        return bool(pattern.search(text_lower))
    return name_lower in text_lower


# ═══════════════════════════════════════════════════════════════════
# 1. STARTUP SYNC: Bible → Characters_Active
# ═══════════════════════════════════════════════════════════════════

def init_characters_from_bible() -> int:
    """
    Đọc Bible Database → Characters_Active.
    Mục đích: đảm bảo pipeline có profile xưng hô cho nhân vật đã được Bible scan.

    Logic:
      - Nhân vật ĐÃ CÓ trong Active → bỏ qua (không overwrite)
      - Nhân vật CHƯA CÓ → convert BibleCharacter → profile format + add

    Trả về số nhân vật đã sync.
    """
    from littrans.config.settings import settings
    from littrans.bible.bible_store import BibleStore
    from littrans.managers.characters import load_active
    from littrans.utils.io_utils import save_json

    store = BibleStore(settings.bible_dir)
    bible_chars = store.get_all_characters()
    if not bible_chars:
        return 0

    active_data  = load_active()
    active_chars = active_data.setdefault("characters", {})
    added = 0

    for bc in bible_chars:
        name = (bc.get("canonical_name") or "").strip() or (bc.get("en_name") or "").strip()
        if not name or len(name) < 2:
            continue
        if name in active_chars:
            continue

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
    """
    Wrapper — tạo BibleStore và gọi build_bible_translation_prompt().
    Được gọi từ pipeline._translate_three_call khi bible_mode=True.
    """
    from littrans.config.settings import settings
    from littrans.bible.bible_store import BibleStore
    from littrans.bible.bible_prompt_builder import build_bible_translation_prompt

    store = BibleStore(settings.bible_dir)
    return build_bible_translation_prompt(
        instructions     = instructions,
        chapter_text     = text,
        chapter_filename = filename,
        store            = store,
        chapter_map      = chapter_map,
        name_lock_table  = name_lock,
        budget_limit     = budget_limit,
    )


# ═══════════════════════════════════════════════════════════════════
# 3. POST-CHAPTER UPDATE
# ═══════════════════════════════════════════════════════════════════

def update_bible_from_post(post_result, filename: str, chapter_text: str) -> None:
    """
    Cập nhật Bible DB sau mỗi chương dịch xong.

    Chỉ cập nhật last_seen và chapter_count — KHÔNG tạo entity mới.

    [v1.1] Pre-compile tất cả regex patterns trước vòng lặp chính
           thay vì compile trong mỗi iteration.
    """
    from littrans.config.settings import settings
    from littrans.bible.bible_store import BibleStore

    try:
        store      = BibleStore(settings.bible_dir)
        text_lower = chapter_text.lower()
        bible_chars = store.get_all_characters()

        if not bible_chars:
            return

        # Pre-compile tất cả patterns một lần
        # entries: list[(bc, pattern_or_None, name_lower)]
        all_entries: list[tuple[dict, re.Pattern | None, str]] = []
        for bc in bible_chars:
            all_entries.extend(_build_entity_patterns(bc))

        # Deduplicate: mỗi bc chỉ update 1 lần dù match nhiều tên
        updated_ids: set[str] = set()

        for bc, pattern, name_lower in all_entries:
            bc_id = bc.get("id", "")
            if bc_id in updated_ids:
                continue

            if _entity_matches(pattern, name_lower, text_lower):
                updated_ids.add(bc_id)
                bc["last_seen"]     = filename
                bc["chapter_count"] = bc.get("chapter_count", 0) + 1
                bc["last_updated"]  = datetime.now().strftime("%Y-%m-%d")
                try:
                    store.upsert_entity("character", bc)
                except Exception as e:
                    name = bc.get("canonical_name") or bc.get("en_name", "?")
                    logging.warning(f"[BiblePatch] upsert last_seen [{name}]: {e}")

    except Exception as e:
        logging.error(f"[BiblePatch] update_bible_from_post {filename}: {e}")


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _bible_char_to_active_profile(bc: dict) -> dict:
    """
    Convert BibleCharacter dict → Characters_Active profile format.
    Tạo profile tối thiểu — đủ để pipeline đọc xưng hô và personality.
    """
    cult  = bc.get("cultivation") or {}
    rels: dict = {}

    for r in bc.get("relationships", []):
        target = (r.get("target_name") or r.get("target_id", "")).strip()
        if not target:
            continue
        rels[target] = {
            "type"          : r.get("rel_type", "neutral"),
            "feeling"       : "",
            "dynamic"       : r.get("dynamic", ""),
            "pronoun_status": "weak",
            "current_status": r.get("description", ""),
            "tension_points": [],
            "history"       : [],
            "intimacy_level": r.get("eps_level", 2),
            "eps_signals"   : [],
        }

    personality_traits = []
    if bc.get("personality_summary"):
        personality_traits = [bc["personality_summary"]]

    return {
        "identity"         : {
            "full_name"       : bc.get("en_name", ""),
            "aliases"         : bc.get("aliases", []),
            "current_title"   : "",
            "faction"         : bc.get("faction_id", ""),
            "cultivation_path": cult.get("realm", ""),
        },
        "power"            : {
            "current_level"   : cult.get("realm", ""),
            "signature_skills": bc.get("skill_ids", []),
            "combat_style"    : bc.get("combat_style", ""),
        },
        "canonical_name"       : bc.get("canonical_name", ""),
        "alias_canonical_map"  : bc.get("alias_canonical_map", {}),
        "active_identity"      : bc.get("canonical_name", ""),
        "known_aliases"        : bc.get("aliases", []),
        "identity_context"     : "",
        "role"                 : bc.get("role", "Unknown"),
        "archetype"            : bc.get("archetype", "UNKNOWN"),
        "personality_traits"   : personality_traits,
        "speech"               : {
            "pronoun_self"        : bc.get("pronoun_self", ""),
            "formality_level"     : "medium",
            "formality_note"      : "",
            "how_refers_to_others": {},
            "speech_quirks"       : bc.get("speech_quirks", []),
        },
        "habitual_behaviors"   : [],
        "relationships"        : rels,
        "arc_status"           : {
            "current_goal"    : bc.get("current_goal", ""),
            "hidden_goal"     : "",
            "current_conflict": "",
        },
        "emotional_state"      : {
            "current"           : "normal",
            "intensity"         : "low",
            "reason"            : "",
            "last_chapter_index": 0,
        },
        "first_seen"              : bc.get("first_appearance", "bible_sync"),
        "last_seen_chapter_index" : 0,
    }