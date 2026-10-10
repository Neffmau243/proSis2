"""Apply only revision 0029 to the configured local development database.

Run while application writes are stopped. Checksums verify that original columns
are unchanged; this is not a substitute for a deployment database backup.
Without --apply this command only reports the current revision and row counts.
No patient values or credentials are printed or written to disk.
"""

# ruff: noqa: E402 -- executable runner sets the repository import path first.
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "20261007_0028_delivery_date"
TARGET = "20261008_0029_nutrition_fields"


def fingerprint(connection, table):
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(select(table).order_by(table.c.id)).mappings():
        digest.update(json.dumps(dict(row), default=str, sort_keys=True).encode())
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def main():
    settings = get_settings()
    url = make_url(settings.sqlalchemy_database_url)
    if settings.environment != "development" or url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Only the configured local development database is permitted.")
    engine = create_engine(url)
    metadata = MetaData()
    tables = [
        Table(name, metadata, autoload_with=engine)
        for name in (
            "pacientes",
            "atenciones",
            "evaluaciones_nutricionales",
        )
    ]
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        before = {table.name: fingerprint(connection, table) for table in tables}
    print("Database:", url.database, "Revision:", revision)
    print("Row counts:", {name: value[0] for name, value in before.items()})
    if "--apply" not in sys.argv:
        print("Read-only check. Use --apply with application writes stopped to migrate.")
        return
    if revision != PREVIOUS:
        raise RuntimeError(f"Expected {PREVIOUS}; refusing to run other migrations.")
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, TARGET)
    with engine.connect() as connection:
        after = {table.name: fingerprint(connection, table) for table in tables}
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if before != after or revision != TARGET:
        raise RuntimeError(
            "Post-migration verification failed; inspect concurrent writes and schema."
        )
    command.check(config)
    print("PASS: original columns and row counts unchanged in all three tables.")
    print("Revision:", revision)
    engine.dispose()


if __name__ == "__main__":
    main()
