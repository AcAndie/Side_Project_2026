"""
src/littrans/core/pre_processor.py — Pre-call: chuẩn bị "bản đồ" cho chapter.

Chạy TRƯỚC Translation call, mỗi chương 1 lần.
Nhiệm vụ:
  - Xác định tên nào / skill nào xuất hiện trong chương này
  - Chốt pronoun pair đang active cho từng cặp nhân vật
  - Phát hiện alias, danh tính đặc biệt, scene bất thường

Input nhỏ → output nhỏ → tiêu tốn ít TPM.
Không raise — nếu lỗi, pipeline vẫn chạy với chapter_map rỗng (fallback).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from littrans.config.settings import settings
from littrans.utils.io_utils import load_json, safe_list, safe_dict


# ── Output schema ─────────────────────────────────────────────────

@dataclass
class ChapterMap:
    """Kết quả Pre-call — đưa vào Translation call."""
    active_names    : dict[str, str]   = field(default_factory=dict)
    # { "English Name": "Bản dịch đã lock" }

    active_skills   : dict[str, str]   = field(default_factory=dict)
    # { "English Skill": "[Tên VN đã lock]" }

    pronoun_pairs   : list[str]        = field(default_factory=list)
    # ["CharA ↔ CharB: Ta–Ngươi (strong)", ...]

    scene_warnings  : list[str]        = field(default_factory=list)
    # ["Chương có flashback — giữ nguyên xưng hô Tao–Mày", ...]

    ok              : bool             = True
    # False nếu pre-call lỗi hoàn toàn → pipeline vẫn chạy

    def is_empty(self) -> bool:
        return not (self.active_names or self.active_skills
                    or self.pronoun_pairs or self.scene_warnings)

    def to_prompt_block(self) -> str:
        """Format để chèn vào Translation prompt."""
        if self.is_empty():
            return ""
        lines = ["**Chapter Map (Pre-analyzed):**"]

        if self.active_names:
            lines.append("\nTên đã chốt trong chương này:")
            for eng, vn in self.active_names.items():
                lines.append(f"  {eng} → {vn}")

        if self.active_skills:
            lines.append("\nKỹ năng đã chốt trong chương này:")
            for eng, vn in self.active_skills.items():
                lines.append(f"  {eng} → {vn}")

        if self.pronoun_pairs:
            lines.append("\nXưng hô đang active:")
            for pair in self.pronoun_pairs:
                lines.append(f"  {pair}")

        if self.scene_warnings:
            lines.append("\n⚠️  Cảnh báo:")
            for w in self.scene_warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)


# ── System prompt ─────────────────────────────────────────────────

_PRE_SYSTEM = """Bạn là AI phân tích truyện, hỗ trợ pipeline dịch LitRPG / Tu Tiên.

Đọc chapter tiếng Anh được cung cấp.
Dựa trên bảng tên đã lock và danh sách nhân vật, sinh "bản đồ chapter".

QUY TẮC:
- Chỉ liệt kê tên/skill THỰC SỰ XUẤT HIỆN trong chapter này.
- active_names: tên nhân vật, địa danh, tổ chức có trong bảng lock → điền bản dịch đã lock.
  Tên chưa có trong bảng → KHÔNG liệt kê (để Translation call tự xử lý).
- active_skills: tương tự, chỉ skill đã có trong danh sách đã biết.
- pronoun_pairs: xác định cặp xưng hô đang dùng, ghi rõ nguồn (strong/weak/inferred).
- scene_warnings: flashback, hồi ký, nhân vật dùng alias, giọng kể bất thường.

Trả về JSON. KHÔNG thêm bất cứ thứ gì ngoài JSON:
{
  "active_names": { "English": "Bản VN đã lock" },
  "active_skills": { "English Skill": "[Tên VN]" },
  "pronoun_pairs": ["CharA ↔ CharB: cặp xưng hô (nguồn)"],
  "scene_warnings": ["cảnh báo nếu có"]
}"""


# ── Public API ────────────────────────────────────────────────────

def run(
    chapter_text    : str,
    name_lock_table : dict[str, str],
    char_profiles   : dict[str, str],
    known_skills    : dict[str, dict],
) -> ChapterMap:
    """
    Chạy Pre-call. Trả về ChapterMap.
    Không raise — lỗi trả về ChapterMap(ok=False).
    """
    if not chapter_text.strip():
        return ChapterMap(ok=False)

    user_msg = _build_user_message(
        chapter_text, name_lock_table, char_profiles, known_skills
    )

    try:
        from littrans.llm.client import call_gemini_json
        data = call_gemini_json(_PRE_SYSTEM, user_msg)
        return _parse(data)
    except Exception as e:
        logging.error(f"[PreProcessor] {e}")
        print(f"  ⚠️  Pre-call lỗi: {e} → tiếp tục không có chapter map")
        return ChapterMap(ok=False)


# ── Helpers ───────────────────────────────────────────────────────

def _build_user_message(
    chapter_text    : str,
    name_lock_table : dict[str, str],
    char_profiles   : dict[str, str],
    known_skills    : dict[str, dict],
) -> str:
    parts = []

    # 1. Bảng tên đã lock (chỉ gửi tên, không cần full format)
    if name_lock_table:
        lock_lines = "\n".join(
            f"  {eng} → {vn}"
            for eng, vn in sorted(name_lock_table.items(), key=lambda x: x[0].lower())
        )
        parts.append(f"## BẢNG TÊN ĐÃ LOCK\n{lock_lines}")

    # 2. Nhân vật active — chỉ tên + pronoun_self + pronoun pairs đã có
    if char_profiles:
        char_lines = []
        active_data = load_json(settings.characters_active_file)
        chars = active_data.get("characters", {}) if active_data else {}
        for name in char_profiles:
            profile = chars.get(name, {})
            pronoun_self = profile.get("speech", {}).get("pronoun_self", "?")
            # Thu thập strong relationships
            strong_rels = []
            for other, r in profile.get("relationships", {}).items():
                if r.get("pronoun_status") == "strong" and r.get("dynamic"):
                    strong_rels.append(f"{name} ↔ {other}: {r['dynamic']} (strong)")
            char_lines.append(f"  {name} | tự xưng: {pronoun_self}")
            char_lines.extend(f"    {rel}" for rel in strong_rels)
        parts.append("## NHÂN VẬT ACTIVE\n" + "\n".join(char_lines))

    # 3. Skills đã biết — chỉ tên EN + VN
    if known_skills:
        skill_lines = "\n".join(
            f"  {eng} → {rec.get('vietnamese', '?')}"
            for eng, rec in known_skills.items()
        )
        parts.append(f"## SKILLS ĐÃ BIẾT\n{skill_lines}")

    # 4. Chapter text — giới hạn để tiết kiệm tokens
    MAX_CHAPTER_CHARS = 12_000
    chapter_preview = chapter_text[:MAX_CHAPTER_CHARS]
    if len(chapter_text) > MAX_CHAPTER_CHARS:
        chapter_preview += "\n\n[... nội dung tiếp theo bị cắt bớt cho pre-analysis ...]"
    parts.append(f"## CHAPTER\n{chapter_preview}")

    return "\n\n---\n\n".join(parts)


def _parse(data: dict) -> ChapterMap:
    """Parse JSON từ AI → ChapterMap, tolerant với field thiếu."""
    return ChapterMap(
        active_names  = safe_dict(data.get("active_names")),
        active_skills = safe_dict(data.get("active_skills")),
        pronoun_pairs = safe_list(data.get("pronoun_pairs")),
        scene_warnings= safe_list(data.get("scene_warnings")),
        ok            = True,
    )