"""
src/littrans/utils/logger.py — DEPRECATED, không còn được dùng.

Tất cả module trong project dùng stdlib `import logging` trực tiếp.
File này không được import từ bất kỳ đâu trong codebase.

Giữ lại để tránh break nếu có code bên ngoài (plugin/script) dùng.
Nếu không có external dependency → xóa file này.
"""
import logging as _logging


def get_logger(name: str) -> _logging.Logger:
    """Deprecated. Dùng: import logging; logger = logging.getLogger(__name__)"""
    return _logging.getLogger(name)


def log_error(name: str, msg: str, exc: Exception | None = None) -> None:
    """Deprecated. Dùng: logging.error(...)"""
    logger = _logging.getLogger(name)
    if exc:
        logger.error(f"{msg}: {exc}", exc_info=False)
    else:
        logger.error(msg)


def log_warning(name: str, msg: str) -> None:
    """Deprecated. Dùng: logging.warning(...)"""
    _logging.getLogger(name).warning(msg)