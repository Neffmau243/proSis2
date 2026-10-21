"""Real HTTP/service/repository checks on isolated reference tables."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.controllers.catalog import router as catalog_router
from app.controllers.staff_catalog import router
from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, get_current_principal
from app.domain.authorization import RolePermissionPolicy
from app.domain.staff_catalog import is_staff_specialty_code
from app.exceptions import register_exception_handlers
from app.models.audit import AuditLog
from app.models.catalog import Profession, Specialty
from app.repositories.staff_catalog import StaffCatalogRepository
from app.schemas.professional import ProfessionalCreate
from app.services.audit import AuditService
from app.services.professional import ProfessionalService


@pytest.fixture
def scene():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    # Only the three tables used here; SQLite's integer PK emulates MySQL's
    # BIGINT auto-increment without changing the production model metadata.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE profesiones (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "nombre VARCHAR(100) NOT NULL UNIQUE, activo BOOLEAN NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE especialidades (codigo VARCHAR(20) PRIMARY KEY, "
            "nombre VARCHAR(150) NOT NULL, grupo VARCHAR(100), activo BOOLEAN NOT NULL, "
            "es_area BOOLEAN NOT NULL DEFAULT FALSE)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id BIGINT, "
            "tabla_nombre VARCHAR(100) NOT NULL, registro_id BIGINT, accion VARCHAR(20) NOT NULL, "
            "fecha DATETIME DEFAULT CURRENT_TIMESTAMP, datos_anteriores JSON, datos_nuevos JSON)"
        )
        for statement in (
            "CREATE TABLE profesionales (id INTEGER PRIMARY KEY, profesion_id BIGINT)",
            "CREATE TABLE profesional_especialidades "
            "(profesional_id BIGINT, especialidad_codigo VARCHAR(20))",
            "CREATE TABLE consultorios (id INTEGER PRIMARY KEY, "
            "area_codigo VARCHAR(20), especialidad_codigo VARCHAR(20))",
            "CREATE TABLE atenciones (id INTEGER PRIMARY KEY, especialidad_codigo VARCHAR(20))",
        ):
            connection.exec_driver_sql(statement)
    with Session(engine) as session:
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router)
        app.include_router(catalog_router)
        app.dependency_overrides[get_db] = lambda: session

        def identity(role="ADMIN"):
            return AuthenticatedPrincipal(
                7, "test", frozenset({role}), RolePermissionPolicy().resolve([role])
            )

        app.dependency_overrides[get_current_principal] = identity
        yield TestClient(app), session, app, identity
    engine.dispose()


@pytest.mark.parametrize("kind,key", [("profesiones", "id"), ("especialidades", "codigo")])
def test_delete_unused_entry_is_audited_and_name_can_be_reused(scene, kind, key):
    client, session, _, _ = scene
    path = f"/configuracion/catalogos-personal/{kind}"
    created = client.post(path, json={"nombre": "Prueba eliminable"}).json()
    response = client.delete(f"{path}/{created[key]}")
    assert response.status_code == 204, response.text
    assert client.get(f"/catalogos/{kind}").json() == []
    audit = session.scalar(select(AuditLog).where(AuditLog.accion == "DELETE"))
    assert audit.usuario_id == 7 and audit.datos_anteriores["nombre"] == created["nombre"]
    assert audit.datos_nuevos is None
    assert client.delete(f"{path}/{created[key]}").status_code == 404
    assert client.post(path, json={"nombre": "Prueba eliminable"}).status_code == 201


@pytest.mark.parametrize("is_area", [True, False])
def test_type_is_persisted_editable_and_keeps_identity(scene, is_area):
    client, session, _, _ = scene
    path = "/configuracion/catalogos-personal/especialidades"
    created = client.post(path, json={"nombre": "Nuevo tipo", "es_area": is_area}).json()
    assert created["es_area"] is is_area
    assert created["es_area_base"] is False
    assert created["area_codigos"] == ([created["codigo"]] if is_area else [])
    session.expire_all()
    assert client.get("/catalogos/especialidades").json() == [created]
    response = client.patch(
        f"{path}/{created['codigo']}", json={"nombre": "Tipo editado", "es_area": not is_area}
    )
    assert response.status_code == 200, response.text
    assert response.json()["codigo"] == created["codigo"]
    assert response.json()["es_area"] is not is_area
    audit = session.scalar(select(AuditLog).where(AuditLog.accion == "UPDATE"))
    assert audit.datos_anteriores["es_area"] is is_area
    assert audit.datos_nuevos["es_area"] is not is_area
    assert (
        client.patch(f"{path}/{created['codigo']}", json={"nombre": "Solo nombre"}).json()[
            "es_area"
        ]
        is not is_area
    )


@pytest.mark.parametrize(
    "table,column",
    [
        ("consultorios", "area_codigo"),
        ("consultorios", "especialidad_codigo"),
        ("atenciones", "especialidad_codigo"),
    ],
)
def test_type_changes_cannot_reclassify_operational_references(scene, table, column):
    from sqlalchemy import text

    client, session, _, _ = scene
    path = "/configuracion/catalogos-personal/especialidades"
    created = client.post(path, json={"nombre": "Área en uso", "es_area": True}).json()
    session.execute(
        text(f"INSERT INTO {table} (id, {column}) VALUES (1, :code)"), {"code": created["codigo"]}
    )
    session.commit()
    response = client.patch(
        f"{path}/{created['codigo']}", json={"nombre": "No se guarda", "es_area": False}
    )
    assert response.status_code == 409, response.text
    assert client.get("/catalogos/especialidades").json() == [created]


def test_base_area_cannot_be_retyped_but_custom_unused_area_can_be_deleted(scene):
    client, session, _, _ = scene
    session.add(
        Specialty(codigo="ESPECIALIDADES:003", nombre="MEDICINA", activo=True, es_area=True)
    )
    session.commit()
    path = "/configuracion/catalogos-personal/especialidades"
    assert (
        client.patch(
            f"{path}/ESPECIALIDADES:003", json={"nombre": "Medicina", "es_area": False}
        ).status_code
        == 409
    )
    created = client.post(path, json={"nombre": "Área eliminable", "es_area": True}).json()
    assert client.delete(f"{path}/{created['codigo']}").status_code == 204


@pytest.mark.parametrize(
    "table,columns,kind,key",
    [
        ("profesionales", "id, profesion_id", "profesiones", "id"),
        (
            "profesional_especialidades",
            "profesional_id, especialidad_codigo",
            "especialidades",
            "codigo",
        ),
        ("consultorios", "id, especialidad_codigo", "especialidades", "codigo"),
        ("consultorios", "id, area_codigo", "especialidades", "codigo"),
        ("atenciones", "id, especialidad_codigo", "especialidades", "codigo"),
    ],
)
def test_delete_protects_assigned_records(scene, table, columns, kind, key):
    from sqlalchemy import text

    client, session, _, _ = scene
    path = f"/configuracion/catalogos-personal/{kind}"
    created = client.post(path, json={"nombre": "Prueba vinculada"}).json()
    session.execute(
        text(f"INSERT INTO {table} ({columns}) VALUES (1, :reference)"), {"reference": created[key]}
    )
    session.commit()
    assert client.delete(f"{path}/{created[key]}").status_code == 409
    assert client.get(f"/catalogos/{kind}").json() == [created]
    assert session.scalar(select(AuditLog).where(AuditLog.accion == "DELETE")) is None


def test_delete_protects_base_areas_services_and_admin_permission(scene):
    client, session, app, identity = scene
    session.add_all(
        [
            Specialty(codigo="ESPECIALIDADES:003", nombre="MEDICINA", activo=True),
            Specialty(codigo="ESP_MEDICINA:001", nombre="SERVICIO", activo=True),
        ]
    )
    session.commit()
    path = "/configuracion/catalogos-personal/especialidades"
    assert client.delete(f"{path}/ESPECIALIDADES:003").status_code == 409
    assert client.delete(f"{path}/ESP_MEDICINA:001").status_code == 404
    for kind, identifier in (("profesiones", "1"), ("especialidades", "ESPECIALIDADES:003")):
        app.dependency_overrides[get_current_principal] = lambda: identity("PROFESIONAL")
        assert (
            client.delete(f"/configuracion/catalogos-personal/{kind}/{identifier}").status_code
            == 403
        )
        app.dependency_overrides.pop(get_current_principal)
        assert (
            client.delete(f"/configuracion/catalogos-personal/{kind}/{identifier}").status_code
            == 401
        )


@pytest.mark.parametrize("kind", ["profesiones", "especialidades"])
def test_create_is_audited_and_immediately_available_in_existing_selectors(scene, kind):
    client, session, _, _ = scene
    payload = {"nombre": "  Terapia   ocupacional "}
    if kind == "especialidades":
        payload["grupo"] = "  Rehabilitación "
    response = client.post(f"/configuracion/catalogos-personal/{kind}", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["nombre"] == "TERAPIA OCUPACIONAL" and created["activo"] is True
    assert client.get(f"/catalogos/{kind}").json() == [created]
    audit = session.scalar(select(AuditLog))
    assert audit.usuario_id == 7 and audit.tabla_nombre == kind and audit.accion == "INSERT"
    assert audit.datos_nuevos["codigo"] == created["codigo"]
    if kind == "especialidades":
        assert len(created["codigo"]) == 20
        assert created["grupo"] == "REHABILITACIÓN"
        assert created["es_area"] is False and created["area_codigos"] == []
        # The existing professional workflow accepts the new qualification.
        service = ProfessionalService(session)
        command = ProfessionalCreate(
            nombre_completo="Profesional",
            especialidades=[
                {
                    "especialidad_codigo": created["codigo"],
                    "es_principal": True,
                }
            ],
        )
        service._validate_specialties(command.especialidades)
    else:
        ProfessionalService(session)._validate_profession(created["id"])


@pytest.mark.parametrize("kind,model", [("profesiones", Profession), ("especialidades", Specialty)])
def test_duplicate_name_including_inactive_accents_case_and_spacing_is_rejected(scene, kind, model):
    client, session, _, _ = scene
    fields = {"nombre": "TERAPIA FÍSICA", "activo": False}
    if model is Specialty:
        fields["codigo"] = "LEGACY:001"
    session.add(model(**fields))
    session.commit()
    response = client.post(
        f"/configuracion/catalogos-personal/{kind}", json={"nombre": "terapia   fisica"}
    )
    assert response.status_code == 409
    assert len(list(session.scalars(select(model)))) == 1
    assert session.scalar(select(AuditLog)) is None


@pytest.mark.parametrize("kind", ["profesiones", "especialidades"])
def test_professional_and_anonymous_cannot_create_catalog_entries(scene, kind):
    client, session, app, identity = scene
    app.dependency_overrides[get_current_principal] = lambda: identity("PROFESIONAL")
    path = f"/configuracion/catalogos-personal/{kind}"
    assert client.post(path, json={"nombre": "Nueva"}).status_code == 403
    app.dependency_overrides.pop(get_current_principal)
    assert client.post(path, json={"nombre": "Nueva"}).status_code == 401
    assert session.scalar(select(Profession)) is None
    assert session.scalar(select(Specialty)) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"nombre": "   "},
        {"nombre": "X"},
        {"nombre": "X" * 151},
        {"nombre": "Nueva", "activo": False},
        {"nombre": "Nueva", "codigo": "ESPECIALIDADES:003"},
    ],
)
def test_invalid_or_identity_overriding_payloads_are_rejected(scene, payload):
    client, session, _, _ = scene
    assert (
        client.post("/configuracion/catalogos-personal/especialidades", json=payload).status_code
        == 422
    )
    assert session.scalar(select(Specialty)) is None


def test_concurrent_specialty_duplicate_rolls_back_without_overwriting_existing(scene, monkeypatch):
    client, session, _, _ = scene
    path = "/configuracion/catalogos-personal/especialidades"
    first = client.post(path, json={"nombre": "Fisioterapia"}).json()
    monkeypatch.setattr(StaffCatalogRepository, "specialty_name_exists", lambda *_: False)
    assert client.post(path, json={"nombre": "FISIOTERAPIA"}).status_code == 409
    assert client.get("/catalogos/especialidades").json() == [first]
    assert len(list(session.scalars(select(AuditLog)))) == 1


def test_a_new_qualification_does_not_overwrite_or_conflict_with_a_legacy_care_service(scene):
    client, session, _, _ = scene
    session.add(
        Specialty(codigo="ESP_MEDICINA:003", nombre="PEDIATRIA", grupo="Esp_Medicina", activo=True)
    )
    session.commit()
    response = client.post(
        "/configuracion/catalogos-personal/especialidades", json={"nombre": "Pediatría"}
    )
    assert response.status_code == 201
    assert is_staff_specialty_code(response.json()["codigo"])
    assert not is_staff_specialty_code("ESP_MEDICINA:003")
    assert is_staff_specialty_code("Especialidades:005")
    original = session.get(Specialty, "ESP_MEDICINA:003")
    assert original.nombre == "PEDIATRIA" and original.grupo == "Esp_Medicina"
    assert len(client.get("/catalogos/especialidades").json()) == 2


@pytest.mark.parametrize("kind,model", [("profesiones", Profession), ("especialidades", Specialty)])
def test_audit_failure_rolls_back_the_new_catalog_entry(scene, monkeypatch, kind, model):
    client, session, _, _ = scene
    monkeypatch.setattr(AuditService, "record", Mock(side_effect=RuntimeError("audit failed")))
    with pytest.raises(RuntimeError, match="audit failed"):
        client.post(f"/configuracion/catalogos-personal/{kind}", json={"nombre": "Nueva"})
    assert session.scalar(select(model)) is None


@pytest.mark.parametrize("kind", ["profesiones", "especialidades"])
def test_rename_preserves_identity_and_audits_before_after(scene, kind):
    client, session, _, _ = scene
    base = f"/configuracion/catalogos-personal/{kind}"
    original = client.post(base, json={"nombre": "Terapia inicial"}).json()
    key = original.get("id", original["codigo"])
    response = client.patch(f"{base}/{key}", json={"nombre": " Terapia nueva "})
    assert response.status_code == 200, response.text
    renamed = response.json()
    assert renamed["codigo"] == original["codigo"]
    assert renamed.get("id") == original.get("id")
    assert renamed["nombre"] == "TERAPIA NUEVA"
    assert client.get(f"/catalogos/{kind}").json() == [renamed]
    audit = session.scalars(select(AuditLog).where(AuditLog.accion == "UPDATE")).one()
    assert audit.datos_anteriores["nombre"] == "TERAPIA INICIAL"
    assert audit.datos_nuevos["nombre"] == "TERAPIA NUEVA"
    assert client.patch(f"{base}/{key}", json={"nombre": "terapia nueva"}).status_code == 200
    # The old name can be used again without reusing or changing the old code.
    recreated = client.post(base, json={"nombre": "Terapia inicial"})
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["codigo"] != original["codigo"]


@pytest.mark.parametrize("kind", ["profesiones", "especialidades"])
def test_rename_rejects_duplicate_and_identity_changes(scene, kind):
    client, _, _, _ = scene
    base = f"/configuracion/catalogos-personal/{kind}"
    original = client.post(base, json={"nombre": "Original"}).json()
    client.post(base, json={"nombre": "Ocupado"})
    key = original.get("id", original["codigo"])
    assert client.patch(f"{base}/{key}", json={"nombre": "ocupado"}).status_code == 409
    for field, value in [("codigo", "OTRO"), ("activo", False), ("grupo", "OTRO")]:
        assert (
            client.patch(f"{base}/{key}", json={"nombre": "Cambio", field: value}).status_code
            == 422
        )
    assert any(item["nombre"] == "ORIGINAL" for item in client.get(f"/catalogos/{kind}").json())


@pytest.mark.parametrize("kind,key", [("profesiones", "999"), ("especialidades", "NO-EXISTE")])
def test_rename_enforces_permissions_and_reports_unknown_record(scene, kind, key):
    client, _, app, identity = scene
    path = f"/configuracion/catalogos-personal/{kind}/{key}"
    assert client.patch(path, json={"nombre": "Cambio"}).status_code == 404
    app.dependency_overrides[get_current_principal] = lambda: identity("PROFESIONAL")
    assert client.patch(path, json={"nombre": "Cambio"}).status_code == 403


def test_legacy_area_can_be_renamed_without_editing_service_codes_or_groups(scene):
    client, session, _, _ = scene
    session.add_all(
        [
            Specialty(
                codigo="ESPECIALIDADES:005", nombre="NUTRICION", grupo="Especialidades", activo=True
            ),
            Specialty(
                codigo="ESP_NUTRICION:002", nombre="CANASTA TBC", grupo="Esp_Nutricion", activo=True
            ),
        ]
    )
    session.commit()
    base = "/configuracion/catalogos-personal/especialidades"
    response = client.patch(f"{base}/ESPECIALIDADES:005", json={"nombre": "Nutrición clínica"})
    assert response.status_code == 200
    assert response.json()["es_area"] is True
    assert response.json()["codigo"] == "ESPECIALIDADES:005"
    assert response.json()["grupo"] == "Especialidades"
    assert client.patch(f"{base}/ESP_NUTRICION:002", json={"nombre": "Cambio"}).status_code == 404
    assert session.get(Specialty, "ESP_NUTRICION:002").nombre == "CANASTA TBC"
