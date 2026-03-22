"""
src/littrans/engine/post_analyzer.py — Post-call: review + extract metadata.

Chạy SAU Translation call + SAU post_processor.run(). Làm 2 việc:
  1. Đánh giá chất lượng bản dịch (đã được code-cleanup):
       - Lỗi dịch thuật (tên, kỹ năng, pronoun) → yêu cầu retry Trans-call
       - Lỗi format nhỏ còn sót → mô tả để log (không cần sửa — post_processor đã làm)
  2. Extract metadata đầy đủ:
       new_terms, new_characters (full profile), relationship_updates, skill_updates

[v4.3 FIX] auto_fixed_translation KHÔNG còn nằm trong JSON response.
[v5.0] Bỏ hoàn toàn _auto_fix_call() — thay bằng post_processor.py (code thuần).
       PostResult.auto_fixed vẫn giữ để backward compat nhưng luôn = False từ đây.

Không raise — nếu lỗi hoàn toàn, trả về PostResult với translation gốc + metadata rỗng.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from littrans.config.settings import settings


# ── Output schema ─────────────────────────────────────────────────

@dataclass
class QualityIssue:
    type      : str   # format | structure | name_leak | pronoun | style | missing
    severity  : str   # warn | retry_required  (không còn "auto_fix" — đã xử lý bởi post_processor)
    location  : str   # trích đoạn ngắn nơi xảy ra lỗi
    detail    : str   # mô tả lỗi


@dataclass
class PostResult:
    # Bản dịch cuối cùng
    final_translation   : str

    # Chất lượng
    passed              : bool
    issues              : list[QualityIssue] = field(default_factory=list)
    retry_instruction   : str               = ""

    # Metadata để update Master State
    new_terms           : list[dict]        = field(default_factory=list)
    new_characters      : list[dict]        = field(default_factory=list)
    relationship_updates: list[dict]        = field(default_factory=list)
    skill_updates       : list[dict]        = field(default_factory=list)

    # Meta
    ok                  : bool = True
    auto_fixed          : bool = False  # Luôn False — cleanup do post_processor.py đảm nhiệm

    def has_retry_required(self) -> bool:
        return any(i.severity == "retry_required" for i in self.issues)

    def has_auto_fix(self) -> bool:
        """Backward compat — luôn False vì post_processor đã xử lý."""
        return False


# ── System prompt ─────────────────────────────────────────────────

_POST_SYSTEM = """Bạn là AI editor chuyên review bản dịch LitRPG / Tu Tiên.

Bạn nhận được:
  1. Bản gốc tiếng Anh
  2. Bản dịch tiếng Việt (đã qua code cleanup cơ bản)
  3. Chapter Map (tên/skill/pronoun đã lock cho chapter này)

═══════════════════════════════════════════════════════════
NHIỆM VỤ 1 — ĐÁNH GIÁ CHẤT LƯỢNG
═══════════════════════════════════════════════════════════
Lưu ý: Bản dịch đã qua code cleanup (dấu câu, dòng trống, code block wrapper).
Chỉ báo cáo các lỗi mà code KHÔNG thể tự sửa:

retry_required (Trans-call phải chạy lại):
  - Tên nhân vật / địa danh sai hoặc lọt qua Name Lock
  - Tên kỹ năng sai so với danh sách đã lock
  - Pronoun sai (dùng sai cặp xưng hô đã chốt)
  - Đoạn văn bị mất hoặc ý nghĩa lệch nghiêm trọng
  - Câu bị cắt cụt, thiếu nội dung quan trọng

warn (ghi log, không cần retry):
  - Văn phong chưa tự nhiên ở đoạn cụ thể
  - Thuật ngữ dịch chưa hay nhưng không sai
  - Lỗi format nhẹ còn sót (ít ảnh hưởng đến đọc)

KHÔNG báo cáo:
  - Dấu câu, dòng trống, code block — đã được xử lý tự động
  - Lỗi spacing thông thường

═══════════════════════════════════════════════════════════
NHIỆM VỤ 2 — EXTRACT METADATA ĐẦY ĐỦ
═══════════════════════════════════════════════════════════
Đọc bản gốc + bản dịch, extract chính xác.

── new_characters ──────────────────────────────────────────
Nhân vật có tên xuất hiện LẦN ĐẦU → điền FULL profile.

Quy tắc tên:
  - "name" = tên gốc tiếng Anh (dùng làm key trong database)
  - "canonical_name" = tên VN chuẩn sẽ dùng xuyên suốt truyện
  - Tên Hán (Zhang Wei, Xiao Yan) → dịch Hán Việt làm canonical_name
  - Tên phương Tây (Arthur, Klein) → canonical_name = giữ nguyên EN

