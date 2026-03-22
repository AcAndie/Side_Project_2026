#!/bin/bash
# docker-entrypoint.sh — Khởi tạo môi trường trước khi chạy pipeline.
#
# Chạy tự động khi container start (ENTRYPOINT trong Dockerfile).
# Không cần chỉnh sửa khi dùng bình thường.
set -e

# ── Đảm bảo tất cả thư mục tồn tại ──────────────────────────────
# Cần thiết vì bind mount từ host có thể tạo thư mục rỗng
# không có đủ subdirectory mà pipeline cần.
mkdir -p \
    /app/inputs \
    /app/outputs \
    /app/logs \
    /app/data/glossary \
    /app/data/characters \
    /app/data/skills \
    /app/data/memory

# ── Kiểm tra API key ──────────────────────────────────────────────
# Warn nhưng không exit — user có thể đã set GEMINI_API_KEY
# trực tiếp qua environment variable thay vì file .env
if [ ! -f /app/.env ] && [ -z "$GEMINI_API_KEY" ]; then
    echo ""
    echo "⚠️  Warning: /app/.env không tìm thấy và GEMINI_API_KEY chưa set."
    echo "   Cách 1: Mount file .env vào container (xem docker-compose.yml)"
    echo "   Cách 2: Set GEMINI_API_KEY trong environment của docker compose"
    echo ""
fi

# ── Chạy lệnh được truyền vào ────────────────────────────────────
exec "$@"