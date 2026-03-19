"""
src/littrans/engine/quality_guard.py — Kiểm tra chất lượng bản dịch.

6 tiêu chí (đã nâng cấp từ 4):
  1. Dính dòng nghiêm trọng  → dòng vượt MAX_LINE_LENGTH ký tự
  2. Quá ít dòng             → tổng dòng không rỗng < MIN_TRANSLATION_LINES
  3. Mất dòng so với bản gốc → tỉ lệ mất > MAX_MERGED_LINE_RATIO  (0.50, hạ từ 0.75)
  4. Thiếu dòng trống        → blank_ratio < MIN_BLANK_LINE_RATIO
  5. Bản dịch quá ngắn       → char_ratio < MIN_CHAR_RATIO  (MỚI)
  6. Còn nhiều dòng tiếng Anh chưa dịch  (MỚI)

Trả về (True, "") nếu ổn, (False, mô_tả_lỗi) nếu phát hiện vấn đề.

Nếu vi phạm → pipeline yêu cầu AI dịch lại với cảnh báo cụ thể.
Tối đa MAX_RETRIES lần.  Cảnh báo reset sau mỗi chương.
"""
from __future__ import annotations

import re

MIN_TRANSLATION_LINES  = 10
MAX_LINE_LENGTH        = 1000
MAX_MERGED_LINE_RATIO  = 0.50   # hạ từ 0.75 → bản dịch không được mất quá 50% dòng
MIN_BLANK_LINE_RATIO   = 0.20
MIN_CHAR_RATIO         = 0.45   # bản dịch tối thiểu 45% độ dài ký tự bản gốc
MAX_UNTRANSLATED_RATIO = 0.15   # tối đa 15% dòng còn tiếng Anh nguyên xi


# ── Helpers ───────────────────────────────────────────────────────

def _count_untranslated_lines(lines: list[str]) -> int:
    """
    Đếm dòng có vẻ chưa dịch: > 70% ký tự là ASCII letter.
    Bỏ qua dòng ngắn (< 20 chars) vì thường là tên, kỹ năng, số liệu.
    """
    count = 0
    for line in lines:
        stripped = line.strip()
        if len(stripped) < 20:
            continue
        ascii_alpha = sum(1 for c in stripped if c.isascii() and c.isalpha())
        if ascii_alpha / len(stripped) > 0.70:
            count += 1
    return count


# ── Main check ────────────────────────────────────────────────────

