"""Portable bootstrap: identity remapping, credentials, filters and atomicity."""

import gzip
import json
from datetime import date

import pytest
import sqlalchemy as sa

from app.models import Base
from app.scripts import docker_bootstrap as bootstrap


@pytest.fixture
def database():
    metadata = sa.MetaData()
    # Use the real master-data columns/FKs with portable SQLite storage types.
    for name in bootstrap.IDENTITIES:
        original = Base.metadata.tables[name]
        columns = []
        for column in original.c:
            original_type = column.type
            if isinstance(original_type, sa.JSON):
                storage = sa.JSON()
            elif isinstance(original_type, sa.DateTime):
                storage = sa.DateTime()
            elif isinstance(original_type, sa.Date):
                storage = sa.Date()
            elif isinstance(original_type, sa.Boolean):
                storage = sa.Boolean()
            elif isinstance(original_type, sa.Integer):
                storage = sa.Integer()
            elif isinstance(original_type, sa.Numeric):
                storage = sa.Numeric()
            else:
                storage = sa.String()
            foreign_keys = [sa.ForeignKey(fk.target_fullname) for fk in column.foreign_keys]
            columns.append(
                sa.Column(
                    column.name,
                    storage,
                    *foreign_keys,
                    primary_key=column.primary_key,
                    autoincrement=column.autoincrement,
                    nullable=not column.primary_key,
                )
            )
        sa.Table(name, metadata, *columns)
    sa.Table("atenciones", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table(
        "auditoria",
        metadata,
        sa.Column("registro_id", sa.Integer),
        sa.Column("tabla_nombre", sa.String),
        sa.Column("accion", sa.String),
        sa.Column("datos_nuevos", sa.JSON),
    )
    sa.Table("alembic_version", metadata, sa.Column("version_num", sa.String))
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["alembic_version"].insert(),
            {
                "version_num": "20261022_0041_assign_services",
            },
        )
    yield engine, metadata
    engine.dispose()


def sample():
    rows = {name: [] for name in bootstrap.IDENTITIES}
    rows.update(
        {
            "roles": [{"id": 80, "codigo": "ADMIN", "nombre": "Administrador"}],
            "profesiones": [{"id": 90, "nombre": "Medicina", "activo": True}],
            "especialidades": [{"codigo": "AREA", "nombre": "Medicina", "es_area": True}],
            "profesionales": [
                {
                    "id": 70,
                    "numero_documento": "99999991",
                    "nombre_completo": "Clínico",
                    "profesion_id": 90,
                    "activo": True,
                }
            ],
            "usuarios": [
                {
                    "id": 60,
                    "nombre_usuario": "clinico",
                    "profesional_id": 70,
                    "password_hash": "source-bcrypt-hash",
                    "activo": True,
                }
            ],
            "usuario_roles": [{"usuario_id": 60, "rol_id": 80}],
            "ubigeos": [{"codigo": "040101", "departamento": "AREQUIPA"}],
            "establecimientos": [
                {
                    "id": 50,
                    "codigo_renaes": "1234",
                    "nombre": "Sede",
                    "ubigeo_codigo": "040101",
                    "activo": True,
                }
            ],
            "consultorios": [
                {
                    "id": 1,
                    "codigo": "SALA",
                    "nombre": "Sala",
                    "establecimiento_id": 50,
                    "consultorio_padre_id": 2,
                    "area_codigo": "AREA",
                    "servicios_codigos": [],
                    "activo": True,
                },
                {
                    "id": 2,
                    "codigo": "MED",
                    "nombre": "Medicina",
                    "establecimiento_id": 50,
                    "consultorio_padre_id": None,
                    "area_codigo": "AREA",
                    "servicios_codigos": ["AREA"],
                    "activo": True,
                },
            ],
            "consultorio_profesionales": [
                {
                    "consultorio_id": 2,
                    "profesional_id": 70,
                    "fecha_inicio": "2024-01-01",
                    "es_responsable": True,
                    "servicios_codigos": ["AREA"],
                }
            ],
            "tipos_documento": [{"codigo": "DNI", "nombre": "DNI"}],
            "pacientes": [
                {
                    "id": 100,
                    "tipo_documento_codigo": "DNI",
                    "numero_documento": "99999992",
                    "fecha_nacimiento": "2000-01-01",
                    "ubigeo_residencia_codigo": "040101",
                    "establecimiento_registro_id": 50,
                    "profesional_registro_id": 70,
                    "estado": True,
                }
            ],
            "paciente_responsables": [
                {
                    "id": 200,
                    "paciente_id": 100,
                    "parentesco": "MADRE",
                    "nombre_completo": "Responsable",
                    "activo": True,
                }
            ],
        }
    )
    return {
        "format": 1,
        "source_revision": "20261022_0041_assign_services",
        "patient_department": "04",
        "tables": rows,
    }


