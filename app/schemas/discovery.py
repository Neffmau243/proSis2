"""Validated filters for paginated patient and attention discovery."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.attention import AttentionStatus


class PatientSearchCriteria(BaseModel):
    """Filters accepted by the patient search endpoint.

    Exact identifiers are intentionally separate from ``q``.  It keeps an
    admission search predictable and avoids treating ``%`` or ``_`` as SQL
    wildcards.
    """

    tipo_documento_codigo: Annotated[str, Field(min_length=1, max_length=10)] | None = None
    numero_documento: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    historia_clinica: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    q: Annotated[str, Field(min_length=2, max_length=100)] | None = None
    establecimiento_id: Annotated[int, Field(gt=0)] | None = None
    incluir_inactivos: bool = False
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0)] = 0

    @field_validator(
        "tipo_documento_codigo",
        "numero_documento",
        "historia_clinica",
        "q",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("tipo_documento_codigo", mode="after")
    @classmethod
    def normalize_document_type(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class AttentionSearchCriteria(BaseModel):
    """Date and ownership filters for the clinical attention history."""

    paciente_id: Annotated[int, Field(gt=0)] | None = None
    consultorio_id: Annotated[int, Field(gt=0)] | None = None
    establecimiento_id: Annotated[int, Field(gt=0)] | None = None
    profesional_id: Annotated[int, Field(gt=0)] | None = None
    desde: date | None = None
    hasta: date | None = None
    fecha_hora_desde: datetime | None = None
    fecha_hora_hasta: datetime | None = None
    estado: AttentionStatus | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def validate_date_range(self) -> "AttentionSearchCriteria":
        if (self.fecha_hora_desde is None) != (self.fecha_hora_hasta is None):
            raise ValueError("El intervalo de turno requiere fecha_hora_desde y fecha_hora_hasta")
        if self.fecha_hora_desde is not None and self.fecha_hora_hasta is not None:
            if self.fecha_hora_desde.tzinfo is not None or self.fecha_hora_hasta.tzinfo is not None:
                raise ValueError("El intervalo de turno usa hora local de Lima sin offset")
            if self.fecha_hora_hasta <= self.fecha_hora_desde:
                raise ValueError("El fin del turno debe ser posterior al inicio")
        if self.desde is not None and self.hasta is not None and self.hasta < self.desde:
            raise ValueError("hasta no puede ser anterior a desde")
        return self
