"""Administrator-owned creation and renaming of staff catalog entries."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, require_permissions
from app.domain.authorization import Permissions
from app.schemas.catalog import IdCatalogItem, SpecialtyCatalogItem
from app.schemas.staff_catalog import (
    ProfessionCreate,
    ProfessionUpdate,
    SpecialtyCreate,
    SpecialtyUpdate,
)
from app.services.audit import AuditService
from app.services.staff_catalog import StaffCatalogService

router = APIRouter(prefix="/configuracion/catalogos-personal", tags=["Configuración"])
DatabaseSession = Annotated[Session, Depends(get_db)]
StaffAdministrator = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.PROFESSIONAL_MANAGE))
]


@router.post("/profesiones", response_model=IdCatalogItem, status_code=status.HTTP_201_CREATED)
def create_profession(
    payload: ProfessionCreate, principal: StaffAdministrator, db: DatabaseSession
) -> IdCatalogItem:
    return StaffCatalogService(db, audit=AuditService(db).record).create_profession(
        payload, actor_id=principal.user_id
    )


@router.post(
    "/especialidades", response_model=SpecialtyCatalogItem, status_code=status.HTTP_201_CREATED
)
def create_specialty(
    payload: SpecialtyCreate, principal: StaffAdministrator, db: DatabaseSession
) -> SpecialtyCatalogItem:
    return StaffCatalogService(db, audit=AuditService(db).record).create_specialty(
        payload, actor_id=principal.user_id
    )


@router.patch("/profesiones/{profession_id}", response_model=IdCatalogItem)
def update_profession(
    profession_id: int,
    payload: ProfessionUpdate,
    principal: StaffAdministrator,
    db: DatabaseSession,
) -> IdCatalogItem:
    return StaffCatalogService(db, audit=AuditService(db).record).update_profession(
        profession_id, payload, actor_id=principal.user_id
    )


@router.patch("/especialidades/{specialty_code}", response_model=SpecialtyCatalogItem)
def update_specialty(
    specialty_code: str,
    payload: SpecialtyUpdate,
    principal: StaffAdministrator,
    db: DatabaseSession,
) -> SpecialtyCatalogItem:
    return StaffCatalogService(db, audit=AuditService(db).record).update_specialty(
        specialty_code, payload, actor_id=principal.user_id
    )


@router.delete("/profesiones/{profession_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profession(
    profession_id: int, principal: StaffAdministrator, db: DatabaseSession
) -> None:
    StaffCatalogService(db, audit=AuditService(db).record).delete_profession(
        profession_id, actor_id=principal.user_id
    )


@router.delete("/especialidades/{specialty_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_specialty(
    specialty_code: str, principal: StaffAdministrator, db: DatabaseSession
) -> None:
    StaffCatalogService(db, audit=AuditService(db).record).delete_specialty(
        specialty_code, actor_id=principal.user_id
    )