Quy tắc archetype (chọn đúng 1):
  MC_GREMLIN    → cợt nhả, ảo thật, tự xưng Tao/Tôi
  SYSTEM_AI     → vô cảm, châm biếm ngầm, Hệ thống/Ký chủ
  EDGELORD      → tỏ vẻ nguy hiểm, ngầu lòi, Ta/bọn kiến rệp
  ARROGANT_NOBLE → khinh khỉnh, thượng đẳng, Bản thiếu gia/Ngươi
  BRO_COMPANION → sảng khoái, nhiệt huyết, Tớ/Cậu
  ANCIENT_MAGE  → cổ trang, uyên bác, Lão phu/Tiểu tử
  UNKNOWN       → chưa xác định

Quy tắc personality_traits:
  - 4-6 câu, MỖI câu phải đủ ngữ cảnh để dùng ngay khi dịch
  - KHÔNG dùng keyword ngắn một mình ("lạnh lùng", "mạnh mẽ")
  - ĐÚNG: "Bề ngoài lạnh lùng với người lạ nhưng quan sát — tin rồi thì trung thành tuyệt đối"

Quy tắc relationships.dynamic:
  - Cặp đại từ 2 chiều: VD "Tao/Mày", "Ta/Ngươi", "Anh/Em"
  - pronoun_status: "weak" nếu chưa chắc, "strong" nếu đã xác nhận rõ ràng

Quy tắc relationships.intimacy_level:
  1 = FORMAL (lạnh lùng, trang trọng)
  2 = NEUTRAL (mặc định)
  3 = FRIENDLY (thân thiện, thoải mái)
  4 = CLOSE (rất thân, nickname, bỏ kính ngữ)
  5 = INTIMATE (yêu/gia đình gần gũi, ngôn ngữ đặc biệt)

Quy tắc relationships.eps_signals:
  Liệt kê các dấu hiệu cụ thể về mức độ thân mật:
  - Có dùng nickname hay không
  - Bỏ kính ngữ từ lúc nào
  - Độ dài câu khi nói chuyện (ngắn/dài)
  - Chia sẻ cảm xúc trực tiếp hay không

═══════════════════════════════════════════════════════════

