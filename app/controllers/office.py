"""HTTP endpoints for managing office-professional assignments."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, require_permissions
from app.domain.authorization import Permissions
from app.exceptions import AuthorizationError
from app.schemas.office import (
    OfficeAssignmentClose,
    OfficeAssignmentCreate,
    OfficeAssignmentResponse,
    OfficeCreate,
    OfficeResponse,
    OfficeUpdate,
)
from app.services.audit import AuditService
from app.services.office import OfficeAssignmentService, OfficeService

router = APIRouter(prefix="/configuracion/consultorios", tags=["Configuración"])
DatabaseSession = Annotated[Session, Depends(get_db)]
OfficeAdministrator = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.OFFICE_MANAGE))
]


@router.get("", response_model=list[OfficeResponse])
def list_offices(
    _: OfficeAdministrator,
    db: DatabaseSession,
    establecimiento_id: int | None = Query(default=None, gt=0),
    incluir_inactivos: bool = Query(default=False),
) -> list[OfficeResponse]:
    return OfficeService(db).list(
        establishment_id=establecimiento_id,
        include_inactive=incluir_inactivos,
    )


@router.get("/{office_id}", response_model=OfficeResponse)
def get_office(office_id: int, _: OfficeAdministrator, db: DatabaseSession) -> OfficeResponse:
    return OfficeService(db).get(office_id)


@router.post("", response_model=OfficeResponse, status_code=status.HTTP_201_CREATED)
def create_office(
    payload: OfficeCreate,
    principal: OfficeAdministrator,
    db: DatabaseSession,
) -> OfficeResponse:
    return OfficeService(db, audit=AuditService(db).record).create(
        payload,
        actor_id=principal.user_id,
    )


@router.patch("/{office_id}", response_model=OfficeResponse)
def update_office(
    office_id: int,
    payload: OfficeUpdate,
    principal: OfficeAdministrator,
    db: DatabaseSession,
) -> OfficeResponse:
    return OfficeService(db, audit=AuditService(db).record).update(
        office_id,
        payload,
        actor_id=principal.user_id,
    )


@router.delete("/{office_id}", response_model=OfficeResponse)
def deactivate_office(
    office_id: int,
    principal: OfficeAdministrator,
    db: DatabaseSession,
) -> OfficeResponse:
    return OfficeService(db, audit=AuditService(db).record).deactivate(
        office_id,
        actor_id=principal.user_id,
    )


@router.get("/{office_id}/profesionales", response_model=list[OfficeAssignmentResponse])
def list_assignments(
    office_id: int,
    _: OfficeAdministrator,
    db: DatabaseSession,
) -> list[OfficeAssignmentResponse]:
    return OfficeAssignmentService(db).list(office_id)


@router.post(
    "/{office_id}/profesionales",
    response_model=OfficeAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_professional(
    office_id: int,
    payload: OfficeAssignmentCreate,
    principal: OfficeAdministrator,
    db: DatabaseSession,
) -> OfficeAssignmentResponse:
    if payload.vincular_area and Permissions.PROFESSIONAL_MANAGE not in principal.permissions:
        raise AuthorizationError("Necesita permiso de gestión de personal para vincular el área.")
    return OfficeAssignmentService(db).assign(office_id, payload, actor_id=principal.user_id)


@router.patch(
    "/{office_id}/profesionales/{professional_id}/{start_date}/cierre",
    response_model=OfficeAssignmentResponse,
)
def close_assignment(
    office_id: int,
    professional_id: int,
    start_date: date,
    payload: OfficeAssignmentClose,
    principal: OfficeAdministrator,
    db: DatabaseSession,
) -> OfficeAssignmentResponse:
    return OfficeAssignmentService(db).close(
        office_id,
        professional_id,
        start_date,
        payload,
        actor_id=principal.user_id,
    )
