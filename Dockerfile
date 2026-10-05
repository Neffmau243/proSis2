# syntax=docker/dockerfile:1

# --- Stage 1: build the Vue SPA -------------------------------------------
# The SPA is compiled here so the runtime image serves the interface and the
# API from the same Uvicorn process (no separate web server, no CORS).
FROM node:24-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: production runtime -------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Installed before the source so the dependency layer is cached across builds.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --create-home --uid 10001 ipress \
    && chown -R ipress:ipress /app
USER ipress

EXPOSE 8000

# Healthcheck uses the standard library so the image needs no extra packages.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
