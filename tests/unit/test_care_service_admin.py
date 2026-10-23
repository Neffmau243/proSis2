"""Administrative CRUD and service-scoped admission on isolated SQL persistence."""

from datetime import date, datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Integer, MetaData, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.controllers.care_service import router as care_router
from app.controllers.catalog import router as catalog_router
from app.controllers.office import router as office_router
from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, get_current_principal
from app.domain.authorization import RolePermissionPolicy
from app.exceptions import register_exception_handlers
from app.models import Base
from app.models.audit import AuditLog
from app.models.catalog import Specialty
from app.models.clinical import Attention
from app.models.organization import Establishment, Office, OfficeProfessional
from app.models.security import Professional, ProfessionalSpecialty
from app.repositories.attention import AttentionRepository
from app.schemas.office_service import CareServiceCreate
from app.services.care_service_catalog import CareServiceCatalog

MED = "ESPECIALIDADES:003"
GENERAL = "ESP_MEDICINA:001"
PED = "ESP_MEDICINA:003"
START = "2026-01-01"


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
        "profesiones",
        "profesionales",
        "profesional_especialidades",
        "auditoria",
        "atenciones",
    ]
    for name in names:
        if "id" in metadata.tables[name].c:
            metadata.tables[name].c.id.type = Integer()
    metadata.create_all(engine, tables=[metadata.tables[name] for name in names])
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                Specialty(codigo=MED, nombre="MEDICINA", activo=True, es_area=True),
                Specialty(codigo=GENERAL, nombre="MEDICINA GENERAL", activo=True),
                Specialty(codigo=PED, nombre="PEDIATRÍA", activo=True),
            ]
        )
        site = Establishment(nombre="SEDE DE PRUEBA", activo=True)
        session.add(site)
        session.flush()
        office = Office(
            establecimiento_id=site.id,
            codigo="MED",
            nombre="MEDICINA",
            area_codigo=MED,
            servicios_codigos=[GENERAL, PED],
            activo=True,
        )
        session.add(office)
        for number in range(1, 5):
            professional = Professional(
                id=number, nombre_completo=f"Profesional {number}", activo=True
            )
            session.add(professional)
            session.add(ProfessionalSpecialty(profesional_id=number, especialidad_codigo=MED))
        session.commit()
        app = FastAPI()
        register_exception_handlers(app)
        for router in (care_router, office_router, catalog_router):
            app.include_router(router)
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
            7, "test", frozenset({"ADMIN"}), RolePermissionPolicy().resolve(["ADMIN"])
        )
        yield TestClient(app), session, office, app
    engine.dispose()


