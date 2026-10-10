"""Create a NEW disposable local database and verify migrations + HTTP integration.

Never accepts an existing database name. Only the fresh schema is passed to the
integration suite (whose fixture downgrades it to base on exit). Leaves the empty
schema for inspection, does not drop databases or touch the configured app data.
"""

# ruff: noqa: E402 -- executable runner sets the repository import path first.

import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def main():
    settings = get_settings()
    original = make_url(settings.sqlalchemy_database_url)
    if settings.environment != "development" or original.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Requires local development MySQL.")
    database = "ipress_test_nutrition_" + uuid4().hex[:12]
    target = original.set(database=database)
    server = create_engine(original.set(database=None))
    with server.connect() as connection:
        connection.execute(
            text(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        )
    server.dispose()
    print("Fresh disposable database:", database, flush=True)
    os.environ["DATABASE_URL"] = target.render_as_string(hide_password=False)
    os.environ["TEST_DATABASE_URL"] = target.render_as_string(hide_password=False)
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "20261007_0028_delivery_date")
    engine = create_engine(target)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO pacientes (tipo_documento_codigo, numero_documento, "
                "fecha_nacimiento, historia_clinica, historia_familiar) "
                "VALUES ('DNI', '99000001', '1990-01-01', "
                "'HC-MIGRACION-PRUEBA', 'HF-MIGRACION-PRUEBA')"
            )
        )
        patient_id = connection.execute(text("SELECT LAST_INSERT_ID()")).scalar_one()
        site = connection.execute(text("SELECT MIN(id) FROM establecimientos")).scalar_one()
        connection.execute(
            text(
                "INSERT INTO evaluaciones_nutricionales (paciente_id, establecimiento_id, "
                "fecha, hemoglobina, waz, haz, whz, enviado) "
                "VALUES (:patient, :site, '2026-10-01', 0, 0, 0, 0, FALSE)"
            ),
            {"patient": patient_id, "site": site},
        )
        before_patient = dict(
            connection.execute(text("SELECT * FROM pacientes WHERE id=:id"), {"id": patient_id})
            .mappings()
            .one()
        )
        before_eval = dict(
            connection.execute(
                text("SELECT * FROM evaluaciones_nutricionales WHERE paciente_id=:id"),
                {"id": patient_id},
            )
            .mappings()
            .one()
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        after_patient = dict(
            connection.execute(text("SELECT * FROM pacientes WHERE id=:id"), {"id": patient_id})
            .mappings()
            .one()
        )
        after_eval = dict(
            connection.execute(
                text("SELECT * FROM evaluaciones_nutricionales WHERE paciente_id=:id"),
                {"id": patient_id},
            )
            .mappings()
            .one()
        )
    assert before_patient == {key: after_patient[key] for key in before_patient}
    assert before_eval == {key: after_eval[key] for key in before_eval}
    assert after_patient["sufijo_documento"] is None
    assert after_eval["estado_exportacion"] is None
    command.check(config)
    command.downgrade(config, "20261007_0028_delivery_date")
    assert "sufijo_documento" not in {x["name"] for x in inspect(engine).get_columns("pacientes")}
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
    print("Migration preservation, downgrade/upgrade and ORM consistency: PASS", flush=True)
    args = sys.argv[1:] or [
        "tests/integration/test_mysql_nutrition_records.py",
        "tests/integration/test_mysql_attention_flow.py",
        "tests/integration/test_mysql_patients.py",
        "tests/integration/test_mysql_patient_discovery.py",
    ]
    return pytest.main([*args, "--no-cov", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
