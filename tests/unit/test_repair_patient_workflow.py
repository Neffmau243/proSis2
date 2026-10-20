"""Development repair: preview/apply, existing data preservation and failure cleanup."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.scripts.repair_patient_data as repair
from app.models.organization import Localidad, Ubigeo
from app.models.patient import Patient

TODAY = date(2026, 10, 20)


def district(code="040101", name="AREQUIPA", locality=None):
    return Ubigeo(
        codigo=code,
        departamento="AREQUIPA",
        provincia="AREQUIPA",
        distrito=name,
        localidad=locality,
    )


def local():
    return Localidad(
        id=10,
        ubigeo_codigo="040101",
        codigo_catalogo="0001",
        nombre="CERCADO",
        nombre_norm="cercado",
    )


def patient(**changes):
    return Patient(id=7, tipo_documento_codigo="DNI", numero_documento="00000001", **changes)


def completion_session(patients, localities=None, insurance=True):
    session = Mock()
    session.scalars.side_effect = [
        localities if localities is not None else [local()],
        [district()],
        patients,
    ]
    session.scalar.return_value = SimpleNamespace(id=3) if insurance else None
    return session


@pytest.mark.parametrize("apply", [False, True])
def test_catalog_repair_is_limited_to_official_districts_and_clears_stale_locality(apply):
    wrong = district("040102", "CAYMA", "CAYMA")
    correct = district()
    outside = district("150101", "LIMA", "REAL")
    session = Mock()
    session.scalars.return_value = [wrong, correct, outside]
    changes = repair.repair_ubigeos(session, apply)
    assert [(item.field, item.after) for item in changes] == [
        ("ubigeos.distrito", "ALTO SELVA ALEGRE"),
        ("ubigeos.localidad", None),
    ]
    assert wrong.distrito == "ALTO SELVA ALEGRE" and wrong.localidad is None
    assert outside.distrito == "LIMA" and outside.localidad == "REAL"
    session.commit.assert_not_called()


@pytest.mark.parametrize("apply", [False, True])
def test_completion_reports_missing_values_and_only_applies_with_explicit_flag(apply):
    record = patient(fecha_nacimiento=date(1990, 1, 1))
    initial = deepcopy(
        {column.key: getattr(record, column.key) for column in Patient.__table__.columns}
    )
    changes = repair.complete_patients(completion_session([record]), apply, TODAY)
    expected = {
        "ubigeo_residencia_codigo": "040101",
        "localidad_id": 10,
        "localidad": "CERCADO",
        "direccion": repair.PLACEHOLDER_ADDRESS,
        "seguro_id": 3,
        "sexo_codigo": "M",
        "telefono_principal": "900000007",
        "condicion": "ADULTO",
    }
    assert {change.field: change.after for change in changes} == expected
    if apply:
        for key, value in expected.items():
            assert getattr(record, key) == value
        assert repair.complete_patients(completion_session([record]), True, TODAY) == []
    else:
        assert {
            column.key: getattr(record, column.key) for column in Patient.__table__.columns
        } == initial


def test_completion_never_overwrites_real_contact_insurance_sex_or_condition():
    record = patient(
        ubigeo_residencia_codigo="040101",
        localidad_id=10,
        localidad="CERCADO",
        direccion="DIRECCIÓN REAL",
        seguro_id=9,
        sexo_codigo="F",
        telefono_principal="987654321",
        condicion="GESTANTE",
    )
    assert repair.complete_patients(completion_session([record]), True, TODAY) == []
    assert record.direccion == "DIRECCIÓN REAL" and record.seguro_id == 9
    assert record.condicion == "GESTANTE" and record.telefono_principal == "987654321"


@pytest.mark.parametrize("birth", [None, date(2027, 1, 1)])
def test_unknown_or_future_birth_does_not_invent_a_condition(birth):
    record = patient(fecha_nacimiento=birth)
    changes = repair.complete_patients(completion_session([record]), True, TODAY)
    assert record.condicion is None
    assert "condicion" not in {change.field for change in changes}


@pytest.mark.parametrize(
    "missing,message", [("insurance", "Falta el seguro"), ("locality", "no tiene localidades")]
)
def test_missing_reference_catalog_stops_before_mutating_patient(missing, message):
    record = patient()
    session = completion_session(
        [record], insurance=missing != "insurance", localities=[] if missing == "locality" else None
    )
    with pytest.raises(RuntimeError, match=message):
        repair.complete_patients(session, True, TODAY)
    assert record.direccion is None and record.seguro_id is None


def test_incomplete_report_identifies_each_missing_required_field():
    complete = dict(
        ubigeo_residencia_codigo="040101",
        localidad_id=10,
        localidad="CERCADO",
        direccion="REAL",
        seguro_id=3,
    )
    records = [patient(**complete)]
    for key in complete:
        records.append(patient(**{**complete, key: None}))
    session = Mock()
    session.scalars.return_value = records
    assert repair.incomplete_patients(session) == records[1:]


@pytest.mark.parametrize("apply", [False, True])
def test_cli_reports_changes_commits_only_apply_and_always_closes(monkeypatch, capsys, apply):
    session = Mock()
    monkeypatch.setattr(repair, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        repair, "get_settings", lambda: SimpleNamespace(environment=" Development ")
    )
    monkeypatch.setattr("sys.argv", ["repair_patient_data", *(["--apply"] if apply else [])])
    catalog = repair.Change("040102", "distrito", "Cayma", "ALTO SELVA ALEGRE")
    data = repair.Change("7 00000001", "direccion", None, "NO REGISTRADA")
    monkeypatch.setattr(repair, "repair_ubigeos", lambda session, flag: [catalog])
    monkeypatch.setattr(repair, "complete_patients", lambda session, flag, today: [data])
    monkeypatch.setattr(repair, "incomplete_patients", lambda session: [patient()])
    repair.main()
    output = capsys.readouterr().out
    assert "Valores de catálogo corregidos: 1" in output
    assert "Campos de paciente completados: 1" in output
    assert "Pacientes incompletos restantes: 1" in output
    assert "00000001" in output
    assert session.commit.call_count == int(apply)
    assert session.rollback.call_count == int(not apply)
    session.close.assert_called_once()


def test_cli_refuses_production_before_opening_a_session(monkeypatch):
    monkeypatch.setattr("sys.argv", ["repair_patient_data", "--apply"])
    monkeypatch.setattr(repair, "get_settings", lambda: SimpleNamespace(environment="production"))
    connect = Mock()
    monkeypatch.setattr(repair, "SessionLocal", connect)
    with pytest.raises(RuntimeError, match="solo corre"):
        repair.main()
    connect.assert_not_called()


def test_cli_failure_rolls_back_and_closes(monkeypatch):
    session = Mock()
    monkeypatch.setattr("sys.argv", ["repair_patient_data", "--apply"])
    monkeypatch.setattr(repair, "get_settings", lambda: SimpleNamespace(environment="development"))
    monkeypatch.setattr(repair, "SessionLocal", lambda: session)
    monkeypatch.setattr(repair, "repair_ubigeos", Mock(side_effect=RuntimeError("catalog failure")))
    with pytest.raises(RuntimeError, match="catalog failure"):
        repair.main()
    session.rollback.assert_called_once()
    session.close.assert_called_once()
