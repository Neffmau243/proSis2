"""Authenticated, read-only endpoints for frontend reference catalogs."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, get_current_principal
from app.schemas.catalog import (
    AgeGroupCatalogItem,
    Cie10CatalogItem,
    CodeCatalogItem,
    EstablishmentCatalogItem,
    FamilyHistoryCatalogItem,
    IdCatalogItem,
    InsuranceCatalogItem,
    LocalidadCatalogItem,
    OfficeCatalogItem,
    ProfessionalCatalogItem,
    RiskGroupCatalogItem,
    ServiceCatalogItem,
    SpecialtyCatalogItem,
    UbigeoCatalogItem,
)
from app.schemas.common import PageResponse
from app.services.catalog import CatalogService

router = APIRouter(prefix="/catalogos", tags=["Catálogos"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CatalogReader = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
SearchText = Annotated[str | None, Query(min_length=2, max_length=100)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/tipos-documento", response_model=list[CodeCatalogItem])
def list_document_types(_: CatalogReader, db: DatabaseSession) -> list[CodeCatalogItem]:
    return CatalogService(db).document_types()


@router.get("/sexos", response_model=list[CodeCatalogItem])
def list_sexes(_: CatalogReader, db: DatabaseSession) -> list[CodeCatalogItem]:
    return CatalogService(db).sexes()


@router.get("/etnias", response_model=list[CodeCatalogItem])
def list_ethnicities(_: CatalogReader, db: DatabaseSession) -> list[CodeCatalogItem]:
    return CatalogService(db).ethnicities()


@router.get("/seguros", response_model=list[InsuranceCatalogItem])
def list_insurances(_: CatalogReader, db: DatabaseSession) -> list[InsuranceCatalogItem]:
    return CatalogService(db).insurances()


@router.get("/profesiones", response_model=list[IdCatalogItem])
def list_professions(_: CatalogReader, db: DatabaseSession) -> list[IdCatalogItem]:
    return CatalogService(db).professions()


@router.get("/especialidades", response_model=list[SpecialtyCatalogItem])
def list_specialties(_: CatalogReader, db: DatabaseSession) -> list[SpecialtyCatalogItem]:
    return CatalogService(db).specialties()


@router.get("/modalidades-atencion", response_model=list[CodeCatalogItem])
def list_attention_modes(_: CatalogReader, db: DatabaseSession) -> list[CodeCatalogItem]:
    return CatalogService(db).attention_modes()


@router.get("/grupos-etarios", response_model=list[AgeGroupCatalogItem])
def list_age_groups(_: CatalogReader, db: DatabaseSession) -> list[AgeGroupCatalogItem]:
    return CatalogService(db).age_groups()


@router.get("/grupos-riesgo", response_model=list[RiskGroupCatalogItem])
def list_risk_groups(_: CatalogReader, db: DatabaseSession) -> list[RiskGroupCatalogItem]:
    return CatalogService(db).risk_groups()


@router.get("/historias-familiares", response_model=PageResponse[FamilyHistoryCatalogItem])
def list_family_histories(
    _: CatalogReader,
    db: DatabaseSession,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[FamilyHistoryCatalogItem]:
    return CatalogService(db).family_histories(query=q, limit=limit, offset=offset)


@router.get("/prestaciones", response_model=PageResponse[ServiceCatalogItem])
def list_services(
    _: CatalogReader,
    db: DatabaseSession,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[ServiceCatalogItem]:
    return CatalogService(db).services(query=q, limit=limit, offset=offset)


@router.get("/cie10", response_model=PageResponse[Cie10CatalogItem])
def list_cie10(
    _: CatalogReader,
    db: DatabaseSession,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[Cie10CatalogItem]:
    return CatalogService(db).cie10(query=q, limit=limit, offset=offset)


@router.get("/establecimientos", response_model=PageResponse[EstablishmentCatalogItem])
def list_establishments(
    _: CatalogReader,
    db: DatabaseSession,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[EstablishmentCatalogItem]:
    return CatalogService(db).establishments(query=q, limit=limit, offset=offset)


@router.get("/consultorios", response_model=PageResponse[OfficeCatalogItem])
def list_offices(
    _: CatalogReader,
    db: DatabaseSession,
    establecimiento_id: Annotated[int | None, Query(gt=0)] = None,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[OfficeCatalogItem]:
    return CatalogService(db).offices(
        establishment_id=establecimiento_id,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/profesionales", response_model=PageResponse[ProfessionalCatalogItem])
def list_professionals(
    _: CatalogReader,
    db: DatabaseSession,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
    consultorio_id: Annotated[int | None, Query(gt=0)] = None,
    fecha: date | None = None,
    servicio_codigo: str | None = None,
) -> PageResponse[ProfessionalCatalogItem]:
    return CatalogService(db).professionals(
        query=q,
        limit=limit,
        offset=offset,
        office_id=consultorio_id,
        on_date=fecha,
        service_code=servicio_codigo,
    )


@router.get("/localidades", response_model=PageResponse[LocalidadCatalogItem])
def list_localities(
    _: CatalogReader,
    db: DatabaseSession,
    ubigeo_codigo: Annotated[str | None, Query(min_length=6, max_length=6)] = None,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[LocalidadCatalogItem]:
    return CatalogService(db).localities(
        ubigeo_codigo=ubigeo_codigo,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/ubigeos", response_model=PageResponse[UbigeoCatalogItem])
def list_ubigeos(
    _: CatalogReader,
    db: DatabaseSession,
    q: SearchText = None,
    limit: PageLimit = 25,
    offset: PageOffset = 0,
) -> PageResponse[UbigeoCatalogItem]:
    return CatalogService(db).ubigeos(query=q, limit=limit, offset=offset)
