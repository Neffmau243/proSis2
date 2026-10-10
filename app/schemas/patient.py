"""DTOs for the patient registration and maintenance use cases.

These schemas intentionally use the same Spanish vocabulary as the IPRESS
database.  They are API contracts, not ORM models: the service decides which
business operations are valid and the mapper performs all conversions.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.family_history import normalize_family_history
from app.domain.patient_condition import PatientCondition
from app.schemas.patient_sis import PatientSisFields


DocumentCode = Annotated[str, Field(min_length=1, max_length=10)]
DocumentNumber = Annotated[str, Field(min_length=1, max_length=30)]


class ResponsibleRelationship(str, Enum):
    """Relationships accepted by the IPRESS policy (RB-02)."""

    MOTHER = "MADRE"
    FATHER = "PADRE"
    GUARDIAN = "TUTOR"


class PatientResponsibleCreate(BaseModel):
    """A responsible person supplied while registering a patient."""

    parentesco: ResponsibleRelationship
    nombre_completo: Annotated[str, Field(min_length=2, max_length=200)]
    tipo_documento_codigo: DocumentCode | None = None
    numero_documento: DocumentNumber | None = None
    telefono: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    es_principal: bool = False
    activo: bool = True

    @field_validator(
        "nombre_completo",
        "tipo_documento_codigo",
        "numero_documento",
        "telefono",
        mode="before",
    )
    @classmethod
    def strip_external_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("tipo_documento_codigo", mode="after")
    @classmethod
    def normalize_document_type(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def require_a_complete_document_reference(self) -> "PatientResponsibleCreate":
        if (self.tipo_documento_codigo is None) != (self.numero_documento is None):
            raise ValueError(
                "tipo_documento_codigo y numero_documento deben enviarse juntos"
            )
        return self


class PatientResponsibleUpdate(BaseModel):
    """Whitelisted mutable fields for an existing responsible person."""

    parentesco: ResponsibleRelationship | None = None
    nombre_completo: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    tipo_documento_codigo: DocumentCode | None = None
    numero_documento: DocumentNumber | None = None
    telefono: Annotated[str, Field(min_length=1, max_length=30)] | None = None
    es_principal: bool | None = None
    activo: bool | None = None

    @field_validator(
        "nombre_completo",
        "tipo_documento_codigo",
        "numero_documento",
        "telefono",
        mode="before",
    )
    @classmethod
    def strip_external_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("tipo_documento_codigo", mode="after")
    @classmethod
    def normalize_document_type(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class PatientRiskCreate(BaseModel):
    """A period in a configured risk group for a patient."""

    grupo_riesgo_id: Annotated[int, Field(gt=0)]
    fecha_inicio: date
    fecha_fin: date | None = None
    observacion: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("observacion", mode="before")
    @classmethod
    def strip_external_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class PatientRiskUpdate(BaseModel):
    """Only closes or annotates an existing risk period.

    The beginning date and risk group participate in the database primary key;
    changing them would be a new period, not an in-place mutation.
    """

    fecha_fin: date | None = None
    observacion: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("observacion", mode="before")
    @classmethod
    def strip_external_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class PatientCreate(PatientSisFields):
    """Atomic registration payload for an adult or a minor patient."""

    codclie_legacy: Annotated[int, Field(gt=0)] | None = None
    sufijo_documento: Annotated[str, Field(pattern=r"^[A-Za-z0-9]{1,10}$")] | None = None
    historia_clinica: Annotated[str, Field(max_length=255)] | None = None
    historia_familiar: str | None = None
    tipo_documento_codigo: DocumentCode
    numero_documento: DocumentNumber
    fecha_inscripcion: date | None = None
    fecha_nacimiento: date
    apellido_paterno: Annotated[str, Field(max_length=100)] | None = None
    apellido_materno: Annotated[str, Field(max_length=100)] | None = None
    primer_nombre: Annotated[str, Field(max_length=100)] | None = None
    otros_nombres: Annotated[str, Field(max_length=150)] | None = None
    sexo_codigo: Annotated[str, Field(min_length=1, max_length=1)] | None = None
    ubigeo_residencia_codigo: Annotated[str, Field(min_length=6, max_length=6)] | None = None
    localidad: Annotated[str, Field(max_length=150)] | None = None
    localidad_id: Annotated[int, Field(gt=0)] | None = None
    direccion: Annotated[str, Field(max_length=300)] | None = None
    establecimiento_registro_id: Annotated[int, Field(gt=0)] | None = None
    seguro_id: Annotated[int, Field(gt=0)] | None = None
    telefono_principal: Annotated[str, Field(max_length=30)] | None = None
    condicion: PatientCondition = None
    responsables: list[PatientResponsibleCreate] = Field(default_factory=list)
    riesgos: list[PatientRiskCreate] = Field(default_factory=list)

    @field_validator(
        "historia_clinica",
        "historia_familiar",
        "tipo_documento_codigo",
        "numero_documento",
        "apellido_paterno",
        "apellido_materno",
        "primer_nombre",
        "otros_nombres",
        "sexo_codigo",
        "ubigeo_residencia_codigo",
        "localidad",
        "direccion",
        "telefono_principal",
        "condicion",
        mode="before",
    )
    @classmethod
    def strip_external_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("historia_familiar", mode="after")
    @classmethod
    def normalize_family_history_code(cls, value: str | None) -> str | None:
        return normalize_family_history(value)

    @field_validator("tipo_documento_codigo", "sexo_codigo", mode="after")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class PatientUpdate(PatientSisFields):
    """Safe partial update for the patient record.

    Child collections are deliberately excluded.  They have dedicated service
    operations so a PATCH cannot silently remove responsible people or risk
    history.
    """

    model_config = ConfigDict(extra="forbid")
    sufijo_documento: Annotated[str, Field(pattern=r"^[A-Za-z0-9]{1,10}$")] | None = None

    historia_clinica: Annotated[str, Field(max_length=255)] | None = None
    historia_familiar: str | None = None
    tipo_documento_codigo: DocumentCode | None = None
    numero_documento: DocumentNumber | None = None
    fecha_inscripcion: date | None = None
    fecha_nacimiento: date | None = None
    apellido_paterno: Annotated[str, Field(max_length=100)] | None = None
    apellido_materno: Annotated[str, Field(max_length=100)] | None = None
    primer_nombre: Annotated[str, Field(max_length=100)] | None = None
    otros_nombres: Annotated[str, Field(max_length=150)] | None = None
    sexo_codigo: Annotated[str, Field(min_length=1, max_length=1)] | None = None
    ubigeo_residencia_codigo: Annotated[str, Field(min_length=6, max_length=6)] | None = None
    localidad: Annotated[str, Field(max_length=150)] | None = None
    localidad_id: Annotated[int, Field(gt=0)] | None = None
    direccion: Annotated[str, Field(max_length=300)] | None = None
    establecimiento_registro_id: Annotated[int, Field(gt=0)] | None = None
    seguro_id: Annotated[int, Field(gt=0)] | None = None
    telefono_principal: Annotated[str, Field(max_length=30)] | None = None
    condicion: PatientCondition = None

    @field_validator("tipo_documento_codigo", "numero_documento", "fecha_nacimiento")
    @classmethod
    def reject_null_required_columns(cls, value: Any) -> Any:
        # Omitted fields retain their values; explicit null must not reach a
        # NOT NULL column or date comparison in the domain service.
        if value is None:
            raise ValueError("Este campo no puede ser nulo; omítalo para conservar su valor.")
        return value

    @field_validator(
        "historia_clinica",
        "historia_familiar",
        "tipo_documento_codigo",
        "numero_documento",
        "apellido_paterno",
        "apellido_materno",
        "primer_nombre",
        "otros_nombres",
        "sexo_codigo",
        "ubigeo_residencia_codigo",
        "localidad",
        "direccion",
        "telefono_principal",
        "condicion",
        mode="before",
    )
    @classmethod
    def strip_external_whitespace(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("historia_familiar", mode="after")
    @classmethod
    def normalize_family_history_code(cls, value: str | None) -> str | None:
        return normalize_family_history(value)

    @field_validator("tipo_documento_codigo", "sexo_codigo", mode="after")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class PatientResponsibleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parentesco: str
    nombre_completo: str
    tipo_documento_codigo: str | None
    numero_documento: str | None
    telefono: str | None
    es_principal: bool
    activo: bool


class PatientRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grupo_riesgo_id: int
    fecha_inicio: date
    fecha_fin: date | None
    observacion: str | None
    grupo_riesgo_codigo: str | None = None
    grupo_riesgo_nombre: str | None = None


class PatientResponse(PatientSisFields):
    """Public patient projection; ORM entities never cross the HTTP boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sufijo_documento: str | None = None
    codclie_legacy: int | None
    historia_clinica: str | None
    historia_familiar: str | None
    tipo_documento_codigo: str
    numero_documento: str
    fecha_inscripcion: date | None
    fecha_nacimiento: date
    apellido_paterno: str | None
    apellido_materno: str | None
    primer_nombre: str | None
    otros_nombres: str | None
    sexo_codigo: str | None
    ubigeo_residencia_codigo: str | None
    distrito_residencia: str | None = None
    localidad: str | None
    localidad_id: int | None = None
    direccion: str | None
    establecimiento_registro_id: int | None
    seguro_id: int | None
    telefono_principal: str | None
    condicion: str | None
    estado: bool
    created_at: datetime
    updated_at: datetime
    responsables: list[PatientResponsibleResponse] = Field(default_factory=list)
    riesgos: list[PatientRiskResponse] = Field(default_factory=list)


class PatientDeactivationResponse(BaseModel):
    id: int
    estado: bool
    mensaje: str
