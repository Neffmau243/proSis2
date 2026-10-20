"""Transaction and projection contracts for the service decomposition."""

from copy import deepcopy
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from app.domain.age import calendar_age
from app.models.audit import AuditLog
from app.models.catalog import Cie10, ServiceOffering
from app.models.clinical import Attention, AttentionDiagnosis
from app.models.clinical import AttentionService as AttentionDetail
from app.models.patient import Patient
from app.models.surveillance import NutritionalEvaluation
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.schemas.attention import AttentionCreate
from app.services.attention import AttentionService
from app.services.attention_context import AttentionContextLoader
from app.services.attention_origin import AttentionOriginReader
from app.services.nutrition_export import NutritionExportService

pytestmark = pytest.mark.integration


def payload(scene, patient, **changes):
    return {
        "paciente_id": patient["id"],
        "establecimiento_id": scene.establecimiento_id,
        "profesional_id": scene.profesional_id,
        "consultorio_id": scene.consultorio_id,
        "modalidad_atencion_codigo": "AMBULATORIA",
        "fecha_atencion": datetime.combine(date.today(), datetime.min.time()).isoformat(),
        "peso_kg": "60.50",
        "talla_cm": "160.00",
        **changes,
    }


@pytest.mark.parametrize("failure_point", ["details", "evaluation", "audit"])
def test_failed_attention_rolls_back_aggregate_but_preserves_committed_patient_patch(
    clinic_scene, create_patient, db_session, api_prefix, monkeypatch, failure_point
):
    client = clinic_scene.professional_client
    patient = create_patient(client)
    patched = client.patch(
        f"{api_prefix}/patients/{patient['id']}", json={"direccion": "PATCH YA CONFIRMADO"}
    )
    assert patched.status_code == 200, patched.text
    initial_condition = patched.json()["condicion"]
    token = uuid4().hex[:8].upper()
    service_code, diagnosis_code = f"P{token}", f"Z{token}"
    db_session.add_all(
        [
            ServiceOffering(codigo=service_code, descripcion="Prestación de prueba"),
            Cie10(codigo=diagnosis_code, descripcion="Diagnóstico de prueba"),
        ]
    )
    db_session.commit()
    # Force an actual condition transition before failing at the last audit.
    values = payload(
        clinic_scene,
        patient,
        grupo_atencion_codigo="GESTANTES",
        peso_antes_embarazo_kg="55",
        tipo_embarazo_codigo="UNICO",
        fecha_probable_parto=(date.today() + timedelta(days=90)).isoformat(),
        prestaciones=[{"prestacion_codigo": service_code, "cantidad": "1"}],
        diagnosticos=[{"cie10_codigo": diagnosis_code}],
    )
    baseline = {
        model: db_session.scalar(select(func.count()).select_from(model))
        for model in (
            Attention,
            AttentionDetail,
            AttentionDiagnosis,
            NutritionalEvaluation,
            AuditLog,
        )
    }
    method = {
        "details": "add_details",
        "evaluation": "add_nutritional_evaluation",
        "audit": "add_audit",
    }[failure_point]
    original = getattr(AttentionRepository, method)

    def fail_after_pending_changes(repository, *args, **kwargs):
        original(repository, *args, **kwargs)
        repository.flush()
        raise RuntimeError("fallo simulado antes del commit")

    monkeypatch.setattr(AttentionRepository, method, fail_after_pending_changes)
    with pytest.raises(RuntimeError, match="fallo simulado"):
        AttentionService(db_session).create(
            AttentionCreate.model_validate(values),
            actor_id=clinic_scene.professional_user_id,
            actor_roles=("PROFESIONAL",),
        )
    with Session(db_session.get_bind()) as independent:
        saved = independent.get(Patient, patient["id"])
        assert saved.direccion == "PATCH YA CONFIRMADO"
        assert saved.condicion == initial_condition
        for model, count in baseline.items():
            assert independent.scalar(select(func.count()).select_from(model)) == count


