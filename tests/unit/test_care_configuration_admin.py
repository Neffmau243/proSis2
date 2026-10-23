"""HTTP administration on isolated SQLite; no clinic/default-print rewrites."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Integer, MetaData, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.controllers.care_configuration import router
from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, get_current_principal
from app.domain.authorization import RolePermissionPolicy
from app.exceptions import register_exception_handlers
from app.models import Base
from app.models.audit import AuditLog
from app.models.catalog import Specialty
from app.models.organization import Establishment, Office
from app.schemas.care_configuration import EstablishmentUpdate
from app.services.care_configuration import EstablishmentAdministration

MED = "ESPECIALIDADES:003"


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
        "ubigeos",
        "auditoria",
        "profesionales",
        "profesional_especialidades",
    ]
    for name in names:
        if "id" in metadata.tables[name].c:
            metadata.tables[name].c.id.type = Integer()
    metadata.create_all(engine, tables=[metadata.tables[name] for name in names])
    with Session(engine, expire_on_commit=False) as session:
        site = Establishment(
            nombre="SEDE ORIGINAL",
            codigo_renaes="00001291",
            activo=True,
            fua_personal_atiende="IPRESS",
            fua_lugar_atencion="EXTRAMURAL",
            fua_codigo_aisped="123",
            fua_renipress_preimpreso=False,
        )
        session.add_all([site, Specialty(codigo=MED, nombre="MEDICINA", es_area=True, activo=True)])
        session.commit()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
            7, "admin", frozenset({"ADMIN"}), RolePermissionPolicy().resolve(["ADMIN"])
        )
        yield TestClient(app), session, site, app
    engine.dispose()


def test_establishment_crud_and_pagination_keep_read_only_fua_defaults(scene):
    client, session, site, _ = scene
    renamed = client.patch(
        f"/configuracion/establecimientos/{site.id}", json={"nombre": "Sede nueva"}
    )
    assert renamed.status_code == 200, renamed.text
    data = renamed.json()
    assert data["codigo_renaes"] == "00001291"
    assert data["fua_lugar_atencion"] == "EXTRAMURAL"
    assert data["fua_codigo_aisped"] == "123"
    assert data["fua_renipress_preimpreso"] is False
    session.expire_all()
    assert site.fua_lugar_atencion == "EXTRAMURAL"
    assert (
        client.patch(
            f"/configuracion/establecimientos/{site.id}", json={"fua_lugar_atencion": "INTRAMURAL"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/configuracion/establecimientos/{site.id}", json={"nombre": None}
        ).status_code
        == 422
    )
    created = client.post(
        "/configuracion/establecimientos", json={"nombre": "Segunda sede", "codigo_renaes": "002"}
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    page = client.get("/configuracion/establecimientos", params={"limit": 1}).json()
    assert page["total"] == 2 and page["has_more"]
    assert client.delete(f"/configuracion/establecimientos/{identifier}").json()["activo"] is False
    assert client.get("/configuracion/establecimientos").json()["total"] == 1
    assert (
        client.get("/configuracion/establecimientos", params={"incluir_inactivos": True}).json()[
            "total"
        ]
        == 2
    )
    assert (
        client.post(f"/configuracion/establecimientos/{identifier}/reactivar").json()["activo"]
        is True
    )
    assert len(list(session.scalars(select(AuditLog)))) == 4


def test_establishment_conflicts_and_dependencies_do_not_cascade(scene):
    client, session, site, _ = scene
    duplicate = client.post(
        "/configuracion/establecimientos",
        json={"nombre": "Duplicado", "codigo_renaes": site.codigo_renaes},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert (
        client.post(
            "/configuracion/establecimientos",
            json={"nombre": "Distrito inválido", "ubigeo_codigo": "999999"},
        ).status_code
        == 404
    )
    office = Office(
        establecimiento_id=site.id, codigo="MED", nombre="MEDICINA", area_codigo=MED, activo=True
    )
    session.add(office)
    session.commit()
    rejected = client.delete(f"/configuracion/establecimientos/{site.id}")
    assert rejected.status_code == 409, rejected.text
    session.expire_all()
    assert site.activo and office.activo
    assert (
        client.get(f"/configuracion/establecimientos/{site.id}").json()["consultorios_total"] == 1
    )


def test_area_lifecycle_and_shared_office_usage_preserve_identity(scene):
    client, session, site, _ = scene
    created = client.post("/configuracion/areas", json={"nombre": "Rehabilitación"})
    assert created.status_code == 201, created.text
    code = created.json()["codigo"]
    assert created.json()["consultorios"] == []
    assert (
        client.patch(
            f"/configuracion/areas/{code}", json={"nombre": "Rehabilitación integral"}
        ).json()["codigo"]
        == code
    )
    assert client.delete(f"/configuracion/areas/{code}").json()["activo"] is False
    assert code not in {item["codigo"] for item in client.get("/configuracion/areas").json()}
    assert client.post(f"/configuracion/areas/{code}/reactivar").json()["activo"] is True
    other = Establishment(nombre="OTRA SEDE", activo=True)
    session.add(other)
    session.flush()
    for identifier in (site.id, other.id):
        session.add(
            Office(
                establecimiento_id=identifier,
                codigo="REH",
                nombre="Consultorio",
                area_codigo=code,
                activo=True,
            )
        )
    session.commit()
    items = client.get("/configuracion/areas").json()
    area = next(item for item in items if item["codigo"] == code)
    assert {item["establecimiento_id"] for item in area["consultorios"]} == {site.id, other.id}
    assert client.delete(f"/configuracion/areas/{code}").status_code == 409
    assert session.get(Specialty, code).activo
    assert client.delete(f"/configuracion/areas/{MED}").status_code == 409


def test_failed_audit_rolls_back_administrative_changes(scene):
    _, session, site, _ = scene
    service = EstablishmentAdministration(session, Mock(side_effect=RuntimeError("audit failed")))
    with pytest.raises(RuntimeError):
        service.save(EstablishmentUpdate(nombre="No guardar"), identifier=site.id, actor_id=7)
    session.expire_all()
    assert site.nombre == "SEDE ORIGINAL"


@pytest.mark.parametrize("path", ["/configuracion/establecimientos", "/configuracion/areas"])
def test_clinical_role_cannot_enter_configuration(scene, path):
    client, _, _, app = scene
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        8, "medico", frozenset({"PROFESIONAL"}), RolePermissionPolicy().resolve(["PROFESIONAL"])
    )
    assert client.get(path).status_code == 403
    assert client.post(path, json={"nombre": "No autorizado"}).status_code == 403
