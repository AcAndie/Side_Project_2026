"""
src/littrans/utils/post_processor.py — Redirect shim.

File gốc đã được chuyển về src/littrans/core/post_processor.py.
File này giữ lại để không break bất kỳ import nào từ utils còn sót.

[v5.3 Refactor] Không sửa file này. Sửa core/post_processor.py.
"""
# Re-export toàn bộ public API từ core
from littrans.core.post_processor import (  # noqa: F401
    run,
    report,
)

__all__ = ["run", "report"]