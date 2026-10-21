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
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Lima

WORKDIR /app

# Installed before the source so the dependency layer is cached across builds.
COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --create-home --uid 10001 ipress \
    && chown -R ipress:ipress /app
USER ipress

EXPOSE 8000

# Container readiness checks HTTP and MySQL; /health remains process liveness.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-m", "app.scripts.container_healthcheck"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
