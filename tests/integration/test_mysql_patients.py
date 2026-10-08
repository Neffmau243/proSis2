"""Patient registration rules exercised through HTTP against MySQL.

The patient aggregate concentrates most of the business rules of the system
(identity uniqueness, minor guardianship, risk periods, clinical scope), so
these tests assert the domain codes the frontend relies on.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.patient import Patient, PatientResponsible

pytestmark = pytest.mark.integration


def _document() -> str:
    return str(uuid4().int)[:8]


def _error(response) -> dict:
    return response.json()["error"]


def test_professional_registers_a_patient_with_derived_data(
    clinic_scene, db_session: Session, create_patient, api_prefix
) -> None:
    document = _document()
    patient = create_patient(
        clinic_scene.professional_client,
        numero_documento=document,
        ubigeo_residencia_codigo=clinic_scene.ubigeo_codigo,
        establecimiento_registro_id=clinic_scene.establecimiento_id,
        localidad="PUEBLO JOVEN",
        telefono_principal="999888777",
    )

    assert patient["numero_documento"] == document
    assert patient["estado"] is True
    assert patient["distrito_residencia"] == "CERCADO"
    assert patient["responsables"] == []
    assert patient["riesgos"] == []
    assert patient["created_at"] and patient["updated_at"]

    # The registration professional is derived from the authenticated clinician.
    stored = db_session.get(Patient, patient["id"])
    assert stored is not None
    assert stored.profesional_registro_id == clinic_scene.profesional_id

    audit = db_session.scalars(
        select(AuditLog).where(
            AuditLog.tabla_nombre == "pacientes",
            AuditLog.registro_id == patient["id"],
        )
    ).all()
    assert [record.accion for record in audit] == ["INSERT"]
    assert audit[0].usuario_id == clinic_scene.professional_user_id


def test_personal_and_family_histories_persist_and_update_together(
    clinic_scene, db_session: Session, create_patient, api_prefix
) -> None:
    """The two histories are distinct patient fields throughout the HTTP flow."""

    token = uuid4().hex[:8].upper()
    created = create_patient(
        clinic_scene.professional_client,
        historia_clinica=f"HC-{token}",
        historia_familiar=f"HF-VERDE-{token}",
    )
    assert created["historia_clinica"] == f"HC-{token}"
    assert created["historia_familiar"] == f"HF-VERDE-{token}"

    stored = db_session.get(Patient, created["id"])
    assert stored is not None
    assert stored.historia_clinica == f"HC-{token}"
    assert stored.historia_familiar == f"HF-VERDE-{token}"

    updated = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{created['id']}",
        json={
            "historia_clinica": f"HC-ACTUALIZADA-{token}",
            "historia_familiar": f"HF-AZUL-{token}",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["historia_clinica"] == f"HC-ACTUALIZADA-{token}"
    assert updated.json()["historia_familiar"] == f"HF-AZUL-{token}"

    reread = clinic_scene.professional_client.get(f"{api_prefix}/patients/{created['id']}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["historia_clinica"] == f"HC-ACTUALIZADA-{token}"
    assert reread.json()["historia_familiar"] == f"HF-AZUL-{token}"

    db_session.refresh(stored)
    assert stored.historia_clinica == f"HC-ACTUALIZADA-{token}"
    assert stored.historia_familiar == f"HF-AZUL-{token}"


def test_administrator_keeps_break_glass_read_access(
    clinic_scene, create_patient, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)

    response = clinic_scene.admin_client.get(f"{api_prefix}/patients/{patient['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == patient["id"]


def test_registration_rejects_duplicate_documents_and_invalid_dates(
    clinic_scene, create_patient, api_prefix
) -> None:
    document = _document()
    create_patient(clinic_scene.professional_client, numero_documento=document)

    duplicate = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": document,
            "fecha_nacimiento": "1990-05-10",
        },
    )
    assert duplicate.status_code == 409
    assert _error(duplicate)["code"] == "DOCUMENTO_PACIENTE_DUPLICADO"

    future_birth = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": (date.today() + timedelta(days=30)).isoformat(),
        },
    )
    assert future_birth.status_code == 422
    assert _error(future_birth)["code"] == "FECHA_NACIMIENTO_FUTURA"

    birth_after_registration = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "2025-06-01",
            "fecha_inscripcion": "2025-01-01",
        },
    )
    assert birth_after_registration.status_code == 422
    assert _error(birth_after_registration)["code"] == "FECHA_NACIMIENTO_POSTERIOR_A_INSCRIPCION"


def test_registration_rejects_unknown_catalogs(clinic_scene, api_prefix) -> None:
    unknown_document = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "XXX",
            "numero_documento": _document(),
            "fecha_nacimiento": "1990-05-10",
        },
    )
    assert unknown_document.status_code == 422
    assert _error(unknown_document)["code"] == "CATALOGO_NO_DISPONIBLE"
    assert _error(unknown_document)["details"]["catalogo"] == "tipo de documento"
    assert _error(unknown_document)["details"]["valor"] == "XXX"

    unknown_sex = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "1990-05-10",
            "sexo_codigo": "Z",
        },
    )
    assert unknown_sex.status_code == 422
    assert _error(unknown_sex)["details"]["catalogo"] == "sexo"

    unknown_establishment = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "1990-05-10",
            "establecimiento_registro_id": 999999999,
        },
    )
    assert unknown_establishment.status_code == 422
    assert _error(unknown_establishment)["details"]["catalogo"] == "establecimiento"

    locality_without_district = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "1990-05-10",
            "localidad": "PUEBLO JOVEN",
        },
    )
    assert locality_without_district.status_code == 422
    assert _error(locality_without_district)["code"] == "LOCALIDAD_SIN_DISTRITO"


def test_minor_patient_requires_an_active_responsible(
    clinic_scene, db_session: Session, api_prefix
) -> None:
    without_responsible = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "2020-05-10",
        },
    )
    assert without_responsible.status_code == 422
    assert _error(without_responsible)["code"] == "MENOR_SIN_RESPONSABLE"

    with_responsible = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "2020-05-10",
            "responsables": [
                {
                    "parentesco": "MADRE",
                    "nombre_completo": "Rosa Mamani",
                    "tipo_documento_codigo": "DNI",
                    "numero_documento": _document(),
                    "es_principal": True,
                }
            ],
        },
    )
    assert with_responsible.status_code == 201, with_responsible.text
    body = with_responsible.json()
    persisted = db_session.scalars(
        select(PatientResponsible).where(PatientResponsible.paciente_id == body["id"])
    ).all()
    assert len(persisted) == 1, [row.id for row in persisted]
    assert len(body["responsables"]) == 1, body["responsables"]
    assert body["responsables"][0]["parentesco"] == "MADRE"
    assert body["responsables"][0]["es_principal"] is True
    assert body["responsables"][0]["activo"] is True

    two_principals = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "fecha_nacimiento": "2020-05-10",
            "responsables": [
                {"parentesco": "MADRE", "nombre_completo": "Rosa Mamani", "es_principal": True},
                {"parentesco": "PADRE", "nombre_completo": "Luis Quispe", "es_principal": True},
            ],
        },
    )
    assert two_principals.status_code == 422
    assert _error(two_principals)["code"] == "RESPONSABLE_PRINCIPAL_DUPLICADO"


def test_responsible_lifecycle_and_validation(clinic_scene, create_patient, api_prefix) -> None:
    patient = create_patient(clinic_scene.professional_client)

    # The contract already refuses half a document, so the service rule is
    # unreachable through HTTP and the schema is the single source of truth.
    incomplete_document = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/responsibles",
        json={
            "parentesco": "TUTOR",
            "nombre_completo": "Tutor Sin Tipo",
            "numero_documento": "12345678",
        },
    )
    assert incomplete_document.status_code == 422
    assert _error(incomplete_document)["code"] == "REQUEST_VALIDATION_ERROR"

    unknown_document_type = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/responsibles",
        json={
            "parentesco": "TUTOR",
            "nombre_completo": "Tutor Sin Tipo",
            "tipo_documento_codigo": "XXX",
            "numero_documento": "12345678",
        },
    )
    assert unknown_document_type.status_code == 422
    assert _error(unknown_document_type)["code"] == "CATALOGO_NO_DISPONIBLE"

    invalid_relationship = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/responsibles",
        json={"parentesco": "HERMANO", "nombre_completo": "Hermano Mayor"},
    )
    assert invalid_relationship.status_code == 422
    assert _error(invalid_relationship)["code"] == "REQUEST_VALIDATION_ERROR"

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/responsibles",
        json={
            "parentesco": "MADRE",
            "nombre_completo": "Rosa Mamani Quispe",
            "tipo_documento_codigo": "DNI",
            "numero_documento": _document(),
            "es_principal": True,
            "telefono": "988777666",
        },
    )
    assert created.status_code == 201, created.text
    responsible = created.json()
    assert responsible["activo"] is True

    second_principal = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/responsibles",
        json={"parentesco": "PADRE", "nombre_completo": "Luis Quispe", "es_principal": True},
    )
    assert second_principal.status_code == 422
    assert _error(second_principal)["code"] == "RESPONSABLE_PRINCIPAL_DUPLICADO"

    updated = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}/responsibles/{responsible['id']}",
        json={"telefono": "900111222", "activo": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["telefono"] == "900111222"
    assert updated.json()["activo"] is False

    # Repeating the same value is a valid request; omitting every modifiable
    # field is not.
    repeated = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}/responsibles/{responsible['id']}",
        json={"telefono": "900111222"},
    )
    assert repeated.status_code == 200

    empty = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}/responsibles/{responsible['id']}",
        json={},
    )
    assert empty.status_code == 422
    assert _error(empty)["code"] == "ACTUALIZACION_SIN_CAMBIOS"

    missing = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}/responsibles/999999999",
        json={"telefono": "900333444"},
    )
    assert missing.status_code == 404
    assert _error(missing)["code"] == "RESPONSABLE_NO_ENCONTRADO"


def test_risk_group_lifecycle_and_period_rules(
    clinic_scene, create_patient, create_risk_group, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)
    group = create_risk_group()

    unknown_group = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/risk-groups",
        json={"grupo_riesgo_id": 999999999, "fecha_inicio": "2026-01-01"},
    )
    assert unknown_group.status_code == 422
    assert _error(unknown_group)["details"]["catalogo"] == "grupo de riesgo"

    invalid_period = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/risk-groups",
        json={
            "grupo_riesgo_id": group.id,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-02-01",
        },
    )
    assert invalid_period.status_code == 422
    assert _error(invalid_period)["code"] == "PERIODO_RIESGO_INVALIDO"

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/risk-groups",
        json={
            "grupo_riesgo_id": group.id,
            "fecha_inicio": "2026-01-01",
            "observacion": "Control mensual",
        },
    )
    assert created.status_code == 201, created.text
    risk = created.json()
    assert risk["grupo_riesgo_id"] == group.id
    assert risk["grupo_riesgo_codigo"] == group.codigo
    assert risk["fecha_fin"] is None

    overlapping = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/risk-groups",
        json={"grupo_riesgo_id": group.id, "fecha_inicio": "2026-02-01"},
    )
    assert overlapping.status_code == 422
    assert _error(overlapping)["code"] == "RIESGO_SUPERPUESTO"

    closed = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}/risk-groups/{group.id}/2026-01-01",
        json={"fecha_fin": "2026-06-30", "observacion": "Alta del programa"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["fecha_fin"] == "2026-06-30"

    missing = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}/risk-groups/{group.id}/2020-01-01",
        json={"observacion": "No existe"},
    )
    assert missing.status_code == 404
    assert _error(missing)["code"] == "RIESGO_NO_ENCONTRADO"


def test_editing_requires_a_real_change_and_valid_residence(
    clinic_scene, create_patient, api_prefix
) -> None:
    patient = create_patient(
        clinic_scene.professional_client,
        ubigeo_residencia_codigo=clinic_scene.ubigeo_codigo,
        localidad="CENTRO",
        direccion="Av. Siempre Viva 100",
    )

    repeated = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={"primer_nombre": "Ana", "localidad": "CENTRO"},
    )
    assert repeated.status_code == 200

    empty = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}", json={}
    )
    assert empty.status_code == 422
    assert _error(empty)["code"] == "ACTUALIZACION_SIN_CAMBIOS"

    extra_field = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={"estado": False},
    )
    assert extra_field.status_code == 422
    assert _error(extra_field)["code"] == "REQUEST_VALIDATION_ERROR"

    locality_as_ubigeo = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={"localidad": clinic_scene.ubigeo_codigo},
    )
    assert locality_as_ubigeo.status_code == 422
    assert _error(locality_as_ubigeo)["code"] == "LOCALIDAD_NO_PUEDE_SER_CODIGO_UBIGEO"

    updated = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={"primer_nombre": "Anabel", "localidad": None, "direccion": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["primer_nombre"] == "Anabel"
    assert updated.json()["localidad"] is None
    assert updated.json()["direccion"] is None

    missing = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/999999999", json={"primer_nombre": "Nadie"}
    )
    assert missing.status_code == 404
    assert _error(missing)["code"] == "PACIENTE_NO_ENCONTRADO"


def test_deactivation_is_logical_for_the_professional_who_admits(
    clinic_scene, create_patient, db_session: Session, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)

    # El profesional que admite al paciente puede revertir una admisión
    # equivocada; la baja sigue siendo lógica y auditada.
    deactivated = clinic_scene.professional_client.delete(
        f"{api_prefix}/patients/{patient['id']}"
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["estado"] is False
    assert "baja" in deactivated.json()["mensaje"].lower()

    # The row survives: the operation is logical, not physical.
    stored = db_session.get(Patient, patient["id"])
    assert stored is not None
    assert stored.estado is False
    assert (
        db_session.scalars(
            select(AuditLog.accion).where(
                AuditLog.tabla_nombre == "pacientes",
                AuditLog.registro_id == patient["id"],
            )
        ).all()
        == ["INSERT", "DEACTIVATE"]
    )

    assert (
        clinic_scene.professional_client.get(f"{api_prefix}/patients/{patient['id']}").status_code
        == 404
    )

    already_inactive = clinic_scene.professional_client.delete(
        f"{api_prefix}/patients/{patient['id']}"
    )
    assert already_inactive.status_code == 404


def test_patient_access_requires_a_care_relationship(
    clinic_scene, create_patient, create_professional, create_account, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client, numero_documento=_document())

    unassigned = create_professional()
    intruder = create_account(profesional_id=unassigned.id)

    read_attempt = intruder.client.get(f"{api_prefix}/patients/{patient['id']}")
    assert read_attempt.status_code == 403
    assert _error(read_attempt)["code"] == "PACIENTE_FUERA_DE_AMBITO"

    write_attempt = intruder.client.patch(
        f"{api_prefix}/patients/{patient['id']}", json={"primer_nombre": "Intruso"}
    )
    assert write_attempt.status_code == 403

    # The document must not leak through discovery either.
    search = intruder.client.get(
        f"{api_prefix}/patients", params={"q": patient["numero_documento"]}
    )
    assert search.status_code == 200
    assert search.json()["items"] == []
    assert search.json()["total"] == 0

    # The clinician who registered it keeps access.
    owner_read = clinic_scene.professional_client.get(f"{api_prefix}/patients/{patient['id']}")
    assert owner_read.status_code == 200