Trả về JSON. KHÔNG thêm bất cứ thứ gì ngoài JSON:
{
  "quality": {
    "passed": true,
    "issues": [
      {
        "type": "format|structure|name_leak|pronoun|style|missing",
        "severity": "warn|retry_required",
        "location": "trích đoạn ngắn dưới 50 ký tự",
        "detail": "mô tả lỗi cụ thể"
      }
    ],
    "retry_instruction": ""
  },
  "metadata": {
    "new_terms": [
      {
        "english": "tên/thuật ngữ EN",
        "vietnamese": "bản dịch VN",
        "category": "general|items|locations|organizations|pathways"
      }
    ],
    "new_characters": [
      {
        "name": "tên gốc EN — dùng làm key",
        "canonical_name": "tên VN chuẩn",
        "alias_canonical_map": { "alias_EN": "alias_VN" },
        "full_name": "",
        "aliases": [],
        "active_identity": "",
        "identity_context": "",
        "current_title": "",
        "faction": "",
        "cultivation_path": "",
        "current_level": "",
        "signature_skills": [],
        "combat_style": "",
        "role": "MC|Party Member|Enemy|NPC|Mentor|Rival|Love Interest|Antagonist|Unknown",
        "archetype": "MC_GREMLIN|SYSTEM_AI|EDGELORD|ARROGANT_NOBLE|BRO_COMPANION|ANCIENT_MAGE|UNKNOWN",
        "personality_traits": [
          "trait 1 — câu đủ ngữ cảnh",
          "trait 2 — câu đủ ngữ cảnh"
        ],
        "pronoun_self": "Tao|Ta|Tôi|...",
        "formality_level": "low|medium-low|medium|medium-high|high",
        "formality_note": "",
        "how_refers_to_others": [
          { "target": "tên cụ thể hoặc default_ally/default_enemy", "style": "đại từ + ngữ cảnh" }
        ],
        "speech_quirks": [],
        "relationships": [
          {
            "with_character": "tên nhân vật kia",
            "rel_type": "ally|enemy|neutral|romantic|family|mentor|rival",
            "feeling": "cảm xúc hiện tại",
            "dynamic": "Tao/Mày",
            "pronoun_status": "weak|strong",
            "intimacy_level": 2,
            "eps_signals": ["dấu hiệu 1", "dấu hiệu 2"],
            "current_status": "mô tả trạng thái",
            "tension_points": [],
            "history": []
          }
        ],
        "relationship_to_mc": "",
        "current_goal": "",
        "hidden_goal": "",
        "current_conflict": ""
      }
    ],
    "relationship_updates": [
      {
        "character_a": "tên nhân vật A",
        "character_b": "tên nhân vật B",
        "event": "mô tả sự kiện",
        "new_type": "",
        "new_feeling": "",
        "new_status": "",
        "new_dynamic": "",
        "new_tension": "",
        "new_intimacy_level": 0,
        "new_eps_signals": [],
        "promote_to_strong": false
      }
    ],
    "skill_updates": [
      {
        "english": "tên kỹ năng EN",
        "vietnamese": "[Tên Kỹ Năng VN]",
        "owner": "",
        "skill_type": "active|passive|ultimate|evolution|system",
        "evolved_from": "",
        "description": ""
      }
    ]
  }
}"""


# ── Public API ────────────────────────────────────────────────────

def run(
    source_text     : str,
    translation     : str,
    chapter_map     = None,  # ChapterMap | None
    source_filename : str = "",
) -> PostResult:
    """
    Chạy Post-call. Trả về PostResult.

    Lưu ý: translation đầu vào đã được post_processor.py xử lý trước.
    Post-call chỉ review chất lượng dịch thuật và extract metadata.

    Không raise — lỗi trả về PostResult với translation gốc + metadata rỗng.
    """
    if not translation.strip():
        return PostResult(
            final_translation = translation,
            passed            = False,
            ok                = False,
            retry_instruction = "Bản dịch rỗng.",
        )

    user_msg = _build_user_message(source_text, translation, chapter_map)

    try:
        from littrans.llm.client import call_gemini_json
        data = call_gemini_json(_POST_SYSTEM, user_msg)
        return _parse(data, translation, source_filename)
    except Exception as e:
        logging.error(f"[PostAnalyzer] {source_filename} | {e}")
        print(f"  ⚠️  Post-call lỗi: {e} → dùng bản dịch gốc, bỏ qua metadata")
        return PostResult(
            final_translation = translation,
            passed            = True,   # không block pipeline
            ok                = False,
        )


# ── Helpers ───────────────────────────────────────────────────────

def _build_user_message(
    source_text : str,
    translation : str,
    chapter_map,
) -> str:
    parts = []

    if chapter_map and not chapter_map.is_empty():
        parts.append(f"## CHAPTER MAP\n{chapter_map.to_prompt_block()}")

    MAX_CHARS = 15_000
    src_preview = source_text[:MAX_CHARS]
    if len(source_text) > MAX_CHARS:
        src_preview += "\n[... bị cắt bớt ...]"
    tl_preview = translation[:MAX_CHARS]
    if len(translation) > MAX_CHARS:
        tl_preview += "\n[... bị cắt bớt ...]"

    parts.append(f"## BẢN GỐC (EN)\n{src_preview}")
    parts.append(f"## BẢN DỊCH (VN)\n{tl_preview}")

    return "\n\n---\n\n".join(parts)


def _parse(data: dict, original_translation: str, filename: str) -> PostResult:
    quality  = data.get("quality", {})
    metadata = data.get("metadata", {})

    issues = []
    for raw in quality.get("issues", []):
        if not isinstance(raw, dict):
            continue
        severity = raw.get("severity", "warn")
        # Map legacy "auto_fix" → "warn" (post_processor đã xử lý)
        if severity == "auto_fix":
            severity = "warn"
        issues.append(QualityIssue(
            type     = raw.get("type", "unknown"),
            severity = severity,
            location = raw.get("location", ""),
            detail   = raw.get("detail", ""),
        ))

    passed = bool(quality.get("passed", True))
    retry  = quality.get("retry_instruction", "").strip()

    retry_issues = [i for i in issues if i.severity == "retry_required"]
    if retry_issues:
        for issue in retry_issues:
            logging.warning(
                f"[PostAnalyzer] {filename} | {issue.type} | {issue.detail} | at: {issue.location}"
            )

    return PostResult(
        final_translation    = original_translation,
        passed               = passed,
        issues               = issues,
        retry_instruction    = retry,
        new_terms            = _safe_list(metadata.get("new_terms")),
        new_characters       = _safe_list(metadata.get("new_characters")),
        relationship_updates = _safe_list(metadata.get("relationship_updates")),
        skill_updates        = _safe_list(metadata.get("skill_updates")),
        ok                   = True,
        auto_fixed           = False,
    )


def _safe_list(v: Any) -> list:
    return v if isinstance(v, list) else []