def write_snapshot(tmp_path, snapshot):
    path = tmp_path / "snapshot.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(snapshot, stream)
    return path


def test_restore_remaps_ids_office_tree_services_and_responsibles(database, tmp_path):
    engine, metadata = database
    path = write_snapshot(tmp_path, sample())
    with engine.begin() as connection:
        result = bootstrap.restore_snapshot(connection, path)
        assert result["pacientes"] == 1
        professionals = metadata.tables["profesionales"]
        professional = connection.execute(sa.select(professionals)).mappings().one()
        patient = connection.execute(sa.select(metadata.tables["pacientes"])).mappings().one()
        responsible = (
            connection.execute(sa.select(metadata.tables["paciente_responsables"])).mappings().one()
        )
        assert professional["id"] != 70
        assert patient["id"] != 100
        assert patient["profesional_registro_id"] == professional["id"]
        assert responsible["paciente_id"] == patient["id"]
        offices = metadata.tables["consultorios"]
        root = (
            connection.execute(sa.select(offices).where(offices.c.codigo == "MED")).mappings().one()
        )
        child = (
            connection.execute(sa.select(offices).where(offices.c.codigo == "SALA"))
            .mappings()
            .one()
        )
        assert child["consultorio_padre_id"] == root["id"]
        assert child["servicios_codigos"] == []
        assignment = (
            connection.execute(sa.select(metadata.tables["consultorio_profesionales"]))
            .mappings()
            .one()
        )
        assert assignment["servicios_codigos"] == ["AREA"]
        assert assignment["consultorio_id"] == root["id"]
        assert assignment["fecha_inicio"] == date(2024, 1, 1)
        audit = metadata.tables["auditoria"]
        event = connection.execute(sa.select(audit)).mappings().one()
        assert event["accion"] == "IMPORTAR_DOCKER"
        assert event["datos_nuevos"]["inserted"]["pacientes"] == 1
        assert "source-bcrypt-hash" not in json.dumps(event["datos_nuevos"])


def test_reimport_preserves_changed_passwords_and_patient_data(database, tmp_path):
    engine, metadata = database
    path = write_snapshot(tmp_path, sample())
    with engine.begin() as connection:
        bootstrap.restore_snapshot(connection, path)
        users, patients = metadata.tables["usuarios"], metadata.tables["pacientes"]
        connection.execute(users.update().values(password_hash="new-local-hash"))
        connection.execute(patients.update().values(direccion="Actualizada"))
        assert sum(bootstrap.restore_snapshot(connection, path).values()) == 0
        assert connection.scalar(sa.select(users.c.password_hash)) == "new-local-hash"
        assert connection.scalar(sa.select(patients.c.direccion)) == "Actualizada"


def test_fresh_baseline_adopts_current_hash_of_previously_seeded_user(database, tmp_path):
    engine, metadata = database
    path = write_snapshot(tmp_path, sample())
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["usuarios"].insert(),
            {
                "id": 500,
                "nombre_usuario": "clinico",
                "password_hash": "old-dni-hash",
            },
        )
        connection.execute(
            metadata.tables["auditoria"].insert(),
            {
                "registro_id": 500,
                "tabla_nombre": "usuarios",
                "accion": "BOOTSTRAP",
                "datos_nuevos": {"origen": "operarios_sis"},
            },
        )
        bootstrap.restore_snapshot(connection, path)
        users = metadata.tables["usuarios"]
        user = connection.execute(sa.select(users)).mappings().one()
        assert user["id"] == 500
        assert user["password_hash"] == "source-bcrypt-hash"
        assert user["profesional_id"] != 70


def test_missing_reference_rolls_back_the_whole_import(database, tmp_path):
    engine, metadata = database
    snapshot = sample()
    snapshot["tables"]["pacientes"][0]["profesional_registro_id"] = 9999
    path = write_snapshot(tmp_path, snapshot)
    with pytest.raises(ValueError, match="Falta una referencia"):
        with engine.begin() as connection:
            bootstrap.restore_snapshot(connection, path)
    with engine.connect() as connection:
        assert (
            connection.scalar(sa.select(sa.func.count()).select_from(metadata.tables["usuarios"]))
            == 0
        )


