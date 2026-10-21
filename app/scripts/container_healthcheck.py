"""Container readiness: the HTTP process and an authenticated MySQL query."""

from __future__ import annotations

import os
from urllib.request import urlopen

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def is_ready() -> bool:
    settings = get_settings()
    port = int(os.environ.get("PORT", "8000"))
    url = f"http://127.0.0.1:{port}{settings.api_v1_prefix}/health"
    with urlopen(url, timeout=3) as response:
        if response.status != 200:
            return False
    engine = create_engine(
        settings.sqlalchemy_database_url,
        poolclass=NullPool,
        connect_args={"connect_timeout": 3, "read_timeout": 3},
    )
    try:
        with engine.connect() as connection:
            return connection.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()


def main() -> int:
    try:
        return 0 if is_ready() else 1
    except Exception:
        # Health status must not expose credentials, URLs or driver tracebacks.
        print("Container not ready: HTTP or MySQL check failed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
