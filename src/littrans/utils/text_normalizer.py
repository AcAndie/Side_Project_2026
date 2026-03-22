"""
src/littrans/utils/text_normalizer.py — Redirect shim.

File gốc đã được chuyển về src/littrans/core/text_normalizer.py.
File này giữ lại để không break bất kỳ import nào từ utils còn sót.

[v5.3 Refactor] Không sửa file này. Sửa core/text_normalizer.py.
"""
# Re-export toàn bộ public API từ core
from littrans.core.text_normalizer import (  # noqa: F401
    normalize,
    _rejoin_broken_lines,
    _clean_box_blank_lines,
    _is_special_line,
    _looks_like_box_content,
    _peek_next_non_empty,
)

__all__ = ["normalize"]