def test_catalog_create_rename_deactivate_and_reactivate_do_not_enable_service(scene):
    client, session, office, _ = scene
    created = client.post(
        "/configuracion/servicios", json={"nombre": "  servicio nuevo ", "area_codigo": MED}
    )
    assert created.status_code == 201, created.text
    data = created.json()
    code = data["codigo"]
    assert data["nombre"] == "SERVICIO NUEVO"
    assert data["consultorios"] == []
    assert office.servicios_codigos == [GENERAL, PED]
    duplicate = client.post(
        "/configuracion/servicios", json={"nombre": "servicio NUEVO", "area_codigo": MED}
    )
    assert duplicate.json()["codigo"] == code
    renamed = client.patch(
        f"/configuracion/servicios/{code}", json={"nombre": "Servicio renombrado"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["codigo"] == code
    assert client.delete(f"/configuracion/servicios/{code}").json()["activo"] is False
    assert code not in {row["codigo"] for row in client.get("/configuracion/servicios").json()}
    assert client.post(f"/configuracion/servicios/{code}/reactivar").json()["activo"] is True
    assert session.get(Specialty, code).activo


def test_catalog_explains_dependencies_and_protects_staff_qualifications(scene):
    client, session, office, _ = scene
    session.add(Specialty(codigo="ESP-CARDIO", nombre="CUALIFICACIÓN", activo=True))
    session.commit()
    items = client.get("/configuracion/servicios").json()
    general = next(item for item in items if item["codigo"] == GENERAL)
    assert general["consultorios"][0]["id"] == office.id
    assert general["consultorios"][0]["nombre"] == "MEDICINA"
    assert general["consultorios"][0]["establecimiento_nombre"] == "SEDE DE PRUEBA"
    assert general["consultorios"][0]["consultorio_padre_id"] is None
    assert "ESP-CARDIO" not in {item["codigo"] for item in items}
    rejected = client.delete(f"/configuracion/servicios/{GENERAL}")
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["code"] == "SERVICIO_EN_USO"
    assert (
        client.patch("/configuracion/servicios/ESP-CARDIO", json={"nombre": "OTRO"}).status_code
        == 404
    )


def test_service_catalog_identifies_suboffice_by_own_name_and_site(scene):
    client, session, office, _ = scene
    child = Office(
        establecimiento_id=office.establecimiento_id,
        consultorio_padre_id=office.id,
        nombre="PEDIATRÍA 2",
        codigo="PED-2",
        servicios_codigos=[PED],
        activo=True,
    )
    session.add(child)
    session.commit()
    pediatric = next(
        item for item in client.get("/configuracion/servicios").json() if item["codigo"] == PED
    )
    suboffice = next(item for item in pediatric["consultorios"] if item["id"] == child.id)
    assert suboffice["nombre"] == "PEDIATRÍA 2"
    assert suboffice["codigo"] == "PED-2"
    assert suboffice["consultorio_padre_id"] == office.id
    assert suboffice["consultorio_padre_nombre"] == "MEDICINA"
    assert suboffice["establecimiento_nombre"] == "SEDE DE PRUEBA"


def test_three_professionals_scoped_to_service_and_legacy_inheritance_match_clinical_queries(scene):
    client, session, office, _ = scene
    path = f"/configuracion/consultorios/{office.id}/profesionales"
    for professional_id in (1, 2, 3):
        response = client.post(
            path,
            json={
                "profesional_id": professional_id,
                "fecha_inicio": START,
                "servicios_codigos": [GENERAL],
            },
        )
        assert response.status_code == 201, response.text
    assert len(client.get(path).json()) == 3
    assert client.get(path).json()[2]["profesional_nombre"] == "Profesional 3"
    child = Office(
        establecimiento_id=office.establecimiento_id,
        consultorio_padre_id=office.id,
        codigo="HIJO",
        nombre="HIJO",
        activo=True,
    )
    session.add(child)
    session.add(
        OfficeProfessional(
            consultorio_id=office.id,
            profesional_id=4,
            fecha_inicio=date(2026, 1, 1),
            es_responsable=False,
        )
    )
    session.commit()

    def professionals(service):
        return client.get(
            "/catalogos/profesionales",
            params={"consultorio_id": child.id, "servicio_codigo": service, "fecha": "2026-10-22"},
        ).json()["items"]

    assert {row["id"] for row in professionals(GENERAL)} == {1, 2, 3, 4}
    assert {row["id"] for row in professionals(PED)} == {4}
    repository = AttentionRepository(session)
    assert repository.professional_is_assigned(child, 1, date(2026, 10, 22), GENERAL)
    assert not repository.professional_is_assigned(child, 1, date(2026, 10, 22), PED)
    inherited = client.get(
        f"/configuracion/consultorios/{child.id}/profesionales",
        params={"incluir_heredados": True, "servicio_codigo": GENERAL},
    ).json()
    assert len(inherited) == 4
    assert all(row["heredada"] for row in inherited)
    assert all(row["consultorio_nombre"] == "MEDICINA" for row in inherited)
    changed = client.patch(
        f"{path}/1/{START}/servicios", json={"servicios_codigos": [GENERAL, PED]}
    )
    assert changed.status_code == 200, changed.text
    assert {row["id"] for row in professionals(PED)} == {1, 4}
    assert (
        client.patch(f"{path}/1/{START}/servicios", json={"servicios_codigos": []}).status_code
        == 422
    )
    invalid = client.post(
        path,
        json={
            "profesional_id": 2,
            "fecha_inicio": START,
            "servicios_codigos": ["ESP_NUTRICION:001"],
        },
    )
    assert invalid.status_code == 422


def test_editing_office_identity_preserves_services_assignments_and_clinical_options(scene):
    client, session, office, _ = scene
    assignments_path = f"/configuracion/consultorios/{office.id}/profesionales"
    for professional_id in (1, 2, 3):
        response = client.post(
            assignments_path,
            json={
                "profesional_id": professional_id,
                "fecha_inicio": START,
                "servicios_codigos": [GENERAL],
            },
        )
        assert response.status_code == 201, response.text
    assignments_before = client.get(assignments_path).json()

    renamed = client.patch(
        f"/configuracion/consultorios/{office.id}",
        json={"codigo": "MED-2", "nombre": "MEDICINA RENOMBRADA"},
    )
    assert renamed.status_code == 200, renamed.text
    session.expire_all()
    assert office.consultorio_padre_id is None
    assert office.area_codigo == MED
    assert office.servicios_codigos == [GENERAL, PED]
    assert client.get(assignments_path).json() == [
        {**item, "consultorio_nombre": "MEDICINA RENOMBRADA"} for item in assignments_before
    ]
    clinical_offices = client.get("/catalogos/consultorios").json()["items"]
    clinical_office = next(item for item in clinical_offices if item["id"] == office.id)
    assert clinical_office["nombre"] == "MEDICINA RENOMBRADA"
    assert {item["codigo"] for item in clinical_office["servicios_habilitados"]} == {GENERAL, PED}
    professionals = client.get(
        "/catalogos/profesionales",
        params={"consultorio_id": office.id, "servicio_codigo": GENERAL, "fecha": "2026-10-22"},
    ).json()["items"]
    assert {item["id"] for item in professionals} == {1, 2, 3}
    repository = AttentionRepository(session)
    assert repository.professional_is_assigned(office, 1, date(2026, 10, 22), GENERAL)
    assert not repository.professional_is_assigned(office, 1, date(2026, 10, 22), PED)


def test_office_reactivation_preserves_identity_and_requires_active_parent(scene):
    client, session, office, _ = scene
    child = Office(
        establecimiento_id=office.establecimiento_id,
        consultorio_padre_id=office.id,
        codigo="HIJO",
        nombre="HIJO",
        activo=False,
    )
    session.add(child)
    session.commit()
    assert client.delete(f"/configuracion/consultorios/{office.id}").status_code == 200
    assert client.post(f"/configuracion/consultorios/{child.id}/reactivar").status_code >= 400
    response = client.post(f"/configuracion/consultorios/{office.id}/reactivar")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == office.id
    assert response.json()["servicios_codigos"] == [GENERAL, PED]
    assert client.post(f"/configuracion/consultorios/{child.id}/reactivar").status_code == 200


def test_failed_audit_rolls_back_catalog_registration(scene):
    _, session, office, _ = scene
    service = CareServiceCatalog(session, audit=Mock(side_effect=RuntimeError("audit unavailable")))
    before = len(list(session.scalars(select(Specialty))))
    with pytest.raises(RuntimeError):
        service.create(CareServiceCreate(nombre="NO GUARDAR", area_codigo=MED), actor_id=7)
    assert len(list(session.scalars(select(Specialty)))) == before
    assert office.servicios_codigos == [GENERAL, PED]
    assert list(session.scalars(select(AuditLog))) == []


def test_nonadministrator_cannot_mutate_services_or_reactivate_offices(scene):
    client, _, office, app = scene
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        2, "clinical", frozenset({"PROFESIONAL"}), RolePermissionPolicy().resolve(["PROFESIONAL"])
    )
    assert client.get("/configuracion/servicios").status_code == 403
    assert (
        client.post(
            "/configuracion/servicios", json={"nombre": "NO", "area_codigo": MED}
        ).status_code
        == 403
    )
    assert client.post(f"/configuracion/consultorios/{office.id}/reactivar").status_code == 403
    assert client.get(f"/configuracion/servicios/{GENERAL}").status_code == 403
    assert (
        client.patch(
            f"/configuracion/consultorios/{office.id}/profesionales/1/{START}",
            json={
                "fecha_inicio": START,
                "fecha_fin": None,
                "es_responsable": False,
                "servicios_codigos": None,
            },
        ).status_code
        == 403
    )


def test_area_protections_cannot_be_bypassed_through_services(scene):
    from app.controllers.care_configuration import router as area_router

    client, session, office, app = scene
    app.include_router(area_router)
    assert client.delete(f"/configuracion/areas/{MED}").status_code == 409
    rejected = client.delete(f"/configuracion/servicios/{MED}")
    assert rejected.status_code == 409, rejected.text
    assert session.get(Specialty, MED).activo
    assert (
        client.patch(
            f"/configuracion/consultorios/{office.id}", json={"nombre": "Sigue editable"}
        ).status_code
        == 200
    )
    session.add(
        Specialty(codigo="ESPECIALIDADES:005", nombre="NUTRICION", activo=True, es_area=True)
    )
    session.commit()
    for path in ("areas", "servicios"):
        response = client.patch(f"/configuracion/{path}/{MED}", json={"nombre": "NUTRICION"})
        assert response.status_code == 409, response.text
    assert session.get(Specialty, MED).nombre == "MEDICINA"
    for path in ("areas", "servicios"):
        response = client.patch(f"/configuracion/{path}/{MED}", json={"nombre": "MEDICINA GENERAL"})
        assert response.status_code == 409, response.text


def test_shared_custom_area_requires_consistent_dependencies_and_can_be_restored(scene):
    from app.controllers.care_configuration import router as area_router

    client, session, office, app = scene
    app.include_router(area_router)
    code = client.post("/configuracion/areas", json={"nombre": "REHABILITACION"}).json()["codigo"]
    office.area_codigo = code
    office.especialidad_codigo = None
    office.servicios_codigos = []
    session.commit()
    for path in ("areas", "servicios"):
        assert client.delete(f"/configuracion/{path}/{code}").status_code == 409
    office.activo = False
    session.commit()
    assert client.delete(f"/configuracion/servicios/{code}").status_code == 200
    assert client.post(f"/configuracion/areas/{code}/reactivar").status_code == 200
    assert client.get(f"/configuracion/servicios/{code}").json()["activo"] is True
    assert client.get("/configuracion/servicios/NO-EXISTE").status_code == 404


def assignment_payload(**changes):
    return {
        "fecha_inicio": START,
        "fecha_fin": None,
        "es_responsable": False,
        "servicios_codigos": [GENERAL],
        **changes,
    }


def register_assignment(client, office, professional=1, **changes):
    path = f"/configuracion/consultorios/{office.id}/profesionales"
    created = client.post(
        path, json={"profesional_id": professional, **assignment_payload(**changes)}
    )
    assert created.status_code == 201, created.text
    return f"{path}/{professional}/{created.json()['fecha_inicio']}"


def test_edit_assignment_dates_responsible_and_services_keep_clinical_scope_and_audit(scene):
    client, session, office, _ = scene
    path = register_assignment(client, office)
    command = assignment_payload(
        fecha_inicio="2026-02-01", es_responsable=True, servicios_codigos=[PED]
    )
    edited = client.patch(path, json=command)
    assert edited.status_code == 200, edited.text
    assert {key: edited.json()[key] for key in command} == command
    assert session.get(OfficeProfessional, (office.id, 1, date(2026, 1, 1))) is None
    assert session.get(OfficeProfessional, (office.id, 1, date(2026, 2, 1))) is not None
    repo = AttentionRepository(session)
    assert repo.professional_is_assigned(office, 1, date(2026, 10, 22), PED)
    assert not repo.professional_is_assigned(office, 1, date(2026, 10, 22), GENERAL)
    audit = list(session.scalars(select(AuditLog)))[-1]
    assert audit.datos_anteriores["fecha_inicio"] == START
    assert audit.datos_nuevos["fecha_inicio"] == "2026-02-01"


def test_assignment_edits_reject_overlap_responsible_conflicts_and_invalid_input(scene):
    client, session, office, _ = scene
    path = register_assignment(client, office, fecha_fin="2026-01-31")
    register_assignment(client, office, fecha_inicio="2026-02-01")
    assert client.patch(path, json=assignment_payload()).status_code == 409
    register_assignment(client, office, professional=2, es_responsable=True)
    result = client.patch(
        path, json=assignment_payload(fecha_fin="2026-01-31", es_responsable=True)
    )
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "RESPONSABLE_VIGENTE_EXISTENTE"
    for command in (
        assignment_payload(fecha_fin="2025-12-31"),
        assignment_payload(servicios_codigos=[]),
        {"fecha_inicio": START},
    ):
        assert client.patch(path, json=command).status_code == 422
    assert (
        client.patch(path.replace("/1/2026", "/99/2026"), json=assignment_payload()).status_code
        == 404
    )
    assert session.get(OfficeProfessional, (office.id, 1, date(2026, 1, 1))).fecha_fin == date(
        2026, 1, 31
    )


@pytest.mark.parametrize("inherited", [False, True])
def test_date_edit_and_closure_cannot_withdraw_existing_attention_or_fua_snapshot(scene, inherited):
    client, session, office, _ = scene
    path = register_assignment(client, office)
    target = office
    if inherited:
        target = Office(
            establecimiento_id=office.establecimiento_id,
            consultorio_padre_id=office.id,
            codigo="HIJO",
            nombre="Consulta hija",
            activo=True,
        )
        session.add(target)
        session.flush()
    snapshot = {"marca": "FUA HISTORICO", "profesional": 1}
    attention = Attention(
        paciente_id=99,
        establecimiento_id=office.establecimiento_id,
        profesional_id=1,
        consultorio_id=target.id,
        especialidad_codigo=GENERAL,
        modalidad_atencion_codigo="INTRA",
        grupo_etario_codigo="ADULTO",
        fecha_atencion=datetime(2026, 10, 10, 12),
        fua_impresion=snapshot,
    )
    session.add(attention)
    session.commit()
    for command in (
        assignment_payload(fecha_inicio="2026-10-11"),
        assignment_payload(fecha_fin="2026-10-09"),
    ):
        rejected = client.patch(path, json=command)
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["error"]["code"] == "ASIGNACION_CON_ATENCIONES"
    assert client.patch(f"{path}/cierre", json={"fecha_fin": "2026-10-09"}).status_code == 409
    assert client.patch(path, json=assignment_payload(fecha_inicio="2026-02-01")).status_code == 200
    session.refresh(attention)
    assert attention.fecha_atencion == datetime(2026, 10, 10, 12)
    assert attention.fua_impresion == snapshot


def test_failed_assignment_edit_audit_rolls_back_primary_key_and_dates(scene, monkeypatch):
    from app.repositories.office import OfficeRepository

    client, session, office, _ = scene
    path = register_assignment(client, office)
    monkeypatch.setattr(OfficeRepository, "audit", Mock(side_effect=RuntimeError("audit failed")))
    with pytest.raises(RuntimeError):
        client.patch(path, json=assignment_payload(fecha_inicio="2026-02-01"))
    assert session.get(OfficeProfessional, (office.id, 1, date(2026, 1, 1))) is not None
    assert session.get(OfficeProfessional, (office.id, 1, date(2026, 2, 1))) is None


@pytest.mark.parametrize(
    "problem,expected",
    [
        ("office", "CONSULTORIO_NO_ACTIVO"),
        ("professional", "PROFESIONAL_NO_ACTIVO"),
        ("qualification", "PROFESIONAL_SIN_ESPECIALIDAD"),
        ("service", "SERVICIO_ASIGNACION_INVALIDO"),
    ],
)
def test_assignment_edit_keeps_active_context_and_staff_requirements(scene, problem, expected):
    from app.models.security import Professional

    client, session, office, _ = scene
    path = register_assignment(client, office)
    if problem == "office":
        office.activo = False
    elif problem == "professional":
        session.get(Professional, 1).activo = False
    elif problem == "qualification":
        session.delete(session.get(ProfessionalSpecialty, (1, MED)))
    session.commit()
    command = assignment_payload(
        servicios_codigos=["UNKNOWN"] if problem == "service" else [GENERAL]
    )
    response = client.patch(path, json=command)
    assert response.status_code in (404, 422), response.text
    assert response.json()["error"]["code"] == expected
    assert session.get(OfficeProfessional, (office.id, 1, date(2026, 1, 1))).fecha_fin is None
