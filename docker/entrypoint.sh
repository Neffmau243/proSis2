#!/usr/bin/env sh
# Production entrypoint: migrate, optionally create the first admin, then serve.
set -eu

# Compose secrets are files, so passwords never appear in container configuration.
# Load only these explicit names; reject ambiguous configurations.
load_secret() {
    case "$1" in
        SECRET_KEY) value="${SECRET_KEY:-}"; file="${SECRET_KEY_FILE:-}" ;;
        MYSQL_PASSWORD) value="${MYSQL_PASSWORD:-}"; file="${MYSQL_PASSWORD_FILE:-}" ;;
        CREATE_ADMIN_PASSWORD) value="${CREATE_ADMIN_PASSWORD:-}"; file="${CREATE_ADMIN_PASSWORD_FILE:-}" ;;
        *) exit 1 ;;
    esac
    if [ -n "$file" ]; then
        if [ -n "$value" ]; then
            echo "Configure either $1 or its _FILE, not both." >&2
            exit 1
        fi
        value="$(cat "$file")"
        export "$1=$value"
    fi
}
load_secret SECRET_KEY
load_secret MYSQL_PASSWORD
load_secret CREATE_ADMIN_PASSWORD

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

# Installation data is also checked outside Alembic. A database which already
# applied 0042 can receive its explicitly configured snapshot; successful hashes
# are skipped on restart, preserving subsequent account/patient changes.
if [ -n "${IPRESS_BOOTSTRAP_FILE:-}" ]; then
    echo "[entrypoint] Checking configured installation snapshot"
    python -m app.scripts.docker_bootstrap ensure
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
