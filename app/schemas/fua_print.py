"""Prefill for the paper FUA (RJ 000178-2024-SIS/J, annexes 1 and 3).

This is not a SETI-SIS claim or an official FUA-number generator. Unknown
affiliation/ethnicity values remain blank and require verification by the IPRESS.
"""

from datetime import date, time
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FuaPrintInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    personal_atiende: Literal["IPRESS", "ITINERANTE", "AISPED"] | None = None
    lugar_atencion: Literal["INTRAMURAL", "EXTRAMURAL"] | None = None
    tipo_atencion: Literal["AMBULATORIA", "REFERENCIA", "EMERGENCIA"] | None = None
    codigo_aisped: Annotated[str, Field(max_length=20)] | None = None
    codigo_renipress: Annotated[str, Field(pattern=r"^[0-9]{8}$")] | None = None
    sis_diresa: Annotated[str, Field(pattern=r"^[A-Z0-9]{3}$")] | None = None
    sis_tipo: Annotated[str, Field(pattern=r"^[A-Z0-9]{1,2}$")] | None = None
    sis_numero: Annotated[str, Field(pattern=r"^[A-Z0-9-]{1,30}$")] | None = None
    sis_componente: Annotated[str, Field(pattern=r"^[A-Z0-9-]{1,20}$")] | None = None
    etnia_codigo: Annotated[str, Field(pattern=r"^[0-9]{1,3}$")] | None = None
    referencia_renipress: Annotated[str, Field(pattern=r"^[0-9]{8}$")] | None = None
    referencia_nombre: Annotated[str, Field(max_length=200)] | None = None
    referencia_hoja: Annotated[str, Field(max_length=50)] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def clean_optional_text(cls, value: Any) -> Any:
        return (value.strip().upper() or None) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_groups(self) -> "FuaPrintInput":
        affiliation = (self.sis_diresa, self.sis_tipo, self.sis_numero)
        if (any(affiliation) or self.sis_componente) and not all(affiliation[1:]):
            raise ValueError("Complete tipo y número de afiliación SIS juntos.")
        if self.personal_atiende == "AISPED" and not self.codigo_aisped:
            raise ValueError("La atención AISPED requiere el código de brigada.")
        if self.personal_atiende != "AISPED" and self.codigo_aisped:
            raise ValueError("El código AISPED solo corresponde a personal AISPED.")
        reference = (self.referencia_renipress, self.referencia_nombre, self.referencia_hoja)
        if self.tipo_atencion == "REFERENCIA" and not all(reference):
            raise ValueError("La referencia requiere RENIPRESS, nombre de origen y hoja.")
        if self.tipo_atencion != "REFERENCIA" and any(reference):
            raise ValueError("Los datos de referencia requieren atención REFERENCIA.")
        return self


class FuaPrintSnapshot(FuaPrintInput):
    version: Literal[1, 2] = 1
    # Version 1 keeps its original loose affiliation contract for historical reads.
    # Version 2 comes exclusively from validated patient/site master data.
    sis_secuencia: Annotated[str, Field(pattern=r"^[0-9]{1,2}$")] | None = None
    renipress_preimpreso: bool = True
    ipress_nombre: str
    profesional_nombre: str
    profesional_documento: str | None = None
    profesional_colegiatura: str | None = None
    tipo_documento: str
    tdi: Literal["2", "3"] | None = None
    numero_documento: str
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    primer_nombre: str | None = None
    otros_nombres: str | None = None
    sexo_codigo: str | None = None
    fecha_nacimiento: date
    historia_clinica: str | None = None
    fecha_atencion: date
    hora_atencion: time
    peso_kg: Decimal | None = None
    talla_cm: Decimal | None = None
    presion_sistolica: int | None = None
    presion_diastolica: int | None = None
    imc: Decimal | None = None
    grupo_referencia: str | None = None
    estado_nutricional: str | None = None
    pe: Decimal | None = None
    te: Decimal | None = None
    pt: Decimal | None = None
    diagnostico_peso_edad: str | None = None
    diagnostico_talla_edad: str | None = None
    diagnostico_peso_talla: str | None = None
    diagnostico_imc: str | None = None
    imc_pregestacional: Decimal | None = None
    ganancia_peso_kg: Decimal | None = None
    perimetro_abdominal_cm: Decimal | None = None
    grupo_atencion_codigo: str
    #: FPP de la gestante; en una puérpera el mismo recuadro del formato lleva
    #: la fecha real del parto.
    fecha_probable_parto: date | None = None
    fecha_parto: date | None = None
