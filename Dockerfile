# ============================================
# Stage 1: Builder — cài dependencies bằng uv
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Build tools + git (undetected-chromedriver cài từ git source trong pyproject)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# uv binary (quản lý dependency thay cho pip/requirements.txt)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy lockfiles trước — tận dụng Docker layer caching
COPY pyproject.toml uv.lock ./

# Tạo virtualenv tại /app/.venv, chỉ deps production (--no-dev),
# không cài chính project (--no-install-project) vì source copy ở stage sau
RUN uv sync --frozen --no-dev --no-install-project

# ============================================
# Stage 2: Production — image cuối cùng
# ============================================
FROM python:3.12-slim AS production

# Thiết lập biến môi trường (venv của uv nằm ở /app/.venv)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

WORKDIR /app

# libpq5 cho runtime của psycopg (binary wheel thường tự đủ, thêm cho chắc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Tạo non-root user cho bảo mật
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtualenv đã build từ builder stage (giữ nguyên path /app/.venv)
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY . .

# Chown tất cả file cho appuser
RUN chown -R appuser:appuser /app

# Chuyển sang non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check — gọi /health (start-period dài vì khởi động phải load model + nối DB)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# venv đã nằm trong PATH nên gọi uvicorn trực tiếp (không cần "uv run")
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
