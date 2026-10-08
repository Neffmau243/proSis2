"""HTTP contracts for FUA, certificates and referrals."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FuaStatus(str, Enum):
    ISSUED = "EMITIDO"
    CANCELLED = "ANULADO"


class CertificateStatus(str, Enum):
    ISSUED = "EMITIDO"
    CANCELLED = "ANULADO"


class ReferralStatus(str, Enum):
    PENDING = "PENDIENTE"
    ACCEPTED = "ACEPTADA"
    ATTENDED = "ATENDIDA"
    COUNTER_REFERRED = "CONTRARREFERIDA"
    CLOSED = "CERRADA"
    CANCELLED = "ANULADA"


class FuaIssueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    atencion_id: Annotated[int, Field(gt=0)]
    observaciones: str | None = None


class CertificateIssueInput(BaseModel):
    atencion_id: Annotated[int, Field(gt=0)]
    tipo: Annotated[str, Field(min_length=1, max_length=100)]
    profesional_id: Annotated[int, Field(gt=0)] | None = None
    prestaciones: list[Annotated[str, Field(min_length=1, max_length=30)]] = Field(default_factory=list)

    @field_validator("tipo", mode="before")
    @classmethod
    def trim_type(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("prestaciones", mode="before")
    @classmethod
    def normalize_services(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [item.strip().upper() if isinstance(item, str) else item for item in value]
        return value


class ReferralCreateInput(BaseModel):
    atencion_id: Annotated[int, Field(gt=0)]
    tipo: Annotated[str, Field(min_length=1, max_length=30)]
    establecimiento_destino_id: Annotated[int, Field(gt=0)]
    motivo: Annotated[str, Field(min_length=1, max_length=10_000)]
    observaciones: str | None = None
    # A referral always starts pending.  Later lifecycle transitions must use
    # a dedicated state-transition use case rather than a client-selected
    # creation state.
    estado: ReferralStatus = ReferralStatus.PENDING

    @field_validator("tipo", "motivo", "observaciones", "estado", mode="before")
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def starts_pending(self) -> "ReferralCreateInput":
        if self.estado != ReferralStatus.PENDING:
            raise ValueError("Una referencia nueva debe iniciar en estado PENDIENTE")
        return self


class FuaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    atencion_id: int
    numero_fua: str | None
    codigo_renipress: str | None
    lote_fua: str | None
    correlativo_fua: str | None
    # Compatibility data from the legacy FUA model. New FUA records leave
    # these blank; they are not the official SIS number components.
    codigo_ciudad: str | None
    codigo_anio: str | None
    codigo_eess: str | None
    edad_declarada: str | None
    fecha_emision: datetime
    estado: FuaStatus
    observaciones: str | None


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    atencion_id: int
    establecimiento_id: int
    profesional_id: int
    numero_certificado: str
    tipo: str
    fecha_emision: datetime
    consultorio: str | None
    admision: str | None
    estado: CertificateStatus
    prestaciones: list[str] = Field(default_factory=list)


class ReferralResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    atencion_id: int
    numero_referencia: str | None
    tipo: str
    establecimiento_origen_id: int
    establecimiento_destino_id: int
    fecha_emision: datetime
    motivo: str | None
    observaciones: str | None
    estado: ReferralStatus
