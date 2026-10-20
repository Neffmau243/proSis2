"""Shared preview, nutritional validation and evaluation construction.

Uses the enclosing encounter transaction; never commits or rolls it back.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from app.domain.age import CalendarAge, completed_months
from app.domain.clinical import (
    ClinicalProtocolValidator,
    VitalSignPayload,
)
from app.domain.nutrition import NutritionalIndicators
from app.domain.nutrition_followup import assess_followup
from app.exceptions import BusinessRuleError
from app.models.clinical import Attention
from app.models.surveillance import NutritionalEvaluation
from app.repositories.attention import AttentionRepository
from app.schemas.attention import (
    AttentionCreate,
    NutritionalIndicatorsResponse,
    NutritionalSnapshotInput,
)
from app.schemas.nutrition_record import ADULT_FIELDS, CHILD_FIELDS, PREGNANT_FIELDS


class NutritionAssessmentService:
    def __init__(
        self, attentions: AttentionRepository, clinical_protocol: ClinicalProtocolValidator
    ):
        self._attentions = attentions
        self._clinical_protocol = clinical_protocol

    def assessment(self, indicators, patient, measured_on, weight, height, scope):
        age_months = completed_months(patient.fecha_nacimiento, measured_on)
        previous = None
        if age_months < 60 and indicators.grupo_referencia == "INFANTIL":
            previous = self._attentions.previous_growth_control(
                patient.id,
                measured_on,
                birth_date=patient.fecha_nacimiento,
                professional_id=scope[0] if scope is not None else None,
                establishment_ids=scope[1] if scope is not None else None,
            )
        return NutritionalIndicatorsResponse(
            **asdict(indicators),
            **indicators.classifications,
            seguimiento=assess_followup(
                indicators,
                measured_on=measured_on,
                age_months=age_months,
                weight=weight,
                height=height,
                previous=previous,
            ),
        )

    def add_nutritional_snapshot(
        self,
        entity: Attention,
        command: AttentionCreate,
        age: CalendarAge,
        indicators: NutritionalIndicators,
    ) -> None:
        snapshot = command.valoracion_nutricional
        if snapshot is None and indicators.estado != "CALCULADO":
            return
        if snapshot is None:
            snapshot = NutritionalSnapshotInput()
        captured = snapshot.model_dump(
            exclude={
                "tipo",
                "diagnostico_peso_edad",
                "diagnostico_talla_edad",
                "diagnostico_peso_talla",
            }
        )
        kind = {"GESTANTES": "GESTANTE", "PUERPERAS": "PUERPERA"}.get(
            command.grupo_atencion_codigo.value, "NINO" if age.years < 18 else "ADULTO"
        )
        self._attentions.add_nutritional_evaluation(
            NutritionalEvaluation(
                paciente_id=entity.paciente_id,
                atencion_id=entity.id,
                establecimiento_id=entity.establecimiento_id,
                tipo=kind,
                fecha=entity.fecha_atencion,
                peso_kg=entity.peso_kg,
                talla_cm=entity.talla_cm,
                **captured,
                edad_anios=age.years,
                edad_meses=age.months,
                edad_dias=age.days,
                perimetro_abdominal_cm=entity.perimetro_abdominal_cm,
                imc=indicators.imc,
                whz=indicators.pt,
                haz=indicators.te,
                waz=indicators.pe,
                **indicators.classifications,
                estado_exportacion="PENDIENTE",
                enviado=False,
            )
        )

    @staticmethod
    def validate_nutrition_record(
        command: AttentionCreate, birth_date: date, age: CalendarAge
    ) -> None:
        record = command.valoracion_nutricional
        if record is None:
            return
        group = command.grupo_atencion_codigo.value
        child = group == "NINOS_ADOLESCENTES_ADULTOS_MAYORES" and age.years < 18
        adult = group == "NINOS_ADOLESCENTES_ADULTOS_MAYORES" and age.years >= 18
        invalid = []
        for applies, fields in (
            (child, CHILD_FIELDS),
            (adult, ADULT_FIELDS),
            (group == "GESTANTES", PREGNANT_FIELDS),
        ):
            if not applies:
                invalid.extend(name for name in fields if getattr(record, name) is not None)
        if child and record.pending_legacy is not None:
            invalid.append("pending_legacy")
        if invalid:
            raise BusinessRuleError(
                code="CAMPOS_NUTRICION_NO_APLICAN",
                message="Estos campos no corresponden al grupo y edad: " + ", ".join(invalid),
            )
        if record.fecha_hemoglobina is not None and not (
            birth_date <= record.fecha_hemoglobina <= command.fecha_atencion.date()
        ):
            raise BusinessRuleError(
                code="FECHA_HEMOGLOBINA_INVALIDA",
                message="La fecha del resultado debe estar entre el nacimiento y la atención.",
            )

    def validate_measurements(self, values: VitalSignPayload, age_in_months: int) -> None:
        """Preview and persistence must apply the same configured protocol."""
        try:
            self._clinical_protocol.validate(
                values,
                age_in_months=age_in_months,
            )
        except ValueError as exc:
            raise BusinessRuleError(code="SIGNOS_VITALES_INVALIDOS", message=str(exc)) from exc
