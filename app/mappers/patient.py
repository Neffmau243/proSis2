"""Pure conversions between patient DTOs and ORM-facing data structures."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.patient import (
    PatientCreate,
    PatientResponsibleCreate,
    PatientResponsibleResponse,
    PatientResponsibleUpdate,
    PatientResponse,
    PatientRiskCreate,
    PatientRiskResponse,
    PatientRiskUpdate,
    PatientUpdate,
)

if TYPE_CHECKING:
    from app.models.patient import Patient, PatientResponsible, PatientRisk


_PATIENT_MUTABLE_FIELDS = frozenset(
    {
        "historia_clinica",
        "historia_familiar",
        "sufijo_documento",
        "sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia", "etnia_codigo",
        "tipo_documento_codigo",
        "numero_documento",
        "fecha_inscripcion",
        "fecha_nacimiento",
        "apellido_paterno",
        "apellido_materno",
        "primer_nombre",
        "otros_nombres",
        "sexo_codigo",
        "ubigeo_residencia_codigo",
        "localidad",
        "localidad_id",
        "direccion",
        "establecimiento_registro_id",
        "seguro_id",
        "telefono_principal",
        "condicion",
    }
)


def patient_create_to_entity_kwargs(payload: PatientCreate) -> dict[str, Any]:
    """Returns only columns that belong to ``pacientes``.

    Nested responsible people and risks are handled by their own mappers after
    SQLAlchemy has assigned the patient's technical id.
    """

    values = payload.model_dump(exclude={"responsables", "riesgos"})
    return values


def patient_update_to_entity_kwargs(payload: PatientUpdate) -> dict[str, Any]:
    """Returns a PATCH-safe, whitelisted field mapping.

    ``exclude_unset`` is important: an omitted field must never clear a stored
    value, while an explicitly supplied ``null`` is preserved for nullable
    database columns.
    """

    values = payload.model_dump(exclude_unset=True)
    return {name: value for name, value in values.items() if name in _PATIENT_MUTABLE_FIELDS}


def responsible_create_to_entity_kwargs(
    payload: PatientResponsibleCreate,
    *,
    patient_id: int,
) -> dict[str, Any]:
    """Converts a responsible-person input into mapped column values."""

    values = payload.model_dump()
    values["parentesco"] = payload.parentesco.value
    values["paciente_id"] = patient_id
    return values


def responsible_update_to_entity_kwargs(payload: PatientResponsibleUpdate) -> dict[str, Any]:
    """Converts only supplied mutable responsible fields."""

    values = payload.model_dump(exclude_unset=True)
    if "parentesco" in values and payload.parentesco is not None:
        values["parentesco"] = payload.parentesco.value
    return values


def risk_create_to_entity_kwargs(payload: PatientRiskCreate, *, patient_id: int) -> dict[str, Any]:
    """Converts a risk period input into mapped column values."""

    return {"paciente_id": patient_id, **payload.model_dump()}


def risk_update_to_entity_kwargs(payload: PatientRiskUpdate) -> dict[str, Any]:
    """Converts only fields allowed to change on a risk period."""

    return payload.model_dump(exclude_unset=True)


def responsible_to_response(entity: "PatientResponsible") -> PatientResponsibleResponse:
    """Builds a response DTO without exposing the ORM entity."""

    return PatientResponsibleResponse(
        id=entity.id,
        parentesco=entity.parentesco,
        nombre_completo=entity.nombre_completo,
        tipo_documento_codigo=entity.tipo_documento_codigo,
        numero_documento=entity.numero_documento,
        telefono=entity.telefono,
        es_principal=entity.es_principal,
        activo=entity.activo,
    )


def risk_to_response(entity: "PatientRisk") -> PatientRiskResponse:
    """Builds a risk response, including optional read-only catalog labels."""

    group = getattr(entity, "grupo_riesgo", None)
    return PatientRiskResponse(
        **{key: getattr(entity, key, None) for key in (
            "atencion_origen_id", "evaluacion_origen", "confirmado_por_usuario_id",
            "fecha_proximo_control", "motivo_cierre",
        )},
        grupo_riesgo_id=entity.grupo_riesgo_id,
        fecha_inicio=entity.fecha_inicio,
        fecha_fin=entity.fecha_fin,
        observacion=entity.observacion,
        grupo_riesgo_codigo=getattr(group, "codigo", None),
        grupo_riesgo_nombre=getattr(group, "nombre", None),
    )


def patient_to_response(entity: "Patient") -> PatientResponse:
    """Maps the patient aggregate loaded by the repository to a public DTO."""

    ubigeo = getattr(entity, "ubigeo_residencia", None)
    return PatientResponse(
        sufijo_documento=getattr(entity, "sufijo_documento", None),
        id=entity.id,
        codclie_legacy=entity.codclie_legacy,
        historia_clinica=entity.historia_clinica,
        historia_familiar=entity.historia_familiar,
        **{key: getattr(entity, key, None) for key in ("sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia", "etnia_codigo")},
        tipo_documento_codigo=entity.tipo_documento_codigo,
        numero_documento=entity.numero_documento,
        fecha_inscripcion=entity.fecha_inscripcion,
        fecha_nacimiento=entity.fecha_nacimiento,
        apellido_paterno=entity.apellido_paterno,
        apellido_materno=entity.apellido_materno,
        primer_nombre=entity.primer_nombre,
        otros_nombres=entity.otros_nombres,
        sexo_codigo=entity.sexo_codigo,
        ubigeo_residencia_codigo=entity.ubigeo_residencia_codigo,
        distrito_residencia=getattr(ubigeo, "distrito", None),
        localidad=entity.localidad,
        localidad_id=getattr(entity, "localidad_id", None),
        direccion=entity.direccion,
        establecimiento_registro_id=entity.establecimiento_registro_id,
        seguro_id=entity.seguro_id,
        telefono_principal=entity.telefono_principal,
        condicion=entity.condicion,
        estado=entity.estado,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        responsables=[responsible_to_response(item) for item in entity.responsables],
        riesgos=[risk_to_response(item) for item in entity.riesgos],
    )
