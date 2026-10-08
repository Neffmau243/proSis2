"""Clinical document issuance (FUA, certificate, referral) against MySQL.

Document numbering is one of the few places where a race could corrupt data,
so these tests also pin the reserved-sequence format and the cross-document
invariants (an annulled encounter cannot keep valid documents).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models.catalog import Cie10, ServiceOffering, Specialty
from app.models.organization import Establishment

pytestmark = pytest.mark.integration


def _moment(days_ago: int = 1) -> str:
    return datetime.combine(date.today() - timedelta(days=days_ago), time(9, 0)).isoformat()


@pytest.fixture
def clinical_catalogs(db_session: Session) -> dict[str, str]:
    token = uuid4().hex[:6].upper()
    db_session.add(Specialty(codigo=f"E{token}", nombre=f"Medicina {token}"))
    db_session.add(ServiceOffering(codigo=f"P{token}", descripcion=f"Consulta {token}"))
    db_session.add(Cie10(codigo=f"Z{token[:3]}", descripcion=f"Diagnóstico {token}"))
    db_session.commit()
    return {"prestacion": f"P{token}"}


@pytest.fixture
def second_establishment(db_session: Session, clinic_scene) -> Establishment:
    establishment = Establishment(
        nombre=f"CS Destino {uuid4().hex[:8]}", activo=True
    )
    db_session.add(establishment)
    db_session.commit()
    return establishment


@pytest.fixture
def attention(clinic_scene, create_patient):
    """One attendable encounter registered by the scene clinician."""

    patient = create_patient(clinic_scene.professional_client)
    response = clinic_scene.professional_client.post(
        "/api/v1/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "profesional_id": clinic_scene.profesional_id,
            "consultorio_id": clinic_scene.consultorio_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": _moment(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_fua_is_issued_once_and_the_sequence_advances(
    clinic_scene, attention, create_patient, api_prefix
) -> None:
    issued = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": attention["id"]}
    )
    assert issued.status_code == 201, issued.text
    fua = issued.json()
    lote = datetime.now(ZoneInfo("America/Lima")).strftime("%y")
    assert fua["numero_fua"] == f"{clinic_scene.codigo_renaes}-{lote}-00000001"
    assert fua["codigo_renipress"] == clinic_scene.codigo_renaes
    assert fua["lote_fua"] == lote
    assert fua["correlativo_fua"] == "00000001"
    assert fua["codigo_ciudad"] is None
    assert fua["codigo_anio"] is None
    assert fua["codigo_eess"] is None
    assert fua["estado"] == "EMITIDO"
    assert fua["edad_declarada"] == str(attention["edad_anios"])
    assert fua["fecha_emision"]

    duplicated = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": attention["id"]}
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["code"] == "FUA_YA_EMITIDO"

    # A second encounter continues the per-year, per-site sequence.
    patient = create_patient(clinic_scene.professional_client)
    second = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "profesional_id": clinic_scene.profesional_id,
            "consultorio_id": clinic_scene.consultorio_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": _moment(2),
        },
    ).json()
    next_fua = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": second["id"], "observaciones": "Copia"}
    )
    assert next_fua.status_code == 201
    assert next_fua.json()["numero_fua"].endswith("00000002")
    assert next_fua.json()["correlativo_fua"] == "00000002"


def test_documents_are_limited_to_the_owning_clinician(
    clinic_scene, attention, create_professional, create_account, api_prefix
) -> None:
    outsider = create_account(profesional_id=create_professional().id)

    forbidden = outsider.client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": attention["id"]}
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PROFESIONAL_DISTINTO_AL_USUARIO"

    # ADMIN holds no FUA permission at all.
    admin_attempt = clinic_scene.admin_client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": attention["id"]}
    )
    assert admin_attempt.status_code == 403
    assert admin_attempt.json()["error"]["details"]["required_permissions"] == ["FUA_EMITIR"]

    missing = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": 999999999}
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ATENCION_NO_ENCONTRADA"


def test_annulled_encounter_cannot_receive_or_keep_documents(
    clinic_scene, attention, api_prefix
) -> None:
    issued = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/fua", json={"atencion_id": attention["id"]}
    )
    assert issued.status_code == 201

    # With a valid FUA in place the encounter cannot be cancelled silently.
    cancellation = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/{attention['id']}/anulacion",
        json={"observaciones": "Anulación con documentos vigentes"},
    )
    assert cancellation.status_code == 422
    assert cancellation.json()["error"]["code"] == "ATENCION_CON_DOCUMENTOS_VIGENTES"


def test_certificate_requires_the_attending_professional_and_active_services(
    clinic_scene, attention, clinical_catalogs: dict[str, str], create_professional, api_prefix
) -> None:
    issued = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/certificados",
        json={
            "atencion_id": attention["id"],
            "tipo": "CERTIFICADO_ATENCION",
            "prestaciones": [clinical_catalogs["prestacion"]],
        },
    )
    assert issued.status_code == 201, issued.text
    certificate = issued.json()
    assert certificate["atencion_id"] == attention["id"]
    assert certificate["profesional_id"] == clinic_scene.profesional_id
    assert certificate["establecimiento_id"] == clinic_scene.establecimiento_id
    assert certificate["numero_certificado"].startswith("CERT-")
    assert certificate["tipo"] == "CERTIFICADO_ATENCION"
    assert certificate["prestaciones"] == [clinical_catalogs["prestacion"]]
    assert certificate["estado"]

    other_professional = create_professional()
    co_signed = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/certificados",
        json={
            "atencion_id": attention["id"],
            "tipo": "CERTIFICADO_ATENCION",
            "profesional_id": other_professional.id,
        },
    )
    assert co_signed.status_code == 422
    assert co_signed.json()["error"]["code"] == "CERTIFICADO_PROFESIONAL_DISTINTO_ATENCION"

    unknown_service = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/certificados",
        json={
            "atencion_id": attention["id"],
            "tipo": "CERTIFICADO_ATENCION",
            "prestaciones": ["NO-EXISTE"],
        },
    )
    assert unknown_service.status_code == 404
    assert unknown_service.json()["error"]["code"] == "PRESTACION_NO_ACTIVA"

    missing_type = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/certificados", json={"atencion_id": attention["id"]}
    )
    assert missing_type.status_code == 422


def test_referral_validates_the_destination_and_numbers_the_document(
    clinic_scene, attention, second_establishment: Establishment, api_prefix
) -> None:
    same_site = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/referencias",
        json={
            "atencion_id": attention["id"],
            "tipo": "TRANSFERENCIA",
            "establecimiento_destino_id": clinic_scene.establecimiento_id,
            "motivo": "Referencia a la misma sede",
        },
    )
    assert same_site.status_code == 422
    assert same_site.json()["error"]["code"] == "REFERENCIA_MISMA_SEDE"

    unknown_destination = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/referencias",
        json={
            "atencion_id": attention["id"],
            "tipo": "TRANSFERENCIA",
            "establecimiento_destino_id": 999999999,
            "motivo": "Destino inexistente",
        },
    )
    assert unknown_destination.status_code == 404
    assert unknown_destination.json()["error"]["code"] == "ESTABLECIMIENTO_DESTINO_NO_ACTIVO"

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/documentos/referencias",
        json={
            "atencion_id": attention["id"],
            "tipo": "TRANSFERENCIA",
            "establecimiento_destino_id": second_establishment.id,
            "motivo": "Requiere evaluación por especialista",
            "observaciones": "Paciente estable",
        },
    )
    assert created.status_code == 201, created.text
    referral = created.json()
    assert referral["establecimiento_origen_id"] == clinic_scene.establecimiento_id
    assert referral["establecimiento_destino_id"] == second_establishment.id
    assert referral["numero_referencia"].startswith("REF-")
    assert referral["estado"] == "PENDIENTE"
    assert referral["motivo"] == "Requiere evaluación por especialista"


def test_document_payloads_validate_required_fields(clinic_scene, attention, api_prefix) -> None:
    client = clinic_scene.professional_client
    invalid_payloads = [
        (f"{api_prefix}/documentos/fua", {}),
        (f"{api_prefix}/documentos/fua", {"atencion_id": 0}),
        (f"{api_prefix}/documentos/certificados", {"atencion_id": attention["id"], "tipo": ""}),
        (
            f"{api_prefix}/documentos/referencias",
            {
                "atencion_id": attention["id"],
                "tipo": "TRANSFERENCIA",
                "establecimiento_destino_id": clinic_scene.establecimiento_id,
            },
        ),
    ]
    for path, payload in invalid_payloads:
        response = client.post(path, json=payload)
        assert response.status_code == 422, (path, payload, response.text)
        assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
