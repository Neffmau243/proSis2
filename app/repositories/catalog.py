"""Read-only persistence queries for API reference catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.catalog import (
    AgeGroup,
    AttentionMode,
    Cie10,
    DocumentType,
    Ethnicity,
    Insurance,
    Profession,
    ServiceOffering,
    Sex,
    Specialty,
)
from app.models.organization import Establishment, Localidad, Office, Ubigeo
from app.models.patient import Patient, RiskGroup
from app.models.security import Professional


EntityT = TypeVar("EntityT")


@dataclass(frozen=True, slots=True)
class CatalogPage(Generic[EntityT]):
    """Persistence result before it is mapped to a public page DTO."""

    items: list[EntityT]
    total: int


class CatalogRepository:
    """Queries only; catalog authorization and mapping remain in upper layers."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_document_types(self) -> list[DocumentType]:
        return self._list_active(DocumentType, DocumentType.codigo)

    def list_sexes(self) -> list[Sex]:
        return self._list_active(Sex, Sex.codigo)

    def list_ethnicities(self) -> list[Ethnicity]:
        return self._list_active(Ethnicity, Ethnicity.nombre)

    def list_insurances(self) -> list[Insurance]:
        return self._list_active(Insurance, Insurance.nombre, Insurance.id)

    def list_professions(self) -> list[Profession]:
        return self._list_active(Profession, Profession.nombre, Profession.id)

    def list_specialties(self) -> list[Specialty]:
        return self._list_active(Specialty, Specialty.nombre, Specialty.codigo)

    def list_attention_modes(self) -> list[AttentionMode]:
        return self._list_active(AttentionMode, AttentionMode.codigo)

    def list_age_groups(self) -> list[AgeGroup]:
        return self._list_active(AgeGroup, AgeGroup.edad_minima_meses, AgeGroup.codigo)

    def list_risk_groups(self) -> list[RiskGroup]:
        return self._list_active(RiskGroup, RiskGroup.nombre, RiskGroup.id)

    def page_family_histories(
        self, *, query: str | None, limit: int, offset: int
    ) -> CatalogPage[str]:
        """Return the reusable, non-empty family codes already in the register."""

        code = func.trim(Patient.historia_familiar)
        conditions = [
            Patient.estado.is_(True),
            Patient.historia_familiar.is_not(None),
            code != "",
        ]
        if query:
            conditions.append(code.ilike(self._contains_pattern(query), escape="\\"))
        statement = select(code).where(*conditions).distinct().order_by(code)
        count_statement = select(func.count(func.distinct(code))).where(*conditions)
        return CatalogPage(
            items=list(self._session.scalars(statement.limit(limit).offset(offset))),
            total=int(self._session.scalar(count_statement) or 0),
        )

    def page_services(self, *, query: str | None, limit: int, offset: int) -> CatalogPage[ServiceOffering]:
        conditions = [ServiceOffering.activo.is_(True)]
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    ServiceOffering.codigo.ilike(pattern, escape="\\"),
                    ServiceOffering.descripcion.ilike(pattern, escape="\\"),
                    ServiceOffering.grupo.ilike(pattern, escape="\\"),
                )
            )
        statement = select(ServiceOffering).where(*conditions).order_by(ServiceOffering.codigo)
        count_statement = select(func.count()).select_from(ServiceOffering).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def page_cie10(self, *, query: str | None, limit: int, offset: int) -> CatalogPage[Cie10]:
        conditions = [Cie10.activo.is_(True)]
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    Cie10.codigo.ilike(pattern, escape="\\"),
                    Cie10.descripcion.ilike(pattern, escape="\\"),
                    Cie10.categoria.ilike(pattern, escape="\\"),
                )
            )
        statement = select(Cie10).where(*conditions).order_by(Cie10.codigo)
        count_statement = select(func.count()).select_from(Cie10).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def page_establishments(
        self, *, query: str | None, limit: int, offset: int
    ) -> CatalogPage[Establishment]:
        conditions = [Establishment.activo.is_(True)]
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    Establishment.nombre.ilike(pattern, escape="\\"),
                    Establishment.abreviatura.ilike(pattern, escape="\\"),
                    Establishment.codigo_renaes.ilike(pattern, escape="\\"),
                    Establishment.codigo_ideess.ilike(pattern, escape="\\"),
                )
            )
        statement = select(Establishment).where(*conditions).order_by(Establishment.nombre, Establishment.id)
        count_statement = select(func.count()).select_from(Establishment).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def page_offices(
        self,
        *,
        establishment_id: int | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> CatalogPage[Office]:
        conditions = [Office.activo.is_(True)]
        if establishment_id is not None:
            conditions.append(Office.establecimiento_id == establishment_id)
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    Office.codigo.ilike(pattern, escape="\\"),
                    Office.nombre.ilike(pattern, escape="\\"),
                )
            )
        statement = select(Office).where(*conditions).order_by(Office.establecimiento_id, Office.codigo)
        count_statement = select(func.count()).select_from(Office).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def page_professionals(
        self, *, query: str | None, limit: int, offset: int
    ) -> CatalogPage[Professional]:
        conditions = [Professional.activo.is_(True)]
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    Professional.nombre_completo.ilike(pattern, escape="\\"),
                    Professional.numero_documento.ilike(pattern, escape="\\"),
                    Professional.colegiatura.ilike(pattern, escape="\\"),
                )
            )
        statement = select(Professional).where(*conditions).order_by(Professional.nombre_completo, Professional.id)
        count_statement = select(func.count()).select_from(Professional).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def page_ubigeos(self, *, query: str | None, limit: int, offset: int) -> CatalogPage[Ubigeo]:
        conditions: list[Any] = []
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    Ubigeo.codigo.ilike(pattern, escape="\\"),
                    Ubigeo.departamento.ilike(pattern, escape="\\"),
                    Ubigeo.provincia.ilike(pattern, escape="\\"),
                    Ubigeo.distrito.ilike(pattern, escape="\\"),
                    Ubigeo.localidad.ilike(pattern, escape="\\"),
                )
            )
        statement = select(Ubigeo).where(*conditions).order_by(
            Ubigeo.departamento,
            Ubigeo.provincia,
            Ubigeo.distrito,
            Ubigeo.codigo,
        )
        count_statement = select(func.count()).select_from(Ubigeo).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def page_localities(
        self,
        *,
        ubigeo_codigo: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> CatalogPage[Localidad]:
        conditions: list[Any] = [Localidad.activo.is_(True)]
        if ubigeo_codigo:
            conditions.append(Localidad.ubigeo_codigo == ubigeo_codigo)
        if query:
            pattern = self._contains_pattern(query)
            conditions.append(
                or_(
                    Localidad.nombre.ilike(pattern, escape="\\"),
                    Localidad.codigo_sis.ilike(pattern, escape="\\"),
                )
            )
        statement = select(Localidad).where(*conditions).order_by(Localidad.nombre, Localidad.id)
        count_statement = select(func.count()).select_from(Localidad).where(*conditions)
        return self._page(statement, count_statement, limit=limit, offset=offset)

    def _list_active(self, model: type[EntityT], *order_by: Any) -> list[EntityT]:
        statement = select(model).where(model.activo.is_(True)).order_by(*order_by)
        return list(self._session.scalars(statement))

    def _page(
        self,
        statement: Select[tuple[EntityT]],
        count_statement: Select[tuple[int]],
        *,
        limit: int,
        offset: int,
    ) -> CatalogPage[EntityT]:
        return CatalogPage(
            items=list(self._session.scalars(statement.limit(limit).offset(offset))),
            total=int(self._session.scalar(count_statement) or 0),
        )

    @staticmethod
    def _contains_pattern(value: str) -> str:
        """Build a literal LIKE search pattern, not a user-controlled wildcard."""

        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"
