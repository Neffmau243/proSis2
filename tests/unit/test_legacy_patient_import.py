"""Synthetic records only: no real patient data in test fixtures."""

from copy import deepcopy
from datetime import date

import pytest

from app.services.legacy_patients import Catalogs, build_plan, digest, summarize

AS_OF = date(2026, 10, 20)


@pytest.fixture
def catalogs():
    return Catalogs(
        districts={"AREQUIPA": "040101", "CAYMA": "040103", "LIMA": "150101"},
        establishments={"SEDE PRUEBA": 7},
        insurances={"S.I.S. GRATUITO": (9, True)},
        localities={("040103", "SECTOR PRUEBA"): (55, "Sector Prueba")},
        family_prefixes={"AM"},
        sexes={"F", "M"},
        document_types={"DNI"},
    )


@pytest.fixture
def row():
    return {
        "Codclie": 800,
        "N°_DNI": "01234567",
        "Fecha_nacimiento": "1980-01-02T00:00:00",
        "Fecha_inscripcion": "2024-01-01T00:00:00",
        "Apellido_Paterno": "PRUEBA",
        "Apellido_Materno": "SINTETICA",
        "Primer_Nombre": "PACIENTE",
        "Otros_Nombres": None,
        "Sexo": "FEMENINO",
        "Distrito": "CAYMA",
        "Localidad": "SECTOR PRUEBA",
        "Dirección": "DOMICILIO SINTETICO",
        "Establecimiento": "SEDE PRUEBA",
        "Seguro": "S.I.S. Gratuito",
        "Historia_Clinica": "0000123",
        "Historia_Familiar": "am-000123",
        "Arequipa_040": "040",
        "Arequipa_2": "3",
        "Arequipa_SIS": "002345678",
        "Condicion": "GESTANTE",
        "Anexo1": "ORIGINAL SIN INTERPRETAR",
    }


def plan(rows, catalogs, existing=None, archived=None):
    return build_plan({"Pacientes": rows}, catalogs, existing or [], archived or {}, as_of=AS_OF)


def test_maps_valid_adult_preserving_leading_zeroes_and_catalog_ids(row, catalogs):
    before = deepcopy(row)
    (d,) = plan([row], catalogs)
    assert d.state == "ACEPTADO"
    assert d.payload.numero_documento == "01234567"
    assert d.payload.historia_clinica == "0000123"
    assert d.payload.historia_familiar == "AM-000123"
    assert d.payload.sis_numero == "002345678"
    assert d.payload.localidad_id == 55
    assert d.payload.establecimiento_registro_id == 7
    assert "id" not in d.payload.model_dump()
    assert d.payload.condicion is None  # Historical pregnancy is not current clinical truth.
    assert row == before


@pytest.mark.parametrize("document", [None, "", "123", "1234567A", "11111111", "12345678-1"])
def test_never_invents_or_pads_document(row, catalogs, document):
    row["N°_DNI"] = document
    (d,) = plan([row], catalogs)
    assert d.state == "PENDIENTE"
    assert d.payload is None


def test_checks_duplicates_in_entire_source_before_geographic_filter(row, catalogs):
    outside = {**row, "Codclie": 801, "Distrito": "LIMA"}
    decisions = plan([row, outside], catalogs)
    assert decisions[0].state == "PENDIENTE"
    assert "dni_duplicado_en_origen" in decisions[0].issues
    assert decisions[1].state == "FUERA_DE_AMBITO"


def test_duplicate_legacy_code_blocks_different_documents(row, catalogs):
    other = {**row, "N°_DNI": "12345679", "Primer_Nombre": "OTRO"}
    assert all(d.payload is None for d in plan([row, other], catalogs))


@pytest.mark.parametrize("birth", [None, "not-a-date", "2027-01-01", "1800-01-01"])
def test_invalid_birth_is_pending(row, catalogs, birth):
    row["Fecha_nacimiento"] = birth
    assert plan([row], catalogs)[0].payload is None


def test_minor_at_registration_needs_real_responsible_even_if_now_adult(row, catalogs):
    row["Fecha_nacimiento"] = "2007-01-01"
    (d,) = plan([row], catalogs)
    assert "menor_sin_responsable_acreditado" in d.issues
    assert d.payload is None


def test_bad_registration_date_is_archived_not_fabricated(row, catalogs):
    row["Fecha_inscripcion"] = "1970-01-01"
    (d,) = plan([row], catalogs)
    assert d.state == "ACEPTADO"
    assert d.payload.fecha_inscripcion is None


@pytest.mark.parametrize("hf", ["-", "AM", "OTHER-00001", "AM-abc"])
def test_unusable_family_history_stays_only_in_original(row, catalogs, hf):
    row["Historia_Familiar"] = hf
    (d,) = plan([row], catalogs)
    assert d.state == "ACEPTADO"
    assert d.payload.historia_familiar is None
    assert d.source["Historia_Familiar"] == hf


def test_text_locality_does_not_force_a_catalog_match(row, catalogs):
    row["Localidad"] = "BARRIO SIN CATALOGO"
    (d,) = plan([row], catalogs)
    assert d.state == "ACEPTADO"
    assert d.payload.localidad_id is None
    assert d.payload.localidad == "BARRIO SIN CATALOGO"


