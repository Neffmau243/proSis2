"""Care-configuration administration; clinical read catalogs keep their contracts."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, require_permissions
from app.domain.authorization import Permissions
from app.schemas.care_configuration import (
    AreaAdminItem,
    AreaName,
    EstablishmentAdminItem,
    EstablishmentFields,
    EstablishmentUpdate,
)
from app.schemas.common import PageResponse
from app.services.audit import AuditService
from app.services.care_configuration import AreaAdministration, EstablishmentAdministration

router = APIRouter(prefix="/configuracion", tags=["Configuración de atención"])
Database = Annotated[Session, Depends(get_db)]
# Reuse the existing care-configuration permission: no new role or clinical grants.
Administrator = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.OFFICE_MANAGE))
]


@router.get("/establecimientos", response_model=PageResponse[EstablishmentAdminItem])
def establishments(
    _: Administrator,
    db: Database,
    q: str | None = Query(None, max_length=100),
    incluir_inactivos: bool = False,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return EstablishmentAdministration(db).list(
        query=q, include_inactive=incluir_inactivos, limit=limit, offset=offset
    )


@router.get("/establecimientos/{identifier}", response_model=EstablishmentAdminItem)
def establishment(identifier: int, _: Administrator, db: Database):
    return EstablishmentAdministration(db).get(identifier)


@router.post(
    "/establecimientos", response_model=EstablishmentAdminItem, status_code=status.HTTP_201_CREATED
)
def create_establishment(command: EstablishmentFields, principal: Administrator, db: Database):
    return EstablishmentAdministration(db, AuditService(db).record).save(
        command, actor_id=principal.user_id
    )


@router.patch("/establecimientos/{identifier}", response_model=EstablishmentAdminItem)
def update_establishment(
    identifier: int, command: EstablishmentUpdate, principal: Administrator, db: Database
):
    return EstablishmentAdministration(db, AuditService(db).record).save(
        command, identifier=identifier, actor_id=principal.user_id
    )


@router.delete("/establecimientos/{identifier}", response_model=EstablishmentAdminItem)
def deactivate_establishment(identifier: int, principal: Administrator, db: Database):
    return EstablishmentAdministration(db, AuditService(db).record).set_active(
        identifier, False, actor_id=principal.user_id
    )


@router.post("/establecimientos/{identifier}/reactivar", response_model=EstablishmentAdminItem)
def reactivate_establishment(identifier: int, principal: Administrator, db: Database):
    return EstablishmentAdministration(db, AuditService(db).record).set_active(
        identifier, True, actor_id=principal.user_id
    )


@router.get("/areas", response_model=list[AreaAdminItem])
def areas(_: Administrator, db: Database, incluir_inactivos: bool = False):
    return AreaAdministration(db).list(include_inactive=incluir_inactivos)


@router.post("/areas", response_model=AreaAdminItem, status_code=status.HTTP_201_CREATED)
def create_area(command: AreaName, principal: Administrator, db: Database):
    return AreaAdministration(db, AuditService(db).record).save(command, actor_id=principal.user_id)


@router.patch("/areas/{code}", response_model=AreaAdminItem)
def update_area(code: str, command: AreaName, principal: Administrator, db: Database):
    return AreaAdministration(db, AuditService(db).record).save(
        command, code=code, actor_id=principal.user_id
    )


@router.delete("/areas/{code}", response_model=AreaAdminItem)
def deactivate_area(code: str, principal: Administrator, db: Database):
    return AreaAdministration(db, AuditService(db).record).set_active(
        code, False, actor_id=principal.user_id
    )


@router.post("/areas/{code}/reactivar", response_model=AreaAdminItem)
def reactivate_area(code: str, principal: Administrator, db: Database):
    return AreaAdministration(db, AuditService(db).record).set_active(
        code, True, actor_id=principal.user_id
    )
