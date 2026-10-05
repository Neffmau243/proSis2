#!/usr/bin/env sh
# Production entrypoint: migrate, optionally create the first admin, then serve.
set -eu

# MySQL creates the database from MYSQL_DATABASE on first start, so the app only
# needs to bring the schema up to date. Set RUN_MIGRATIONS=false to skip this
# (for example when migrations run as a separate release job).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Applying Alembic migrations (alembic upgrade head)"
    alembic upgrade head
fi

# First-run administrator. Idempotent: create_admin refuses an existing user.
# Passwords must be exactly eight digits and are never logged.
if [ -n "${CREATE_ADMIN_USERNAME:-}" ]; then
    echo "[entrypoint] Creating initial ADMIN user '${CREATE_ADMIN_USERNAME}'"
    python -m app.scripts.create_admin \
        --username "${CREATE_ADMIN_USERNAME}" \
        --password "${CREATE_ADMIN_PASSWORD:?CREATE_ADMIN_PASSWORD is required}"
fi

# A single worker by default; raise WEB_CONCURRENCY for busier deployments.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
