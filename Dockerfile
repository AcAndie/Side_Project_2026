# ── Stage 1: Builder ─────────────────────────────────────────────
# Cài compiler để build pyahocorasick (C extension) và các wheel khác.
# Compiler không đi vào image runtime.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml requirements.txt ./

# Build tất cả wheels tại đây — bao gồm pyahocorasick cần gcc
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels \
    "google-genai>=1.0" \
    "pydantic>=2.0" \
    "python-dotenv>=1.0" \
    "typer[all]>=0.12" \
    "tqdm>=4.0" \
    "pyahocorasick>=2.0" \
    "streamlit>=1.30" \
    "pandas>=2.0"


# ── Stage 2: Runtime ─────────────────────────────────────────────
# Image gọn nhẹ: chỉ cài wheels đã build sẵn, không cần gcc.
FROM python:3.11-slim AS runtime

WORKDIR /app

# Cài từ wheels đã build — không compile lại
COPY --from=builder /build/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/*.whl && \
    rm -rf /tmp/wheels

# Source code và prompts (baked vào image)
COPY src/          ./src/
COPY main.py       ./
COPY run_ui.py     ./
COPY prompts/      ./prompts/

# Tạo sẵn thư mục data — sẽ bị override bởi bind mounts khi chạy
RUN mkdir -p \
    inputs outputs logs \
    data/glossary data/characters \
    data/skills data/memory

# Non-root user để tăng security
RUN useradd -m -u 1000 -s /bin/bash littrans && \
    chown -R littrans:littrans /app
USER littrans

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8501

# Health check dùng urllib stdlib — không cần cài curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" \
    || exit 1

# Entrypoint script khởi tạo thư mục và kiểm tra .env
COPY --chown=littrans:littrans docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# Default: khởi động Web UI
CMD ["python", "run_ui.py", "--host", "0.0.0.0"]