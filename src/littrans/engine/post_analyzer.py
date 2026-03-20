"""
src/littrans/engine/post_analyzer.py — Post-call: review + extract metadata.

Chạy SAU Translation call. Làm 2 việc:
  1. Đánh giá chất lượng bản dịch:
       - Lỗi trình bày/cấu trúc → tự sửa (auto_fix)
       - Lỗi dịch thuật (tên, kỹ năng, pronoun) → yêu cầu retry Trans-call
  2. Extract metadata:
       new_terms, new_characters, relationship_updates, skill_updates

Severity:
  auto_fix       → Post-call tự sửa trong auto_fixed_translation
  retry_required → Trans-call cần chạy lại với retry_instruction

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
    severity  : str   # auto_fix | retry_required
    location  : str   # trích đoạn ngắn nơi xảy ra lỗi
    detail    : str   # mô tả lỗi


@dataclass
class PostResult:
    # Bản dịch cuối cùng — có thể đã được auto_fix
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
    ok                  : bool = True   # False nếu post-call lỗi hoàn toàn
    auto_fixed          : bool = False  # True nếu có auto_fix được áp dụng

    def has_retry_required(self) -> bool:
        return any(i.severity == "retry_required" for i in self.issues)

    def has_auto_fix(self) -> bool:
        return any(i.severity == "auto_fix" for i in self.issues)


# ── System prompt ─────────────────────────────────────────────────

_POST_SYSTEM = """Bạn là AI editor chuyên review bản dịch LitRPG / Tu Tiên.

Bạn nhận được:
  1. Bản gốc tiếng Anh
  2. Bản dịch tiếng Việt
  3. Chapter Map (tên/skill/pronoun đã lock cho chapter này)

Nhiệm vụ 1 — ĐÁNH GIÁ CHẤT LƯỢNG:
Phân loại lỗi theo severity:

auto_fix (tự sửa được):
  - Thiếu dòng trống giữa các đoạn văn thường
  - Thoại bị dính dòng (2 người nói cùng dòng)
  - System box / bảng hệ thống có dòng trống thừa GIỮA các dòng trong box
    (Lưu ý: system box phải liền nhau, không có dòng trống ở giữa)
  - Thừa/thiếu dấu cách, markdown lỗi lẻ tẻ

retry_required (Trans-call phải chạy lại):
  - Tên nhân vật / địa danh sai hoặc lọt qua Name Lock
  - Tên kỹ năng sai so với danh sách đã lock
  - Pronoun sai (dùng sai cặp xưng hô)
  - Đoạn văn bị mất hoặc ý nghĩa lệch nghiêm trọng
  - Câu bị cắt cụt, thiếu nội dung

Nhiệm vụ 2 — EXTRACT METADATA:
Đọc bản gốc + bản dịch, extract:
  - new_terms: tên/thuật ngữ mới lần đầu xuất hiện (kể cả giữ nguyên EN)
  - new_characters: nhân vật có tên xuất hiện lần đầu (tên + vai trò + mô tả ngắn)
  - relationship_updates: thay đổi quan hệ thực sự quan trọng giữa 2 nhân vật
  - skill_updates: kỹ năng MỚI hoặc TIẾN HÓA lần đầu

QUAN TRỌNG khi viết auto_fixed_translation:
  - Chỉ sửa đúng những gì bị đánh dấu auto_fix
  - Giữ nguyên toàn bộ nội dung còn lại
  - Nếu không có lỗi auto_fix, để auto_fixed_translation = ""

