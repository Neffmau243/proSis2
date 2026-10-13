"""Administrative endpoints: offices, staff assignments and age-group ranges."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import AgeGroup, Profession, Specialty
from app.models.organization import Office, OfficeProfessional
from app.models.security import ProfessionalSpecialty

pytestmark = pytest.mark.integration


def test_office_crud_is_administrative_and_audited(
    clinic_scene, db_session: Session, api_prefix
) -> None:
    code = f"C{uuid4().hex[:6].upper()}"
    created = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": code,
            "nombre": "Consultorio de prueba",
        },
    )
    assert created.status_code == 201, created.text
    office = created.json()
    assert office["activo"] is True
    assert office["codigo"] == code

    duplicated = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": code,
            "nombre": "Duplicado",
        },
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["code"] == "CONSULTORIO_EN_CONFLICTO"

    fetched = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/consultorios/{office['id']}"
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == office["id"]

    listed = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/consultorios",
        params={"establecimiento_id": clinic_scene.establecimiento_id},
    )
    assert listed.status_code == 200
    assert office["id"] in [item["id"] for item in listed.json()]

    updated = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/consultorios/{office['id']}",
        json={"nombre": "Consultorio renombrado"},
    )
    assert updated.status_code == 200
    assert updated.json()["nombre"] == "Consultorio renombrado"

    relative = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": f"H{uuid4().hex[:6].upper()}",
            "nombre": "Consultorio hijo",
            "consultorio_padre_id": office["id"],
        },
    )
    assert relative.status_code == 201

    cyclic = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/consultorios/{office['id']}",
        json={"consultorio_padre_id": relative.json()["id"]},
    )
    assert cyclic.status_code == 422
    assert cyclic.json()["error"]["code"] == "JERARQUIA_CONSULTORIO_CICLICA"

    blocked = clinic_scene.admin_client.delete(
        f"{api_prefix}/configuracion/consultorios/{office['id']}"
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "CONSULTORIO_CON_HIJOS_ACTIVOS"
    closed_child = clinic_scene.admin_client.delete(
        f"{api_prefix}/configuracion/consultorios/{relative.json()['id']}"
    )
    assert closed_child.status_code == 200
    deactivated = clinic_scene.admin_client.delete(
        f"{api_prefix}/configuracion/consultorios/{office['id']}"
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["activo"] is False

    again = clinic_scene.admin_client.delete(
        f"{api_prefix}/configuracion/consultorios/{office['id']}"
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "CONSULTORIO_YA_INACTIVO"

    missing = clinic_scene.admin_client.get(f"{api_prefix}/configuracion/consultorios/999999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONSULTORIO_NO_ENCONTRADO"


def test_office_administration_requires_the_administrative_permission(
    clinic_scene, api_prefix
) -> None:
    response = clinic_scene.professional_client.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": f"X{uuid4().hex[:6].upper()}",
            "nombre": "No permitido",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"


def test_staff_assignment_lifecycle(clinic_scene, create_professional, db_session: Session, api_prefix) -> None:
    office = Office(
        establecimiento_id=clinic_scene.establecimiento_id,
        codigo=f"A{uuid4().hex[:6].upper()}",
        nombre="Consultorio de asignaciones",
        activo=True,
    )
    db_session.add(office)
    db_session.commit()
    professional = create_professional()

    started = date.today() - timedelta(days=5)
    assigned = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios/{office.id}/profesionales",
        json={
            "profesional_id": professional.id,
            "fecha_inicio": started.isoformat(),
            "es_responsable": True,
        },
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["profesional_id"] == professional.id
    assert assigned.json()["es_responsable"] is True

    duplicated = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios/{office.id}/profesionales",
        json={"profesional_id": professional.id, "fecha_inicio": started.isoformat()},
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["code"] == "ASIGNACION_DUPLICADA"

    listed = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/consultorios/{office.id}/profesionales"
    )
    assert listed.status_code == 200
    assert [item["profesional_id"] for item in listed.json()] == [professional.id]

    closed = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/consultorios/{office.id}/profesionales/"
        f"{professional.id}/{started.isoformat()}/cierre",
        json={"fecha_fin": date.today().isoformat()},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["fecha_fin"] == date.today().isoformat()

    widened = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/consultorios/{office.id}/profesionales/"
        f"{professional.id}/{started.isoformat()}/cierre",
        json={"fecha_fin": (date.today() + timedelta(days=30)).isoformat()},
    )
    assert widened.status_code == 422, widened.text
    assert widened.json()["error"]["code"] == "CIERRE_AMPLIA_VIGENCIA"

    unknown_assignment = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/consultorios/{office.id}/profesionales/"
        f"{professional.id}/2020-01-01/cierre",
        json={"fecha_fin": date.today().isoformat()},
    )
    assert unknown_assignment.status_code == 404
    assert unknown_assignment.json()["error"]["code"] == "ASIGNACION_NO_ENCONTRADA"


def test_professional_crud_and_specialties(
    clinic_scene, db_session: Session, api_prefix
) -> None:
    token = uuid4().hex[:6].upper()
    created = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/profesionales",
        json={
            "nombre_completo": f"Profesional Nuevo {token}",
            "numero_documento": str(uuid4().int)[:8],
            "colegiatura": f"CMP-{token}",
        },
    )
    assert created.status_code == 201, created.text
    professional = created.json()
    assert professional["activo"] is True
    assert professional["especialidades"] == []

    listed = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/profesionales", params={"incluir_inactivos": True}
    )
    assert listed.status_code == 200
    assert professional["id"] in [item["id"] for item in listed.json()]

    fetched = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/profesionales/{professional['id']}"
    )
    assert fetched.status_code == 200

    updated = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/profesionales/{professional['id']}",
        json={"colegiatura": f"CMP-{token}-2"},
    )
    assert updated.status_code == 200
    assert updated.json()["colegiatura"] == f"CMP-{token}-2"

    unknown_specialty = clinic_scene.admin_client.put(
        f"{api_prefix}/configuracion/profesionales/{professional['id']}/especialidades",
        json={"especialidades": [{"especialidad_codigo": "NO-EXISTE", "es_principal": True}]},
    )
    assert unknown_specialty.status_code == 404, unknown_specialty.text
    assert unknown_specialty.json()["error"]["code"] == "ESPECIALIDAD_NO_ACTIVA"

    deactivated = clinic_scene.admin_client.delete(
        f"{api_prefix}/configuracion/profesionales/{professional['id']}"
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["activo"] is False

    again = clinic_scene.admin_client.delete(
        f"{api_prefix}/configuracion/profesionales/{professional['id']}"
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "PROFESIONAL_YA_INACTIVO"

    missing = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/profesionales/999999999"
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROFESIONAL_NO_ENCONTRADO"


def test_professional_specialties_are_replaced_atomically(
    clinic_scene, create_professional, db_session: Session, api_prefix
) -> None:
    token = uuid4().hex[:6].upper()
    required = Specialty(
        codigo=f"REQ-{token}", nombre=f"Especialidad requerida {token}", activo=True
    )
    optional = Specialty(
        codigo=f"OPT-{token}", nombre=f"Especialidad opcional {token}", activo=True
    )
    db_session.add_all([required, optional])
    db_session.commit()
    professional = create_professional()
    endpoint = f"{api_prefix}/configuracion/profesionales/{professional.id}/especialidades"

    assigned = clinic_scene.admin_client.put(
        endpoint,
        json={
            "especialidades": [
                {"especialidad_codigo": required.codigo, "es_principal": True}
            ]
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["especialidades"] == [
        {"especialidad_codigo": required.codigo, "es_principal": True}
    ]

    # The whole set is replaced, so the previous principal flag is not kept.
    replaced = clinic_scene.admin_client.put(
        endpoint,
        json={
            "especialidades": [
                {"especialidad_codigo": required.codigo, "es_principal": False},
                {"especialidad_codigo": optional.codigo, "es_principal": True},
            ]
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert sorted(
        item["especialidad_codigo"] for item in replaced.json()["especialidades"]
    ) == sorted([required.codigo, optional.codigo])
    stored = db_session.scalars(
        select(ProfessionalSpecialty).where(
            ProfessionalSpecialty.profesional_id == professional.id
        )
    ).all()
    assert len(stored) == 2

    # An open assignment of an office that needs the specialty protects it.
    office = Office(
        establecimiento_id=clinic_scene.establecimiento_id,
        codigo=f"E{uuid4().hex[:6].upper()}",
        nombre="Consultorio especializado",
        especialidad_codigo=required.codigo,
        activo=True,
    )
    db_session.add(office)
    db_session.flush()
    assignment = OfficeProfessional(
        consultorio_id=office.id,
        profesional_id=professional.id,
        fecha_inicio=date.today() - timedelta(days=1),
        es_responsable=True,
    )
    db_session.add(assignment)
    db_session.commit()

    blocked = clinic_scene.admin_client.put(
        endpoint,
        json={
            "especialidades": [
                {"especialidad_codigo": optional.codigo, "es_principal": True}
            ]
        },
    )
    assert blocked.status_code == 422, blocked.text
    error = blocked.json()["error"]
    assert error["code"] == "ESPECIALIDAD_REQUERIDA_POR_ASIGNACION"
    assert required.codigo in error["message"]

    # Closing the assignment releases the specialty.
    assignment.fecha_fin = date.today() - timedelta(days=1)
    db_session.commit()

    released = clinic_scene.admin_client.put(
        endpoint,
        json={
            "especialidades": [
                {"especialidad_codigo": optional.codigo, "es_principal": True}
            ]
        },
    )
    assert released.status_code == 200, released.text
    assert released.json()["especialidades"] == [
        {"especialidad_codigo": optional.codigo, "es_principal": True}
    ]

    # An empty list is a valid way to clear the set.
    cleared = clinic_scene.admin_client.put(endpoint, json={"especialidades": []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["especialidades"] == []


def test_professional_updates_validate_the_profession_and_report_conflicts(
    clinic_scene, create_professional, db_session: Session, api_prefix
) -> None:
    token = uuid4().hex[:6].upper()
    active_profession = Profession(nombre=f"Medicina {token}", activo=True)
    inactive_profession = Profession(nombre=f"Retirada {token}", activo=False)
    db_session.add_all([active_profession, inactive_profession])
    db_session.commit()

    professional = create_professional()
    other = create_professional(numero_documento=f"DOC{token}")
    endpoint = f"{api_prefix}/configuracion/profesionales/{professional.id}"

    assigned = clinic_scene.admin_client.patch(
        endpoint, json={"profesion_id": active_profession.id}
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["profesion_id"] == active_profession.id

    retired = clinic_scene.admin_client.patch(
        endpoint, json={"profesion_id": inactive_profession.id}
    )
    assert retired.status_code == 404, retired.text
    assert retired.json()["error"]["code"] == "PROFESION_NO_ACTIVA"

    unknown_profession = clinic_scene.admin_client.patch(
        endpoint, json={"profesion_id": 999999999}
    )
    assert unknown_profession.status_code == 404
    assert unknown_profession.json()["error"]["code"] == "PROFESION_NO_ACTIVA"

    # The unique document of another professional must not be reusable.
    conflicted = clinic_scene.admin_client.patch(
        endpoint, json={"numero_documento": other.numero_documento}
    )
    assert conflicted.status_code == 409, conflicted.text
    assert conflicted.json()["error"]["code"] == "PROFESIONAL_EN_CONFLICTO"

    duplicated_document = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/profesionales",
        json={
            "nombre_completo": f"Profesional Clon {token}",
            "numero_documento": other.numero_documento,
        },
    )
    assert duplicated_document.status_code == 409, duplicated_document.text
    assert duplicated_document.json()["error"]["code"] == "PROFESIONAL_EN_CONFLICTO"

    unknown_professional = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/profesionales/999999999",
        json={"nombre_completo": "Nadie"},
    )
    assert unknown_professional.status_code == 404
    assert unknown_professional.json()["error"]["code"] == "PROFESIONAL_NO_ENCONTRADO"

    unknown_specialty_professional = clinic_scene.admin_client.put(
        f"{api_prefix}/configuracion/profesionales/999999999/especialidades",
        json={"especialidades": []},
    )
    assert unknown_specialty_professional.status_code == 404
    assert unknown_specialty_professional.json()["error"]["code"] == "PROFESIONAL_NO_ENCONTRADO"


def _range_payload(item: dict) -> dict:
    return {
        "codigo": item["codigo"],
        "edad_minima_meses": item["edad_minima_meses"],
        "edad_maxima_meses": item["edad_maxima_meses"],
        "activo": item["activo"],
    }


def test_age_group_configuration_requires_every_group_and_rejects_overlaps(
    clinic_scene, api_prefix
) -> None:
    listed = clinic_scene.admin_client.get(f"{api_prefix}/configuracion/grupos-etarios")
    assert listed.status_code == 200
    assert listed.json(), "Las migraciones siembran rangos etarios iniciales"
    original = [_range_payload(item) for item in listed.json()]

    unknown_group = clinic_scene.admin_client.put(
        f"{api_prefix}/configuracion/grupos-etarios",
        json={"grupos": [{"codigo": "INVENTADO", "edad_minima_meses": 0}]},
    )
    assert unknown_group.status_code == 404
    assert unknown_group.json()["error"]["code"] == "GRUPO_ETARIO_NO_ENCONTRADO"

    # Every existing group must be part of one atomic reconfiguration.
    incomplete = clinic_scene.admin_client.put(
        f"{api_prefix}/configuracion/grupos-etarios",
        json={
            "grupos": [{"codigo": original[0]["codigo"], "edad_minima_meses": 0}],
            "exigir_cobertura_continua": True,
        },
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["error"]["code"] == "CONFIGURACION_GRUPOS_INCOMPLETA"

    try:
        ordered = sorted(
            original, key=lambda item: item["edad_minima_meses"] if item["edad_minima_meses"] is not None else -1
        )
        overlapping_payload = [dict(item) for item in ordered]
        overlapping_payload[1]["edad_minima_meses"] = overlapping_payload[0]["edad_maxima_meses"]
        overlapping = clinic_scene.admin_client.put(
            f"{api_prefix}/configuracion/grupos-etarios",
            json={"grupos": overlapping_payload, "exigir_cobertura_continua": False},
        )
        assert overlapping.status_code == 422
        assert overlapping.json()["error"]["code"] == "RANGOS_ETARIOS_SUPERPUESTOS"

        # Re-sending the current configuration is idempotent and valid.
        idempotent = clinic_scene.admin_client.put(
            f"{api_prefix}/configuracion/grupos-etarios",
            json={"grupos": original, "exigir_cobertura_continua": False},
        )
        assert idempotent.status_code == 200, idempotent.text
        assert all("rango_edad_legible" in item for item in idempotent.json())

        # Disabling the oldest group lets the previous one stay open-ended:
        # only one active group without a maximum is allowed.
        reconfigured = [dict(item) for item in ordered]
        reconfigured[-1]["activo"] = False
        reconfigured[-2]["edad_maxima_meses"] = None
        accepted = clinic_scene.admin_client.put(
            f"{api_prefix}/configuracion/grupos-etarios",
            json={"grupos": reconfigured, "exigir_cobertura_continua": False},
        )
        assert accepted.status_code == 200, accepted.text
        assert all("rango_edad_legible" in item for item in accepted.json())
    finally:
        restored = clinic_scene.admin_client.put(
            f"{api_prefix}/configuracion/grupos-etarios",
            json={"grupos": original, "exigir_cobertura_continua": False},
        )
        assert restored.status_code == 200, restored.text


def test_age_group_configuration_is_admin_only(clinic_scene, api_prefix) -> None:
    response = clinic_scene.professional_client.get(f"{api_prefix}/configuracion/grupos-etarios")

    assert response.status_code == 403
    assert response.json()["error"]["details"]["required_permissions"] == [
        "GRUPO_ETARIO_CONFIGURAR"
    ]


def test_age_group_ranges_survive_a_reconfiguration(
    clinic_scene, db_session: Session, api_prefix
) -> None:
    listed = clinic_scene.admin_client.get(f"{api_prefix}/configuracion/grupos-etarios").json()
    assert {item["codigo"] for item in listed} >= {"NINO", "ADULTO"}
    stored = db_session.scalars(select(AgeGroup)).all()
    assert {group.codigo for group in stored} >= {"NINO", "ADULTO"}
