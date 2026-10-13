"""Clinical attention lifecycle (create, read, cancel, search) over MySQL.

These tests protect the rules that make an encounter attributable: a linked
PROFESIONAL records it, the selected clinician must be assigned to the site and
office, and every derived value is computed server-side.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Cie10, Insurance, ServiceOffering, Specialty
from app.models.clinical import Attention
from app.models.organization import Office, OfficeProfessional
from app.models.patient import Patient

pytestmark = pytest.mark.integration


def _moment(days_ago: int = 1) -> str:
    return datetime.combine(date.today() - timedelta(days=days_ago), time(9, 30)).isoformat()


#: One real row as produced by the legacy ETL for a "S.I.S. SIS Para Todos"
#: affiliate.  Access stores the affiliation in three separate columns, so the
#: paper FUA keeps the DIRESA in its own box instead of gluing it to the number.
#: ``historia_clinica`` repeats the document and ``historia_familiar`` carries a
#: code instead of free text: both are legacy shapes the API must accept, not fix.
LEGACY_SIS_ROW: dict[str, object] = {
    "codclie_legacy": 27773,
    "historia_clinica": "72769512",
    "historia_familiar": "AM-28159",
    "tipo_documento_codigo": "DNI",
    "numero_documento": "72769512",
    "apellido_paterno": "PACCO",
    "apellido_materno": "MOSCOSO",
    "primer_nombre": "NEPTALY",
    "sexo_codigo": "M",
    "fecha_nacimiento": "2003-10-29",
    "fecha_inscripcion": "2016-01-01",
    "direccion": "AMERICA 100-A",
    "localidad": "ALTO SELVA ALEGRE",
    "sis_diresa": "040",
    "sis_tipo": "2",
    "sis_numero": "72769512",
}


@pytest.fixture
def clinical_catalogs(db_session: Session) -> dict[str, str]:
    """One active specialty, service and diagnosis usable by an encounter."""

    token = uuid4().hex[:6].upper()
    db_session.add(Specialty(codigo=f"E{token}", nombre=f"Medicina {token}", grupo="CLINICA"))
    db_session.add(
        ServiceOffering(codigo=f"P{token}", descripcion=f"Consulta {token}", grupo="CONSULTA")
    )
    db_session.add(Cie10(codigo=f"Z{token[:3]}", descripcion=f"Diagnóstico {token}"))
    db_session.commit()
    return {"especialidad": f"E{token}", "prestacion": f"P{token}", "cie10": f"Z{token[:3]}"}


def _payload(clinic_scene, patient: dict, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "paciente_id": patient["id"],
        "establecimiento_id": clinic_scene.establecimiento_id,
        "profesional_id": clinic_scene.profesional_id,
        "consultorio_id": clinic_scene.consultorio_id,
        "modalidad_atencion_codigo": "AMBULATORIA",
        "fecha_atencion": _moment(),
        "hora_inicio": "09:30:00",
        "hora_fin": "10:00:00",
    }
    payload.update(overrides)
    return payload


def test_professional_registers_an_encounter_with_derived_values(
    clinic_scene, create_patient, db_session: Session, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client, fecha_nacimiento="1990-05-10")

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(
            clinic_scene,
            patient,
            peso_kg="70.5",
            talla_cm="170.0",
            presion_sistolica=120,
            presion_diastolica=80,
            temperatura_c="36.5",
            observaciones="Control de rutina",
        ),
    )
    assert created.status_code == 201, created.text
    attention = created.json()

    assert attention["paciente_id"] == patient["id"]
    assert attention["estado"] == "ATENDIDO"
    assert attention["profesional_id"] == clinic_scene.profesional_id
    assert attention["created_by_usuario_id"] == clinic_scene.professional_user_id
    assert attention["historia_clinica_snapshot"] == patient["historia_clinica"]
    assert attention["consultorio_nombre"]
    assert attention["grupo_atencion_codigo"] == "NINOS_ADOLESCENTES_ADULTOS_MAYORES"
    assert attention["edad_anios"] >= 30
    assert attention["edad_detallada"]
    # Body-mass index is computed by the server, never trusted from the client.
    assert float(attention["imc"]) == pytest.approx(70.5 / (1.70**2), rel=1e-3)
    assert attention["prestaciones"] == []
    assert attention["diagnosticos"] == []

    stored = db_session.get(Attention, attention["id"])
    assert stored is not None
    assert stored.historia_clinica_snapshot == patient["historia_clinica"]

    fetched = clinic_scene.professional_client.get(f"{api_prefix}/atenciones/{attention['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == attention["id"]

    history = clinic_scene.professional_client.get(
        f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]}
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [attention["id"]]


def test_encounter_records_services_and_diagnoses(
    clinic_scene, clinical_catalogs: dict[str, str], create_patient, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(
            clinic_scene,
            patient,
            prestaciones=[{"prestacion_codigo": clinical_catalogs["prestacion"], "cantidad": 1}],
            diagnosticos=[
                {
                    "cie10_codigo": clinical_catalogs["cie10"],
                    "tipo_diagnostico": "PRESUNTIVO",
                    "observacion": "Seguimiento",
                }
            ],
            valoracion_nutricional={"diagnostico": "NORMAL", "hemoglobina": "13.5", "fecha_hemoglobina": _moment()[:10]},
        ),
    )
    assert created.status_code == 201, created.text
    attention = created.json()
    assert [item["prestacion_codigo"] for item in attention["prestaciones"]] == [
        clinical_catalogs["prestacion"]
    ]
    assert [item["cie10_codigo"] for item in attention["diagnosticos"]] == [
        clinical_catalogs["cie10"]
    ]

    unknown_service = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(
            clinic_scene, patient, prestaciones=[{"prestacion_codigo": "NO-EXISTE", "cantidad": 1}]
        ),
    )
    assert unknown_service.status_code == 404
    assert unknown_service.json()["error"]["code"] == "PRESTACION_NO_ACTIVA"

    unknown_diagnosis = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, diagnosticos=[{"cie10_codigo": "Z999"}]),
    )
    assert unknown_diagnosis.status_code == 404
    assert unknown_diagnosis.json()["error"]["code"] == "CIE10_NO_ACTIVO"


def test_linked_professional_can_select_an_active_attending_professional(
    clinic_scene, create_professional, create_patient, db_session, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)
    other = create_professional()
    db_session.add(OfficeProfessional(consultorio_id=clinic_scene.consultorio_id,
        profesional_id=other.id, fecha_inicio=date(2020, 1, 1)))
    db_session.commit()

    response = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, profesional_id=other.id),
    )

    assert response.status_code == 201, response.text
    assert response.json()["profesional_id"] == other.id


def test_encounter_validates_site_and_office_context(
    clinic_scene, create_patient, db_session: Session, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)

    unknown_office = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient, consultorio_id=999999999)
    )
    assert unknown_office.status_code == 404
    assert unknown_office.json()["error"]["code"] == "CONSULTORIO_NO_ACTIVO"

    unknown_establishment = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, establecimiento_id=999999999),
    )
    assert unknown_establishment.status_code == 404
    assert unknown_establishment.json()["error"]["code"] == "ESTABLECIMIENTO_NO_ACTIVO"

    unassigned_office = Office(
        establecimiento_id=clinic_scene.establecimiento_id,
        codigo=f"CON-{uuid4().hex[:8]}",
        nombre="Consultorio sin asignación",
        activo=True,
    )
    db_session.add(unassigned_office)
    db_session.commit()

    active_office = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, consultorio_id=unassigned_office.id),
    )
    assert active_office.status_code == 422, active_office.text
    assert active_office.json()["error"]["code"] == "PROFESIONAL_NO_ASIGNADO"

    unknown_mode = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, modalidad_atencion_codigo="DOMICILIARIA"),
    )
    assert unknown_mode.status_code == 422
    assert unknown_mode.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    inactive_office = db_session.get(Office, clinic_scene.consultorio_id)
    inactive_office.activo = False
    db_session.commit()
    try:
        inactive = clinic_scene.professional_client.post(
            f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient)
        )
        assert inactive.status_code == 404
        assert inactive.json()["error"]["code"] == "CONSULTORIO_NO_ACTIVO"
    finally:
        inactive_office.activo = True
        db_session.commit()


def test_encounter_validates_dates_and_vital_signs(
    clinic_scene, create_patient, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client, fecha_nacimiento="1990-05-10")

    future = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(
            clinic_scene,
            patient,
            fecha_atencion=_moment(days_ago=-1),
            hora_inicio=None,
            hora_fin=None,
        ),
    )
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "FECHA_ATENCION_FUTURA"

    future_attended = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, fecha_atendido=_moment(days_ago=-2)),
    )
    assert future_attended.status_code == 422
    assert future_attended.json()["error"]["code"] == "FECHA_ATENDIDO_FUTURA"

    before_birth = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, fecha_atencion="1989-01-01T09:30:00"),
    )
    assert before_birth.status_code == 422
    assert before_birth.json()["error"]["code"] == "FECHA_ATENCION_ANTERIOR_NACIMIENTO"

    impossible_weight = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient, peso_kg="900")
    )
    assert impossible_weight.status_code == 422
    assert impossible_weight.json()["error"]["code"] == "SIGNOS_VITALES_INVALIDOS"

    inverted_pressure = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, presion_sistolica=80, presion_diastolica=120),
    )
    assert inverted_pressure.status_code == 422
    assert "sistólica" in inverted_pressure.json()["error"]["message"]


def test_minor_encounter_requires_an_active_responsible(
    clinic_scene, create_patient, db_session: Session, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client, fecha_nacimiento="2000-05-10")
    assert (
        clinic_scene.professional_client.post(
            f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient)
        ).status_code
        == 201
    )

    # The API itself refuses to turn an adult into a minor without a
    # responsible person, so the rule cannot be bypassed with a PATCH either.
    refused_correction = clinic_scene.professional_client.patch(
        f"{api_prefix}/patients/{patient['id']}", json={"fecha_nacimiento": "2018-05-10"}
    )
    assert refused_correction.status_code == 422
    assert refused_correction.json()["error"]["code"] == "MENOR_SIN_RESPONSABLE"

    # Legacy data can still hold that state, and the encounter re-checks it.
    stored = db_session.get(Patient, patient["id"])
    stored.fecha_nacimiento = date(2018, 5, 10)
    db_session.commit()

    blocked = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient)
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "MENOR_SIN_RESPONSABLE"

    registered = clinic_scene.professional_client.post(
        f"{api_prefix}/patients/{patient['id']}/responsibles",
        json={"parentesco": "MADRE", "nombre_completo": "Rosa Mamani", "es_principal": True},
    )
    assert registered.status_code == 201, registered.text
    assert (
        clinic_scene.professional_client.post(
            f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient)
        ).status_code
        == 201
    )


def test_nutritional_preview_matches_the_stored_indicators(
    clinic_scene, create_patient, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client, fecha_nacimiento="1995-03-01")

    preview = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/indicadores-nutricionales/vista-previa",
        json={
            "paciente_id": patient["id"],
            "fecha_atencion": _moment(),
            "peso_kg": "70.5",
            "talla_cm": "170.0",
        },
    )
    assert preview.status_code == 200, preview.text
    indicators = preview.json()
    assert indicators["estado"]
    assert indicators["mensaje"]
    assert float(indicators["imc"]) == pytest.approx(70.5 / (1.70**2), rel=1e-3)
    # The WHO 2006 z-scores are not extrapolated beyond 60 months.
    assert (indicators["pe"], indicators["te"], indicators["pt"]) == (None, None, None)

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(clinic_scene, patient, peso_kg="70.5", talla_cm="170.0"),
    )
    assert created.status_code == 201
    assert created.json()["imc"] == indicators["imc"]
    assert created.json()["pe"] == indicators["pe"]

    without_measurements = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/indicadores-nutricionales/vista-previa",
        json={"paciente_id": patient["id"], "fecha_atencion": _moment()},
    )
    assert without_measurements.status_code == 200
    assert without_measurements.json()["imc"] is None
    assert without_measurements.json()["mensaje"]

    # The preview checks the clinical scope before disclosing whether the
    # patient exists at all.
    unknown_patient = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/indicadores-nutricionales/vista-previa",
        json={"paciente_id": 999999999, "fecha_atencion": _moment()},
    )
    assert unknown_patient.status_code == 403
    assert unknown_patient.json()["error"]["code"] == "PACIENTE_FUERA_DE_AMBITO"


def test_encounter_cancellation_keeps_the_row_and_the_reason(
    clinic_scene, create_patient, db_session: Session, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)
    attention = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient)
    ).json()

    short_reason = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/{attention['id']}/anulacion", json={"observaciones": "mal"}
    )
    assert short_reason.status_code == 422

    cancelled = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/{attention['id']}/anulacion",
        json={"observaciones": "Registro duplicado del día"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["estado"] == "ANULADO"
    assert "Registro duplicado" in cancelled.json()["observaciones"]

    stored = db_session.get(Attention, attention["id"])
    assert stored is not None and stored.estado == "ANULADO"

    again = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/{attention['id']}/anulacion",
        json={"observaciones": "Segundo intento de anulación"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ATENCION_YA_ANULADA"

    missing = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones/999999999/anulacion",
        json={"observaciones": "No existe la atención"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ATENCION_NO_ENCONTRADA"


def test_attention_history_search_filters_by_patient_and_period(
    clinic_scene, create_patient, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)
    older = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient, fecha_atencion=_moment(10))
    ).json()
    recent = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient, fecha_atencion=_moment(1))
    ).json()

    by_patient = clinic_scene.professional_client.get(
        f"{api_prefix}/atenciones/busqueda", params={"paciente_id": patient["id"], "limit": 50}
    )
    assert by_patient.status_code == 200, by_patient.text
    body = by_patient.json()
    assert {older["id"], recent["id"]} <= {item["id"] for item in body["items"]}
    assert body["total"] >= 2
    assert set(body) == {"items", "total", "limit", "offset", "has_more"}

    today = date.today()
    windowed = clinic_scene.professional_client.get(
        f"{api_prefix}/atenciones/busqueda",
        params={
            "paciente_id": patient["id"],
            "desde": (today - timedelta(days=3)).isoformat(),
            "hasta": today.isoformat(),
            "limit": 50,
        },
    )
    assert windowed.status_code == 200
    assert [item["id"] for item in windowed.json()["items"]] == [recent["id"]]

    by_status = clinic_scene.professional_client.get(
        f"{api_prefix}/atenciones/busqueda",
        params={"paciente_id": patient["id"], "estado": "ANULADO", "limit": 50},
    )
    assert by_status.status_code == 200
    assert by_status.json()["items"] == []

    invalid = clinic_scene.professional_client.get(
        f"{api_prefix}/atenciones/busqueda", params={"paciente_id": 0}
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_encounters_are_private_to_the_treating_professional(
    clinic_scene, create_patient, create_professional, create_account, api_prefix
) -> None:
    patient = create_patient(clinic_scene.professional_client)
    attention = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=_payload(clinic_scene, patient)
    ).json()

    outsider = create_account(profesional_id=create_professional().id)
    forbidden = outsider.client.get(f"{api_prefix}/atenciones/{attention['id']}")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "ATENCION_FUERA_DE_AMBITO"

    history = outsider.client.get(
        f"{api_prefix}/atenciones/busqueda", params={"paciente_id": patient["id"]}
    )
    assert history.status_code == 200
    assert history.json()["items"] == []

    # ADMIN holds administrative permissions only: clinical history remains
    # out of reach even for the account that manages users and catalogs.
    admin_read = clinic_scene.admin_client.get(f"{api_prefix}/atenciones/{attention['id']}")
    assert admin_read.status_code == 403
    assert admin_read.json()["error"]["details"]["required_permissions"] == ["ATENCION_LEER"]


def test_legacy_sis_patient_stamps_the_affiliation_on_the_fua_snapshot(
    clinic_scene, db_session: Session, api_prefix
) -> None:
    """A real ETL patient registers and keeps its SIS affiliation on the paper FUA.

    The affiliation is stored as three independent boxes.  The paper layout must
    never glue the DIRESA to the affiliate number, and the client cannot override
    what the patient's own record owns.
    """

    insurance = db_session.scalar(
        select(Insurance).where(Insurance.codigo == "SIS_PARA_TODOS")
    )
    assert insurance is not None, "La migración 0017 debe sembrar los planes SIS."

    registered = clinic_scene.professional_client.post(
        f"{api_prefix}/patients",
        json={
            **LEGACY_SIS_ROW,
            # At the historical registration date this patient was a minor.
            "responsables": [{"parentesco": "TUTOR", "nombre_completo": "TUTOR FICTICIO DE PRUEBA"}],
            "ubigeo_residencia_codigo": clinic_scene.ubigeo_codigo,
            "establecimiento_registro_id": clinic_scene.establecimiento_id,
            "seguro_id": insurance.id,
        },
    )
    assert registered.status_code == 201, registered.text
    patient = registered.json()

    # The source key and the typed affiliation survive registration unchanged.
    assert patient["codclie_legacy"] == 27773
    assert patient["tipo_documento_codigo"] == "DNI"
    assert patient["numero_documento"] == "72769512"
    assert patient["seguro_id"] == insurance.id
    assert (patient["sis_diresa"], patient["sis_tipo"], patient["sis_numero"]) == (
        "040",
        "2",
        "72769512",
    )

    created = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json=_payload(
            clinic_scene,
            patient,
            # The client offers a different affiliation; the patient's record owns the truth.
            fua_datos={"sis_diresa": "999", "sis_tipo": "9", "sis_numero": "99999999"},
        ),
    )
    assert created.status_code == 201, created.text
    attention = created.json()

    snapshot = attention["fua_impresion"]
    assert snapshot is not None
    assert snapshot["version"] == 2
    # Three separate boxes: DIRESA is never merged with the affiliate number.
    assert snapshot["sis_diresa"] == "040"
    assert snapshot["sis_tipo"] == "2"
    assert snapshot["sis_numero"] == "72769512"
    assert "sis_numero_completo" not in snapshot
    assert "040" not in snapshot["sis_numero"]
    # Document identity travels with the encounter so the paper TDI stays printable.
    assert snapshot["tipo_documento"] == "DNI"
    assert snapshot["tdi"] == "2"
    assert snapshot["numero_documento"] == "72769512"
    assert snapshot["historia_clinica"] == "72769512"
    assert snapshot["apellido_paterno"] == "PACCO"
    assert snapshot["apellido_materno"] == "MOSCOSO"
    assert snapshot["primer_nombre"] == "NEPTALY"
    assert snapshot["sexo_codigo"] == "M"

    # The snapshot is persisted server-side, not just echoed in the response.
    stored = db_session.get(Attention, attention["id"])
    assert stored is not None
    persisted = stored.fua_impresion
    assert persisted is not None
    assert persisted["sis_diresa"] == "040"
    assert persisted["sis_tipo"] == "2"
    assert persisted["sis_numero"] == "72769512"
    assert persisted["historia_clinica"] == "72769512"
