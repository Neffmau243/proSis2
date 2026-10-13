"""HTTP adapter for scoped, paginated attention-history discovery."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, require_permissions
from app.domain.authorization import Permissions
from app.schemas.attention import AttentionResponse, AttentionStatus
from app.schemas.common import PageResponse
from app.schemas.discovery import AttentionSearchCriteria
from app.services.discovery import AttentionDiscoveryService

router = APIRouter(prefix="/atenciones", tags=["Atenciones"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AttentionReader = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions(Permissions.ATTENTION_READ)),
]


@router.get(
    "/busqueda",
    response_model=PageResponse[AttentionResponse],
    summary="Buscar historial de atenciones",
)
def search_attentions(
    principal: AttentionReader,
    db: DatabaseSession,
    paciente_id: Annotated[int | None, Query(gt=0)] = None,
    consultorio_id: Annotated[int | None, Query(gt=0)] = None,
    establecimiento_id: Annotated[int | None, Query(gt=0)] = None,
    profesional_id: Annotated[int | None, Query(gt=0)] = None,
    desde: date | None = None,
    hasta: date | None = None,
    fecha_hora_desde: datetime | None = None,
    fecha_hora_hasta: datetime | None = None,
    estado: AttentionStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageResponse[AttentionResponse]:
    try:
        criteria = AttentionSearchCriteria(
            paciente_id=paciente_id,
            consultorio_id=consultorio_id,
            establecimiento_id=establecimiento_id,
            profesional_id=profesional_id,
            desde=desde,
            hasta=hasta,
            fecha_hora_desde=fecha_hora_desde,
            fecha_hora_hasta=fecha_hora_hasta,
            estado=estado,
            limit=limit,
            offset=offset,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return AttentionDiscoveryService(db).search(
        criteria,
        actor_id=principal.user_id,
        actor_roles=principal.roles,
    )
