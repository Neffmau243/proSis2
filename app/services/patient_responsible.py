"""PatientResponsibleRules: validation only; transaction ownership remains in PatientService."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from app.exceptions import (
    BusinessRuleError,
    ValidationDomainError,
)
from app.schemas.patient import (
    PatientResponsibleCreate,
    ResponsibleRelationship,
)
from app.services.patient_data import PatientDataRules


class PatientResponsibleRules:
    def __init__(self, data_rules: PatientDataRules, today_provider: Callable[[], date]) -> None:
        self._data = data_rules
        self._today_provider = today_provider

    def validate_new_responsibles(
        self,
        commands: list[PatientResponsibleCreate],
        *,
        birth_date: date,
        registration_date: date | None,
    ) -> None:
        for command in commands:
            self.validate_responsible(command)
        active = [command for command in commands if command.activo]
        self.ensure_active_principal_limit(active)
        self.ensure_minor_has_active_responsible(
            birth_date=birth_date,
            registration_date=registration_date,
            active_responsibles=active,
        )

    def validate_responsible(self, command: PatientResponsibleCreate) -> None:
        if command.parentesco.value not in {item.value for item in ResponsibleRelationship}:
            raise ValidationDomainError(
                code="PARENTESCO_NO_PERMITIDO",
                message="El parentesco debe ser MADRE, PADRE o TUTOR.",
            )
        if (command.tipo_documento_codigo is None) != (command.numero_documento is None):
            raise ValidationDomainError(
                code="DOCUMENTO_RESPONSABLE_INCOMPLETO",
                message="El responsable debe enviar tipo y número de documento juntos.",
            )
        if command.tipo_documento_codigo is not None:
            self._data.require_active_document_type(command.tipo_documento_codigo)

    def validate_responsible_update(self, responsible: Any, values: dict[str, Any]) -> None:
        effective_relationship = values.get("parentesco", responsible.parentesco)
        allowed = {item.value for item in ResponsibleRelationship}
        if effective_relationship not in allowed:
            raise ValidationDomainError(
                code="PARENTESCO_NO_PERMITIDO",
                message="El parentesco debe ser MADRE, PADRE o TUTOR.",
            )
        effective_type = values.get("tipo_documento_codigo", responsible.tipo_documento_codigo)
        effective_number = values.get("numero_documento", responsible.numero_documento)
        if (effective_type is None) != (effective_number is None):
            raise ValidationDomainError(
                code="DOCUMENTO_RESPONSABLE_INCOMPLETO",
                message="El responsable debe conservar tipo y número de documento juntos.",
            )
        if "tipo_documento_codigo" in values and effective_type is not None:
            self._data.require_active_document_type(effective_type)

    @staticmethod
    def ensure_active_principal_limit(active_responsibles: list[Any]) -> None:
        principals = [item for item in active_responsibles if item.es_principal]
        if len(principals) > 1:
            raise BusinessRuleError(
                code="RESPONSABLE_PRINCIPAL_DUPLICADO",
                message="Solo puede existir un responsable principal activo por paciente.",
            )

    def ensure_minor_has_active_responsible(
        self,
        *,
        birth_date: date,
        registration_date: date | None,
        active_responsibles: list[Any],
    ) -> None:
        reference_date = registration_date or self._today_provider()
        if self.is_minor(birth_date, reference_date) and not active_responsibles:
            raise BusinessRuleError(
                code="MENOR_SIN_RESPONSABLE",
                message="Un paciente menor de 18 años debe tener al menos un responsable activo.",
            )

    @staticmethod
    def is_minor(birth_date: date, reference_date: date) -> bool:
        try:
            adulthood = birth_date.replace(year=birth_date.year + 18)
        except ValueError:
            # A 29-Feb birth reaches the age threshold on 28-Feb in a
            # non-leap year, avoiding an approximation by days.
            adulthood = birth_date.replace(year=birth_date.year + 18, day=28)
        return reference_date < adulthood
