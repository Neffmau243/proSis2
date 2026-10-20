"""PatientRiskRules: validation only; transaction ownership remains in PatientService."""

from __future__ import annotations

from datetime import date

from app.domain.age import completed_months
from app.domain.nutrition_followup import FOLLOWUP_GROUPS
from app.exceptions import (
    BusinessRuleError,
    ValidationDomainError,
)
from app.repositories.patient import PatientRepository
from app.schemas.patient import (
    PatientRiskCreate,
)
from app.services.attention_origin import AttentionOriginReader
from app.services.patient_data import PatientDataRules


class PatientRiskRules:
    def __init__(self, repository: PatientRepository, origin_reader: AttentionOriginReader) -> None:
        self._repository = repository
        self._origin_reader = origin_reader

    def validate_new_risks(self, commands: list[PatientRiskCreate]) -> None:
        by_group: dict[int, list[PatientRiskCreate]] = {}
        for command in commands:
            self.validate_risk_dates(command.fecha_inicio, command.fecha_fin)
            self.require_active_risk_group(command.grupo_riesgo_id)
            if command.atencion_origen_id is not None:
                raise ValidationDomainError(
                    code="ORIGEN_RIESGO_INVALIDO",
                    message=(
                        "Vincule el seguimiento a una atención después de registrar al paciente."
                    ),
                )
            periods = by_group.setdefault(command.grupo_riesgo_id, [])
            if any(
                self.periods_overlap(
                    command.fecha_inicio,
                    command.fecha_fin,
                    existing.fecha_inicio,
                    existing.fecha_fin,
                )
                for existing in periods
            ):
                raise BusinessRuleError(
                    code="RIESGO_SUPERPUESTO",
                    message=(
                        "Un grupo de riesgo no puede tener periodos superpuestos para el paciente."
                    ),
                )
            periods.append(command)

    @staticmethod
    def validate_followup_fields(start, end, reason, next_control, closure):
        if not reason or not reason.strip():
            raise ValidationDomainError(
                code="MOTIVO_SEGUIMIENTO_REQUERIDO",
                message="Explique el motivo y la evaluación que sustentan el seguimiento.",
            )
        if next_control is not None and next_control < start:
            raise ValidationDomainError(
                code="CONTROL_ANTERIOR_AL_INICIO",
                message="El próximo control no puede ser anterior al inicio del seguimiento.",
            )
        if end is not None and (not closure or not closure.strip()):
            raise ValidationDomainError(
                code="MOTIVO_CIERRE_REQUERIDO",
                message="Indique el motivo de cierre del seguimiento.",
            )

    def risk_origin(self, patient, command, actor_id, actor_roles):
        group = self._repository.get_active_risk_group(command.grupo_riesgo_id)
        code = getattr(group, "codigo", None)
        modern = code in FOLLOWUP_GROUPS
        if modern:
            self.validate_followup_fields(
                command.fecha_inicio,
                command.fecha_fin,
                command.observacion,
                command.fecha_proximo_control,
                command.motivo_cierre,
            )
            if command.fecha_inicio < patient.fecha_nacimiento:
                raise ValidationDomainError(
                    code="INICIO_ANTERIOR_NACIMIENTO",
                    message="El seguimiento no puede comenzar antes del nacimiento.",
                )
            if (
                code == "NUT_CRECIMIENTO"
                and completed_months(patient.fecha_nacimiento, command.fecha_inicio) >= 60
            ):
                raise ValidationDomainError(
                    code="SEGUIMIENTO_CRECIMIENTO_NO_APLICA",
                    message=(
                        "La comparación de crecimiento implementada corresponde "
                        "a menores de 5 años."
                    ),
                )
        snapshot = {"version": "1", "metodo": "VALORACION_PROFESIONAL", "tamizaje": "NO_EVALUADO"}
        if command.atencion_origen_id is not None:
            origin = self._origin_reader.get(
                command.atencion_origen_id, actor_id=actor_id, actor_roles=actor_roles
            )
            if (
                origin.paciente_id != patient.id
                or origin.estado != "ATENDIDO"
                or origin.fecha_atencion.date() > command.fecha_inicio
            ):
                raise ValidationDomainError(
                    code="ORIGEN_RIESGO_INVALIDO",
                    message=(
                        "Seleccione una atención vigente del mismo paciente, "
                        "anterior o igual al inicio."
                    ),
                )
            assessment = origin.valoracion_calculada
            followup = assessment.seguimiento if assessment else None
            if code in {"NUT_HALLAZGO", "NUT_CRECIMIENTO"} and not any(
                suggestion["codigo"] == code
                for suggestion in (followup or {}).get("sugerencias", [])
            ):
                raise ValidationDomainError(
                    code="SUGERENCIA_NO_DISPONIBLE",
                    message="La atención seleccionada no contiene esa sugerencia de seguimiento.",
                )
            snapshot = assessment.model_dump(mode="json") if assessment else snapshot
        if not modern and command.atencion_origen_id is None:
            return {}
        return {
            "confirmado_por_usuario_id": actor_id,
            "evaluacion_origen": snapshot,
            **({"fecha_proximo_control": None} if command.fecha_fin else {}),
        }

    @staticmethod
    def validate_risk_dates(start_date: date, end_date: date | None) -> None:
        if end_date is not None and end_date < start_date:
            raise ValidationDomainError(
                code="PERIODO_RIESGO_INVALIDO",
                message="La fecha de fin del riesgo no puede ser anterior a su fecha de inicio.",
            )

    def ensure_risk_does_not_overlap(
        self,
        patient_id: int,
        risk_group_id: int,
        *,
        start_date: date,
        end_date: date | None,
        exclude_start_date: date | None = None,
    ) -> None:
        overlap = self._repository.find_overlapping_risk(
            patient_id,
            risk_group_id,
            start_date=start_date,
            end_date=end_date,
            exclude_start_date=exclude_start_date,
        )
        if overlap is not None:
            raise BusinessRuleError(
                code="RIESGO_SUPERPUESTO",
                message="Un grupo de riesgo no puede tener periodos superpuestos para el paciente.",
            )

    def require_active_risk_group(self, risk_group_id: int) -> None:
        if self._repository.get_active_risk_group(risk_group_id) is None:
            PatientDataRules.raise_unavailable_catalog("grupo de riesgo", risk_group_id)

    @staticmethod
    def periods_overlap(
        first_start: date,
        first_end: date | None,
        second_start: date,
        second_end: date | None,
    ) -> bool:
        return first_start <= (second_end or date.max) and second_start <= (first_end or date.max)