def check(translation: str, source_text: str = "") -> tuple[bool, str]:
    """
    Kiểm tra bản dịch.
    Trả về (True, "") nếu ổn, (False, mô_tả_lỗi) nếu phát hiện vấn đề.
    Thứ tự kiểm tra: từ lỗi nghiêm trọng nhất → nhẹ nhất.
    """
    if not translation or not translation.strip():
        return False, "Bản dịch rỗng."

    all_lines       = translation.splitlines()
    non_empty_lines = [l for l in all_lines if l.strip()]
    blank_lines     = [l for l in all_lines if not l.strip()]
    line_count      = len(non_empty_lines)
    total_lines     = len(all_lines)

    # ── Kiểm tra 1: dính dòng nghiêm trọng ───────────────────────
    long_lines = [l for l in non_empty_lines if len(l) > MAX_LINE_LENGTH]
    if long_lines:
        longest = max(len(l) for l in long_lines)
        return False, (
            f"DÍNH DÒNG NGHIÊM TRỌNG: {len(long_lines)} dòng vượt {MAX_LINE_LENGTH} ký tự "
            f"(dài nhất: {longest} ký tự). Toàn bộ nội dung bị gộp vào một số dòng duy nhất."
        )

    # ── Kiểm tra 2: quá ít dòng ──────────────────────────────────
    if line_count < MIN_TRANSLATION_LINES:
        return False, (
            f"DÍNH DÒNG: Bản dịch chỉ có {line_count} dòng "
            f"(tối thiểu: {MIN_TRANSLATION_LINES}). "
            f"Nhiều đoạn văn bị gộp thành một dòng."
        )

    src_lines = 0
    if source_text and source_text.strip():
        src_lines = len([l for l in source_text.splitlines() if l.strip()])

    # ── Kiểm tra 3: mất dòng so với bản gốc ─────────────────────
    if src_lines >= MIN_TRANSLATION_LINES:
        lost_ratio = (src_lines - line_count) / src_lines
        if lost_ratio > MAX_MERGED_LINE_RATIO:
            lost_pct = int(lost_ratio * 100)
            return False, (
                f"DÍNH DÒNG NHIỀU CHỖ: Bản gốc {src_lines} dòng, "
                f"bản dịch còn {line_count} dòng "
                f"(mất {lost_pct}%, ngưỡng: {int(MAX_MERGED_LINE_RATIO*100)}%). "
                f"Cần xuống dòng đúng như bản gốc."
            )

    # ── Kiểm tra 4: thiếu dòng trống ─────────────────────────────
    if total_lines >= MIN_TRANSLATION_LINES:
        blank_ratio = len(blank_lines) / total_lines if total_lines > 0 else 0
        if blank_ratio < MIN_BLANK_LINE_RATIO:
            blank_pct = int(blank_ratio * 100)
            return False, (
                f"THIẾU DÒNG TRỐNG: {len(blank_lines)}/{total_lines} dòng trống "
                f"({blank_pct}%, ngưỡng: {int(MIN_BLANK_LINE_RATIO*100)}%). "
                f"Mỗi đoạn văn phải cách nhau đúng 1 dòng trống."
            )

    # ── Kiểm tra 5: bản dịch quá ngắn (nội dung bị bỏ qua) ──────
    if source_text and source_text.strip():
        src_char_count  = len(source_text.strip())
        trl_char_count  = len(translation.strip())
        if src_char_count > 200:  # Bỏ qua chương cực ngắn
            char_ratio = trl_char_count / src_char_count
            if char_ratio < MIN_CHAR_RATIO:
                return False, (
                    f"BẢN DỊCH QUÁ NGẮN: chỉ {int(char_ratio*100)}% độ dài bản gốc "
                    f"({trl_char_count:,} / {src_char_count:,} ký tự, "
                    f"ngưỡng tối thiểu: {int(MIN_CHAR_RATIO*100)}%). "
                    f"Nhiều đoạn văn có thể bị bỏ qua."
                )

    # ── Kiểm tra 6: còn nhiều dòng tiếng Anh chưa dịch ──────────
    if line_count >= MIN_TRANSLATION_LINES:
        untranslated = _count_untranslated_lines(non_empty_lines)
        untranslated_ratio = untranslated / line_count
        if untranslated_ratio > MAX_UNTRANSLATED_RATIO and untranslated >= 5:
            return False, (
                f"CÒN DÒNG CHƯA DỊCH: {untranslated}/{line_count} dòng "
                f"({int(untranslated_ratio*100)}%) vẫn là tiếng Anh "
                f"(ngưỡng: {int(MAX_UNTRANSLATED_RATIO*100)}%). "
                f"Kiểm tra lại và dịch các dòng còn sót."
            )

    return True, ""


# ── Retry prompt ──────────────────────────────────────────────────

def build_retry_prompt(original_text: str, quality_msg: str) -> str:
    """
    Tạo input text có gắn cảnh báo khi yêu cầu AI dịch lại.
    """
    # Xác định loại lỗi để đưa ra hướng dẫn cụ thể hơn
    if "DÍNH DÒNG" in quality_msg or "THIẾU DÒNG TRỐNG" in quality_msg:
        specific = (
            "  • TUYỆT ĐỐI KHÔNG gộp nhiều đoạn thành một dòng\n"
            "  • Mỗi đoạn văn gốc = MỘT đoạn văn trong bản dịch\n"
            "  • Sau mỗi đoạn văn PHẢI có đúng 1 dòng trống\n"
        )
    elif "QUÁ NGẮN" in quality_msg:
        specific = (
            "  • KHÔNG bỏ qua bất kỳ đoạn văn, câu, hay hội thoại nào\n"
            "  • Dịch ĐẦY ĐỦ 100% nội dung, không tóm tắt hay rút gọn\n"
            "  • Mỗi đoạn gốc phải có đoạn dịch tương ứng\n"
        )
    elif "CHƯA DỊCH" in quality_msg:
        specific = (
            "  • Dịch TẤT CẢ các dòng tiếng Anh sang tiếng Việt\n"
            "  • Chỉ giữ nguyên tên riêng đã có trong Name Lock Table\n"
            "  • Hội thoại, mô tả, kỹ năng — tất cả phải được dịch\n"
        )
    else:
        specific = (
            "  • GIỮ NGUYÊN cấu trúc đoạn văn của bản gốc\n"
            "  • Xuống dòng và dòng trống đúng như bản gốc\n"
        )

    return (
        f"⚠️ CẢNH BÁO: Bản dịch lần trước bị lỗi — {quality_msg}\n\n"
        f"Hãy dịch lại TOÀN BỘ chương dưới đây, đảm bảo:\n"
        f"{specific}"
        f"  • Số dòng bản dịch phải xấp xỉ số dòng bản gốc\n\n"
        f"--- NỘI DUNG GỐC ---\n\n{original_text}"
    )