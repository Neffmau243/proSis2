"""Explicit mapping from professional ORM aggregates to API contracts."""

from __future__ import annotations

from app.models.security import Professional
from app.schemas.professional import ProfessionalResponse, ProfessionalSpecialtyResponse


def professional_to_response(entity: Professional) -> ProfessionalResponse:
    specialties = sorted(
        (
            ProfessionalSpecialtyResponse(
                especialidad_codigo=item.especialidad_codigo,
                es_principal=item.es_principal,
            )
            for item in entity.especialidades
        ),
        key=lambda item: (not item.es_principal, item.especialidad_codigo),
    )
    return ProfessionalResponse(
        id=entity.id,
        codigo_legacy=entity.codigo_legacy,
        numero_documento=entity.numero_documento,
        nombre_completo=entity.nombre_completo,
        profesion_id=entity.profesion_id,
        colegiatura=entity.colegiatura,
        activo=entity.activo,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        especialidades=specialties,
    )