@pytest.mark.parametrize("problem", ["department", "format", "columns", "cycle"])
def test_invalid_snapshot_fails_without_success(database, tmp_path, problem):
    engine, _ = database
    snapshot = sample()
    if problem == "department":
        snapshot["tables"]["pacientes"][0]["ubigeo_residencia_codigo"] = "150101"
    elif problem == "format":
        snapshot["format"] = 99
    elif problem == "columns":
        snapshot["tables"]["usuarios"][0]["password_plaintext"] = "invalid"
    else:
        snapshot["tables"]["consultorios"][1]["consultorio_padre_id"] = 1
    path = write_snapshot(tmp_path, snapshot)
    with pytest.raises(ValueError):
        with engine.begin() as connection:
            bootstrap.restore_snapshot(connection, path)


def test_operational_filter_excludes_test_users_patients_and_their_assignments():
    tables = sample()["tables"]
    tables["usuarios"].extend(
        [
            {"id": 61, "nombre_usuario": "medico.demo", "activo": True},
            {"id": 62, "nombre_usuario": "inactivo", "activo": False},
        ]
    )
    tables["usuario_roles"].append({"usuario_id": 61, "rol_id": 80})
    tables["pacientes"].append({"id": 101, "historia_clinica": "UI26003", "estado": True})
    tables["paciente_responsables"].append({"id": 201, "paciente_id": 101, "activo": True})
    tables["consultorios"].append({"id": 3, "nombre": "CARDIOLOGIA E2E", "activo": True})
    result = bootstrap._operational_data(tables)
    assert len(result["usuarios"]) == len(result["usuario_roles"]) == 1
    assert len(result["pacientes"]) == len(result["paciente_responsables"]) == 1
    assert len(result["consultorios"]) == 2


def test_export_filters_outside_arequipa_and_does_not_overwrite(database, tmp_path):
    engine, metadata = database
    path = write_snapshot(tmp_path, sample())
    exported = tmp_path / "export.json.gz"
    with engine.begin() as connection:
        bootstrap.restore_snapshot(connection, path)
        connection.execute(
            metadata.tables["pacientes"].insert(),
            {
                "tipo_documento_codigo": "DNI",
                "numero_documento": "99999993",
                "ubigeo_residencia_codigo": "150101",
                "estado": True,
            },
        )
        counts = bootstrap.export_snapshot(connection, exported)
        assert counts["pacientes"] == 1
        with pytest.raises(FileExistsError):
            bootstrap.export_snapshot(connection, exported)


def test_no_environment_snapshot_means_no_import(monkeypatch):
    monkeypatch.delenv("IPRESS_BOOTSTRAP_FILE", raising=False)
    monkeypatch.setattr(
        bootstrap, "restore_snapshot", lambda *args: pytest.fail("Unexpected import")
    )
    bootstrap.migrate_from_environment(None)


def test_explicit_missing_file_does_not_silently_skip_import(monkeypatch, tmp_path):
    monkeypatch.setenv("IPRESS_BOOTSTRAP_FILE", str(tmp_path / "missing.gz"))
    with pytest.raises(FileNotFoundError):
        bootstrap.migrate_from_environment(None)


def test_nullable_service_scope_remains_sql_null(database, tmp_path):
    engine, metadata = database
    snapshot = sample()
    snapshot["tables"]["consultorios"][1]["servicios_codigos"] = None
    path = write_snapshot(tmp_path, snapshot)
    with engine.begin() as connection:
        bootstrap.restore_snapshot(connection, path)
        offices = metadata.tables["consultorios"]
        assert (
            connection.scalar(
                sa.select(sa.func.count())
                .select_from(offices)
                .where(
                    offices.c.codigo == "MED",
                    offices.c.servicios_codigos.is_(None),
                )
            )
            == 1
        )


def test_conflicting_natural_keys_abort_instead_of_merging_two_patients(database, tmp_path):
    engine, metadata = database
    path = write_snapshot(tmp_path, sample())
    with engine.begin() as connection:
        bootstrap.restore_snapshot(connection, path)
        patients = metadata.tables["pacientes"]
        connection.execute(
            patients.insert(),
            {
                "codclie_legacy": 777,
                "tipo_documento_codigo": "DNI",
                "numero_documento": "99999994",
            },
        )
    snapshot = sample()
    snapshot["tables"]["pacientes"][0]["codclie_legacy"] = 777
    path = write_snapshot(tmp_path, snapshot)
    with pytest.raises(ValueError, match="Identidades incompatibles"):
        with engine.begin() as connection:
            bootstrap.restore_snapshot(connection, path)