def test_missing_district_or_unverified_site_is_not_imported(row, catalogs):
    row["Establecimiento"] = "SIN CORRESPONDENCIA"
    assert plan([row], catalogs)[0].payload is None
    row["Distrito"] = "DISTRITO NO HOMOLOGADO"
    assert plan([row], catalogs)[0].state == "FUERA_DE_AMBITO"


@pytest.mark.parametrize("bad", ["A\ud800B", "A\ufffdB", "A\x00B", "A" * 101])
def test_damaged_or_overlong_identity_never_truncated(row, catalogs, bad):
    row["Apellido_Paterno"] = bad
    (d,) = plan([row], catalogs)
    assert d.payload is None
    assert d.source["Apellido_Paterno"] == bad


def test_partial_sis_is_archived_without_guessing_from_dni(row, catalogs):
    row["Arequipa_SIS"] = None
    (d,) = plan([row], catalogs)
    assert d.state == "ACEPTADO"
    assert d.payload.sis_diresa is None
    assert d.payload.sis_tipo is None
    assert d.payload.sis_numero is None


def test_sis_not_kept_for_unknown_insurance(row, catalogs):
    row["Seguro"] = "NO HOMOLOGADO"
    (d,) = plan([row], catalogs)
    assert d.payload.seguro_id is None
    assert d.payload.sis_numero is None


def test_existing_inactive_identity_is_not_overwritten_or_duplicated(row, catalogs):
    existing = [
        dict(
            id=90,
            codclie_legacy=None,
            tipo_documento_codigo="DNI",
            numero_documento=row["N°_DNI"],
            estado=False,
        )
    ]
    (d,) = plan([row], catalogs, existing)
    assert d.payload is None
    assert "identidad_ya_existe_en_destino" in d.issues


def test_repeat_import_uses_source_provenance_even_after_patient_edits(row, catalogs):
    existing = [
        dict(id=90, codclie_legacy=800, tipo_documento_codigo="DNI", numero_documento=row["N°_DNI"])
    ]
    archived = {1: dict(huella_fila=digest(row), destino_tabla="pacientes", destino_id="90")}
    (d,) = plan([row], catalogs, existing, archived)
    assert d.state == "YA_IMPORTADO"
    assert d.patient_id == 90
    assert d.payload is None
    archived[1]["destino_id"] = "91"
    assert plan([row], catalogs, existing, archived)[0].state == "PENDIENTE"


def test_summary_contains_counts_no_patient_values(row, catalogs):
    import json

    summary = summarize(plan([row], catalogs))
    serialized = json.dumps(summary)
    assert summary["estados"] == {"ACEPTADO": 1}
    assert row["N°_DNI"] not in serialized
    assert row["Primer_Nombre"] not in serialized


@pytest.fixture
def snapshot_files(tmp_path):
    import json

    from app.services.legacy_patients import file_digest

    source = tmp_path / "source.mdb"
    source.write_bytes(b"synthetic source only")
    directory = tmp_path / "snapshot"
    directory.mkdir()
    tables = []
    for number, name in enumerate(("Pacientes", "Provincia", "EESS")):
        path = directory / f"table-{number}.jsonl"
        path.write_text('{"example":1}\n', encoding="utf-8")
        tables.append(
            dict(
                name=name,
                file=path.name,
                sha256=file_digest(path),
                rows=1,
                columns=[{"name": "example"}],
            )
        )
    manifest = dict(
        version=1,
        reader="Microsoft.ACE.OLEDB.16.0",
        source_sha256=file_digest(source),
        tables=tables,
    )
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source, directory, manifest


def test_snapshot_verifies_source_and_all_tables(snapshot_files):
    from app.services.legacy_patients import read_source

    source, directory, _ = snapshot_files
    _, tables = read_source(directory, source)
    assert tables["Pacientes"] == [{"example": 1}]
    source.write_bytes(b"different source")
    with pytest.raises(ValueError, match="MDB"):
        read_source(directory, source)


@pytest.mark.parametrize("damage", ["checksum", "path", "duplicate", "row_count", "columns"])
def test_snapshot_rejects_tampering(snapshot_files, damage):
    import json

    from app.services.legacy_patients import read_source

    source, directory, manifest = snapshot_files
    if damage == "checksum":
        (directory / "table-0.jsonl").write_text("tampered")
    elif damage == "path":
        manifest["tables"][0]["file"] = "../source.mdb"
    elif damage == "duplicate":
        manifest["tables"].append(manifest["tables"][0])
    elif damage == "row_count":
        manifest["tables"][0]["rows"] = 2
    else:
        manifest["tables"][0]["columns"] = [{"name": "another_column"}]
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        read_source(directory, source)


@pytest.mark.parametrize(
    "environment,host", [("production", "localhost"), ("development", "remote.example")]
)
def test_import_refuses_production_or_remote_database(monkeypatch, environment, host):
    from pathlib import Path
    from types import SimpleNamespace

    from app.scripts import import_legacy_patients as cli

    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(environment=environment))
    monkeypatch.setattr(cli, "engine", SimpleNamespace(url=SimpleNamespace(host=host)))
    with pytest.raises(ValueError, match="local"):
        cli.run(source=Path("unused.mdb"), snapshot=Path("unused"), as_of=AS_OF, apply=True)
