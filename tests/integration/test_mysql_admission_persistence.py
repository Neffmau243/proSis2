"""Admission fields survive HTTP writes, reloads and immutable FUA snapshots."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.catalog import Insurance, Specialty
from app.models.clinical import Attention
from app.models.organization import Localidad, Office
from app.models.patient import Patient
from app.models.security import ProfessionalSpecialty

pytestmark = pytest.mark.integration


def test_admission_patient_measurements_and_insurance_survive_reload(
    clinic_scene, db_session, create_patient, create_risk_group, api_prefix
):
    client = clinic_scene.professional_client
    token = uuid4().hex[:8].upper()
    plans = {
        item.codigo: item
        for item in db_session.scalars(
            select(Insurance).where(Insurance.codigo.in_(["SIS_GRATUITO", "SIS_NRUS", "ESSALUD"]))
        )
    }
    assert len(plans) == 3
    locality = Localidad(
        ubigeo_codigo=clinic_scene.ubigeo_codigo,
        codigo_catalogo="AUDIT",
        codigo_sis="07",
        nombre=f"LOCALIDAD {token}",
        nombre_norm=f"LOCALIDAD {token}",
    )
    specialty = Specialty(codigo=token, nombre=f"Especialidad {token}", es_area=True)
    db_session.add_all([locality, specialty])
    # Use the same explicit office/service qualification required by admission.
    office = db_session.get(Office, clinic_scene.consultorio_id)
    office.area_codigo = specialty.codigo
    office.servicios_codigos = [specialty.codigo]
    db_session.add(
        ProfessionalSpecialty(
            profesional_id=clinic_scene.profesional_id,
            especialidad_codigo=specialty.codigo,
            es_principal=True,
        )
    )
    db_session.commit()
    original = create_patient(client, seguro_id=plans["SIS_GRATUITO"].id)
    patient_url = f"{api_prefix}/patients/{original['id']}"
    document = str(uuid4().int)[:8]
    fields = {
        "historia_clinica": f"HC-AUD-{token}",
        "historia_familiar": f"AM-{str(uuid4().int)[:10]}",
        "tipo_documento_codigo": "DNI",
        "numero_documento": document,
        "fecha_nacimiento": "2000-08-27",
        "apellido_paterno": "PRUEBA",
        "apellido_materno": "ADMISION",
        "primer_nombre": "PACIENTE",
        "otros_nombres": "FICTICIO",
        "sexo_codigo": "F",
        "ubigeo_residencia_codigo": clinic_scene.ubigeo_codigo,
        "localidad_id": locality.id,
        "direccion": "DIRECCION FICTICIA 123",
        "establecimiento_registro_id": clinic_scene.establecimiento_id,
        "seguro_id": plans["SIS_GRATUITO"].id,
        "sis_diresa": "040",
        "sis_tipo": "2",
        "sis_numero": document,
        "telefono_principal": "900000001",
        "condicion": "ADULTO",
    }
    response = client.patch(patient_url, json=fields)
    assert response.status_code == 200, response.text
    responsible = client.post(
        f"{patient_url}/responsibles",
        json={"parentesco": "MADRE", "nombre_completo": "MADRE FICTICIA", "es_principal": True},
    )
    assert responsible.status_code == 201, responsible.text
    risk = create_risk_group()
    risk_response = client.post(
        f"{patient_url}/risk-groups",
        json={"grupo_riesgo_id": risk.id, "fecha_inicio": "2020-01-01"},
    )
    assert risk_response.status_code == 201, risk_response.text
    reread = client.get(patient_url)
    assert reread.status_code == 200, reread.text
    patient = reread.json()
    for key, value in fields.items():
        assert patient[key] == value, key
    assert patient["localidad"] == locality.nombre
    assert patient["responsables"][0]["nombre_completo"] == "MADRE FICTICIA"
    assert patient["riesgos"][0]["grupo_riesgo_id"] == risk.id
    db_session.expire_all()
    stored_patient = db_session.get(Patient, patient["id"])
    for key, value in fields.items():
        actual = getattr(stored_patient, key)
        assert (actual.isoformat() if isinstance(actual, date) else actual) == value, key

    encounter_fields = {
        "paciente_id": patient["id"],
        "establecimiento_id": clinic_scene.establecimiento_id,
        "consultorio_id": clinic_scene.consultorio_id,
        "especialidad_codigo": specialty.codigo,
        "profesional_id": clinic_scene.profesional_id,
        "modalidad_atencion_codigo": "EMERGENCIA",
        "grupo_atencion_codigo": "NINOS_ADOLESCENTES_ADULTOS_MAYORES",
        "fecha_atencion": datetime.combine(
            date.today() - timedelta(days=1), time(9, 30)
        ).isoformat(),
        "peso_kg": "65.50",
        "talla_cm": "165.00",
        "perimetro_abdominal_cm": "80.50",
        "presion_sistolica": 120,
        "presion_diastolica": 80,
        "temperatura_c": "36.5",
    }
    created = client.post(f"{api_prefix}/atenciones", json=encounter_fields)
    assert created.status_code == 201, created.text
    attention = created.json()
    reloaded = client.get(f"{api_prefix}/atenciones/{attention['id']}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json() == attention
    for key, value in encounter_fields.items():
        if key != "fecha_atencion":
            assert attention[key] == value, key
    assert attention["valoracion_calculada"]["grupo_referencia"] == "ADULTO"
    assert all(attention[key] is None for key in ("pe", "te", "pt"))
    assert attention["imc"] is not None
    db_session.expire_all()
    stored_attention = db_session.get(Attention, attention["id"])
    assert stored_attention.temperatura_c == Decimal("36.5")
    assert stored_attention.perimetro_abdominal_cm == Decimal("80.50")
    snapshot = attention["fua_impresion"]
    for key in (
        "historia_clinica",
        "numero_documento",
        "apellido_paterno",
        "apellido_materno",
        "primer_nombre",
        "otros_nombres",
        "sexo_codigo",
        "fecha_nacimiento",
        "sis_diresa",
        "sis_tipo",
        "sis_numero",
    ):
        assert snapshot[key] == fields[key], key
    for key in (
        "peso_kg",
        "talla_cm",
        "perimetro_abdominal_cm",
        "presion_sistolica",
        "presion_diastolica",
    ):
        assert snapshot[key] == encounter_fields[key], key
    assert snapshot["imc"] == attention["imc"]
    assert snapshot["tipo_atencion"] == "EMERGENCIA"
    assert snapshot["codigo_renipress"] == clinic_scene.codigo_renaes.zfill(8)
    location = snapshot["contexto_territorial"]
    for key in (
        "ubigeo_residencia_codigo",
        "localidad_id",
        "direccion",
        "establecimiento_registro_id",
    ):
        assert location[key] == fields[key], key
    assert location["localidad_codigo_sis"] == "07"
    assert location["consultorio_id"] == clinic_scene.consultorio_id
    assert location["especialidad_codigo"] == specialty.codigo

    # Plan changes persist explicitly, while a previous FUA retains its accreditation.
    nrus = client.patch(patient_url, json={"seguro_id": plans["SIS_NRUS"].id, "sis_tipo": "R"})
    assert nrus.status_code == 200, nrus.text
    assert client.get(patient_url).json()["sis_tipo"] == "R"
    next_attention = client.post(f"{api_prefix}/atenciones", json=encounter_fields)
    assert next_attention.status_code == 201, next_attention.text
    assert next_attention.json()["fua_impresion"]["sis_tipo"] == "R"
    other = client.patch(patient_url, json={"seguro_id": plans["ESSALUD"].id})
    assert other.status_code == 200, other.text
    other_patient = client.get(patient_url).json()
    assert other_patient["seguro_id"] == plans["ESSALUD"].id
    assert all(
        other_patient[key] is None
        for key in ("sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia")
    )
    old = client.get(f"{api_prefix}/atenciones/{attention['id']}").json()
    assert old["fua_impresion"] == snapshot
