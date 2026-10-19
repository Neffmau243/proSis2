"""Pydantic contracts for clinical attention use cases."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.fua_print import FuaPrintInput, FuaPrintSnapshot
from app.schemas.nutrition_record import NutritionRecordInput, NutritionRecordResponse


class AttentionModeCode(str, Enum):
    AMBULATORY = "AMBULATORIA"
    EMERGENCY = "EMERGENCIA"


class AttentionStatus(str, Enum):
    ATTENDED = "ATENDIDO"
    CANCELLED = "ANULADO"


class CareGroupCode(str, Enum):
    """Clinical population the professional declares for the encounter.

    Unlike ``grupo_etario_codigo`` (derived from the patient's age), this is an
    explicit choice made during admission and is therefore persisted as-is.
    """

    GENERAL = "NINOS_ADOLESCENTES_ADULTOS_MAYORES"
    PREGNANT = "GESTANTES"
    PUERPERAL = "PUERPERAS"


class PregnancyTypeCode(str, Enum):
    """Gestation plurality recorded during a pregnant person's admission."""

    SINGLE = "UNICO"
    MULTIPLE = "MULTIPLE"


class AttentionServiceInput(BaseModel):
    prestacion_codigo: Annotated[str, Field(min_length=1, max_length=30)]
    cantidad: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)] = Decimal("1")

    @field_validator("prestacion_codigo", mode="before")
    @classmethod
    def normalize_code(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class AttentionDiagnosisInput(BaseModel):
    cie10_codigo: Annotated[str, Field(min_length=1, max_length=20)]
    tipo_diagnostico: Annotated[str, Field(max_length=50)] | None = None
    observacion: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("cie10_codigo", mode="before")
    @classmethod
    def normalize_code(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("tipo_diagnostico", "observacion", mode="before")
    @classmethod
    def trim_optional_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class NutritionalSnapshotInput(NutritionRecordInput):
    """Optional historic nutrition record created atomically with an attention."""

    tipo: Annotated[str, Field(max_length=20)] | None = None
    diagnostico_peso_edad: Annotated[str, Field(max_length=100)] | None = None
    diagnostico_talla_edad: Annotated[str, Field(max_length=100)] | None = None
    diagnostico_peso_talla: Annotated[str, Field(max_length=100)] | None = None


class AttentionCreate(BaseModel):
    """Input excluding fields that the backend must calculate or own."""

    paciente_id: Annotated[int, Field(gt=0)]
    numero_referencia_ingreso: Annotated[str, Field(max_length=50)] | None = None
    numero_contrarreferencia_ingreso: Annotated[str, Field(max_length=50)] | None = None
    establecimiento_id: Annotated[int, Field(gt=0)]
    profesional_id: Annotated[int, Field(gt=0)]
    especialidad_codigo: Annotated[str, Field(max_length=20)] | None = None
    consultorio_id: Annotated[int, Field(gt=0)]
    modalidad_atencion_codigo: AttentionModeCode
    grupo_atencion_codigo: CareGroupCode = CareGroupCode.GENERAL
    fecha_atencion: datetime
    fecha_atendido: datetime | None = None
    tipo_embarazo_codigo: PregnancyTypeCode | None = None
    peso_antes_embarazo_kg: (
        Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None
    ) = None
    fecha_probable_parto: date | None = None
    fecha_parto: date | None = None
    peso_kg: Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None = None
    talla_cm: Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None = None
    perimetro_abdominal_cm: (
        Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None
    ) = None
    presion_sistolica: Annotated[int, Field(gt=0, le=999)] | None = None
    presion_diastolica: Annotated[int, Field(gt=0, le=999)] | None = None
    temperatura_c: Annotated[Decimal, Field(max_digits=4, decimal_places=1)] | None = None
    hora_inicio: time | None = None
    hora_fin: time | None = None
    admision: Annotated[str, Field(max_length=100)] | None = None
    observaciones: str | None = None
    prestaciones: list[AttentionServiceInput] = Field(default_factory=list)
    diagnosticos: list[AttentionDiagnosisInput] = Field(default_factory=list)
    valoracion_nutricional: NutritionalSnapshotInput | None = None
    fua_datos: FuaPrintInput | None = None

    @field_validator("especialidad_codigo", mode="before")
    @classmethod
    def normalize_specialty(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator(
        "admision",
        "observaciones",
        "numero_referencia_ingreso",
        "numero_contrarreferencia_ingreso",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_times(self) -> AttentionCreate:
        # Shared obstetric data: the plurality and the weight before the pregnancy
        # are meaningful for both a pregnant person and a puerperal one.
        shared = (self.tipo_embarazo_codigo, self.peso_antes_embarazo_kg)
        pregnant_only = (
            self.fecha_probable_parto,
            self.valoracion_nutricional.edad_gestacional_semanas
            if self.valoracion_nutricional
            else None,
        )
        if self.grupo_atencion_codigo not in (
            CareGroupCode.PREGNANT,
            CareGroupCode.PUERPERAL,
        ) and any(value is not None for value in (*shared, *pregnant_only, self.fecha_parto)):
            raise ValueError(
                "Los datos obstetricos solo se admiten para los grupos GESTANTES y PUERPERAS"
            )
        if self.grupo_atencion_codigo == CareGroupCode.PREGNANT and self.fecha_parto is not None:
            raise ValueError("La fecha de parto solo se admite para el grupo PUERPERAS")
        if self.grupo_atencion_codigo == CareGroupCode.PUERPERAL and any(
            value is not None for value in pregnant_only
        ):
            raise ValueError(
                "La fecha probable de parto y la edad gestacional solo se admiten "
                "para el grupo GESTANTES"
            )
        if (
            self.hora_inicio is not None
            and self.hora_fin is not None
            and self.hora_fin < self.hora_inicio
        ):
            raise ValueError("hora_fin no puede ser anterior a hora_inicio")
        if self.fecha_atendido is not None and self.fecha_atendido < self.fecha_atencion:
            raise ValueError("fecha_atendido no puede ser anterior a fecha_atencion")
        return self


class AttentionCancellationInput(BaseModel):
    observaciones: Annotated[str, Field(min_length=5, max_length=10_000)]

    @field_validator("observaciones", mode="before")
    @classmethod
    def require_reason(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("La anulación requiere una justificación")
        return value.strip()


class NutritionalIndicatorsPreviewInput(BaseModel):
    """Only measurements and patient context used for a server-side preview."""

    paciente_id: Annotated[int, Field(gt=0)]
    grupo_atencion_codigo: CareGroupCode = CareGroupCode.GENERAL
    peso_antes_embarazo_kg: (
        Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None
    ) = None
    fecha_atencion: datetime
    peso_kg: Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None = None
    talla_cm: Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)] | None = None

    @model_validator(mode="after")
    def validate_pregestational_weight(self) -> NutritionalIndicatorsPreviewInput:
        if (
            self.grupo_atencion_codigo not in (CareGroupCode.PREGNANT, CareGroupCode.PUERPERAL)
            and self.peso_antes_embarazo_kg is not None
        ):
            raise ValueError(
                "El peso antes del embarazo solo se admite para los grupos GESTANTES y PUERPERAS"
            )
        return self


class NutritionalIndicatorsResponse(BaseModel):
    version_calculo: str | None = None
    seguimiento: dict[str, Any] | None = None
    grupo_referencia: str = "INFANTIL"
    imc_edad: Decimal | None = None
    diagnostico_imc: str | None = None
    imc_pregestacional: Decimal | None = None
    ganancia_peso_kg: Decimal | None = None
    diagnostico_peso_edad: str | None = None
    diagnostico_talla_edad: str | None = None
    diagnostico_peso_talla: str | None = None
    imc: Decimal | None
    pe: Decimal | None
    te: Decimal | None
    pt: Decimal | None
    estado: str
    mensaje: str
    referencia: str | None


class AttentionServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numero_orden: int
    prestacion_codigo: str
    cantidad: Decimal


class AttentionDiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numero_orden: int
    cie10_codigo: str
    tipo_diagnostico: str | None
    observacion: str | None


class AttentionResponse(BaseModel):
    numero_referencia_ingreso: str | None = None
    numero_contrarreferencia_ingreso: str | None = None
    contexto_clinico: dict[str, Any] | None = None
    evaluaciones_nutricionales: list[NutritionRecordResponse] = Field(default_factory=list)
    valoracion_calculada: NutritionalIndicatorsResponse | None = None
    model_config = ConfigDict(from_attributes=True)

    fua_impresion: FuaPrintSnapshot | None = None

    id: int
    paciente_id: int
    establecimiento_id: int
    establecimiento_nombre: str | None = None
    profesional_id: int
    profesional_nombre: str | None = None
    especialidad_codigo: str | None
    especialidad_nombre: str | None = None
    consultorio_id: int
    consultorio_nombre: str | None
    consultorio_ruta: str | None = None
    modalidad_atencion_codigo: str
    grupo_etario_codigo: str
    grupo_atencion_codigo: str
    fecha_atencion: datetime
    fecha_atendido: datetime | None
    historia_clinica_snapshot: str | None
    edad_anios: int | None
    edad_detallada: str | None
    peso_kg: Decimal | None
    talla_cm: Decimal | None
    perimetro_abdominal_cm: Decimal | None
    tipo_embarazo_codigo: str | None
    peso_antes_embarazo_kg: Decimal | None
    fecha_probable_parto: date | None
    fecha_parto: date | None
    presion_sistolica: int | None
    presion_diastolica: int | None
    temperatura_c: Decimal | None
    imc: Decimal | None
    pe: str | None
    te: str | None
    pt: str | None
    referencia_nutricional: str | None
    hora_inicio: time | None
    hora_fin: time | None
    admision: str | None
    observaciones: str | None
    estado: str
    created_by_usuario_id: int | None
    created_at: datetime
    updated_at: datetime
    prestaciones: list[AttentionServiceResponse] = Field(default_factory=list)
    diagnosticos: list[AttentionDiagnosisResponse] = Field(default_factory=list)