@pytest.mark.parametrize("operation", ["export", "confirm"])
def test_failed_export_or_confirmation_does_not_leave_state_or_audit_changes(
    clinic_scene, create_patient, db_session, api_prefix, monkeypatch, operation
):
    client = clinic_scene.professional_client
    patient = create_patient(client)
    response = client.post(f"{api_prefix}/atenciones", json=payload(clinic_scene, patient))
    assert response.status_code == 201, response.text
    attention_id = response.json()["id"]
    if operation == "confirm":
        exported = client.post(f"{api_prefix}/atenciones/{attention_id}/nutricion/exportacion")
        assert exported.status_code == 200, exported.text
    record = db_session.scalar(
        select(NutritionalEvaluation).where(NutritionalEvaluation.atencion_id == attention_id)
    )
    expected = (
        record.estado_exportacion,
        record.exportado_at,
        record.enviado,
        record.constancia_envio,
    )
    audit_count = db_session.scalar(select(func.count()).select_from(AuditLog))
    original = AttentionRepository.add_audit

    def failing_audit(repository, **kwargs):
        original(repository, **kwargs)
        repository.flush()
        raise RuntimeError("auditoría de exportación fallida")

    monkeypatch.setattr(AttentionRepository, "add_audit", failing_audit)
    service = NutritionExportService(db_session)
    actor = dict(actor_id=clinic_scene.professional_user_id, actor_roles=("PROFESIONAL",))
    with pytest.raises(RuntimeError, match="auditoría de exportación"):
        if operation == "export":
            service.export_review(attention_id, **actor)
        else:
            service.confirm_sent(
                attention_id, SimpleNamespace(constancia="PRUEBA-ROLLBACK"), **actor
            )
    with Session(db_session.get_bind()) as independent:
        persisted = independent.scalar(
            select(NutritionalEvaluation).where(NutritionalEvaluation.atencion_id == attention_id)
        )
        assert (
            persisted.estado_exportacion,
            persisted.exportado_at,
            persisted.enviado,
            persisted.constancia_envio,
        ) == expected
        assert independent.scalar(select(func.count()).select_from(AuditLog)) == audit_count


@pytest.mark.parametrize("reference", [False, True])
def test_prepared_snapshots_match_saved_json_and_do_not_execute_sql(
    clinic_scene, create_patient, db_session, api_prefix, reference
):
    patient = create_patient(clinic_scene.professional_client)
    values = payload(clinic_scene, patient)
    if reference:
        values.update(
            modalidad_atencion_codigo="REFERENCIA",
            profesional_id=None,
            consultorio_id=None,
            fua_datos={
                "tipo_atencion": "REFERENCIA",
                "referencia_renipress": "00001234",
                "referencia_nombre": "ORIGEN",
                "referencia_hoja": "00042",
            },
        )
    response = clinic_scene.professional_client.post(f"{api_prefix}/atenciones", json=values)
    assert response.status_code == 201, response.text
    stored = db_session.get(Attention, response.json()["id"])
    expected_context, expected_fua = (
        deepcopy(stored.contexto_clinico),
        deepcopy(stored.fua_impresion),
    )
    target = SimpleNamespace(
        **{column.key: getattr(stored, column.key) for column in Attention.__table__.columns}
    )
    command = AttentionCreate.model_validate(values)
    patient_entity = db_session.get(Patient, patient["id"])
    context = AttentionContextLoader(
        AttentionRepository(db_session), PatientRepository(db_session)
    ).load(patient_entity, command)
    age = calendar_age(patient_entity.fecha_nacimiento, command.fecha_atencion.date())
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        context.apply(target, command, age, expected_context["condicion"])
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert statements == []
    assert target.contexto_clinico == expected_context
    assert target.fua_impresion == expected_fua
    if reference:
        # The disposable fixture downgrades to NOT NULL assignments at teardown.
        db_session.execute(
            delete(NutritionalEvaluation).where(NutritionalEvaluation.atencion_id == stored.id)
        )
        db_session.execute(delete(Attention).where(Attention.id == stored.id))
        db_session.commit()


def test_origin_projection_reads_one_query_and_keeps_historical_assessment(
    clinic_scene, create_patient, db_session, api_prefix
):
    patient = create_patient(clinic_scene.professional_client)
    response = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones", json=payload(clinic_scene, patient)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        origin = AttentionOriginReader(db_session).get(body["id"], actor_id=None, actor_roles=None)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert origin.valoracion_calculada.model_dump(mode="json") == body["valoracion_calculada"]
    assert origin.paciente_id == patient["id"]
    assert origin.fecha_atencion.isoformat() == body["fecha_atencion"]


def test_quick_history_keeps_five_and_paginated_history_reaches_older_records(
    clinic_scene, create_patient, api_prefix
):
    client = clinic_scene.professional_client
    patient = create_patient(client)
    ids = []
    for _ in range(7):
        response = client.post(f"{api_prefix}/atenciones", json=payload(clinic_scene, patient))
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    quick = client.get(f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]})
    assert [row["id"] for row in quick.json()] == list(reversed(ids))[:5]
    collected = []
    for offset in (0, 5):
        page = client.get(
            f"{api_prefix}/atenciones/busqueda",
            params={"paciente_id": patient["id"], "limit": 5, "offset": offset},
        )
        assert page.status_code == 200, page.text
        assert page.json()["total"] == 7
        collected.extend(row["id"] for row in page.json()["items"])
    assert collected == list(reversed(ids))
