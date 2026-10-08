"""Explicit ORM-to-DTO mapping for clinical attention responses."""

from app.domain.age import calendar_age
from app.models.clinical import Attention
from app.schemas.attention import (
    AttentionDiagnosisResponse,
    AttentionResponse,
    AttentionServiceResponse,
)


def attention_to_response(entity: Attention) -> AttentionResponse:
    return AttentionResponse(
        valoracion_calculada=getattr(entity, "valoracion_calculada", None),
        fua_impresion=entity.fua_impresion,
        id=entity.id,
        paciente_id=entity.paciente_id,
        establecimiento_id=entity.establecimiento_id,
        profesional_id=entity.profesional_id,
        especialidad_codigo=entity.especialidad_codigo,
        consultorio_id=entity.consultorio_id,
        consultorio_nombre=entity.consultorio.nombre if entity.consultorio is not None else None,
        modalidad_atencion_codigo=entity.modalidad_atencion_codigo,
        grupo_etario_codigo=entity.grupo_etario_codigo,
        grupo_atencion_codigo=entity.grupo_atencion_codigo,
        fecha_atencion=entity.fecha_atencion,
        fecha_atendido=entity.fecha_atendido,
        historia_clinica_snapshot=entity.historia_clinica_snapshot,
        edad_anios=entity.edad_anios,
        edad_detallada=_age_display(entity),
        peso_kg=entity.peso_kg,
        talla_cm=entity.talla_cm,
        perimetro_abdominal_cm=entity.perimetro_abdominal_cm,
        tipo_embarazo_codigo=entity.tipo_embarazo_codigo,
        peso_antes_embarazo_kg=entity.peso_antes_embarazo_kg,
        fecha_probable_parto=entity.fecha_probable_parto,
        fecha_parto=entity.fecha_parto,
        presion_sistolica=entity.presion_sistolica,
        presion_diastolica=entity.presion_diastolica,
        temperatura_c=entity.temperatura_c,
        imc=entity.imc,
        pe=entity.pe,
        te=entity.te,
        pt=entity.pt,
        referencia_nutricional=entity.referencia_nutricional,
        hora_inicio=entity.hora_inicio,
        hora_fin=entity.hora_fin,
        admision=entity.admision,
        observaciones=entity.observaciones,
        estado=entity.estado,
        created_by_usuario_id=entity.created_by_usuario_id,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        prestaciones=[
            AttentionServiceResponse(
                numero_orden=item.numero_orden,
                prestacion_codigo=item.prestacion_codigo,
                cantidad=item.cantidad,
            )
            for item in entity.prestaciones
        ],
        diagnosticos=[
            AttentionDiagnosisResponse(
                numero_orden=item.numero_orden,
                cie10_codigo=item.cie10_codigo,
                tipo_diagnostico=item.tipo_diagnostico,
                observacion=item.observacion,
            )
            for item in entity.diagnosticos
        ],
    )


def _age_display(entity: Attention) -> str | None:
    """Render the exact calendar age at the encounter date for history views."""

    patient = entity.paciente
    if patient is None or patient.fecha_nacimiento > entity.fecha_atencion.date():
        return f"{entity.edad_anios} años" if entity.edad_anios is not None else None
    return calendar_age(patient.fecha_nacimiento, entity.fecha_atencion).display
