"""Administrative contracts kept separate from clinical reference catalogs."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EstablishmentFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Annotated[str, Field(min_length=2, max_length=200)]
    abreviatura: Annotated[str, Field(max_length=50)] | None = None
    codigo_renaes: Annotated[str, Field(max_length=30)] | None = None
    codigo_ideess: Annotated[str, Field(max_length=30)] | None = None
    ubigeo_codigo: Annotated[str, Field(pattern=r"^\d{6}$")] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return " ".join(value.split()) or None
        return value


class EstablishmentUpdate(EstablishmentFields):
    nombre: Annotated[str, Field(min_length=2, max_length=200)] = Field(default=None)

    @field_validator("nombre")
    @classmethod
    def name_cannot_be_cleared(cls, value: str) -> str:
        if value is None:
            raise ValueError("Ingrese el nombre del establecimiento.")
        return value


class EstablishmentAdminItem(EstablishmentFields):
    id: int
    activo: bool
    ubicacion: str | None
    consultorios_total: int
    # Read-only projection: ordinary administration never overwrites FUA defaults.
    fua_personal_atiende: str
    fua_lugar_atencion: str
    fua_codigo_aisped: str | None
    fua_renipress_preimpreso: bool


class AreaName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Annotated[str, Field(min_length=2, max_length=150)]

    @field_validator("nombre", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> Any:
        return " ".join(value.split()).upper() if isinstance(value, str) else value


class AreaOfficeUsage(BaseModel):
    id: int
    nombre: str
    establecimiento_id: int
    establecimiento_nombre: str
    activo: bool


class AreaAdminItem(BaseModel):
    codigo: str
    nombre: str
    activo: bool
    es_area_base: bool
    consultorios: list[AreaOfficeUsage]
