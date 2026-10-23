"""Explicit catalog registration or enabling of one care service."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.catalog import CodeCatalogItem
from app.schemas.office import OfficeResponse


class OfficeServiceAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=2, max_length=150)] | None = None
    codigo: Annotated[str, Field(min_length=1, max_length=20)] | None = None

    @field_validator("nombre", "codigo", mode="before")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        return " ".join(value.split()).upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def exactly_one_identity(self) -> "OfficeServiceAdd":
        if (self.nombre is None) == (self.codigo is None):
            raise ValueError("Indique el código existente o el nombre del nuevo servicio.")
        return self


class OfficeServiceAdded(BaseModel):
    consultorio: OfficeResponse
    servicio: CodeCatalogItem


class CareServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Annotated[str, Field(min_length=2, max_length=150)]
    area_codigo: Annotated[str, Field(min_length=1, max_length=20)]

    @field_validator("nombre", "area_codigo", mode="before")
    @classmethod
    def normalize(cls, value: str) -> str:
        return OfficeServiceAdd.normalize(value)


class CareServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Annotated[str, Field(min_length=2, max_length=150)]

    @field_validator("nombre", mode="before")
    @classmethod
    def normalize(cls, value: str) -> str:
        return OfficeServiceAdd.normalize(value)


class CareServiceOffice(BaseModel):
    id: int
    nombre: str
    codigo: str = ""
    consultorio_padre_id: int | None = None
    consultorio_padre_nombre: str | None = None
    establecimiento_id: int
    establecimiento_nombre: str | None = None
    activo: bool


class CareServiceItem(CodeCatalogItem):
    area_codigos: list[str]
    consultorios: list[CareServiceOffice]
