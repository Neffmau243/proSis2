"""Captured nutrition data; missing, zero and not applicable remain distinct."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Count = Annotated[int, Field(ge=0, le=65535)]
LegacyCode = Annotated[int, Field(ge=-2147483648, le=2147483647)]
ShortText = Annotated[str, Field(max_length=100)]

CHILD_FIELDS = (
    "juntos",
    "pin",
    "crecer",
    "nro_controles_cred",
    "nro_sachets",
    "nro_consejerias",
    "nro_sesiones",
    "nro_visitas",
    "institucion_educativa",
    "nivel_educativo",
    "grado",
    "turno",
    "codigo_matricula",
    "seccion",
    "aula",
    "flag_legacy",
)
ADULT_FIELDS = ("p65", "vl", "cp")
PREGNANT_FIELDS = ("edad_gestacional_semanas", "estado_ganancia_peso")


class NutritionRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    hemoglobina: Annotated[Decimal, Field(gt=0, le=30, decimal_places=2)] | None = None
    fecha_hemoglobina: date | None = None
    hemoglobina_corregida: Annotated[Decimal, Field(gt=0, le=30, decimal_places=2)] | None = None
    metodo_correccion_hb: Annotated[str, Field(max_length=200)] | None = None
    hematocrito: Annotated[Decimal, Field(gt=0, le=100, decimal_places=2)] | None = None
    altitud_msnm: Annotated[Decimal, Field(ge=-500, le=9000, decimal_places=2)] | None = None
    edad_gestacional_semanas: Annotated[int, Field(ge=0, le=45)] | None = None
    estado_ganancia_peso: ShortText | None = None
    diagnostico: Annotated[str, Field(max_length=500)] | None = None
    juntos: bool | None = None
    pin: bool | None = None
    crecer: bool | None = None
    nro_controles_cred: Count | None = None
    nro_sachets: Count | None = None
    nro_consejerias: Count | None = None
    nro_sesiones: Count | None = None
    nro_visitas: Count | None = None
    institucion_educativa: Annotated[str, Field(max_length=200)] | None = None
    nivel_educativo: ShortText | None = None
    grado: ShortText | None = None
    turno: ShortText | None = None
    codigo_matricula: ShortText | None = None
    seccion: ShortText | None = None
    aula: ShortText | None = None
    p65: LegacyCode | None = None
    vl: LegacyCode | None = None
    cp: LegacyCode | None = None
    flag_legacy: LegacyCode | None = None
    pending_legacy: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_is_missing(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def validate_laboratory(self) -> "NutritionRecordInput":
        if (self.hemoglobina is None) != (self.fecha_hemoglobina is None):
            raise ValueError("Registre hemoglobina y fecha del resultado juntas.")
        if self.hemoglobina_corregida is not None and (
            self.hemoglobina is None or not self.metodo_correccion_hb or self.altitud_msnm is None
        ):
            raise ValueError("La Hb corregida requiere Hb medida, altitud y método de corrección.")
        if self.metodo_correccion_hb and self.hemoglobina_corregida is None:
            raise ValueError("El método de corrección requiere Hb corregida.")
        return self


class NutritionRecordResponse(BaseModel):
    """Permissive historical projection: old sentinel values are never revalidated."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str | None = None
    hemoglobina: Decimal | None = None
    fecha_hemoglobina: date | None = None
    hemoglobina_corregida: Decimal | None = None
    metodo_correccion_hb: str | None = None
    hematocrito: Decimal | None = None
    altitud_msnm: Decimal | None = None
    edad_gestacional_semanas: int | None = None
    estado_ganancia_peso: str | None = None
    diagnostico: str | None = None
    juntos: bool | None = None
    pin: bool | None = None
    crecer: bool | None = None
    nro_controles_cred: int | None = None
    nro_sachets: int | None = None
    nro_consejerias: int | None = None
    nro_sesiones: int | None = None
    nro_visitas: int | None = None
    institucion_educativa: str | None = None
    nivel_educativo: str | None = None
    grado: str | None = None
    turno: str | None = None
    codigo_matricula: str | None = None
    seccion: str | None = None
    aula: str | None = None
    p65: int | None = None
    vl: int | None = None
    cp: int | None = None
    flag_legacy: int | None = None
    pending_legacy: bool | None = None
    imc: Decimal | None = None
    whz: Decimal | None = None
    haz: Decimal | None = None
    waz: Decimal | None = None
    estado_exportacion: str | None = None
    exportado_at: datetime | None = None
    enviado: bool = False
    enviado_at: datetime | None = None
    constancia_envio: str | None = None


class NutritionSendConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    constancia: Annotated[str, Field(min_length=5, max_length=200)]
