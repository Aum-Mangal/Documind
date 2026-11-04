# ── Stage 1: build the React frontend ────────────────
FROM node:22.23.4-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Empty: the frontend calls the API on the same origin when served by this image
ARG VITE_API_URL=""
RUN npm run build

# ── Stage 2: the API, serving the built frontend ─────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    # Models are downloaded at build time, so the first question after a restart is fast
    FASTEMBED_CACHE_PATH=/app/models \
    HF_HUB_DISABLE_TELEMETRY=1

# Tesseract for OCR on scanned PDFs and images
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user (uid 1000 is also what Hugging Face Spaces expects)
RUN useradd --create-home --uid 1000 app

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Fetch the embedding and reranker models into the image (a layer that rarely changes)
COPY backend/scripts/download_models.py /tmp/download_models.py
RUN python /tmp/download_models.py && rm /tmp/download_models.py && chown -R app:app /app/models

COPY --chown=app:app backend/ /app/backend/
COPY --from=frontend --chown=app:app /frontend/dist/ /app/frontend/dist/

USER app
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"10000\")}/api/health', timeout=4)"

# Apply database migrations, then start the API
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
