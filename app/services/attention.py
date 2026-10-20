"""Clinical attention use cases and their transactional business rules."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.age import CalendarAge, calendar_age, completed_months
from app.domain.clinical import (
    ClinicalProtocolValidator,
    ConfigurableClinicalProtocol,
    VitalSignPayload,
)
from app.domain.nutrition import NutritionalIndicators, calculate_nutritional_indicators
from app.domain.patient_condition import condition_for_attention
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.attention import attention_from_command, attention_to_response
from app.models.clinical import Attention
from app.repositories.age_group import AgeGroupRepository
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.schemas.attention import (
    AttentionCancellationInput,
    AttentionCreate,
    AttentionResponse,
    NutritionalIndicatorsPreviewInput,
    NutritionalIndicatorsResponse,
)
from app.services.age_group_resolver import AgeGroupResolver
from app.services.attention_context import AttentionContextLoader
from app.services.attention_validation import AttentionContextValidator
from app.services.clinical_access import ClinicalAccessService
from app.services.nutrition_assessment import NutritionAssessmentService


class AttentionService:
    """Registers and cancels the clinical aggregate without HTTP dependencies."""

    def __init__(
        self,
        session: Session,
        clinical_protocol: ClinicalProtocolValidator | None = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._session = session
        self._attentions = AttentionRepository(session)
        self._patients = PatientRepository(session)
        self._age_groups = AgeGroupResolver(AgeGroupRepository(session))
        self._clinical_protocol = clinical_protocol or ConfigurableClinicalProtocol()
        self._today_provider = today_provider

    def get(
        self,
        attention_id: int,
        *,
        actor_id: int | None = None,
        actor_roles: Iterable[str] | None = None,
    ) -> AttentionResponse:
        entity = self._attentions.get_by_id(attention_id)
        if entity is None:
            raise NotFoundError(
                code="ATENCION_NO_ENCONTRADA", message="No existe la atención solicitada."
            )
        self._ensure_attention_in_scope(
            entity,
            actor_id=actor_id,
            actor_roles=actor_roles,
        )
        return attention_to_response(entity)

    def list_by_patient(
        self,
        patient_id: int,
        *,
        actor_id: int | None = None,
        actor_roles: Iterable[str] | None = None,
    ) -> list[AttentionResponse]:
        scope = self._ensure_patient_in_scope(
            patient_id,
            actor_id=actor_id,
            actor_roles=actor_roles,
        )
        return [
            attention_to_response(entity)
            for entity in self._attentions.list_by_patient(
                patient_id,
                professional_id=scope[0] if scope is not None else None,
                establishment_ids=scope[1] if scope is not None else None,
            )
        ]

    def create(
        self,
        command: AttentionCreate,
        *,
        actor_id: int,
        actor_roles: Iterable[str] = (),
    ) -> AttentionResponse:
        """Validate and persist the encounter, its details and audit atomically."""
        try:
            self._ensure_actor_is_linked_professional(
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            attention_date = command.fecha_atencion.date()
            self._validate_attention_dates(command, attention_date)
            patient = self._patients.get_by_id(command.paciente_id, for_update=True)
            if patient is None:
                raise NotFoundError(
                    code="PACIENTE_NO_ENCONTRADO", message="El paciente no existe o está inactivo."
                )
            # A guessed identifier must not let a clinician create an
            # encounter outside an assigned site or existing care relation.
            scope = self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            if patient.fecha_nacimiento > attention_date:
                raise BusinessRuleError(
                    code="FECHA_ATENCION_ANTERIOR_NACIMIENTO",
                    message="La fecha de atención no puede ser anterior al nacimiento.",
                )

            age = calendar_age(patient.fecha_nacimiento, attention_date)
            age_in_months = completed_months(patient.fecha_nacimiento, attention_date)
            if age.years < 18 and not self._patients.get_active_responsibles(patient.id):
                raise BusinessRuleError(
                    code="MENOR_SIN_RESPONSABLE",
                    message="Un paciente menor de edad requiere al menos un responsable activo.",
                )
            age_group = self._age_groups.resolve(age_in_months)
            condition = condition_for_attention(
                age_group_code=age_group.codigo,
                care_group_code=command.grupo_atencion_codigo.value,
                age=age,
            )
            self._validate_clinical_context(command)
            self._validate_vital_signs(command, age_in_months)
            self._validate_nutrition_record(command, patient.fecha_nacimiento, age)
            indicators = calculate_nutritional_indicators(
                care_group=command.grupo_atencion_codigo.value,
                pregestational_weight_kg=command.peso_antes_embarazo_kg,
                birth_date=patient.fecha_nacimiento,
                sex_code=patient.sexo_codigo,
                measured_on=attention_date,
                weight_kg=command.peso_kg,
                height_cm=command.talla_cm,
            )

            assessment = self._assessment(
                indicators, patient, attention_date, command.peso_kg, command.talla_cm, scope
            )
            entity = attention_from_command(
                command, patient, age, age_group.codigo, indicators, assessment, actor_id
            )
            context = AttentionContextLoader(self._attentions, self._patients).load(
                patient, command
            )
            context.apply(entity, command, age, condition)
            self._attentions.add(entity)
            self._attentions.flush()
            self._add_details(entity, command)
            self._add_nutritional_snapshot(entity, command, age, indicators)
            self._attentions.flush()
            # The locked patient and immutable encounter snapshot are updated in
            # one transaction, so neither can expose a partially applied stage.
            if patient.condicion != condition:
                previous_condition = patient.condicion
                self._patients.update_fields(patient, {"condicion": condition})
                self._patients.add_audit_entry(
                    actor_id=actor_id,
                    action="UPDATE",
                    record_id=patient.id,
                    before={"condicion": previous_condition},
                    after={"condicion": condition, "atencion_id": entity.id},
                )
            self._attentions.add_audit(
                actor_id=actor_id,
                action="INSERT",
                record_id=entity.id,
                before=None,
                after=self._snapshot(entity),
            )
            self._session.commit()
            persisted = self._attentions.get_by_id(entity.id)
            return attention_to_response(persisted or entity)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="ATENCION_EN_CONFLICTO",
                message="No se pudo registrar la atención por una restricción de datos.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def preview_nutritional_indicators(
        self,
        command: NutritionalIndicatorsPreviewInput,
        *,
        actor_id: int,
        actor_roles: Iterable[str] = (),
    ) -> NutritionalIndicatorsResponse:
        """Return a non-persisted server calculation for the admission form.

        The same function is called again by :meth:`create`, so the preview is
        helpful to the user but never becomes a client-controlled source of
        truth.
        """

        scope = self._ensure_patient_in_scope(
            command.paciente_id,
            actor_id=actor_id,
            actor_roles=actor_roles,
        )
        patient = self._patients.get_by_id(command.paciente_id)
        if patient is None:
            raise NotFoundError(
                code="PACIENTE_NO_ENCONTRADO", message="El paciente no existe o está inactivo."
            )
        measured_on = command.fecha_atencion.date()
        if patient.fecha_nacimiento > measured_on:
            raise BusinessRuleError(
                code="FECHA_ATENCION_ANTERIOR_NACIMIENTO",
                message="La fecha de atención no puede ser anterior al nacimiento.",
            )
        self._validate_measurements(
            VitalSignPayload(peso_kg=command.peso_kg, talla_cm=command.talla_cm),
            completed_months(patient.fecha_nacimiento, measured_on),
        )
        indicators = calculate_nutritional_indicators(
            care_group=command.grupo_atencion_codigo.value,
            pregestational_weight_kg=command.peso_antes_embarazo_kg,
            birth_date=patient.fecha_nacimiento,
            sex_code=patient.sexo_codigo,
            measured_on=measured_on,
            weight_kg=command.peso_kg,
            height_cm=command.talla_cm,
        )
        return self._assessment(
            indicators, patient, measured_on, command.peso_kg, command.talla_cm, scope
        )

    def _assessment(self, indicators, patient, measured_on, weight, height, scope):
        return self._nutrition.assessment(indicators, patient, measured_on, weight, height, scope)

    def cancel(
        self,
        attention_id: int,
        command: AttentionCancellationInput,
        *,
        actor_id: int,
        actor_roles: Iterable[str] = (),
    ) -> AttentionResponse:
        """Applies a logical cancellation; clinical encounters are never deleted."""
        try:
            entity = self._attentions.get_by_id(attention_id, lock=True)
            if entity is None:
                raise NotFoundError(
                    code="ATENCION_NO_ENCONTRADA", message="No existe la atención solicitada."
                )
            self._ensure_actor_can_cancel_attention(
                actor_id=actor_id,
                actor_roles=actor_roles,
                professional_id=entity.profesional_id,
                recorded_by_id=getattr(entity, "created_by_usuario_id", None),
            )
            if entity.estado == "ANULADO":
                raise ConflictError(
                    code="ATENCION_YA_ANULADA", message="La atención ya fue anulada."
                )
            if entity.estado != "ATENDIDO":
                raise BusinessRuleError(
                    code="TRANSICION_ESTADO_NO_PERMITIDA",
                    message="El estado actual de la atención no permite anularla.",
                )
            if self._attentions.has_active_documents_for_attention(entity.id):
                raise BusinessRuleError(
                    code="ATENCION_CON_DOCUMENTOS_VIGENTES",
                    message=(
                        "No se puede anular una atención que tiene documentos emitidos vigentes. "
                        "Primero anule o cierre los documentos correspondientes."
                    ),
                )
            before = self._snapshot(entity)
            entity.estado = "ANULADO"
            entity.observaciones = self._with_cancellation_reason(
                entity.observaciones, command.observaciones
            )
            self._attentions.add_audit(
                actor_id=actor_id,
                action="CANCEL",
                record_id=entity.id,
                before=before,
                after=self._snapshot(entity),
            )
            self._session.commit()
            return attention_to_response(entity)
        except Exception:
            self._session.rollback()
            raise

    def _validate_clinical_context(self, command: AttentionCreate) -> None:
        AttentionContextValidator(self._attentions).validate(command)

    def _ensure_actor_is_linked_professional(
        self,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
    ) -> int:
        return self._access.linked_professional(actor_id=actor_id, actor_roles=actor_roles)

    def _ensure_actor_can_cancel_attention(
        self,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
        professional_id: int | None,
        recorded_by_id: int | None = None,
    ) -> None:
        self._access.ensure_cancellation(
            actor_id=actor_id,
            actor_roles=actor_roles,
            professional_id=professional_id,
            recorded_by_id=recorded_by_id,
        )

    def _ensure_attention_in_scope(
        self,
        entity: Attention,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> None:
        scope = self._resolve_clinical_scope(actor_id=actor_id, actor_roles=actor_roles)
        self._access.ensure_attention(entity, scope, actor_id=actor_id)

    def _ensure_patient_in_scope(
        self,
        patient_id: int,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> tuple[int, set[int]] | None:
        scope = self._resolve_clinical_scope(actor_id=actor_id, actor_roles=actor_roles)
        self._access.ensure_patient(patient_id, scope)
        return scope

    def _resolve_clinical_scope(
        self,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> tuple[int, set[int]] | None:
        return self._access.attention_scope(actor_id=actor_id, actor_roles=actor_roles)

    def _validate_attention_dates(self, command: AttentionCreate, attention_date: date) -> None:
        today = self._today_provider()
        if attention_date > today:
            raise BusinessRuleError(
                code="FECHA_ATENCION_FUTURA",
                message="La fecha de atención no puede estar en el futuro.",
            )
        if command.fecha_atendido is not None and command.fecha_atendido.date() > today:
            raise BusinessRuleError(
                code="FECHA_ATENDIDO_FUTURA",
                message="La fecha de atención efectiva no puede estar en el futuro.",
            )

    def _validate_vital_signs(self, command: AttentionCreate, age_in_months: int) -> None:
        self._validate_measurements(
            VitalSignPayload(
                peso_kg=command.peso_kg,
                talla_cm=command.talla_cm,
                perimetro_abdominal_cm=command.perimetro_abdominal_cm,
                presion_sistolica=command.presion_sistolica,
                presion_diastolica=command.presion_diastolica,
                temperatura_c=command.temperatura_c,
            ),
            age_in_months,
        )

    def _validate_measurements(self, values: VitalSignPayload, age_in_months: int) -> None:
        self._nutrition.validate_measurements(values, age_in_months)

    def _add_details(self, entity: Attention, command: AttentionCreate) -> None:
        service_details: list[tuple[int, str, Decimal]] = []
        for order, item in enumerate(command.prestaciones, start=1):
            if self._attentions.get_active_service_offering(item.prestacion_codigo) is None:
                raise NotFoundError(
                    code="PRESTACION_NO_ACTIVA",
                    message=f"La prestación {item.prestacion_codigo} no existe o está inactiva.",
                )
            service_details.append((order, item.prestacion_codigo, item.cantidad))
        diagnosis_details: list[tuple[int, str, str | None, str | None]] = []
        for order, item in enumerate(command.diagnosticos, start=1):
            if self._attentions.get_active_cie10(item.cie10_codigo) is None:
                raise NotFoundError(
                    code="CIE10_NO_ACTIVO",
                    message=f"El código CIE-10 {item.cie10_codigo} no existe o está inactivo.",
                )
            diagnosis_details.append(
                (order, item.cie10_codigo, item.tipo_diagnostico, item.observacion)
            )
        self._attentions.add_details(
            attention_id=entity.id,
            service_details=service_details,
            diagnosis_details=diagnosis_details,
        )

    def _add_nutritional_snapshot(
        self,
        entity: Attention,
        command: AttentionCreate,
        age: CalendarAge,
        indicators: NutritionalIndicators,
    ) -> None:
        self._nutrition.add_nutritional_snapshot(entity, command, age, indicators)

    @staticmethod
    def _validate_nutrition_record(
        command: AttentionCreate, birth_date: date, age: CalendarAge
    ) -> None:
        NutritionAssessmentService.validate_nutrition_record(command, birth_date, age)

    @staticmethod
    def _with_cancellation_reason(existing: str | None, reason: str) -> str:
        cancellation = f"[ANULACIÓN] {reason}"
        return f"{existing}\n{cancellation}" if existing else cancellation

    @staticmethod
    def _snapshot(entity: Attention) -> dict[str, object]:
        return {
            "id": entity.id,
            "paciente_id": entity.paciente_id,
            "establecimiento_id": entity.establecimiento_id,
            "profesional_id": entity.profesional_id,
            "consultorio_id": entity.consultorio_id,
            "modalidad_atencion_codigo": entity.modalidad_atencion_codigo,
            "grupo_etario_codigo": entity.grupo_etario_codigo,
            "grupo_atencion_codigo": entity.grupo_atencion_codigo,
            "fecha_atencion": entity.fecha_atencion.isoformat(),
            "historia_clinica_snapshot": entity.historia_clinica_snapshot,
            "imc": str(entity.imc) if entity.imc is not None else None,
            "pe": entity.pe,
            "te": entity.te,
            "pt": entity.pt,
            "referencia_nutricional": entity.referencia_nutricional,
            "estado": entity.estado,
            "observaciones": entity.observaciones,
            "numero_referencia_ingreso": getattr(entity, "numero_referencia_ingreso", None),
            "numero_contrarreferencia_ingreso": getattr(
                entity, "numero_contrarreferencia_ingreso", None
            ),
        }

    @property
    def _access(self) -> ClinicalAccessService:
        return ClinicalAccessService(self._attentions, self._patients)

    @property
    def _nutrition(self) -> NutritionAssessmentService:
        return NutritionAssessmentService(self._attentions, self._clinical_protocol)
