"""Explicit model-to-DTO mappings for public reference catalogs."""

from __future__ import annotations

from app.domain.office import AREA_NAMES, areas_for_service
from app.domain.staff_catalog import is_care_area
from app.mappers.office import office_to_response
from app.models.catalog import (
    AgeGroup,
    AttentionMode,
    Cie10,
    DocumentType,
    FamilyHistoryPrefix,
    Insurance,
    Profession,
    ServiceOffering,
    Sex,
    Specialty,
)
from app.models.organization import Establishment, Localidad, Office, Ubigeo
from app.models.patient import RiskGroup
from app.models.security import Professional
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


def document_type_to_catalog_item(entity: DocumentType) -> CodeCatalogItem:
    return CodeCatalogItem(codigo=entity.codigo, nombre=entity.nombre, activo=entity.activo)


def sex_to_catalog_item(entity: Sex) -> CodeCatalogItem:
    return CodeCatalogItem(codigo=entity.codigo, nombre=entity.nombre, activo=entity.activo)


def insurance_to_catalog_item(entity: Insurance) -> InsuranceCatalogItem:
    return InsuranceCatalogItem(
        id=entity.id,
        codigo=entity.codigo,
        nombre=entity.nombre,
        activo=entity.activo,
        codigo_sis=entity.codigo_sis,
        regimen=entity.regimen,
    )


def family_history_to_catalog_item(entity: FamilyHistoryPrefix) -> FamilyHistoryCatalogItem:
    return FamilyHistoryCatalogItem(
        codigo=entity.codigo,
        nombre=entity.nombre,
        tipo=entity.tipo,
        color_hex=entity.color_hex,
        activo=entity.activo,
    )


def profession_to_catalog_item(entity: Profession) -> IdCatalogItem:
    return IdCatalogItem(
        id=entity.id, codigo=str(entity.id), nombre=entity.nombre, activo=entity.activo
    )


def specialty_to_catalog_item(entity: Specialty) -> SpecialtyCatalogItem:
    return SpecialtyCatalogItem(
        codigo=entity.codigo,
        nombre=entity.nombre,
        grupo=entity.grupo,
        activo=entity.activo,
        area_codigos=[entity.codigo] if is_care_area(entity) else areas_for_service(entity.codigo),
        es_area=is_care_area(entity),
        es_area_base=entity.codigo in AREA_NAMES,
    )


def attention_mode_to_catalog_item(entity: AttentionMode) -> CodeCatalogItem:
    return CodeCatalogItem(codigo=entity.codigo, nombre=entity.nombre, activo=entity.activo)


def age_group_to_catalog_item(entity: AgeGroup) -> AgeGroupCatalogItem:
    return AgeGroupCatalogItem(
        codigo=entity.codigo,
        nombre=entity.nombre,
        edad_minima_meses=entity.edad_minima_meses,
        edad_maxima_meses=entity.edad_maxima_meses,
        activo=entity.activo,
    )


def risk_group_to_catalog_item(entity: RiskGroup) -> RiskGroupCatalogItem:
    from app.domain.nutrition_followup import group_kind

    return RiskGroupCatalogItem(
        tipo=group_kind(entity.codigo),
        id=entity.id,
        codigo=entity.codigo,
        nombre=entity.nombre,
        descripcion=entity.descripcion,
        activo=entity.activo,
    )


def service_to_catalog_item(entity: ServiceOffering) -> ServiceCatalogItem:
    return ServiceCatalogItem(
        codigo=entity.codigo,
        descripcion=entity.descripcion,
        grupo=entity.grupo,
        activo=entity.activo,
    )


def cie10_to_catalog_item(entity: Cie10) -> Cie10CatalogItem:
    return Cie10CatalogItem(
        codigo=entity.codigo,
        descripcion=entity.descripcion,
        categoria=entity.categoria,
        activo=entity.activo,
    )


def establishment_to_catalog_item(entity: Establishment) -> EstablishmentCatalogItem:
    return EstablishmentCatalogItem(
        id=entity.id,
        codigo_renaes=entity.codigo_renaes,
        codigo_ideess=entity.codigo_ideess,
        disa_codigo=entity.disa_codigo,
        nombre=entity.nombre,
        abreviatura=entity.abreviatura,
        ubigeo_codigo=getattr(entity, "ubigeo_codigo", None),
        distrito=getattr(getattr(entity, "ubigeo", None), "distrito", None),
        provincia=getattr(getattr(entity, "ubigeo", None), "provincia", None),
        departamento=getattr(getattr(entity, "ubigeo", None), "departamento", None),
        activo=entity.activo,
    )


def office_to_catalog_item(
    entity: Office, specialties: dict[str, str] | None = None
) -> OfficeCatalogItem:
    return OfficeCatalogItem.model_validate(office_to_response(entity, specialties).model_dump())


def professional_to_catalog_item(entity: Professional) -> ProfessionalCatalogItem:
    return ProfessionalCatalogItem(
        id=entity.id,
        nombre_completo=entity.nombre_completo,
        colegiatura=entity.colegiatura,
        activo=entity.activo,
    )


def ubigeo_to_catalog_item(entity: Ubigeo) -> UbigeoCatalogItem:
    # The SIS trama splits the six-digit UBIGEO into province (4) + district (2).
    codigo = entity.codigo or ""
    return UbigeoCatalogItem(
        codigo=entity.codigo,
        departamento=entity.departamento,
        provincia=entity.provincia,
        distrito=entity.distrito,
        localidad=entity.localidad,
        sis_provincia=codigo[:4] or None,
        sis_distrito=codigo[4:6] or None,
    )


def localidad_to_catalog_item(entity: Localidad) -> LocalidadCatalogItem:
    return LocalidadCatalogItem(
        id=entity.id,
        ubigeo_codigo=entity.ubigeo_codigo,
        codigo_catalogo=entity.codigo_catalogo,
        codigo_sis=entity.codigo_sis,
        nombre=entity.nombre,
        activo=entity.activo,
    )
