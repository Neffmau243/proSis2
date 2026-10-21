"""Contracts for care-office administration and professional assignments."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.catalog import CodeCatalogItem


class OfficeServicesInput(BaseModel):
    area_codigo: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    servicios_codigos: list[Annotated[str, Field(min_length=1, max_length=20)]] | None = None

    @field_validator("area_codigo", mode="before")
    @classmethod
    def normalize_area(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("servicios_codigos")
    @classmethod
    def normalize_services(cls, value: list[str] | None) -> list[str] | None:
        return (
            list(dict.fromkeys(code.strip().upper() for code in value))
            if value is not None
            else None
        )


class OfficeAssignmentCreate(BaseModel):
    profesional_id: int = Field(gt=0)
    fecha_inicio: date
    fecha_fin: date | None = None
    es_responsable: bool = False
    vincular_area: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> OfficeAssignmentCreate:
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        return self


class OfficeAssignmentClose(BaseModel):
    fecha_fin: date


class OfficeAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consultorio_id: int
    profesional_id: int
    fecha_inicio: date
    fecha_fin: date | None
    es_responsable: bool


class OfficeCreate(OfficeServicesInput):
    """Data an administrator may use to register an active care office."""

    establecimiento_id: Annotated[int, Field(gt=0)]
    codigo: Annotated[str, Field(min_length=1, max_length=30)]
    nombre: Annotated[str, Field(min_length=2, max_length=150)]
    consultorio_padre_id: Annotated[int, Field(gt=0)] | None = None
    especialidad_codigo: Annotated[str, Field(min_length=1, max_length=20)] | None = None

    @field_validator("codigo", "nombre", "especialidad_codigo", mode="before")
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("codigo", "especialidad_codigo", mode="after")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class OfficeUpdate(OfficeServicesInput):
    """Whitelisted mutations for an office; active state has a dedicated action."""

    codigo: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    nombre: Annotated[str, Field(min_length=2, max_length=150)] | None = None
    consultorio_padre_id: Annotated[int, Field(gt=0)] | None = None
    especialidad_codigo: Annotated[str, Field(min_length=1, max_length=20)] | None = None

    @field_validator("codigo", "nombre", "especialidad_codigo", mode="before")
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("codigo", "especialidad_codigo", mode="after")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class OfficeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    establecimiento_id: int
    consultorio_padre_id: int | None
    codigo: str
    nombre: str
    especialidad_codigo: str | None
    especialidad_requerida_codigo: str | None = None
    activo: bool
    area_codigo: str | None = None
    area_nombre: str | None = None
    servicios_codigos: list[str] | None = None
    servicios_habilitados: list[CodeCatalogItem] = Field(default_factory=list)
    ruta: str = ""
    activo_efectivo: bool = True
    establecimiento_nombre: str | None = None
    consultorio_padre_nombre: str | None = None
