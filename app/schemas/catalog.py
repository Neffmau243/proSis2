"""Read-only API contracts for form and reference catalogs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodeCatalogItem(BaseModel):
    codigo: str
    nombre: str
    activo: bool


class IdCatalogItem(BaseModel):
    id: int = Field(gt=0)
    codigo: str
    nombre: str
    activo: bool


class SpecialtyCatalogItem(CodeCatalogItem):
    grupo: str | None = None
    area_codigos: list[str] = Field(default_factory=list)
    es_area: bool = False


class InsuranceCatalogItem(IdCatalogItem):
    """Insurance plan plus the SIS territory codes it maps to."""

    codigo_sis: str | None = None
    regimen: str | None = None


class FamilyHistoryCatalogItem(BaseModel):
    """Prefix that can be combined with the local numeric family identifier."""

    codigo: str = Field(min_length=2, max_length=4)
    nombre: str
    tipo: str
    color_hex: str | None = None
    activo: bool


class LocalidadCatalogItem(BaseModel):
    """A district locality; internal lookup code and source export key differ."""

    id: int = Field(gt=0)
    ubigeo_codigo: str
    codigo_catalogo: str
    codigo_sis: str | None = None
    nombre: str
    activo: bool


class ServiceCatalogItem(BaseModel):
    codigo: str
    descripcion: str
    grupo: str | None = None
    activo: bool


class Cie10CatalogItem(BaseModel):
    codigo: str
    descripcion: str
    categoria: str | None = None
    activo: bool


class AgeGroupCatalogItem(CodeCatalogItem):
    edad_minima_meses: int | None = Field(default=None, ge=0)
    edad_maxima_meses: int | None = Field(default=None, ge=0)


class RiskGroupCatalogItem(IdCatalogItem):
    descripcion: str | None = None
    tipo: str = "RIESGO"


class EstablishmentCatalogItem(BaseModel):
    id: int = Field(gt=0)
    codigo_renaes: str | None = None
    codigo_ideess: str | None = None
    disa_codigo: str | None = None
    nombre: str
    abreviatura: str | None = None
    ubigeo_codigo: str | None = None
    distrito: str | None = None
    provincia: str | None = None
    departamento: str | None = None
    activo: bool


class OfficeCatalogItem(BaseModel):
    id: int = Field(gt=0)
    establecimiento_id: int = Field(gt=0)
    codigo: str
    nombre: str
    especialidad_codigo: str | None = None
    activo: bool
    consultorio_padre_id: int | None = None
    area_codigo: str | None = None
    area_nombre: str | None = None
    ruta: str = ""
    activo_efectivo: bool = True
    servicios_habilitados: list[CodeCatalogItem] = Field(default_factory=list)


class ProfessionalCatalogItem(BaseModel):
    id: int = Field(gt=0)
    nombre_completo: str
    colegiatura: str | None = None
    activo: bool


class UbigeoCatalogItem(BaseModel):
    codigo: str
    departamento: str
    provincia: str
    distrito: str
    localidad: str | None = None
    #: Códigos derivados del UBIGEO de seis dígitos para la trama SIS.
    sis_provincia: str | None = None
    sis_distrito: str | None = None
