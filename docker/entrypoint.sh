#!/usr/bin/env sh
# Production entrypoint: migrate, optionally create the first admin, then serve.
set -eu

# An explicit command is an operational task, not a server startup.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# MySQL creates the database from MYSQL_DATABASE on first start, so the app only
# needs to bring the schema up to date. Set RUN_MIGRATIONS=false to skip this
# (for example when migrations run as a separate release job).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Applying Alembic migrations (alembic upgrade head)"
    alembic upgrade head
fi

# First-run administrator. Existing active ADMINs are preserved on restart.
# Pass the environment variable's name, never the password in process arguments.
if [ -n "${CREATE_ADMIN_USERNAME:-}" ]; then
    echo "[entrypoint] Ensuring initial ADMIN user '${CREATE_ADMIN_USERNAME}'"
    python -m app.scripts.create_admin \
        --username "${CREATE_ADMIN_USERNAME}" \
        --password-env CREATE_ADMIN_PASSWORD \
        --if-not-exists
fi

# A single worker by default; raise WEB_CONCURRENCY for busier deployments.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
