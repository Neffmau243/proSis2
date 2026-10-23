"""Administrative catalog for the care services offered by offices."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, require_permissions
from app.domain.authorization import Permissions
from app.schemas.office_service import CareServiceCreate, CareServiceItem, CareServiceUpdate
from app.services.audit import AuditService
from app.services.care_service_catalog import CareServiceCatalog

router = APIRouter(prefix="/configuracion/servicios", tags=["Configuración"])
DatabaseSession = Annotated[Session, Depends(get_db)]
Administrator = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.OFFICE_MANAGE))
]


@router.get("", response_model=list[CareServiceItem])
def list_services(
    _: Administrator, db: DatabaseSession, incluir_inactivos: bool = False
) -> list[CareServiceItem]:
    return CareServiceCatalog(db).list(include_inactive=incluir_inactivos)


@router.post("", response_model=CareServiceItem, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: CareServiceCreate, principal: Administrator, db: DatabaseSession
) -> CareServiceItem:
    return CareServiceCatalog(db, AuditService(db).record).create(
        payload, actor_id=principal.user_id
    )


@router.get("/{code}", response_model=CareServiceItem)
def get_service(code: str, _: Administrator, db: DatabaseSession) -> CareServiceItem:
    return CareServiceCatalog(db).get(code)


@router.patch("/{code}", response_model=CareServiceItem)
def update_service(
    code: str, payload: CareServiceUpdate, principal: Administrator, db: DatabaseSession
) -> CareServiceItem:
    return CareServiceCatalog(db, AuditService(db).record).update(
        code, payload, actor_id=principal.user_id
    )


@router.delete("/{code}", response_model=CareServiceItem)
def deactivate_service(code: str, principal: Administrator, db: DatabaseSession) -> CareServiceItem:
    return CareServiceCatalog(db, AuditService(db).record).set_active(
        code, False, actor_id=principal.user_id
    )


@router.post("/{code}/reactivar", response_model=CareServiceItem)
def reactivate_service(code: str, principal: Administrator, db: DatabaseSession) -> CareServiceItem:
    return CareServiceCatalog(db, AuditService(db).record).set_active(
        code, True, actor_id=principal.user_id
    )
