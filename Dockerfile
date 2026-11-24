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

# Run as an unprivileged user; /app/state holds the generated secret key (a volume in compose)
RUN useradd --create-home --uid 1000 app && mkdir -p /app/state && chown app:app /app/state

WORKDIR /app/backend

# The spaCy English model is only published as a GitHub release file. Docker fetches it here
# itself (more reliable than pip downloading it inside the build container on some networks),
# pinned to its checksum; pip then installs the local copy and everything else from PyPI.
ADD --checksum=sha256:1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85 \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
    /tmp/wheels/en_core_web_sm-3.8.0-py3-none-any.whl

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && grep -v "en_core_web_sm" requirements.txt > /tmp/requirements-pypi.txt \
    && pip install --retries 10 --timeout 60 -r /tmp/requirements-pypi.txt /tmp/wheels/en_core_web_sm-3.8.0-py3-none-any.whl \
    && rm -rf /tmp/wheels /tmp/requirements-pypi.txt

# Fetch the embedding and reranker models into the image (a layer that rarely changes)
COPY backend/scripts/download_models.py /tmp/download_models.py
RUN python /tmp/download_models.py && rm /tmp/download_models.py && chown -R app:app /app/models

COPY --chown=app:app backend/ /app/backend/
COPY --from=frontend --chown=app:app /frontend/dist/ /app/frontend/dist/

USER app
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"10000\")}/api/health', timeout=4)"

# Make sure there is a secret key, apply database migrations, then start the API
CMD ["sh", "/app/backend/scripts/start.sh"]
