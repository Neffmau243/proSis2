"""Real HTTP, transactions and inherited care-service checks on isolated SQLite."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Integer, MetaData, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.controllers.catalog import router as catalog_router
from app.controllers.office import router
from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, get_current_principal
from app.domain.authorization import RolePermissionPolicy
from app.domain.office import AREA_SERVICES, custom_service_area, office_context
from app.domain.staff_catalog import is_staff_specialty_code
from app.exceptions import register_exception_handlers
from app.models import Base
from app.models.audit import AuditLog
from app.models.catalog import Specialty
from app.models.organization import Establishment, Office
from app.schemas.office_service import OfficeServiceAdd
from app.services.office_service import OfficeCareService

MED = "ESPECIALIDADES:003"
LAB = "ESPECIALIDADES:002"
PED = "ESP_MEDICINA:003"


@pytest.fixture
def scene():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    names = [
        "especialidades",
        "establecimientos",
        "consultorios",
        "consultorio_profesionales",
        "auditoria",
    ]
    for name in ("establecimientos", "consultorios", "auditoria"):
        metadata.tables[name].c.id.type = Integer()
    metadata.create_all(engine, tables=[metadata.tables[name] for name in names])
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                Specialty(codigo=MED, nombre="MEDICINA", es_area=True, activo=True),
                Specialty(codigo=LAB, nombre="LABORATORIO", es_area=True, activo=True),
            ]
        )
        for code, name in zip(
            AREA_SERVICES[MED],
            ["MEDICINA GENERAL", "DANT", "PEDIATRIA", "GINECOLOGIA"],
            strict=True,
        ):
            session.add(Specialty(codigo=code, nombre=name, activo=True))
        site = Establishment(nombre="SEDE DE PRUEBA", activo=True)
        session.add(site)
        session.flush()
        office = Office(
            establecimiento_id=site.id,
            codigo="MED",
            nombre="MEDICINA",
            area_codigo=MED,
            activo=True,
        )
        lab = Office(
            establecimiento_id=site.id,
            codigo="LAB",
            nombre="LABORATORIO",
            area_codigo=LAB,
            activo=True,
        )
        session.add_all([office, lab])
        session.commit()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router)
        app.include_router(catalog_router)
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
            7, "test", frozenset({"ADMIN"}), RolePermissionPolicy().resolve(["ADMIN"])
        )
        yield TestClient(app), session, office, lab, app
    engine.dispose()


def test_new_service_is_persisted_audited_and_usable_by_child_and_clinical_catalog(scene):
    client, session, office, _, _ = scene
    response = client.post(
        f"/configuracion/consultorios/{office.id}/servicios", json={"nombre": "Servicio adicional"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    code = data["servicio"]["codigo"]
    assert code.startswith("SRV-")
    assert {item["nombre"] for item in data["consultorio"]["servicios_habilitados"]} == {
        "MEDICINA GENERAL",
        "DANT",
        "PEDIATRIA",
        "GINECOLOGIA",
        "MEDICINA",
        "SERVICIO ADICIONAL",
    }
    assert custom_service_area(session.get(Specialty, code)) == MED
    assert not is_staff_specialty_code(code)
    assert len(list(session.scalars(select(AuditLog)))) == 2
    child = client.post(
        "/configuracion/consultorios",
        json={
            "establecimiento_id": office.establecimiento_id,
            "codigo": "SUB-1",
            "nombre": "SERVICIO ADICIONAL",
            "consultorio_padre_id": office.id,
            "area_codigo": MED,
            "servicios_codigos": [code],
        },
    )
    assert child.status_code == 201, child.text
    assert child.json()["servicios_habilitados"] == [data["servicio"]]
    catalog = client.get("/catalogos/consultorios", params={"limit": 100}).json()["items"]
    assert next(item for item in catalog if item["id"] == child.json()["id"])[
        "servicios_habilitados"
    ] == [data["servicio"]]
    entry = next(
        item for item in client.get("/catalogos/especialidades").json() if item["codigo"] == code
    )
    assert entry["area_codigos"] == [MED]


def test_existing_service_can_be_enabled_without_recreating_it_and_names_are_idempotent(scene):
    client, session, office, _, _ = scene
    office.servicios_codigos = [MED]
    session.commit()
    path = f"/configuracion/consultorios/{office.id}/servicios"
    assert PED in [item["codigo"] for item in client.get(path).json()]
    first = client.post(path, json={"codigo": PED})
    assert first.status_code == 200, first.text
    assert set(office_context(office).service_codes) == {MED, PED}
    second = client.post(path, json={"nombre": "  pediatría  "})
    assert second.status_code == 200, second.text
    assert second.json()["servicio"]["codigo"] == PED
    assert len(list(session.scalars(select(Specialty)))) == 6


def test_custom_service_is_available_to_other_offices_of_same_area_but_not_other_areas(scene):
    client, session, office, lab, _ = scene
    data = client.post(
        f"/configuracion/consultorios/{office.id}/servicios", json={"nombre": "Servicio compartido"}
    ).json()
    code = data["servicio"]["codigo"]
    other = Office(
        establecimiento_id=office.establecimiento_id,
        codigo="MED2",
        nombre="MEDICINA 2",
        area_codigo=MED,
        activo=True,
    )
    session.add(other)
    session.commit()
    assert code in [
        item["codigo"]
        for item in client.get(f"/configuracion/consultorios/{other.id}/servicios").json()
    ]
    assert code not in [
        item["codigo"]
        for item in client.get(f"/configuracion/consultorios/{lab.id}/servicios").json()
    ]
    rejected = client.post(f"/configuracion/consultorios/{lab.id}/servicios", json={"codigo": code})
    assert 400 <= rejected.status_code < 500
    assert lab.servicios_codigos is None
    # The ordinary office-edit endpoint applies the same area boundary.
    rejected = client.patch(
        f"/configuracion/consultorios/{lab.id}", json={"servicios_codigos": [code]}
    )
    assert 400 <= rejected.status_code < 500


def test_lab_can_register_a_real_addition_without_modifying_other_offices(scene):
    client, _, office, lab, _ = scene
    path = f"/configuracion/consultorios/{lab.id}/servicios"
    assert [item["codigo"] for item in client.get(path).json()] == [LAB]
    added = client.post(path, json={"nombre": "Servicio de prueba"})
    assert added.status_code == 200, added.text
    assert len(added.json()["consultorio"]["servicios_habilitados"]) == 2
    assert len(office_context(office).service_codes) == 5


def test_audit_failure_rolls_back_both_catalog_entry_and_enabled_services(scene):
    _, session, office, _, _ = scene
    use_case = OfficeCareService(session, audit=Mock(side_effect=RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError, match="audit unavailable"):
        use_case.add(office.id, OfficeServiceAdd(nombre="No debe persistir"), actor_id=7)
    session.refresh(office)
    assert office.servicios_codigos is None
    assert session.scalar(select(Specialty).where(Specialty.nombre == "NO DEBE PERSISTIR")) is None


def test_permissions_and_invalid_requests_do_not_create_services(scene):
    client, session, office, _, app = scene
    path = f"/configuracion/consultorios/{office.id}/servicios"
    for payload in (
        {},
        {"nombre": " ", "codigo": PED},
        {"nombre": "x"},
        {"nombre": "Nuevo", "codigo": PED},
    ):
        assert client.post(path, json=payload).status_code == 422
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        8, "doctor", frozenset({"PROFESIONAL"}), RolePermissionPolicy().resolve(["PROFESIONAL"])
    )
    assert client.get(path).status_code == 403
    assert client.post(path, json={"nombre": "Sin permiso"}).status_code == 403
    assert len(list(session.scalars(select(Specialty)))) == 6