Trả về JSON. KHÔNG thêm bất cứ thứ gì ngoài JSON:
{
  "quality": {
    "passed": true/false,
    "auto_fixed_translation": "bản dịch đã sửa hoặc chuỗi rỗng",
    "issues": [
      {
        "type": "format|structure|name_leak|pronoun|style|missing",
        "severity": "auto_fix|retry_required",
        "location": "trích đoạn ngắn (dưới 50 ký tự)",
        "detail": "mô tả lỗi cụ thể"
      }
    ],
    "retry_instruction": "hướng dẫn cụ thể nếu cần retry, chuỗi rỗng nếu passed"
  },
  "metadata": {
    "new_terms": [
      {"english": "...", "vietnamese": "...", "category": "general|items|locations|..."}
    ],
    "new_characters": [
      {"name": "tên VN", "original": "tên EN", "role": "vai trò", "description": "mô tả"}
    ],
    "relationship_updates": [
      {
        "character_a": "...", "character_b": "...",
        "event": "mô tả sự kiện", "new_dynamic": "cặp xưng hô mới nếu có"
      }
    ],
    "skill_updates": [
      {
        "english": "...", "vietnamese": "[...]",
        "owner": "...", "skill_type": "active|passive|ultimate|evolution",
        "evolved_from": ""
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

    # Chapter Map (tóm tắt để tiết kiệm tokens)
    if chapter_map and not chapter_map.is_empty():
        parts.append(f"## CHAPTER MAP\n{chapter_map.to_prompt_block()}")

    # Giới hạn source + translation để tránh tốn quá nhiều TPM
    # Post-call cần đọc đủ để review, không cần đến từng chữ
    MAX_CHARS = 15_000
    src_preview = source_text[:MAX_CHARS]
    if len(source_text) > MAX_CHARS:
        src_preview += "\n[... bị cắt bớt ...]"
    tl_preview  = translation[:MAX_CHARS]
    if len(translation) > MAX_CHARS:
        tl_preview += "\n[... bị cắt bớt ...]"

    parts.append(f"## BẢN GỐC (EN)\n{src_preview}")
    parts.append(f"## BẢN DỊCH (VN)\n{tl_preview}")

    return "\n\n---\n\n".join(parts)


def _parse(data: dict, original_translation: str, filename: str) -> PostResult:
    """Parse JSON từ AI → PostResult, tolerant với field thiếu."""
    quality  = data.get("quality", {})
    metadata = data.get("metadata", {})

    # Parse issues
    issues = []
    for raw in quality.get("issues", []):
        if not isinstance(raw, dict):
            continue
        issues.append(QualityIssue(
            type     = raw.get("type", "unknown"),
            severity = raw.get("severity", "auto_fix"),
            location = raw.get("location", ""),
            detail   = raw.get("detail", ""),
        ))

    passed  = bool(quality.get("passed", True))
    auto_tx = quality.get("auto_fixed_translation", "").strip()
    retry   = quality.get("retry_instruction", "").strip()

    # Xác định final_translation
    has_auto_fix_issues = any(i.severity == "auto_fix" for i in issues)
    if has_auto_fix_issues and auto_tx:
        final_translation = auto_tx
        auto_fixed        = True
        if issues:
            _log_fixes(issues, filename)
    else:
        final_translation = original_translation
        auto_fixed        = False

    # Log retry issues
    retry_issues = [i for i in issues if i.severity == "retry_required"]
    if retry_issues:
        for issue in retry_issues:
            logging.warning(
                f"[PostAnalyzer] {filename} | {issue.type} | {issue.detail} | at: {issue.location}"
            )

    return PostResult(
        final_translation    = final_translation,
        passed               = passed,
        issues               = issues,
        retry_instruction    = retry,
        new_terms            = _safe_list(metadata.get("new_terms")),
        new_characters       = _safe_list(metadata.get("new_characters")),
        relationship_updates = _safe_list(metadata.get("relationship_updates")),
        skill_updates        = _safe_list(metadata.get("skill_updates")),
        ok                   = True,
        auto_fixed           = auto_fixed,
    )


def _log_fixes(issues: list[QualityIssue], filename: str) -> None:
    fix_issues = [i for i in issues if i.severity == "auto_fix"]
    if fix_issues:
        logging.info(
            f"[PostAnalyzer] {filename} | auto_fix {len(fix_issues)} lỗi: "
            + "; ".join(i.type for i in fix_issues)
        )


def _safe_list(v: Any) -> list:
    return v if isinstance(v, list) else []