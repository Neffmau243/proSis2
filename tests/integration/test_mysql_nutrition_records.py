"""Synthetic patients: complete POST → GET → history → MySQL → export coverage."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import product

import pytest
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.clinical import Attention
from app.models.patient import PatientResponsible
from app.models.surveillance import NutritionalEvaluation

pytestmark = pytest.mark.integration
GENERAL = "NINOS_ADOLESCENTES_ADULTOS_MAYORES"


def _moment():
    return datetime.combine(date.today() - timedelta(days=1), datetime.min.time())


def _patient(create_patient, scene, kind, document="DNI", family="AM-100"):
    year = {"NINO": 3, "ESCOLAR": 12, "ADULTO": 35, "MAYOR": 70, "GESTANTE": 28, "PUERPERA": 30}[
        kind
    ]
    born = _moment().date().replace(year=_moment().year - year)
    return create_patient(
        scene.professional_client,
        fecha_nacimiento=born.isoformat(),
        tipo_documento_codigo=document,
        historia_familiar=family,
        sufijo_documento="01",
        apellido_paterno="FICTICIO",
        primer_nombre="PRUEBA",
        sexo_codigo="F",
        establecimiento_registro_id=scene.establecimiento_id,
        ubigeo_residencia_codigo=scene.ubigeo_codigo,
        responsables=[{"parentesco": "MADRE", "nombre_completo": "RESPONSABLE FICTICIA"}]
        if year < 18
        else [],
    )


def _payload(scene, patient, group=GENERAL, mode="AMBULATORIA", **record):
    return dict(
        paciente_id=patient["id"],
        establecimiento_id=scene.establecimiento_id,
        profesional_id=scene.profesional_id,
        consultorio_id=scene.consultorio_id,
        modalidad_atencion_codigo=mode,
        grupo_atencion_codigo=group,
        fecha_atencion=_moment().isoformat(),
        peso_kg=60,
        talla_cm=160,
        valoracion_nutricional=record,
    )


@pytest.mark.parametrize(
    "kind,mode,document",
    list(
        product(
            ["NINO", "ESCOLAR", "ADULTO", "MAYOR", "GESTANTE", "PUERPERA"],
            ["AMBULATORIA", "EMERGENCIA"],
            ["DNI", "CE", "PAS", "DE", "OTRO"],
        )
    ),
)
def test_all_groups_round_trip_with_history_and_family(
    clinic_scene,
    create_patient,
    db_session,
    api_prefix,
    kind,
    mode,
    document,
):
    scene = clinic_scene
    client = scene.professional_client
    patient = _patient(create_patient, scene, kind, document)
    group = {"GESTANTE": "GESTANTES", "PUERPERA": "PUERPERAS"}.get(kind, GENERAL)
    data = dict(
        hemoglobina="13.20",
        fecha_hemoglobina=_moment().date().isoformat(),
        altitud_msnm="2500",
        hemoglobina_corregida="12.10",
        metodo_correccion_hb="Resultado de laboratorio de prueba",
        hematocrito="38.20",
        diagnostico="VALORACION FICTICIA",
    )
    if kind in {"NINO", "ESCOLAR"}:
        data.update(
            juntos=False,
            pin=True,
            crecer=None,
            nro_controles_cred=3,
            nro_sachets=0,
            nro_consejerias=2,
            nro_sesiones=1,
            nro_visitas=4,
            institucion_educativa="IE FICTICIA",
            nivel_educativo="PRUEBA",
            grado="2",
            turno="MAÑANA",
            codigo_matricula="0002",
            seccion="B",
            aula="A1",
            flag_legacy=0,
        )
    elif kind in {"ADULTO", "MAYOR"}:
        data.update(p65=0, vl=1, cp=2, pending_legacy=False)
    elif kind == "GESTANTE":
        data.update(edad_gestacional_semanas=24, estado_ganancia_peso="Registrado por profesional")
    payload = _payload(scene, patient, group, mode, **data)
    if kind == "NINO":
        payload.update(peso_kg=12, talla_cm=86)
    if kind in {"GESTANTE", "PUERPERA"}:
        payload.update(peso_antes_embarazo_kg=55, tipo_embarazo_codigo="UNICO")
    created = client.post(f"{api_prefix}/atenciones", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    context = body["contexto_clinico"]
    assert context["historia_familiar"] == "AM-100"
    assert context["sufijo_documento"] == "01"
    assert body["historia_clinica_snapshot"] == patient["historia_clinica"]
    assert body["modalidad_atencion_codigo"] == mode
    assert body["grupo_atencion_codigo"] == group
    saved = body["evaluaciones_nutricionales"][0]
    for key, value in data.items():
        if key in {"altitud_msnm", "hemoglobina", "hemoglobina_corregida", "hematocrito"}:
            assert Decimal(saved[key]) == Decimal(value)
        else:
            assert saved[key] == value
    assert saved["estado_exportacion"] == "PENDIENTE" and saved["enviado"] is False
    if kind == "NINO":
        assert any(Decimal(saved[key]) != 0 for key in ("waz", "haz", "whz"))
        assert body["fua_impresion"]["pe"] == body["valoracion_calculada"]["pe"]
        assert body["fua_impresion"]["te"] == body["valoracion_calculada"]["te"]
        assert body["fua_impresion"]["pt"] == body["valoracion_calculada"]["pt"]
    if kind in {"ADULTO", "MAYOR"}:
        assert body["valoracion_calculada"]["diagnostico_imc"]
    if kind in {"GESTANTE", "PUERPERA"}:
        assert (
            body["fua_impresion"]["imc_pregestacional"]
            == body["valoracion_calculada"]["imc_pregestacional"]
        )
        assert (
            body["fua_impresion"]["diagnostico_imc"]
            == body["valoracion_calculada"]["diagnostico_imc"].upper()
        )
        assert (
            body["fua_impresion"]["ganancia_peso_kg"]
            == body["valoracion_calculada"]["ganancia_peso_kg"]
        )
    attention_id = body["id"]
    stored = db_session.get(NutritionalEvaluation, saved["id"])
    assert stored.hemoglobina == Decimal("13.20")
    # Later master-data changes cannot rewrite context, results, or age at encounter.
    changed = client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={
            "historia_clinica": "HC-CAMBIADA",
            "historia_familiar": "AZ-200",
            "sufijo_documento": "02",
            "fecha_nacimiento": "1980-01-01",
        },
    )
    assert changed.status_code == 200, changed.text
    get = client.get(f"{api_prefix}/atenciones/{attention_id}").json()
    assert get["contexto_clinico"] == context
    assert get["edad_detallada"] == body["edad_detallada"]
    assert get["valoracion_calculada"] == body["valoracion_calculada"]
    assert get["fua_impresion"] == body["fua_impresion"]
    history = client.get(f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]}).json()
    assert history[0]["evaluaciones_nutricionales"] == body["evaluaciones_nutricionales"]
    exported = client.post(f"{api_prefix}/atenciones/{attention_id}/nutricion/exportacion")
    assert exported.status_code == 200, exported.text
    assert exported.json()["trama_oficial"] is False
    assert exported.json()["campos_legados"]["SufijoDocumento"] == "01"
    assert exported.json()["campos_legados"]["Hist_Clinica"] == patient["historia_clinica"]
    assert exported.json()["campos_legados"]["Enviado"] is False


def test_export_state_receipt_audit_and_authorization(
    clinic_scene, create_patient, db_session, api_prefix, create_account
):
    scene = clinic_scene
    client = scene.professional_client
    patient = _patient(create_patient, scene, "ADULTO")
    response = client.post(f"{api_prefix}/atenciones", json=_payload(scene, patient, p65=0))
    assert response.status_code == 201, response.text
    attention_id = response.json()["id"]
    base = f"{api_prefix}/atenciones/{attention_id}/nutricion"
    assert client.post(base + "/envio", json={"constancia": "PRUEBA-001"}).status_code == 422
    assert scene.anonymous_client.post(base + "/exportacion").status_code == 401
    assert scene.admin_client.post(base + "/exportacion").status_code == 403
    stranger = create_account()
    assert stranger.client.post(base + "/exportacion").status_code == 403
    assert client.post(base + "/exportacion").status_code == 200
    sent = client.post(base + "/envio", json={"constancia": "PRUEBA-001"})
    assert sent.status_code == 200, sent.text
    record = sent.json()["evaluaciones_nutricionales"][0]
    assert record["enviado"] and record["estado_exportacion"] == "ENVIADO"
    assert record["enviado_at"] and record["constancia_envio"] == "PRUEBA-001"
    assert client.post(base + "/envio", json={"constancia": "PRUEBA-001"}).status_code == 200
    assert client.post(base + "/envio", json={"constancia": "OTRA-CONSTANCIA"}).status_code == 409
    repeated = client.post(base + "/exportacion")
    assert repeated.json()["campos_legados"]["Enviado"] is True
    audits = db_session.scalars(
        select(AuditLog).where(
            AuditLog.tabla_nombre == "atenciones",
            AuditLog.registro_id == attention_id,
        )
    ).all()
    assert any(a.accion == "EXPORT" for a in audits)
    assert sum(a.datos_nuevos.get("confirmacion") == "MANUAL" for a in audits) == 1
    assert (
        client.post(
            f"{api_prefix}/atenciones/{attention_id}/anulacion",
            json={
                "observaciones": "ANULACION DE PRUEBA",
            },
        ).status_code
        == 200
    )
    assert client.post(base + "/exportacion").status_code == 422


def test_newborn_registration_attention_history_database_and_fua(
    clinic_scene,
    create_patient,
    db_session,
    api_prefix,
):
    scene = clinic_scene
    client = scene.professional_client
    encounter_date = _moment().date()
    patient = create_patient(
        client,
        tipo_documento_codigo="OTRO",
        numero_documento=f"RN-{encounter_date:%Y%m%d}",
        fecha_nacimiento=encounter_date.isoformat(),
        fecha_inscripcion=encounter_date.isoformat(),
        primer_nombre="RECIEN NACIDO",
        sexo_codigo="F",
        condicion="RECIEN NACIDO",
        historia_familiar="CE-300",
        establecimiento_registro_id=scene.establecimiento_id,
        responsables=[
            {
                "parentesco": "MADRE",
                "nombre_completo": "MADRE FICTICIA",
                "es_principal": True,
            }
        ],
    )
    assert patient["condicion"] == "RECIEN NACIDO"
    assert patient["fecha_nacimiento"] == encounter_date.isoformat()
    assert patient["responsables"][0]["parentesco"] == "MADRE"

    payload = _payload(scene, patient, nro_controles_cred=1)
    payload.update(peso_kg="3.20", talla_cm="50.00")
    created = client.post(f"{api_prefix}/atenciones", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["edad_anios"] == 0
    assert body["edad_detallada"] == "0 años, 0 meses y 0 días"
    assert body["grupo_etario_codigo"] == "NINO"
    assert body["valoracion_calculada"]["grupo_referencia"] == "INFANTIL"
    assert body["valoracion_calculada"]["estado"] == "CALCULADO"
    assert all(body["valoracion_calculada"][key] is not None for key in ("pe", "te", "pt"))

    saved = body["evaluaciones_nutricionales"][0]
    assert saved["tipo"] == "NINO"
    assert saved["waz"] == body["valoracion_calculada"]["pe"]
    assert saved["haz"] == body["valoracion_calculada"]["te"]
    assert saved["whz"] == body["valoracion_calculada"]["pt"]
    assert body["fua_impresion"]["grupo_referencia"] == "INFANTIL"
    assert body["fua_impresion"]["pe"] == body["valoracion_calculada"]["pe"]
    assert body["fua_impresion"]["te"] == body["valoracion_calculada"]["te"]
    assert body["fua_impresion"]["pt"] == body["valoracion_calculada"]["pt"]

    stored = db_session.get(NutritionalEvaluation, saved["id"])
    assert stored is not None
    assert (stored.edad_anios, stored.edad_meses, stored.edad_dias) == (0, 0, 0)
    assert (stored.waz, stored.haz, stored.whz) == (
        Decimal(body["valoracion_calculada"]["pe"]),
        Decimal(body["valoracion_calculada"]["te"]),
        Decimal(body["valoracion_calculada"]["pt"]),
    )

    detail = client.get(f"{api_prefix}/atenciones/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["valoracion_calculada"] == body["valoracion_calculada"]
    history = client.get(
        f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]}
    )
    assert history.status_code == 200
    assert history.json()[0]["evaluaciones_nutricionales"] == body["evaluaciones_nutricionales"]


def test_woman_lifecycle_and_child_mother_document_relation(
    clinic_scene,
    create_patient,
    db_session,
    api_prefix,
):
    scene = clinic_scene
    client = scene.professional_client
    today = date.today()
    general_date = today - timedelta(days=300)
    pregnant_date = today - timedelta(days=120)
    delivery_date = today - timedelta(days=1)
    mother_document = "65000001"
    mother = create_patient(
        client,
        tipo_documento_codigo="DNI",
        numero_documento=mother_document,
        fecha_nacimiento=today.replace(year=today.year - 28).isoformat(),
        fecha_inscripcion=general_date.isoformat(),
        primer_nombre="MARIA",
        apellido_paterno="FICTICIA",
        sexo_codigo="F",
        condicion="NO GESTANTE",
        establecimiento_registro_id=scene.establecimiento_id,
    )

    general_payload = _payload(scene, mother)
    general_payload.update(
        fecha_atencion=datetime.combine(general_date, datetime.min.time()).isoformat(),
        peso_kg="55.00",
        talla_cm="160.00",
    )
    general = client.post(f"{api_prefix}/atenciones", json=general_payload)
    assert general.status_code == 201, general.text
    assert general.json()["valoracion_calculada"]["grupo_referencia"] == "ADULTO"
    assert general.json()["contexto_clinico"]["condicion"] == "JOVEN"
    assert client.get(f"{api_prefix}/patients/{mother['id']}").json()["condicion"] == "JOVEN"

    pregnant_payload = _payload(
        scene,
        mother,
        group="GESTANTES",
        edad_gestacional_semanas=24,
    )
    pregnant_payload.update(
        fecha_atencion=datetime.combine(pregnant_date, datetime.min.time()).isoformat(),
        peso_kg="65.00",
        talla_cm="160.00",
        peso_antes_embarazo_kg="55.00",
        tipo_embarazo_codigo="UNICO",
    )
    pregnant = client.post(f"{api_prefix}/atenciones", json=pregnant_payload)
    assert pregnant.status_code == 201, pregnant.text
    pregnant_body = pregnant.json()
    assert pregnant_body["valoracion_calculada"]["grupo_referencia"] == "GESTANTE"
    assert pregnant_body["valoracion_calculada"]["imc_pregestacional"] == "21.484"
    assert pregnant_body["valoracion_calculada"]["diagnostico_imc"] == "Normal"
    assert pregnant_body["valoracion_calculada"]["ganancia_peso_kg"] == "10.00"
    assert client.get(f"{api_prefix}/patients/{mother['id']}").json()["condicion"] == "GESTANTE"

    puerperal_payload = _payload(scene, mother, group="PUERPERAS")
    puerperal_payload.update(
        fecha_atencion=datetime.combine(delivery_date, datetime.min.time()).isoformat(),
        fecha_parto=delivery_date.isoformat(),
        peso_kg="64.00",
        talla_cm="160.00",
        peso_antes_embarazo_kg="55.00",
        tipo_embarazo_codigo="UNICO",
    )
    puerperal = client.post(f"{api_prefix}/atenciones", json=puerperal_payload)
    assert puerperal.status_code == 201, puerperal.text
    puerperal_body = puerperal.json()
    assert puerperal_body["valoracion_calculada"]["grupo_referencia"] == "PUERPERA"
    assert puerperal_body["valoracion_calculada"]["imc_pregestacional"] == "21.484"
    assert puerperal_body["valoracion_calculada"]["diagnostico_imc"] == "Normal"
    assert client.get(f"{api_prefix}/patients/{mother['id']}").json()["condicion"] == "PUERPERA"

    child = create_patient(
        client,
        tipo_documento_codigo="OTRO",
        numero_documento="RN-65000001",
        fecha_nacimiento=delivery_date.isoformat(),
        fecha_inscripcion=delivery_date.isoformat(),
        primer_nombre="BEBE",
        apellido_paterno="FICTICIO",
        sexo_codigo="F",
        condicion="RECIEN NACIDO",
        establecimiento_registro_id=scene.establecimiento_id,
        responsables=[
            {
                "parentesco": "MADRE",
                "nombre_completo": "MARIA FICTICIA",
                "tipo_documento_codigo": "DNI",
                "numero_documento": mother_document,
                "es_principal": True,
            }
        ],
    )
    responsible = child["responsables"][0]
    assert responsible["parentesco"] == "MADRE"
    assert responsible["tipo_documento_codigo"] == "DNI"
    assert responsible["numero_documento"] == mother_document

    stored_relation = db_session.scalar(
        select(PatientResponsible).where(PatientResponsible.paciente_id == child["id"])
    )
    assert stored_relation is not None
    assert stored_relation.numero_documento == mother_document

    mother_history = client.get(
        f"{api_prefix}/atenciones", params={"paciente_id": mother["id"]}
    )
    assert mother_history.status_code == 200
    assert {item["grupo_atencion_codigo"] for item in mother_history.json()} == {
        GENERAL,
        "GESTANTES",
        "PUERPERAS",
    }
    reread_child = client.get(f"{api_prefix}/patients/{child['id']}")
    assert reread_child.status_code == 200
    assert reread_child.json()["responsables"][0]["numero_documento"] == mother_document


def test_single_patient_age_lifecycle_preserves_encounter_snapshots(
    clinic_scene,
    create_patient,
    db_session,
    api_prefix,
):
    scene = clinic_scene
    client = scene.professional_client
    birth = date(1950, 1, 15)
    patient = create_patient(
        client,
        tipo_documento_codigo="DNI",
        numero_documento="65000002",
        fecha_nacimiento=birth.isoformat(),
        fecha_inscripcion=birth.isoformat(),
        primer_nombre="PACIENTE",
        apellido_paterno="CICLO ETARIO",
        sexo_codigo="M",
        condicion="NIÑO",
        establecimiento_registro_id=scene.establecimiento_id,
        responsables=[
            {
                "parentesco": "MADRE",
                "nombre_completo": "MADRE HISTORICA",
                "es_principal": True,
            }
        ],
    )
    stages = [
        (3, "NINO", "INFANTIL", "CONTROL CRED", "AMBULATORIA", "15.00", "95.00"),
        (
            15,
            "ADOLESCENTE",
            "ESCOLAR",
            "CONSULTA ADOLESCENTE",
            "EMERGENCIA",
            "50.00",
            "160.00",
        ),
        (25, "JOVEN", "ADULTO", "CONSULTA JOVEN", "AMBULATORIA", "60.00", "165.00"),
        (40, "ADULTO", "ADULTO", "CONTROL ADULTO", "AMBULATORIA", "70.00", "165.00"),
        (
            65,
            "ADULTO_MAYOR",
            "ADULTO_MAYOR",
            "CONTROL ADULTO MAYOR",
            "EMERGENCIA",
            "68.00",
            "165.00",
        ),
    ]
    created = []
    for years, age_group, reference_group, reason, mode, weight, height in stages:
        encounter_date = birth.replace(year=birth.year + years)
        payload = _payload(scene, patient, mode=mode)
        payload.update(
            fecha_atencion=datetime.combine(encounter_date, datetime.min.time()).isoformat(),
            peso_kg=weight,
            talla_cm=height,
            observaciones=reason,
        )
        response = client.post(f"{api_prefix}/atenciones", json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["edad_detallada"] == f"{years} años, 0 meses y 0 días"
        assert body["grupo_etario_codigo"] == age_group
        assert body["valoracion_calculada"]["grupo_referencia"] == reference_group
        assert body["fua_impresion"]["grupo_referencia"] == reference_group
        assert body["contexto_clinico"]["condicion"] == {
            "NINO": "NIÑO",
            "ADOLESCENTE": "ADOLESCENTE",
            "JOVEN": "JOVEN",
            "ADULTO": "ADULTO",
            "ADULTO_MAYOR": "ADULTO MAYOR",
        }[age_group]
        assert body["observaciones"] == reason
        assert body["modalidad_atencion_codigo"] == mode
        stored = db_session.get(Attention, body["id"])
        assert stored is not None
        assert stored.grupo_etario_codigo == age_group
        assert stored.contexto_clinico["condicion"] == body["contexto_clinico"]["condicion"]
        created.append(body)

    history = client.get(
        f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]}
    )
    assert history.status_code == 200
    assert len(history.json()) == len(stages)
    by_id = {item["id"]: item for item in history.json()}
    for body in created:
        historical = by_id[body["id"]]
        assert historical["edad_detallada"] == body["edad_detallada"]
        assert historical["grupo_etario_codigo"] == body["grupo_etario_codigo"]
        assert historical["valoracion_calculada"] == body["valoracion_calculada"]
        assert historical["observaciones"] == body["observaciones"]

    # La ficha refleja la etapa vigente y cada atención conserva su foto histórica.
    assert (
        client.get(f"{api_prefix}/patients/{patient['id']}").json()["condicion"]
        == "ADULTO MAYOR"
    )


def test_invalid_records_rollback_and_old_records_remain_readable(
    clinic_scene, create_patient, db_session, api_prefix
):
    scene = clinic_scene
    client = scene.professional_client
    patient = _patient(create_patient, scene, "ADULTO")
    before = db_session.scalar(select(func.count()).select_from(Attention))
    for data in (
        {"juntos": False},
        {"hemoglobina": 0},
        {"enviado": True},
        {"hemoglobina": 12, "fecha_hemoglobina": "2099-01-01"},
    ):
        invalid = client.post(f"{api_prefix}/atenciones", json=_payload(scene, patient, **data))
        assert invalid.status_code == 422, invalid.text
    assert db_session.scalar(select(func.count()).select_from(Attention)) == before
    created = client.post(f"{api_prefix}/atenciones", json=_payload(scene, patient))
    attention_id = created.json()["id"]
    row = db_session.get(Attention, attention_id)
    row.contexto_clinico = None
    row.evaluaciones_nutricionales[0].hemoglobina = Decimal(0)
    db_session.commit()
    historical = client.get(f"{api_prefix}/atenciones/{attention_id}")
    assert historical.status_code == 200
    assert historical.json()["evaluaciones_nutricionales"][0]["hemoglobina"] == "0.00"
    assert (
        client.post(f"{api_prefix}/atenciones/{attention_id}/nutricion/exportacion").status_code
        == 422
    )
