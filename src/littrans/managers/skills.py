"""
src/littrans/managers/skills.py — Quản lý Skills.json.

Lưu kỹ năng đã biết xuyên suốt truyện, bao gồm evolution chain.
Dùng để:
  1. Tra cứu tên VN đã chốt khi dịch bảng hệ thống
  2. Nhận báo cáo kỹ năng mới/tiến hóa từ AI → cập nhật Skills.json
  3. Filter cho prompt: chỉ đưa vào kỹ năng XUẤT HIỆN trong chương

[v2.0] Refactor dùng BaseManager — public API (module-level functions) không đổi.
"""
from __future__ import annotations

import re

from littrans.config.settings import settings
from littrans.managers.base import BaseManager


# ═══════════════════════════════════════════════════════════════════
# MANAGER
# ═══════════════════════════════════════════════════════════════════

class SkillsManager(BaseManager):

    def _empty_db(self) -> dict:
        return {
            "meta"  : {"schema_version": "1.0", "last_updated_chapter": ""},
            "skills": {},
        }

    def stats(self) -> dict[str, int]:
        skills = self._load().get("skills", {})
        evos   = sum(1 for s in skills.values() if s.get("evolved_from"))
        return {"total": len(skills), "evolution": evos, "base": len(skills) - evos}

    # ── Read ──────────────────────────────────────────────────────

    def load_for_chapter(self, chapter_text: str) -> dict[str, dict]:
        """
        Trả về {english_name: skill_record} cho kỹ năng XUẤT HIỆN trong chương.
        Đưa vào prompt phần System Box.
        """
        skills = self._load().get("skills", {})
        result = {}
        for eng, rec in skills.items():
            vn      = rec.get("vietnamese", "")
            vn_bare = vn.strip("[]")
            if (
                (eng and re.search(rf"\b{re.escape(eng)}\b", chapter_text, re.IGNORECASE))
                or (vn_bare and re.search(rf"\b{re.escape(vn_bare)}\b", chapter_text, re.IGNORECASE))
            ):
                result[eng] = rec
        return result

    # ── Write ─────────────────────────────────────────────────────

    def add_updates(self, updates: list, source_chapter: str) -> int:
        """
        Thêm kỹ năng mới / cập nhật evolution chain vào Skills.json.
        Trả về số kỹ năng thực sự thêm/cập nhật.
        """
        if not updates:
            return 0

        self.ensure_dir()

        with self._lock:
            data   = self._load_locked()
            skills = data.setdefault("skills", {})
            count  = 0

            for upd in updates:
                eng = upd.english.strip()
                vn  = upd.vietnamese.strip()
                if not eng or not vn:
                    continue

                if eng in skills:
                    existing = skills[eng]
                    changed  = False

                    if upd.evolved_from and upd.evolved_from != existing.get("evolved_from", ""):
                        existing["evolved_from"] = upd.evolved_from
                        chain = existing.setdefault(
                            "evolution_chain", [existing.get("vietnamese", vn)]
                        )
                        if vn not in chain:
                            chain.append(vn)
                        existing["vietnamese"] = vn
                        changed = True

                    if upd.description and not existing.get("description"):
                        existing["description"] = upd.description
                        changed = True

                    if changed:
                        count += 1
                else:
                    skills[eng] = {
                        "vietnamese"     : vn,
                        "owner"          : upd.owner,
                        "skill_type"     : upd.skill_type,
                        "evolved_from"   : upd.evolved_from,
                        "description"    : upd.description,
                        "first_seen"     : source_chapter,
                        "evolution_chain": (
                            [vn] if not upd.evolved_from else [upd.evolved_from, vn]
                        ),
                    }
                    count += 1

            if count:
                data["meta"]["last_updated_chapter"] = source_chapter
                self._save(data)

        return count


# ═══════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETON + PUBLIC API
# Call-sites không cần đổi gì.
# ═══════════════════════════════════════════════════════════════════

_manager = SkillsManager(settings.skills_file)


def load_skills_for_chapter(chapter_text: str) -> dict[str, dict]:
    return _manager.load_for_chapter(chapter_text)


def format_skills_for_prompt(skills: dict[str, dict]) -> str:
    """Format danh sách kỹ năng để đưa vào PHẦN 2 — system box context."""
    if not skills:
        return ""
    lines = [
        "**Kỹ năng đã biết (tra cứu khi dịch bảng hệ thống):**",
        "  PHẢI dùng tên VN đã chốt. KHÔNG tự đặt tên mới nếu đã có trong danh sách này.",
        "",
        f"  {'TÊN TIẾNG ANH':<30} TÊN CHUẨN (dùng trong bản dịch)   CHỦ SỞ HỮU",
        "  " + "─" * 72,
    ]
    for eng, rec in sorted(skills.items(), key=lambda x: x[0].lower()):
        vn     = rec.get("vietnamese", "?")
        owner  = rec.get("owner", "—")
        evo    = rec.get("evolved_from", "")
        suffix = f"  ← tiến hóa từ [{evo}]" if evo else ""
        lines.append(f"  {eng:<30} {vn:<35} {owner}{suffix}")
    return "\n".join(lines)


def add_skill_updates(updates: list, source_chapter: str) -> int:
    return _manager.add_updates(updates, source_chapter)


def skills_stats() -> dict[str, int]:
    return _manager.stats()