"""
src/littrans/engine/pre_processor.py — Pre-call: chuẩn bị "bản đồ" cho chapter.

Chạy TRƯỚC Translation call, mỗi chương 1 lần.
Nhiệm vụ:
  - Xác định tên nào / skill nào xuất hiện trong chương này
  - Chốt pronoun pair đang active cho từng cặp nhân vật
  - Phát hiện alias, danh tính đặc biệt, scene bất thường
  [v5.0] Scene Planner nhẹ:
  - Xác định POV character chính
  - Lập danh sách 3–5 scene beats theo thứ tự
  - Đánh giá tone cảm xúc chủ đạo của chương

Input nhỏ → output nhỏ → tiêu tốn ít TPM.
Không raise — nếu lỗi, pipeline vẫn chạy với chapter_map rỗng (fallback).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from littrans.config.settings import settings
from littrans.utils.io_utils import load_json


# ── Output schema ─────────────────────────────────────────────────

@dataclass
class ChapterMap:
    """Kết quả Pre-call — đưa vào Translation call."""

    # Tên / skill đã lock
    active_names    : dict[str, str]   = field(default_factory=dict)
    active_skills   : dict[str, str]   = field(default_factory=dict)

    # Pronoun pairs đang active
    pronoun_pairs   : list[str]        = field(default_factory=list)

    # Cảnh báo đặc biệt
    scene_warnings  : list[str]        = field(default_factory=list)

    # ── Scene Planner (v5.0) ──────────────────────────────────────
    pov_character   : str              = ""
    # VD: "Arthur" hoặc "Omniscient" hoặc "Multiple (Arthur → Klein)"

    scene_beats     : list[str]        = field(default_factory=list)
    # ["Beat 1: Arthur gặp Klein tại quán rượu",
    #  "Beat 2: Klein tiết lộ thông tin về Sequence ...",
    #  "Beat 3: Arthur quyết định ..."]
    # Tối đa 5 beats, đủ ngắn để AI dịch hiểu mạch truyện

    chapter_tone    : str              = ""
    # "tense" | "comedic" | "melancholic" | "action" | "slice_of_life"
    # | "revelatory" | "romantic" | "mysterious"

    ok              : bool             = True

    def is_empty(self) -> bool:
        return not (self.active_names or self.active_skills
                    or self.pronoun_pairs or self.scene_warnings
                    or self.pov_character or self.scene_beats)

    def has_scene_plan(self) -> bool:
        return bool(self.pov_character or self.scene_beats or self.chapter_tone)

    def to_prompt_block(self) -> str:
        """Format để chèn vào Translation prompt."""
        if self.is_empty():
            return ""
        lines = ["**Chapter Map (Pre-analyzed):**"]

        # ── Tên / skill ───────────────────────────────────────────
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

        # ── Scene Plan ────────────────────────────────────────────
        if self.has_scene_plan():
            lines.append("\n**Scene Plan:**")

            if self.pov_character:
                lines.append(f"  POV: {self.pov_character}")

            if self.chapter_tone:
                _tone_hint = {
                    "tense"       : "căng thẳng — câu ngắn, nhịp nhanh",
                    "comedic"     : "hài hước — cho phép lối viết nhẹ nhàng, punchline",
                    "melancholic" : "u sầu — câu văn chậm, giàu cảm xúc",
                    "action"      : "hành động — động từ mạnh, mô tả sắc nét",
                    "slice_of_life": "đời thường — tự nhiên, gần gũi",
                    "revelatory"  : "khải thị — trang trọng, nặng tầm quan trọng",
                    "romantic"    : "lãng mạn — tinh tế, ý nhị",
                    "mysterious"  : "bí ẩn — mơ hồ có chủ đích, không giải thích thừa",
                }.get(self.chapter_tone, self.chapter_tone)
                lines.append(f"  Tone: {self.chapter_tone} — {_tone_hint}")

            if self.scene_beats:
                lines.append("  Beats:")
                for beat in self.scene_beats:
                    lines.append(f"    • {beat}")

        # ── Cảnh báo ──────────────────────────────────────────────
        if self.scene_warnings:
            lines.append("\n⚠️  Cảnh báo:")
            for w in self.scene_warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)


# ── System prompt ─────────────────────────────────────────────────

_PRE_SYSTEM = """Bạn là AI phân tích truyện, hỗ trợ pipeline dịch LitRPG / Tu Tiên.

Đọc chapter tiếng Anh được cung cấp.
Dựa trên bảng tên đã lock và danh sách nhân vật, sinh "bản đồ chapter".

═══════════════════════════════════════════════════════════
PHẦN 1 — TÊN / SKILL / XƯNG HÔ
═══════════════════════════════════════════════════════════
QUY TẮC:
- Chỉ liệt kê tên/skill THỰC SỰ XUẤT HIỆN trong chapter này.
- active_names: tên nhân vật, địa danh, tổ chức có trong bảng lock → điền bản dịch đã lock.
  Tên chưa có trong bảng → KHÔNG liệt kê.
- active_skills: tương tự, chỉ skill đã có trong danh sách đã biết.
- pronoun_pairs: xác định cặp xưng hô đang dùng, ghi rõ nguồn (strong/weak/inferred).
- scene_warnings: flashback, hồi ký, nhân vật dùng alias, giọng kể bất thường.

