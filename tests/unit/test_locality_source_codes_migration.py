import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    spec = importlib.util.spec_from_file_location(
        "locality_source_codes", Path("migrations/versions/20261013_0034_locality_source_codes.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rekeys_source_gap_preserving_ids_names_links_and_is_idempotent(monkeypatch):
    module = migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    localities = sa.Table(
        "localidades",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ubigeo_codigo", sa.String),
        sa.Column("codigo_sis", sa.String),
        sa.Column("nombre", sa.String),
        sa.UniqueConstraint("ubigeo_codigo", "codigo_sis"),
    )
    patients = sa.Table("pacientes", metadata, sa.Column("localidad_id", sa.Integer))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            localities.insert(),
            [
                dict(id=i, ubigeo_codigo="040102", codigo_sis=f"{i + 50:04d}", nombre=name)
                for i, name in enumerate(module.SOURCE_NAMES, start=1)
            ],
        )
        connection.execute(patients.insert(), {"localidad_id": 1})
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)
        module.upgrade()
        module.upgrade()
        rows = connection.execute(sa.select(localities).order_by(localities.c.id)).mappings().all()
        assert rows[0]["codigo_sis"] == "0052"
        assert rows[-1]["codigo_sis"] == "0089"
        assert [row["nombre"] for row in rows] == module.SOURCE_NAMES
        assert connection.scalar(sa.select(patients.c.localidad_id)) == 1


def test_custom_conflict_is_rejected_before_any_change(monkeypatch):
    module = migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE localidades (id INTEGER, ubigeo_codigo TEXT, "
            "codigo_sis TEXT, nombre TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO localidades VALUES (1,'040102','0051','PORTALES DEL MIRADOR'),"
            "(2,'040102','0052','CUSTOM')"
        )
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)
        with pytest.raises(RuntimeError, match="already owned"):
            module.upgrade()
        assert connection.scalar(sa.text("SELECT codigo_sis FROM localidades WHERE id=1")) == "0051"
