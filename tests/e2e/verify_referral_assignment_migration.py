"""Exercise 0039 and a full bootstrap on a disposable MySQL/MariaDB database.

Set TEST_DATABASE_URL to an EMPTY database containing 'test' in its name.
Optionally set IPRESS_BOOTSTRAP_FILE to verify a private master-data snapshot.
Only aggregate results are printed; no credentials or patient data.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.scripts.docker_bootstrap import IDENTITIES, ensure_from_environment, restore_snapshot

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "20261019_0038_referral_mode"
AFTER = "20261019_0039_referral_assign"


def foreign_keys(connection):
    inspector = sa.inspect(connection)
    return {
        table: sorted(inspector.get_foreign_keys(table), key=lambda fk: fk["name"])
        for table in ("atenciones", "certificados")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    url = sa.engine.make_url(os.environ["TEST_DATABASE_URL"])
    if not url.drivername.startswith("mysql") or "test" not in (url.database or "").lower():
        raise RuntimeError("An explicitly disposable MySQL/MariaDB database is required")
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    engine = sa.create_engine(url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    checks = {}
    try:
        with engine.connect() as connection:
            if sa.inspect(connection).get_table_names():
                raise RuntimeError("Refusing to migrate a nonempty test database")
            server = connection.scalar(sa.text("SELECT VERSION()"))
        command.upgrade(config, BEFORE)
        with engine.begin() as connection:
            original_fks = foreign_keys(connection)
            if "MariaDB" in server:
                try:
                    connection.exec_driver_sql(
                        "ALTER TABLE atenciones MODIFY profesional_id BIGINT UNSIGNED NULL"
                    )
                except sa.exc.OperationalError as exc:
                    assert exc.orig.args[0] == 1833
                    checks["original_error_1833_reproduced"] = True
                else:
                    raise AssertionError("Expected the original MariaDB failure")
            schema = sa.MetaData()
            schema.reflect(connection)
            patients = schema.tables["pacientes"]
            patient_id = connection.execute(
                patients.insert().values(
                    tipo_documento_codigo=connection.scalar(
                        sa.text("SELECT codigo FROM tipos_documento ORDER BY codigo LIMIT 1")
                    ),
                    numero_documento="99999996",
                    fecha_nacimiento=datetime(2000, 1, 1),
                )
            ).inserted_primary_key[0]
            attention = schema.tables["atenciones"]
            assignment = {
                "paciente_id": patient_id,
                "establecimiento_id": connection.scalar(
                    sa.text("SELECT id FROM establecimientos ORDER BY id LIMIT 1")
                ),
                "profesional_id": connection.scalar(
                    sa.text("SELECT id FROM profesionales ORDER BY id LIMIT 1")
                ),
                "consultorio_id": connection.scalar(
                    sa.text("SELECT id FROM consultorios ORDER BY id LIMIT 1")
                ),
                "modalidad_atencion_codigo": connection.scalar(
                    sa.text(
                        "SELECT codigo FROM modalidades_atencion WHERE codigo <> 'REFERENCIA' "
                        "ORDER BY codigo LIMIT 1"
                    )
                ),
                "grupo_etario_codigo": connection.scalar(
                    sa.text("SELECT codigo FROM grupos_etarios ORDER BY codigo LIMIT 1")
                ),
                "fecha_atencion": datetime(2026, 10, 24, 10),
            }
            attention_id = connection.execute(attention.insert().values(**assignment))
            attention_id = attention_id.inserted_primary_key[0]
            certificates = schema.tables["certificados"]
            certificate = {
                "atencion_id": attention_id,
                "establecimiento_id": assignment["establecimiento_id"],
                "profesional_id": assignment["profesional_id"],
                "numero_certificado": "MIGRATION-TEST",
                "tipo": "TEST",
            }
            connection.execute(certificates.insert().values(**certificate))
            saved_attention = dict(connection.execute(sa.select(attention)).mappings().one())
            saved_certificate = dict(connection.execute(sa.select(certificates)).mappings().one())
        expected_upgrade_fks = copy.deepcopy(original_fks)
        if "MariaDB" in server:
            signer = next(
                fk
                for fk in expected_upgrade_fks["certificados"]
                if fk["name"] == "fk_certificados_atencion_profesional"
            )
            # MariaDB omits explicit RESTRICT when reflecting FK options.
            signer["options"].pop("onupdate", None)
        command.upgrade(config, AFTER)
        with engine.begin() as connection:
            assert foreign_keys(connection) == expected_upgrade_fks
            columns = {c["name"]: c for c in sa.inspect(connection).get_columns("atenciones")}
            assert columns["profesional_id"]["nullable"] and columns["consultorio_id"]["nullable"]
            assert (
                dict(connection.execute(sa.select(attention)).mappings().one()) == saved_attention
            )
            assert (
                dict(connection.execute(sa.select(certificates)).mappings().one())
                == saved_certificate
            )
            checks["upgrade_preserves_history_and_foreign_keys"] = True
            invalid = dict(
                certificate,
                profesional_id=assignment["profesional_id"] + 1,
                numero_certificado="INVALID",
            )
            try:
                with connection.begin_nested():
                    connection.execute(certificates.insert().values(**invalid))
            except sa.exc.IntegrityError:
                checks["mismatched_certificate_professional_rejected"] = True
            else:
                raise AssertionError("Certificate professional invariant was lost")
            referral = dict(
                assignment,
                profesional_id=None,
                consultorio_id=None,
                modalidad_atencion_codigo="REFERENCIA",
            )
            referral_id = connection.execute(attention.insert().values(**referral))
            referral_id = referral_id.inserted_primary_key[0]
        try:
            command.downgrade(config, BEFORE)
        except RuntimeError as exc:
            assert "referencias sin asignación" in str(exc)
            checks["downgrade_refuses_to_destroy_unassigned_history"] = True
        else:
            raise AssertionError("Downgrade should refuse an unassigned encounter")
        with engine.begin() as connection:
            connection.execute(attention.delete().where(attention.c.id == referral_id))
        command.downgrade(config, BEFORE)
        with engine.begin() as connection:
            assert foreign_keys(connection) == original_fks
            columns = {c["name"]: c for c in sa.inspect(connection).get_columns("atenciones")}
            assert not columns["profesional_id"]["nullable"]
            assert not columns["consultorio_id"]["nullable"]
            assert (
                dict(connection.execute(sa.select(attention)).mappings().one()) == saved_attention
            )
            assert (
                dict(connection.execute(sa.select(certificates)).mappings().one())
                == saved_certificate
            )
            checks["downgrade_preserves_history_and_foreign_keys"] = True
            # Simulate an interrupted nontransactional DDL before retrying.
            connection.exec_driver_sql(
                "ALTER TABLE atenciones DROP FOREIGN KEY fk_atenciones_consultorio"
            )
            connection.execute(certificates.delete())
            connection.execute(attention.delete())
            connection.execute(patients.delete().where(patients.c.id == patient_id))
        # Reproduce configuration supplied after 0042 was already applied.
        source = os.environ.pop("IPRESS_BOOTSTRAP_FILE", None)
        try:
            command.upgrade(config, "head")
        finally:
            if source is not None:
                os.environ["IPRESS_BOOTSTRAP_FILE"] = source
        with engine.begin() as connection:
            assert foreign_keys(connection) == expected_upgrade_fks
            checks["interrupted_migration_retry_restores_constraints"] = True
            checks["full_migration_chain_reaches_head"] = True
            if source:
                revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
                assert ensure_from_environment(connection) is not None
                assert ensure_from_environment(connection) is None
                assert (
                    connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
                    == revision
                )
                checks["late_snapshot_import_and_repeat_startup_verified"] = True
                with gzip.open(source, "rt", encoding="utf-8") as stream:
                    snapshot = json.load(stream)
                metadata = sa.MetaData()
                metadata.reflect(connection)
                counts = {
                    name: connection.scalar(
                        sa.select(sa.func.count()).select_from(metadata.tables[name])
                    )
                    for name in IDENTITIES
                }
                assert counts == {name: len(rows) for name, rows in snapshot["tables"].items()}
                expected_users = {
                    row["nombre_usuario"]: row for row in snapshot["tables"]["usuarios"]
                }
                for row in connection.execute(sa.select(metadata.tables["usuarios"])).mappings():
                    expected = expected_users[row["nombre_usuario"]]
                    assert row["password_hash"] == expected["password_hash"]
                    assert row["activo"] == expected["activo"]
                assert not any(restore_snapshot(connection, Path(source)).values())
                checks["complete_snapshot_counts_passwords_and_reimport_verified"] = True
                checks["snapshot_counts"] = counts
        result = {"server": server, "checks": checks}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
