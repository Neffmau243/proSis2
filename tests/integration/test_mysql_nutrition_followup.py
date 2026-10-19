"""Real HTTP/DB checks for confirmed follow-up and immutable origin evidence."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import update

from app.models.clinical import Attention

pytestmark = pytest.mark.integration


def _groups(client, api):
    response = client.get(f"{api}/catalogos/grupos-riesgo")
    assert response.status_code == 200, response.text
    return {group["codigo"]: group["id"] for group in response.json()}


def _control(client, api, scene, patient, day, weight="50", height="175"):
    response = client.post(
        f"{api}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": scene.establecimiento_id,
            "profesional_id": scene.profesional_id,
            "consultorio_id": scene.consultorio_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(day, datetime.min.time()).isoformat(),
            "peso_kg": weight,
            "talla_cm": height,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_adult_suggestion_requires_confirmation_and_preserves_origin(
    clinic_scene,
    create_patient,
    api_prefix,
):
    client, api = clinic_scene.professional_client, api_prefix
    patient = create_patient(client)
    groups = _groups(client, api)
    today = date.today()
    attention = _control(client, api, clinic_scene, patient, today)
    result = attention["valoracion_calculada"]
    assert result["diagnostico_imc"] == "Delgadez grado II"
    assert result["version_calculo"] == "MINSA-2026.1"
    assert result["seguimiento"]["sugerencias"][0]["codigo"] == "NUT_HALLAZGO"
    path = f"{api}/patients/{patient['id']}"
    assert client.get(path).json()["riesgos"] == []
    payload = {
        "grupo_riesgo_id": groups["NUT_HALLAZGO"],
        "fecha_inicio": today.isoformat(),
        "atencion_origen_id": attention["id"],
    }
    assert client.post(f"{path}/risk-groups", json=payload).status_code == 422
    payload.update(
        observacion="Prueba ficticia: se confirma evaluación y seguimiento.",
        fecha_proximo_control=(today + timedelta(days=15)).isoformat(),
    )
    forged = client.post(
        f"{path}/risk-groups", json={**payload, "evaluacion_origen": {"normal": True}}
    )
    assert forged.status_code == 422
    created = client.post(f"{path}/risk-groups", json=payload)
    assert created.status_code == 201, created.text
    risk = created.json()
    assert risk["evaluacion_origen"] == result
    assert risk["confirmado_por_usuario_id"] == clinic_scene.professional_user_id
    assert len(client.get(path).json()["riesgos"]) == 1
    assert client.post(f"{path}/risk-groups", json=payload).status_code == 422

    # Later normal measurements do not close follow-up or rewrite the source.
    normal = _control(client, api, clinic_scene, patient, today, weight="70")
    assert normal["valoracion_calculada"]["diagnostico_imc"] == "Normal"
    unchanged = client.get(path).json()["riesgos"][0]
    assert unchanged["fecha_fin"] is None
    assert unchanged["evaluacion_origen"] == result
    endpoint = f"{path}/risk-groups/{groups['NUT_HALLAZGO']}/{today.isoformat()}"
    assert client.patch(endpoint, json={"fecha_fin": today.isoformat()}).status_code == 422
    closed = client.patch(
        endpoint,
        json={
            "fecha_fin": today.isoformat(),
            "motivo_cierre": "Prueba ficticia: reevaluación y cierre profesional.",
        },
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["fecha_proximo_control"] is None
    assert closed.json()["evaluacion_origen"] == result


def test_source_must_belong_to_patient_and_contain_the_suggestion(
    clinic_scene, create_patient, api_prefix
):
    client, api = clinic_scene.professional_client, api_prefix
    first, second = create_patient(client), create_patient(client)
    origin = _control(client, api, clinic_scene, first, date.today(), weight="70")
    groups = _groups(client, api)
    for patient in (first, second):
        response = client.post(
            f"{api}/patients/{patient['id']}/risk-groups",
            json={
                "grupo_riesgo_id": groups["NUT_HALLAZGO"],
                "fecha_inicio": date.today().isoformat(),
                "atencion_origen_id": origin["id"],
                "observacion": "Prueba ficticia.",
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] in {
            "ORIGEN_RIESGO_INVALIDO",
            "SUGERENCIA_NO_DISPONIBLE",
        }


def test_child_trend_uses_only_previous_attended_date(clinic_scene, create_patient, api_prefix):
    client, api = clinic_scene.professional_client, api_prefix
    today = date.today()
    child = create_patient(
        client,
        fecha_nacimiento=(today - timedelta(days=730)).isoformat(),
        responsables=[
            {"parentesco": "MADRE", "nombre_completo": "Responsable ficticia", "es_principal": True}
        ],
    )
    first = _control(client, api, clinic_scene, child, today - timedelta(days=30), "12", "85")
    assert (
        first["valoracion_calculada"]["seguimiento"]["tendencia"]["estado"] == "DATOS_INSUFICIENTES"
    )
    cancelled = _control(client, api, clinic_scene, child, today - timedelta(days=1), "13", "86")
    response = client.post(
        f"{api}/atenciones/{cancelled['id']}/anulacion",
        json={"observaciones": "Prueba ficticia anulada"},
    )
    assert response.status_code == 200, response.text
    _control(
        client, api, clinic_scene, child, today, "15", "88"
    )  # Same day is not a prior growth control.
    current = _control(client, api, clinic_scene, child, today, "12", "85.5")
    followup = current["valoracion_calculada"]["seguimiento"]
    assert followup["tendencia"]["atencion_anterior_id"] == first["id"]
    assert followup["tendencia"]["dias"] == 30
    assert "NUT_CRECIMIENTO" in [s["codigo"] for s in followup["sugerencias"]]


@pytest.mark.parametrize("legacy_error", ["zero", "before_birth"])
def test_invalid_legacy_measurements_do_not_establish_growth(
    clinic_scene,
    create_patient,
    api_prefix,
    db_session,
    legacy_error,
):
    client, api = clinic_scene.professional_client, api_prefix
    today = date.today()
    birth = today - timedelta(days=730)
    child = create_patient(
        client,
        fecha_nacimiento=birth.isoformat(),
        responsables=[
            {
                "parentesco": "MADRE",
                "nombre_completo": "Responsable ficticia",
                "es_principal": True,
            },
        ],
    )
    prior = _control(client, api, clinic_scene, child, today - timedelta(days=30), "12", "85")
    # Simulate imperfect imported data, without relaxing clinical API validation.
    invalid = (
        {"peso_kg": 0}
        if legacy_error == "zero"
        else {
            "fecha_atencion": datetime.combine(birth - timedelta(days=1), datetime.min.time()),
        }
    )
    db_session.execute(update(Attention).where(Attention.id == prior["id"]).values(**invalid))
    db_session.commit()
    current = _control(client, api, clinic_scene, child, today, "12", "85")
    followup = current["valoracion_calculada"]["seguimiento"]
    assert followup["tendencia"]["estado"] == "DATOS_INSUFICIENTES"
    assert "NUT_CRECIMIENTO" not in [s["codigo"] for s in followup["sugerencias"]]
