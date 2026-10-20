"""Seed repair/abort paths use synthetic catalogs and never connect to a database."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.scripts.bootstrap_database as bootstrap
import app.scripts.reset_demo_database as reset
import app.scripts.seed_demo_data as seed
from app.models.catalog import AgeGroup
from app.models.patient import Patient


def test_bootstrap_entry_point_creates_before_migrating(monkeypatch, capsys):
    events = []
    monkeypatch.setattr(
        bootstrap, "create_database_if_missing", lambda: events.append("create") or "ipress_test"
    )
    monkeypatch.setattr(bootstrap, "upgrade_to_head", lambda: events.append("migrate"))
    bootstrap.bootstrap_database()
    assert events == ["create", "migrate"]
    assert "ipress_test" in capsys.readouterr().out


def test_reset_rejects_non_mysql_without_connecting():
    settings = SimpleNamespace(
        environment="development",
        sqlalchemy_database_url="postgresql://localhost/test",
        mysql_database="test",
    )
    with pytest.raises(ValueError, match="MySQL"):
        reset.drop_configured_database(settings)


def test_reset_with_explicit_password_uses_the_requested_user_without_printing_password(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        "sys.argv",
        ["reset", "--confirm-delete", "--username", "admin.test", "--password", "12345678"],
    )
    monkeypatch.setattr(reset, "drop_configured_database", lambda: "ipress_test")
    monkeypatch.setattr(reset, "create_database_if_missing", lambda: "ipress_test")
    monkeypatch.setattr(reset, "upgrade_to_head", lambda: None)
    create = Mock(return_value=7)
    monkeypatch.setattr(reset, "create_admin", create)
    monkeypatch.setattr(reset, "seed_demo_data", lambda: {"patients": 2})
    reset.main()
    create.assert_called_once_with("admin.test", "12345678")
    assert "12345678" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "helper,args,message",
    [
        ("_catalog_locality", ("040101", "CERCADO"), "localidad"),
        ("_real_establishment", ("00001234",), "sede"),
    ],
)
def test_seed_refuses_missing_catalogs(helper, args, message):
    session = Mock()
    session.scalar.return_value = None
    with pytest.raises(RuntimeError, match=message):
        getattr(seed, helper)(session, *args)


@pytest.mark.parametrize(
    "problem,message",
    [
        ("role", "rol PROFESIONAL"),
        ("linked", "vinculado a otro usuario"),
        ("other_professional", "otro profesional"),
    ],
)
def test_demo_account_is_never_rebound_over_an_existing_identity(problem, message):
    session = Mock()
    role = SimpleNamespace(id=2)
    outputs = {
        "role": [None],
        "linked": [role, None, object()],
        "other_professional": [role, SimpleNamespace(profesional_id=99)],
    }
    session.scalar.side_effect = outputs[problem]
    with pytest.raises(RuntimeError, match=message):
        seed._ensure_demo_professional_user(session, SimpleNamespace(id=7))
    session.add.assert_not_called()


def test_existing_cohort_patient_gets_catalog_locality_repaired_without_identity_changes(
    monkeypatch,
):
    demo = seed.DEMO_PATIENTS[0]
    record = SimpleNamespace(
        id=7, localidad_id=None, localidad="incorrecta", numero_documento=demo.document_number
    )
    session = Mock()
    session.scalar.return_value = record
    monkeypatch.setattr(seed, "DEMO_PATIENTS", [demo])
    monkeypatch.setattr(
        seed, "_catalog_locality", lambda *args: SimpleNamespace(id=9, nombre="CATÁLOGO")
    )
    monkeypatch.setattr(seed, "_get_or_create", Mock())
    patients = seed._seed_demo_patients(
        session,
        origin=object(),
        destination=object(),
        districts={demo.district_code: demo.district_code},
        insurances={},
        risk_groups={demo.risk_code: SimpleNamespace(id=1)},
        professional=object(),
    )
    assert patients[demo.document_number] is record
    assert record.localidad_id == 9 and record.localidad == "CATÁLOGO"
    assert record.numero_documento == demo.document_number
    session.add.assert_not_called()


@pytest.mark.parametrize("missing", ["district", "locality", "site", "insurance"])
def test_source_examples_require_all_catalogs_before_adding_a_patient(missing):
    session = Mock()
    session.get.return_value = None if missing == "district" else SimpleNamespace(codigo="040102")
    items = [None, object(), object(), object()]
    if missing != "district":
        items[["locality", "site", "insurance"].index(missing) + 1] = None
    session.scalar.side_effect = items
    with pytest.raises(RuntimeError):
        seed._seed_source_examples(session, ubigeo_codigo="040102", professional=object())
    session.add.assert_not_called()


def test_unknown_demo_document_type_does_not_issue_anything():
    documents = Mock()
    with pytest.raises(RuntimeError, match="no soportado"):
        seed._issue_demo_document(
            Mock(),
            documents,
            encounter=SimpleNamespace(document="UNKNOWN"),
            attention_id=1,
            destination=object(),
            actor_id=7,
        )
    assert documents.method_calls == []


@pytest.fixture
def seed_scene(monkeypatch):
    session = Mock()
    monkeypatch.setattr(seed, "SessionLocal", lambda: session)
    monkeypatch.setattr(seed, "get_settings", lambda: SimpleNamespace(environment="development"))
    groups = {
        code: SimpleNamespace(edad_minima_meses=None, edad_maxima_meses=None)
        for code in ["NINO", "ADOLESCENTE", "JOVEN", "ADULTO", "ADULTO_MAYOR"]
    }
    session.get.side_effect = lambda model, key: (
        groups.get(key) if model is AgeGroup else SimpleNamespace(codigo=key)
    )
    session.scalars.return_value.all.return_value = []
    session.scalar.side_effect = [SimpleNamespace(id=2), SimpleNamespace(id=3), None]
    patients = []

    def existing_or_created(session, model, lookup, values=None):
        item = SimpleNamespace(id=10 + len(patients), **lookup, **(values or {}))
        if model is Patient:
            item.localidad_id = None
            item.direccion = None
            patients.append(item)
        return item

    monkeypatch.setattr(seed, "_get_or_create", existing_or_created)
    monkeypatch.setattr(seed, "_real_establishment", lambda *args: SimpleNamespace(id=1))
    monkeypatch.setattr(seed, "_ensure_demo_professional_user", lambda *args: SimpleNamespace(id=4))
    monkeypatch.setattr(
        seed, "_catalog_locality", lambda *args: SimpleNamespace(id=5, nombre="CATÁLOGO")
    )
    monkeypatch.setattr(seed, "_seed_demo_patients", lambda *args, **kwargs: {})
    monkeypatch.setattr(seed, "_seed_source_examples", lambda *args, **kwargs: {})
    monkeypatch.setattr(seed, "_seed_demo_encounters", lambda *args, **kwargs: {})
    return session, groups, patients


@pytest.mark.parametrize("state", ["missing", "unset", "configured"])
def test_seed_initializes_only_missing_age_ranges_and_repairs_legacy_patient_residence(
    seed_scene, state
):
    session, groups, patients = seed_scene
    if state == "missing":
        groups.clear()
    elif state == "configured":
        for item in groups.values():
            item.edad_minima_meses, item.edad_maxima_meses = 1, 10
    result = seed.seed_demo_data()
    assert result["adult_patient_id"] > 0 and result["minor_patient_id"] > 0
    assert len(patients) == 2
    assert all(patient.localidad_id == 5 and patient.direccion for patient in patients)
    if state == "missing":
        assert sum(isinstance(call.args[0], AgeGroup) for call in session.add.call_args_list) == 5
    elif state == "unset":
        assert groups["ADOLESCENTE"].edad_minima_meses == 144
    else:
        assert groups["ADOLESCENTE"].edad_minima_meses == 1
    session.commit.assert_called_once()
    session.close.assert_called_once()


@pytest.mark.parametrize(
    "problem,message",
    [("district", "ubigeo"), ("office", "consultorio"), ("professional", "profesional")],
)
def test_seed_failure_rolls_back_pending_catalogs_and_closes(seed_scene, problem, message):
    session, groups, _ = seed_scene
    if problem == "district":
        session.get.side_effect = lambda model, key: groups.get(key) if model is AgeGroup else None
    elif problem == "office":
        session.scalar.side_effect = [None]
    else:
        session.scalar.side_effect = [SimpleNamespace(id=2), None]
    with pytest.raises(RuntimeError, match=message):
        seed.seed_demo_data()
    session.rollback.assert_called_once()
    session.close.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize("problem", ["production", "no_professional"])
def test_real_seed_stops_before_creating_patients(monkeypatch, problem):
    session = Mock()
    session.scalar.return_value = None
    connect = Mock(return_value=session)
    monkeypatch.setattr(seed, "SessionLocal", connect)
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production" if problem == "production" else "development"
        ),
    )
    with pytest.raises(RuntimeError):
        seed.seed_real_patients()
    if problem == "production":
        connect.assert_not_called()
    else:
        session.rollback.assert_called_once()
        session.close.assert_called_once()
