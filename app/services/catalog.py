"""Application use cases for read-only reference catalogs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import TypeVar

from sqlalchemy.orm import Session

from app.mappers.catalog import (
    age_group_to_catalog_item,
    attention_mode_to_catalog_item,
    cie10_to_catalog_item,
    document_type_to_catalog_item,
    establishment_to_catalog_item,
    family_history_to_catalog_item,
    insurance_to_catalog_item,
    localidad_to_catalog_item,
    office_to_catalog_item,
    profession_to_catalog_item,
    professional_to_catalog_item,
    risk_group_to_catalog_item,
    service_to_catalog_item,
    sex_to_catalog_item,
    specialty_to_catalog_item,
    ubigeo_to_catalog_item,
)
from app.repositories.catalog import CatalogPage, CatalogRepository
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

SourceT = TypeVar("SourceT")
ResultT = TypeVar("ResultT")


class CatalogService:
    """Maps active reference data into safe, frontend-ready DTOs."""

    def __init__(self, session: Session, *, repository: CatalogRepository | None = None) -> None:
        self._repository = repository or CatalogRepository(session)

    def document_types(self) -> list[CodeCatalogItem]:
        return [
            document_type_to_catalog_item(item) for item in self._repository.list_document_types()
        ]

    def sexes(self) -> list[CodeCatalogItem]:
        return [sex_to_catalog_item(item) for item in self._repository.list_sexes()]

    def ethnicities(self) -> list[CodeCatalogItem]:
        return [
            CodeCatalogItem(codigo=item.codigo, nombre=item.nombre, activo=item.activo)
            for item in self._repository.list_ethnicities()
        ]

    def insurances(self) -> list[InsuranceCatalogItem]:
        return [insurance_to_catalog_item(item) for item in self._repository.list_insurances()]

    def professions(self) -> list[IdCatalogItem]:
        return [profession_to_catalog_item(item) for item in self._repository.list_professions()]

    def specialties(self) -> list[SpecialtyCatalogItem]:
        return [specialty_to_catalog_item(item) for item in self._repository.list_specialties()]

    def attention_modes(self) -> list[CodeCatalogItem]:
        return [
            attention_mode_to_catalog_item(item) for item in self._repository.list_attention_modes()
        ]

    def age_groups(self) -> list[AgeGroupCatalogItem]:
        return [age_group_to_catalog_item(item) for item in self._repository.list_age_groups()]

    def risk_groups(self) -> list[RiskGroupCatalogItem]:
        return [risk_group_to_catalog_item(item) for item in self._repository.list_risk_groups()]

    def family_histories(
        self, *, query: str | None, limit: int, offset: int
    ) -> PageResponse[FamilyHistoryCatalogItem]:
        page = self._repository.page_family_histories(
            query=self._normalized_query(query), limit=limit, offset=offset
        )
        return self._page(
            page,
            family_history_to_catalog_item,
            limit=limit,
            offset=offset,
        )

    def services(
        self, *, query: str | None, limit: int, offset: int
    ) -> PageResponse[ServiceCatalogItem]:
        page = self._repository.page_services(
            query=self._normalized_query(query), limit=limit, offset=offset
        )
        return self._page(page, service_to_catalog_item, limit=limit, offset=offset)

    def cie10(
        self, *, query: str | None, limit: int, offset: int
    ) -> PageResponse[Cie10CatalogItem]:
        page = self._repository.page_cie10(
            query=self._normalized_query(query), limit=limit, offset=offset
        )
        return self._page(page, cie10_to_catalog_item, limit=limit, offset=offset)

    def establishments(
        self, *, query: str | None, limit: int, offset: int
    ) -> PageResponse[EstablishmentCatalogItem]:
        page = self._repository.page_establishments(
            query=self._normalized_query(query), limit=limit, offset=offset
        )
        return self._page(page, establishment_to_catalog_item, limit=limit, offset=offset)

    def offices(
        self,
        *,
        establishment_id: int | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> PageResponse[OfficeCatalogItem]:
        page = self._repository.page_offices(
            establishment_id=establishment_id,
            query=self._normalized_query(query),
            limit=limit,
            offset=offset,
        )
        names = {item.codigo: item.nombre for item in self._repository.list_specialties()}
        return self._page(
            page, lambda item: office_to_catalog_item(item, names), limit=limit, offset=offset
        )

    def professionals(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
        office_id: int | None = None,
        on_date: date | None = None,
    ) -> PageResponse[ProfessionalCatalogItem]:
        page = self._repository.page_professionals(
            query=self._normalized_query(query),
            limit=limit,
            offset=offset,
            office_id=office_id,
            on_date=on_date,
        )
        return self._page(page, professional_to_catalog_item, limit=limit, offset=offset)

    def localities(
        self,
        *,
        ubigeo_codigo: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> PageResponse[LocalidadCatalogItem]:
        page = self._repository.page_localities(
            ubigeo_codigo=ubigeo_codigo,
            query=self._normalized_query(query),
            limit=limit,
            offset=offset,
        )
        return self._page(page, localidad_to_catalog_item, limit=limit, offset=offset)

    def ubigeos(
        self, *, query: str | None, limit: int, offset: int
    ) -> PageResponse[UbigeoCatalogItem]:
        page = self._repository.page_ubigeos(
            query=self._normalized_query(query), limit=limit, offset=offset
        )
        return self._page(page, ubigeo_to_catalog_item, limit=limit, offset=offset)

    @staticmethod
    def _normalized_query(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _page(
        page: CatalogPage[SourceT],
        mapper: Callable[[SourceT], ResultT],
        *,
        limit: int,
        offset: int,
    ) -> PageResponse[ResultT]:
        # ``mapper`` is intentionally a simple callable.  Keeping the
        # repository generic lets each public catalog preserve its exact DTO.
        items = [mapper(item) for item in page.items]
        return PageResponse(
            items=items,
            total=page.total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < page.total,
        )
