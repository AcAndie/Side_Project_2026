"""
src/littrans/context/bible_store.py — BibleStore: đọc/ghi 3 tầng Bible.

[Refactor] bible/ → context/. Import: bible.schemas → context.schemas.
"""
# Nội dung giống hệt src/littrans/bible/bible_store.py
# CHỈ THAY ĐỔI: dòng import schemas

from __future__ import annotations

import os
import re
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from littrans.context.schemas import (          # ← ĐỔI: bible.schemas → context.schemas
    BibleCharacter, BibleItem, BibleLocation, BibleSkill,
    BibleFaction, BibleConcept, BibleWorldBuilding, BibleMainLore,
    BibleMeta, ScanOutput, IndexEntry, DATABASE_FILES, ENTITY_MODELS,
    BibleChapterSummary, BibleEvent, BiblePlotThread, BibleRevelation,
    ConsistencyReport,
)
from littrans.utils.io_utils import load_json, save_json, atomic_write

try:
    import ahocorasick as _ahocorasick
    _AHO_AVAILABLE = True
except ImportError:
    _AHO_AVAILABLE = False

_entity_automaton_cache : dict[int, Any]  = {}
_entity_automaton_lock  = threading.Lock()
_ENTITY_AHO_CACHE_MAX   = 3

_PREFIXES = {
    "character" : "char",
    "item"      : "item",
    "location"  : "loc",
    "skill"     : "skl",
    "faction"   : "fac",
    "concept"   : "con",
    "event"     : "evt",
    "thread"    : "thr",
    "revelation": "rev",
}


def _make_id(entity_type: str, counter: int) -> str:
    prefix = _PREFIXES.get(entity_type, entity_type[:3])
    return f"{prefix}_{counter:04d}"


def _build_entity_automaton(index: dict[str, dict]):
    if not _AHO_AVAILABLE or not index:
        return None
    cache_key = hash(frozenset(index.keys()))
    with _entity_automaton_lock:
        if cache_key in _entity_automaton_cache:
            return _entity_automaton_cache[cache_key]
        A    = _ahocorasick.Automaton()
        added = 0
        for name_key, entry in index.items():
            if len(name_key) >= 3:
                A.add_word(name_key, (name_key, entry))
                added += 1
        if added == 0:
            return None
        A.make_automaton()
        if len(_entity_automaton_cache) >= _ENTITY_AHO_CACHE_MAX:
            oldest = next(iter(_entity_automaton_cache))
            del _entity_automaton_cache[oldest]
        _entity_automaton_cache[cache_key] = A
        return A


# ══════════════════════════════════════════════════════════════════
# Toàn bộ class BibleStore giống hệt bible/bible_store.py
# (copy nguyên, không sửa gì ngoài import ở trên)
# ══════════════════════════════════════════════════════════════════

# ⚠️  HƯỚNG DẪN DI CHUYỂN:
# Copy toàn bộ nội dung class BibleStore từ src/littrans/bible/bible_store.py
# vào đây, bắt đầu từ dòng "class BibleStore:" đến hết file.
# Không cần sửa gì thêm — import schemas ở trên đã được sửa rồi.

# Dưới đây là phần class đầy đủ — copy từ bible_store.py:

class BibleStore:
    """Đọc/ghi toàn bộ 3 tầng Bible. Thread-safe, atomic write. In-memory cache."""

    def __init__(self, bible_dir: Path) -> None:
        self._dir         = bible_dir
        self._db_dir      = bible_dir / "database"
        self._staging_dir = bible_dir / "staging"
        self._db_lock    = threading.Lock()
        self._wb_lock    = threading.Lock()
        self._lore_lock  = threading.Lock()
        self._meta_lock  = threading.Lock()
        self._idx_lock   = threading.Lock()
        self._db_cache   : dict[str, tuple[list[dict], float]] = {}
        self._index_cache: tuple[dict, float] | None           = None
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._staging_dir.mkdir(parents=True, exist_ok=True)
        self._counters: dict[str, int] = {}

    def _get_file_mtime(self, path: Path) -> float:
        try:
            return os.path.getmtime(str(path))
        except OSError:
            return 0.0

    def invalidate_cache(self, entity_type: str | None = None) -> None:
        if entity_type:
            self._db_cache.pop(entity_type, None)
        else:
            self._db_cache.clear()
            self._index_cache = None

    def _meta_path(self) -> Path:
        return self._dir / "meta.json"

    def load_meta(self) -> BibleMeta:
        with self._meta_lock:
            raw = load_json(self._meta_path())
            return BibleMeta.model_validate(raw) if raw else BibleMeta()

    def save_meta(self, meta: BibleMeta) -> None:
        with self._meta_lock:
            atomic_write(self._meta_path(), meta.model_dump_json(indent=2))

    def update_meta(self, **kwargs) -> None:
        meta = self.load_meta()
        for k, v in kwargs.items():
            if hasattr(meta, k):
                setattr(meta, k, v)
        meta.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.save_meta(meta)

    def get_scan_progress(self) -> dict[str, Any]:
        meta  = self.load_meta()
        total = meta.total_chapters or 1
        return {
            "total": meta.total_chapters, "scanned": meta.scanned_chapters,
            "pct": round(meta.scanned_chapters / total * 100, 1),
            "last_chapter": meta.last_scanned_chapter,
            "depth": meta.scan_depth_used, "cross_ref": meta.cross_ref_last_run,
        }

    def is_chapter_scanned(self, chapter: str) -> bool:
        return chapter in {s.chapter for s in self._load_main_lore().chapter_summaries}

    def mark_chapter_scanned(self, chapter: str) -> None:
        meta = self.load_meta()
        if chapter not in (meta.last_scanned_chapter or ""):
            meta.scanned_chapters += 1
            meta.last_scanned_chapter = chapter
            meta.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.save_meta(meta)

    def get_stats(self) -> dict[str, Any]:
        meta  = self.load_meta()
        index = self._load_index()
        type_counts: dict[str, int] = {}
        for entry in index.values():
            t = entry.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "meta": meta.model_dump(), "by_type": type_counts,
            "staging": len(list(self._staging_dir.glob("*.json"))),
            "lore_chapters": len(self._load_main_lore().chapter_summaries),
        }

    # ── Index ──────────────────────────────────────────────────────

    def _index_path(self) -> Path:
        return self._db_dir / "index.json"

    def _load_index(self) -> dict[str, dict]:
        path  = self._index_path()
        mtime = self._get_file_mtime(path)
        if self._index_cache is not None:
            cached_data, cached_mtime = self._index_cache
            if mtime <= cached_mtime:
                return cached_data
        raw  = load_json(path)
        data = raw if isinstance(raw, dict) else {}
        self._index_cache = (data, mtime)
        return data

    def _save_index(self, index: dict[str, dict]) -> None:
        path = self._index_path()
        save_json(path, index)
        self._index_cache = (index, self._get_file_mtime(path))

    def _index_add(self, entity_id: str, entity_type: str, canonical_name: str, en_name: str) -> None:
        with self._idx_lock:
            index = self._load_index()
            key = (canonical_name or en_name).lower().strip()
            if key:
                index[key] = {"id": entity_id, "type": entity_type, "name": canonical_name, "en": en_name}
            en_key = en_name.lower().strip()
            if en_key and en_key != key:
                index[en_key] = {"id": entity_id, "type": entity_type, "name": canonical_name, "en": en_name}
            self._save_index(index)

    def _index_lookup(self, name: str) -> dict | None:
        index = self._load_index()
        key   = name.lower().strip()
        if key in index:
            return index[key]
        for k, v in index.items():
            if key in k or k in key:
                if len(key) >= 3 and abs(len(key) - len(k)) <= 4:
                    return v
        return None

    # ── DB files ───────────────────────────────────────────────────

    def _db_path(self, entity_type: str) -> Path:
        plural = entity_type + "s" if not entity_type.endswith("s") else entity_type
        return self._db_dir / f"{plural}.json"

    def _load_db_file(self, entity_type: str) -> list[dict]:
        path  = self._db_path(entity_type)
        mtime = self._get_file_mtime(path)
        if entity_type in self._db_cache:
            cached_data, cached_mtime = self._db_cache[entity_type]
            if mtime <= cached_mtime:
                return cached_data
        raw  = load_json(path)
        data = raw.get("entities", []) if isinstance(raw, dict) else []
        self._db_cache[entity_type] = (data, mtime)
        return data

    def _save_db_file(self, entity_type: str, entities: list[dict]) -> None:
        path = self._db_path(entity_type)
        save_json(path, {"entities": entities})
        self._db_cache[entity_type] = (entities, self._get_file_mtime(path))

    def get_entity(self, name: str, entity_type: str | None = None) -> dict | None:
        entry = self._index_lookup(name)
        if not entry:
            return None
        if entity_type and entry["type"] != entity_type:
            return None
        with self._db_lock:
            for e in self._load_db_file(entry["type"]):
                if e.get("id") == entry["id"]:
                    return e
        return None

    def get_entity_by_id(self, entity_id: str) -> dict | None:
        for prefix, t in [("char","character"),("item","item"),("loc","location"),
                           ("skl","skill"),("fac","faction"),("con","concept")]:
            if entity_id.startswith(prefix + "_"):
                with self._db_lock:
                    for e in self._load_db_file(t):
                        if e.get("id") == entity_id:
                            return e
        return None

    def upsert_entity(self, entity_type: str, data: dict) -> str:
        if entity_type not in ENTITY_MODELS:
            raise ValueError(f"entity_type không hợp lệ: {entity_type}")
        with self._db_lock:
            entities  = self._load_db_file(entity_type)
            entity_id = data.get("id", "")
            if not entity_id:
                existing = self._index_lookup(data.get("canonical_name","") or data.get("en_name",""))
                if existing and existing["type"] == entity_type:
                    entity_id = existing["id"]
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            data["last_updated"] = now
            if entity_id:
                for i, e in enumerate(entities):
                    if e.get("id") == entity_id:
                        merged = self._merge_entity(e, data)
                        merged["id"] = entity_id
                        entities[i] = merged
                        self._save_db_file(entity_type, entities)
                        self._index_add(entity_id, entity_type, merged.get("canonical_name",""), merged.get("en_name",""))
                        return entity_id
                data["id"] = entity_id
            else:
                entity_id    = _make_id(entity_type, len(entities) + 1)
                existing_ids = {e.get("id") for e in entities}
                n            = len(entities) + 1
                while entity_id in existing_ids:
                    n += 1; entity_id = _make_id(entity_type, n)
                data["id"] = entity_id
                data.setdefault("type", entity_type)
            entities.append(data)
            self._save_db_file(entity_type, entities)
            self._index_add(entity_id, entity_type, data.get("canonical_name",""), data.get("en_name",""))
            meta = self.load_meta()
            counts = meta.entity_counts
            counts[entity_type] = len(entities)
            meta.entity_counts = counts
            meta.last_updated = now
            self.save_meta(meta)
            return entity_id

    def _merge_entity(self, existing: dict, new_data: dict) -> dict:
        merged = dict(existing)
        LIST_FIELDS = ("aliases","skill_ids","member_ids","effects","notable_features","evolution_chain",
                       "tags","speech_quirks","key_moments","secrets","relationships",
                       "allied_faction_ids","enemy_faction_ids","history_notes","economy_notes","cosmology_notes")
        for key, new_val in new_data.items():
            if key in ("id","type"):
                continue
            old_val = merged.get(key)
            if isinstance(new_val, list) and key in LIST_FIELDS:
                old_list = old_val if isinstance(old_val, list) else []
                for item in new_val:
                    if item and item not in old_list:
                        old_list.append(item)
                merged[key] = old_list
            elif isinstance(new_val, str):
                if new_val.strip(): merged[key] = new_val
            elif isinstance(new_val, dict) and isinstance(old_val, dict):
                merged[key] = {**old_val, **{k: v for k, v in new_val.items() if v}}
            elif isinstance(new_val, int) and key == "chapter_count":
                merged[key] = max(old_val or 0, new_val)
            elif new_val is not None:
                merged[key] = new_val
        return merged

    def get_character(self, name: str) -> dict | None:
        return self.get_entity(name, "character")

    def upsert_character(self, data: dict) -> str:
        return self.upsert_entity("character", data)

    def get_all_entities(self, entity_type: str) -> list[dict]:
        with self._db_lock:
            return list(self._load_db_file(entity_type))

    def get_all_characters(self) -> list[dict]:
        return self.get_all_entities("character")

    def get_entities_for_chapter(self, chapter_text: str) -> dict[str, list[dict]]:
        text_lower = chapter_text.lower()
        index      = self._load_index()
        matched_ids: dict[str, set] = {}
        automaton = _build_entity_automaton(index)
        if automaton is not None:
            for end_idx, (name_key, entry) in automaton.iter(text_lower):
                if len(name_key) < 3: continue
                start  = end_idx - len(name_key) + 1
                before = text_lower[start - 1] if start > 0 else " "
                after  = text_lower[end_idx + 1] if end_idx + 1 < len(text_lower) else " "
                if not before.isalnum() and not after.isalnum():
                    matched_ids.setdefault(entry["type"], set()).add(entry["id"])
        else:
            for name_key, entry in index.items():
                if len(name_key) < 3: continue
                try:
                    if re.search(rf"(?<![^\W_]){re.escape(name_key)}(?![^\W_])", text_lower, re.IGNORECASE|re.UNICODE):
                        matched_ids.setdefault(entry["type"], set()).add(entry["id"])
                except re.error:
                    if name_key in text_lower:
                        matched_ids.setdefault(entry["type"], set()).add(entry["id"])
        result: dict[str, list[dict]] = {}
        for entity_type, ids in matched_ids.items():
            with self._db_lock:
                all_e = self._load_db_file(entity_type)
            result[entity_type] = [e for e in all_e if e.get("id") in ids]
        return result

    def search_entities(self, query: str, entity_type: str | None = None) -> list[dict]:
        query_lower = query.lower().strip()
        index       = self._load_index()
        ids_by_type: dict[str, set[str]] = {}
        for name_key, entry in index.items():
            if query_lower in name_key or name_key in query_lower:
                t = entry["type"]
                if entity_type and t != entity_type: continue
                ids_by_type.setdefault(t, set()).add(entry["id"])
        results: list[dict] = []
        with self._db_lock:
            for t, ids in ids_by_type.items():
                for entity in self._load_db_file(t):
                    if entity.get("id") in ids:
                        results.append(entity)
                        if len(results) >= 50: return results
        return results

    # ── WorldBuilding ──────────────────────────────────────────────

    def _wb_path(self) -> Path: return self._dir / "worldbuilding.json"

    def _load_worldbuilding(self) -> BibleWorldBuilding:
        raw = load_json(self._wb_path())
        return BibleWorldBuilding.model_validate(raw) if raw else BibleWorldBuilding()

    def get_worldbuilding(self) -> BibleWorldBuilding:
        with self._wb_lock: return self._load_worldbuilding()

    def update_worldbuilding(self, updates: dict[str, Any]) -> None:
        with self._wb_lock:
            wb  = self._load_worldbuilding()
            raw = wb.model_dump()
            for key, val in updates.items():
                if key not in raw: continue
                if isinstance(val, list):
                    existing = raw.get(key, [])
                    if not isinstance(existing, list): existing = []
                    _ser = lambda o: o.model_dump() if hasattr(o, "model_dump") else o
                    existing_strs = {json.dumps(_ser(e), ensure_ascii=False, sort_keys=True) for e in existing}
                    for item in val:
                        item_str = json.dumps(_ser(item), ensure_ascii=False, sort_keys=True)
                        if item_str not in existing_strs:
                            existing.append(item); existing_strs.add(item_str)
                    raw[key] = existing
                elif isinstance(val, str) and val.strip(): raw[key] = val
                elif isinstance(val, dict): raw[key] = {**(raw.get(key) or {}), **val}
            raw["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            atomic_write(self._wb_path(), BibleWorldBuilding.model_validate(raw).model_dump_json(indent=2))

    def get_relevant_worldbuilding(self, chapter_text: str) -> str:
        wb = self.get_worldbuilding(); lines = []
        for cs in wb.cultivation_systems:
            if cs.name and cs.name.lower() in chapter_text.lower():
                lines.append(f"**Hệ thống tu luyện: {cs.name}**")
                for realm in cs.realms[:6]:
                    lines.append(f"  {realm.order}. {realm.name_vn} ({realm.name_en})")
        relevant_rules = [r.description for r in wb.confirmed_rules
                          if any(word in chapter_text.lower() for word in r.description.lower().split()[:5])]
        if relevant_rules[:3]:
            lines.append("\n**Quy luật thế giới liên quan:**")
            lines.extend(f"  - {r}" for r in relevant_rules[:3])
        return "\n".join(lines)

    # ── Main Lore ──────────────────────────────────────────────────

    def _lore_path(self) -> Path: return self._dir / "main_lore.json"

    def _load_main_lore(self) -> BibleMainLore:
        raw = load_json(self._lore_path())
        return BibleMainLore.model_validate(raw) if raw else BibleMainLore()

    def _save_main_lore(self, lore: BibleMainLore) -> None:
        atomic_write(self._lore_path(), lore.model_dump_json(indent=2))

    def append_chapter_summary(self, summary: BibleChapterSummary) -> None:
        with self._lore_lock:
            lore = self._load_main_lore()
            if summary.chapter not in {s.chapter for s in lore.chapter_summaries}:
                lore.chapter_summaries.append(summary)
                lore.last_chapter_scanned = summary.chapter
                self._save_main_lore(lore)

    def append_event(self, event: BibleEvent) -> str:
        with self._lore_lock:
            lore = self._load_main_lore()
            lore.event_counter += 1
            if not event.id: event.id = _make_id("event", lore.event_counter)
            lore.events.append(event)
            self._save_main_lore(lore)
            return event.id

    def append_plot_thread(self, thread: BiblePlotThread) -> str:
        with self._lore_lock:
            lore = self._load_main_lore()
            lore.thread_counter += 1
            if not thread.id: thread.id = _make_id("thread", lore.thread_counter)
            for t in lore.plot_threads:
                if t.name.lower() == thread.name.lower():
                    if thread.status in ("closed","abandoned") and t.status == "open":
                        t.status = thread.status; t.closed_chapter = thread.closed_chapter
                        t.resolution = thread.resolution
                        for ch in thread.key_chapters:
                            if ch not in t.key_chapters: t.key_chapters.append(ch)
                    self._save_main_lore(lore); return t.id
            lore.plot_threads.append(thread)
            self._save_main_lore(lore); return thread.id

    def update_plot_thread_status(self, thread_name: str, status: str, closed_chapter: str="", resolution: str="") -> bool:
        with self._lore_lock:
            lore = self._load_main_lore()
            for t in lore.plot_threads:
                if t.name.lower() == thread_name.lower():
                    t.status = status; t.closed_chapter = closed_chapter; t.resolution = resolution
                    self._save_main_lore(lore); return True
        return False

    def append_revelation(self, revelation: BibleRevelation) -> str:
        with self._lore_lock:
            lore = self._load_main_lore()
            lore.revelation_counter += 1
            if not revelation.id: revelation.id = _make_id("revelation", lore.revelation_counter)
            lore.revelations.append(revelation)
            self._save_main_lore(lore); return revelation.id

    def get_recent_lore(self, n: int = 3) -> list[BibleChapterSummary]:
        lore = self._load_main_lore()
        return lore.chapter_summaries[-n:] if lore.chapter_summaries else []

    def get_plot_threads(self, status: str | None = None) -> list[BiblePlotThread]:
        lore = self._load_main_lore()
        threads = lore.plot_threads
        if status: threads = [t for t in threads if t.status == status]
        return threads

    def get_active_foreshadows(self, current_chapter: str) -> list[str]:
        return [f"⚠️  Tuyến truyện đang mở: {t.name} (từ {t.opened_chapter})"
                for t in self.get_plot_threads("open")[:5]]

    def format_recent_lore_for_prompt(self, n: int = 3) -> str:
        recent = self.get_recent_lore(n)
        if not recent: return ""
        lines = [f"**Tóm tắt {len(recent)} chương gần nhất (từ Bible):**"]
        for s in recent:
            lines.append(f"\n**{s.chapter}** [{s.tone}]")
            lines.append(s.summary)
            if s.key_events: lines.extend(f"  - {e}" for e in s.key_events[:3])
        return "\n".join(lines)

    # ── Staging ───────────────────────────────────────────────────

    def _staging_path(self, chapter: str) -> Path:
        safe = re.sub(r"[^\w\-.]", "_", chapter)
        return self._staging_dir / f"stage_{safe}.json"

    def save_staging(self, chapter: str, scan_output: ScanOutput) -> None:
        atomic_write(self._staging_path(chapter), scan_output.model_dump_json(indent=2))

    def load_staging(self, chapter: str) -> ScanOutput | None:
        path = self._staging_path(chapter)
        if not path.exists(): return None
        raw = load_json(path)
        return ScanOutput.model_validate(raw) if raw else None

    def load_all_staging(self) -> list[ScanOutput]:
        outputs = []
        for p in sorted(self._staging_dir.glob("stage_*.json")):
            raw = load_json(p)
            if raw:
                try: outputs.append(ScanOutput.model_validate(raw))
                except Exception as e: logging.warning(f"[BibleStore] staging lỗi {p.name}: {e}")
        outputs.sort(key=lambda o: o.chapter_index)
        return outputs

    def clear_staging(self, chapters: list[str] | None = None) -> int:
        count = 0
        if chapters:
            for ch in chapters:
                p = self._staging_path(ch)
                if p.exists(): p.unlink(); count += 1
        else:
            for p in self._staging_dir.glob("stage_*.json"): p.unlink(); count += 1
        return count

    def has_staging(self) -> bool:
        return any(self._staging_dir.glob("stage_*.json"))

    def staging_count(self) -> int:
        return len(list(self._staging_dir.glob("stage_*.json")))

    def export_all_json(self, output_path: Path) -> None:
        db = {t + "s": self.get_all_entities(t) for t in ("character","item","location","skill","faction","concept")}
        blob = {"meta": self.load_meta().model_dump(), "database": db,
                "worldbuilding": self.get_worldbuilding().model_dump(),
                "main_lore": self._load_main_lore().model_dump()}
        atomic_write(output_path, json.dumps(blob, ensure_ascii=False, indent=2))

    def rebuild_index(self) -> int:
        new_index: dict[str, dict] = {}
        for t in ("character","item","location","skill","faction","concept"):
            for e in self._load_db_file(t):
                eid = e.get("id",""); cname = e.get("canonical_name",""); ename = e.get("en_name","")
                if not eid: continue
                for name in [cname, ename] + e.get("aliases", []):
                    k = name.lower().strip()
                    if k and len(k) >= 2: new_index[k] = {"id": eid, "type": t, "name": cname, "en": ename}
        with self._idx_lock: self._save_index(new_index)
        return len(new_index)