═══════════════════════════════════════════════════════════
PHẦN 2 — SCENE PLAN (MỚI)
═══════════════════════════════════════════════════════════
Phân tích nhẹ để giúp AI dịch hiểu mạch truyện trước khi dịch.

pov_character:
  - Tên nhân vật đang giữ góc nhìn chính (người đọc "ở trong đầu" ai).
  - Nếu ngôi thứ 3 toàn tri: "Omniscient"
  - Nếu POV thay đổi trong chương: "Multiple (A → B)" hoặc "Multiple (A, B)"

scene_beats:
  - 3 đến 5 sự kiện/hành động CHÍNH theo thứ tự xuất hiện.
  - Mỗi beat: 1 câu ngắn, đủ để AI dịch nhận ra đang ở đoạn nào.
  - KHÔNG spoil hay giải thích — chỉ mô tả hành động/sự kiện.
  Ví dụ tốt:
    "Beat 1: Arthur tỉnh dậy trong hầm ngục, phát hiện mình bị giam cầm"
    "Beat 2: Một người lính mang thức ăn, vô tình tiết lộ vị trí"
    "Beat 3: Arthur kích hoạt Fool's Clown, tạo ảo giác đánh lạc hướng"
  Ví dụ xấu: "Beat 1: Arthur bị bắt" (quá mờ)

chapter_tone:
  Chọn MỘT trong các giá trị: tense | comedic | melancholic | action
  | slice_of_life | revelatory | romantic | mysterious
  Chọn tone CHỦ ĐẠO, không phải từng cảnh nhỏ.

═══════════════════════════════════════════════════════════

Trả về JSON. KHÔNG thêm bất cứ thứ gì ngoài JSON:
{
  "active_names"  : { "English": "Bản VN đã lock" },
  "active_skills" : { "English Skill": "[Tên VN]" },
  "pronoun_pairs" : ["CharA ↔ CharB: cặp xưng hô (nguồn)"],
  "scene_warnings": ["cảnh báo nếu có"],
  "pov_character" : "Tên nhân vật hoặc Omniscient",
  "scene_beats"   : [
    "Beat 1: ...",
    "Beat 2: ...",
    "Beat 3: ..."
  ],
  "chapter_tone"  : "tense"
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

    # 1. Bảng tên đã lock
    if name_lock_table:
        lock_lines = "\n".join(
            f"  {eng} → {vn}"
            for eng, vn in sorted(name_lock_table.items(), key=lambda x: x[0].lower())
        )
        parts.append(f"## BẢNG TÊN ĐÃ LOCK\n{lock_lines}")

    # 2. Nhân vật active — tên + pronoun_self + pronoun pairs
    if char_profiles:
        char_lines = []
        active_data = load_json(settings.characters_active_file)
        chars = active_data.get("characters", {}) if active_data else {}
        for name in char_profiles:
            profile = chars.get(name, {})
            pronoun_self = profile.get("speech", {}).get("pronoun_self", "?")
            strong_rels = []
            for other, r in profile.get("relationships", {}).items():
                if r.get("pronoun_status") == "strong" and r.get("dynamic"):
                    strong_rels.append(f"{name} ↔ {other}: {r['dynamic']} (strong)")
            char_lines.append(f"  {name} | tự xưng: {pronoun_self}")
            char_lines.extend(f"    {rel}" for rel in strong_rels)
        parts.append("## NHÂN VẬT ACTIVE\n" + "\n".join(char_lines))

    # 3. Skills đã biết
    if known_skills:
        skill_lines = "\n".join(
            f"  {eng} → {rec.get('vietnamese', '?')}"
            for eng, rec in known_skills.items()
        )
        parts.append(f"## SKILLS ĐÃ BIẾT\n{skill_lines}")

    # 4. Chapter text (giới hạn 12k ký tự)
    MAX_CHAPTER_CHARS = 12_000
    chapter_preview = chapter_text[:MAX_CHAPTER_CHARS]
    if len(chapter_text) > MAX_CHAPTER_CHARS:
        chapter_preview += "\n\n[... nội dung tiếp theo bị cắt bớt cho pre-analysis ...]"
    parts.append(f"## CHAPTER\n{chapter_preview}")

    return "\n\n---\n\n".join(parts)


def _parse(data: dict) -> ChapterMap:
    """Parse JSON từ AI → ChapterMap, tolerant với field thiếu."""
    # Validate và normalize chapter_tone
    tone = _safe_str(data.get("chapter_tone"))
    _valid_tones = {
        "tense", "comedic", "melancholic", "action",
        "slice_of_life", "revelatory", "romantic", "mysterious",
    }
    if tone and tone.lower() not in _valid_tones:
        tone = ""  # bỏ qua giá trị không hợp lệ

    # Normalize scene_beats: đảm bảo là list[str], tối đa 5
    beats = _safe_list(data.get("scene_beats"))
    beats = [str(b).strip() for b in beats if b][:5]

    return ChapterMap(
        active_names   = _safe_dict(data.get("active_names")),
        active_skills  = _safe_dict(data.get("active_skills")),
        pronoun_pairs  = _safe_list(data.get("pronoun_pairs")),
        scene_warnings = _safe_list(data.get("scene_warnings")),
        pov_character  = _safe_str(data.get("pov_character")),
        scene_beats    = beats,
        chapter_tone   = tone.lower() if tone else "",
        ok             = True,
    )


def _safe_dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _safe_list(v) -> list:
    return v if isinstance(v, list) else []


def _safe_str(v) -> str:
    return str(v).strip() if v else ""