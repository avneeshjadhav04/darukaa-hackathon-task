# syntax=docker/dockerfile:1

# ---------- Stage 1: build the React frontend with Bun ----------
FROM oven/bun:1 AS ui
WORKDIR /build
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ROOT=/app \
    PORT=8000
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=ui /build/dist ./static
COPY data/knowledge/ ./data/knowledge/
RUN mkdir -p /app/data

# State is container-local (/app/data): Chroma index + SQLite DB. It resets on
# redeploy/restart by design — structured facts auto-re-ingest on first upload/chat.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD sh -c "python -c \"import sys,urllib.request,os;u=f'http://localhost:{os.environ.get(\"PORT\",\"8000\")}/api/health';sys.exit(0 if urllib.request.urlopen(u).status==200 else 1)\""

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
