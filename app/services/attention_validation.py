"""Clinical assignment and catalog validation for a new encounter."""

from __future__ import annotations

from app.domain.office import office_context
from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.attention import AttentionRepository
from app.schemas.attention import (
    AttentionCreate,
)


class AttentionContextValidator:
    def __init__(self, attentions: AttentionRepository):
        self._attentions = attentions

    def validate(self, command: AttentionCreate) -> None:
        if self._attentions.get_active_establishment(command.establecimiento_id) is None:
            raise NotFoundError(
                code="ESTABLECIMIENTO_NO_ACTIVO",
                message="El establecimiento no existe o está inactivo.",
            )
        if self._attentions.get_active_mode(command.modalidad_atencion_codigo.value) is None:
            raise NotFoundError(
                code="MODALIDAD_NO_ACTIVA", message="La modalidad de atención no está activa."
            )
        if (
            command.modalidad_atencion_codigo.value == "REFERENCIA"
            and command.consultorio_id is None
        ):
            return
        if self._attentions.get_active_professional(command.profesional_id) is None:
            raise NotFoundError(
                code="PROFESIONAL_NO_ACTIVO", message="El profesional no existe o está inactivo."
            )
        office = self._attentions.get_active_office(command.consultorio_id)
        if office is None:
            raise NotFoundError(
                code="CONSULTORIO_NO_ACTIVO", message="El consultorio no existe o está inactivo."
            )
        if office.establecimiento_id != command.establecimiento_id:
            raise BusinessRuleError(
                code="CONSULTORIO_OTRA_SEDE",
                message="El consultorio debe pertenecer al establecimiento de la atención.",
            )
        context = office_context(office)
        if not context.active:
            raise BusinessRuleError(
                code="JERARQUIA_CONSULTORIO_NO_ACTIVA",
                message="El consultorio o alguno de sus padres está inactivo.",
            )
        required_specialty = context.required_specialty
        selected_specialty = command.especialidad_codigo
        if (context.area_code is not None and selected_specialty not in context.service_codes) or (
            getattr(office, "servicios_codigos", None) == []
        ):
            raise BusinessRuleError(
                code="ESPECIALIDAD_INCOMPATIBLE",
                message="Seleccione un servicio o especialidad habilitado en este consultorio.",
            )
        if selected_specialty is not None:
            if self._attentions.get_active_specialty(selected_specialty) is None:
                raise NotFoundError(
                    code="ESPECIALIDAD_NO_ACTIVA",
                    message="La especialidad no existe o está inactiva.",
                )
        if not self._attentions.professional_is_assigned(
            office, command.profesional_id, command.fecha_atencion.date()
        ):
            raise BusinessRuleError(
                code="PROFESIONAL_NO_ASIGNADO",
                message="Seleccione un profesional asignado y vigente en esa fecha.",
            )
        if required_specialty and not self._attentions.professional_has_specialty(
            command.profesional_id, required_specialty
        ):
            raise BusinessRuleError(
                code="PROFESIONAL_SIN_ESPECIALIDAD",
                message="El profesional no tiene la especialidad base requerida.",
            )
