import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    spec = importlib.util.spec_from_file_location(
        "establishment_district",
        Path("migrations/versions/20261013_0035_establishment_district.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def connection():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        bind.exec_driver_sql(
            "CREATE TABLE ubigeos (codigo TEXT, departamento TEXT, provincia TEXT, distrito TEXT)"
        )
        bind.exec_driver_sql(
            "INSERT INTO ubigeos VALUES ('040102','Arequipa','Arequipa','Alto Selva Alegre')"
        )
        bind.exec_driver_sql(
            "CREATE TABLE establecimientos (id INTEGER, codigo_renaes TEXT, ubigeo_codigo TEXT)"
        )
        yield bind


def test_verified_codes_with_varied_padding_are_linked_and_configuration_is_preserved(
    connection,
    monkeypatch,
):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: connection)
    codes = ("1291", "0001300", "00001301", "1302", "1303", "1304", "XYZ", "99999999")
    for index, code in enumerate(codes, start=1):
        connection.execute(
            sa.text("INSERT INTO establecimientos VALUES (:id,:code,NULL)"),
            {"id": index, "code": code},
        )
    connection.exec_driver_sql("INSERT INTO establecimientos VALUES (9,'00001300','040103')")
    module.upgrade()
    module.upgrade()
    rows = connection.execute(sa.text("SELECT * FROM establecimientos ORDER BY id")).all()
    assert [row.ubigeo_codigo for row in rows[:6]] == ["040102"] * 6
    assert [row.codigo_renaes for row in rows[:8]] == list(codes)
    assert rows[6].ubigeo_codigo is None
    assert rows[7].ubigeo_codigo is None
    assert rows[8].ubigeo_codigo == "040103"


def test_internal_id_is_never_used_as_a_renipress(connection, monkeypatch):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: connection)
    connection.exec_driver_sql("INSERT INTO establecimientos VALUES (1291,NULL,NULL)")
    module.upgrade()
    assert connection.scalar(sa.text("SELECT ubigeo_codigo FROM establecimientos")) is None


def test_wrong_district_identity_fails_before_mutating_sites(connection, monkeypatch):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: connection)
    connection.exec_driver_sql("UPDATE ubigeos SET distrito='Cayma'")
    connection.exec_driver_sql("INSERT INTO establecimientos VALUES (1,'1291',NULL)")
    with pytest.raises(RuntimeError, match="inconsistent"):
        module.upgrade()
    assert connection.scalar(sa.text("SELECT ubigeo_codigo FROM establecimientos")) is None
