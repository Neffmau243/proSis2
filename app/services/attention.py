"""Clinical attention use cases and their transactional business rules."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict
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
from app.domain.office import office_context
from app.domain.patient_condition import condition_for_attention
from app.exceptions import AuthorizationError, BusinessRuleError, ConflictError, NotFoundError
from app.mappers.attention import attention_to_response
from app.models.clinical import Attention
from app.models.surveillance import NutritionalEvaluation
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.schemas.attention import (
    AttentionCancellationInput,
    AttentionCreate,
    AttentionResponse,
    NutritionalIndicatorsPreviewInput,
    NutritionalIndicatorsResponse,
    NutritionalSnapshotInput,
)
from app.schemas.nutrition_record import ADULT_FIELDS, CHILD_FIELDS, PREGNANT_FIELDS
from app.services.age_group import AgeGroupService
from app.services.fua_print import build_fua_snapshot
from app.services.nutrition_context import nutrition_context


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
        self._age_groups = AgeGroupService(session)
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
            self._ensure_patient_in_scope(
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

            entity = Attention(
                paciente_id=patient.id,
                numero_referencia_ingreso=command.numero_referencia_ingreso or None,
                numero_contrarreferencia_ingreso=command.numero_contrarreferencia_ingreso or None,
                establecimiento_id=command.establecimiento_id,
                profesional_id=command.profesional_id,
                especialidad_codigo=command.especialidad_codigo,
                consultorio_id=command.consultorio_id,
                modalidad_atencion_codigo=command.modalidad_atencion_codigo.value,
                grupo_etario_codigo=age_group.codigo,
                grupo_atencion_codigo=command.grupo_atencion_codigo.value,
                fecha_atencion=command.fecha_atencion,
                fecha_atendido=command.fecha_atendido,
                historia_clinica_snapshot=patient.historia_clinica,
                edad_anios=age.years,
                peso_kg=command.peso_kg,
                talla_cm=command.talla_cm,
                perimetro_abdominal_cm=command.perimetro_abdominal_cm,
                tipo_embarazo_codigo=(
                    command.tipo_embarazo_codigo.value
                    if command.tipo_embarazo_codigo is not None
                    else None
                ),
                peso_antes_embarazo_kg=command.peso_antes_embarazo_kg,
                fecha_probable_parto=command.fecha_probable_parto,
                fecha_parto=command.fecha_parto,
                presion_sistolica=command.presion_sistolica,
                presion_diastolica=command.presion_diastolica,
                temperatura_c=command.temperatura_c,
                imc=indicators.imc,
                pe=self._format_indicator(indicators.pe),
                te=self._format_indicator(indicators.te),
                pt=self._format_indicator(indicators.pt),
                referencia_nutricional=indicators.referencia,
                valoracion_calculada=NutritionalIndicatorsResponse(
                    **asdict(indicators), **indicators.classifications
                ).model_dump(mode="json"),
                hora_inicio=command.hora_inicio,
                hora_fin=command.hora_fin,
                admision=command.admision,
                observaciones=command.observaciones,
                created_by_usuario_id=actor_id,
            )
            entity.contexto_clinico = nutrition_context(
                patient,
                self._attentions.get_active_establishment(command.establecimiento_id),
                age,
                condition,
                office=self._attentions.get_active_office(command.consultorio_id),
                professional=self._attentions.get_active_professional(command.profesional_id),
                specialty=(
                    self._attentions.get_active_specialty(command.especialidad_codigo)
                    if command.especialidad_codigo
                    else None
                ),
            )
            entity.fua_impresion = build_fua_snapshot(
                entity,
                patient,
                self._attentions.get_active_establishment(command.establecimiento_id),
                self._attentions.get_active_professional(command.profesional_id),
                command.fua_datos,
            )
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

        self._ensure_patient_in_scope(
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
        return NutritionalIndicatorsResponse(
            grupo_referencia=indicators.grupo_referencia,
            imc_edad=indicators.imc_edad,
            diagnostico_imc=indicators.diagnostico_imc,
            imc_pregestacional=indicators.imc_pregestacional,
            ganancia_peso_kg=indicators.ganancia_peso_kg,
            **indicators.classifications,
            imc=indicators.imc,
            pe=indicators.pe,
            te=indicators.te,
            pt=indicators.pt,
            estado=indicators.estado,
            mensaje=indicators.mensaje,
            referencia=indicators.referencia,
        )

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
        if self._attentions.get_active_establishment(command.establecimiento_id) is None:
            raise NotFoundError(
                code="ESTABLECIMIENTO_NO_ACTIVO",
                message="El establecimiento no existe o está inactivo.",
            )
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
        if self._attentions.get_active_mode(command.modalidad_atencion_codigo.value) is None:
            raise NotFoundError(
                code="MODALIDAD_NO_ACTIVA", message="La modalidad de atención no está activa."
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

    def _ensure_actor_is_linked_professional(
        self,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
    ) -> int:
        """Require a valid clinical identity before registering an attention.

        Administrative accounts deliberately cannot use this internal path,
        even if a router is accidentally widened later.  The user who records
        the attention remains in the audit trail, while the selected
        professional represents who attended the patient.
        """

        normalized_roles = {role.upper() for role in actor_roles}
        if "PROFESIONAL" not in normalized_roles:
            raise AuthorizationError(
                code="ROL_CLINICO_REQUERIDO",
                message="Solo un usuario PROFESIONAL vinculado puede operar atenciones.",
            )
        linked_professional_id = self._attentions.get_active_professional_id_for_user(actor_id)
        if linked_professional_id is None:
            raise AuthorizationError(
                code="USUARIO_PROFESIONAL_SIN_VINCULO",
                message="El usuario clínico no está vinculado a un profesional activo.",
            )
        return linked_professional_id

    def _ensure_actor_can_cancel_attention(
        self,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
        professional_id: int,
    ) -> None:
        """Keep cancellation restricted to the clinician who attended."""

        linked_professional_id = self._ensure_actor_is_linked_professional(
            actor_id=actor_id,
            actor_roles=actor_roles,
        )
        if linked_professional_id != professional_id:
            raise AuthorizationError(
                code="PROFESIONAL_DISTINTO_AL_USUARIO",
                message="Solo puede anular atenciones de su propio profesional.",
            )

    def _ensure_attention_in_scope(
        self,
        entity: Attention,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> None:
        """Apply object-level access when called from an authenticated route.

        ``actor_roles=None`` keeps the framework-independent service usable by
        internal maintenance code and existing unit doubles.  Public routes
        always pass the persisted principal and therefore cannot bypass this
        check.
        """

        scope = self._resolve_clinical_scope(actor_id=actor_id, actor_roles=actor_roles)
        if scope is None:
            return
        professional_id, establishment_ids = scope
        if (
            entity.profesional_id == professional_id
            or entity.establecimiento_id in establishment_ids
        ):
            return
        raise AuthorizationError(
            code="ATENCION_FUERA_DE_AMBITO",
            message="La atención no pertenece a su ámbito asistencial.",
        )

    def _ensure_patient_in_scope(
        self,
        patient_id: int,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> tuple[int, set[int]] | None:
        """Return the professional/site scope used by attention-history reads."""

        scope = self._resolve_clinical_scope(actor_id=actor_id, actor_roles=actor_roles)
        if scope is None:
            return None
        professional_id, establishment_ids = scope
        if not self._patients.is_patient_in_professional_scope(
            patient_id=patient_id,
            professional_id=professional_id,
            establishment_ids=establishment_ids,
        ):
            raise AuthorizationError(
                code="PACIENTE_FUERA_DE_AMBITO",
                message="El paciente no pertenece a su ámbito asistencial.",
            )
        return scope

    def _resolve_clinical_scope(
        self,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> tuple[int, set[int]] | None:
        """Resolve the authenticated clinician and their active assigned sites.

        ``None`` is reserved for internal framework-independent callers. All
        public clinical routes provide actor data, so a generic ADMIN account
        cannot reach this path without a PROFESIONAL role and database link.
        """

        if actor_roles is None:
            return None
        if actor_id is None:
            raise AuthorizationError(
                code="ACTOR_CLINICO_REQUERIDO",
                message="Se requiere una identidad clínica autenticada.",
            )
        normalized_roles = {role.upper() for role in actor_roles}
        if "PROFESIONAL" not in normalized_roles:
            raise AuthorizationError(
                code="ROL_CLINICO_REQUERIDO",
                message="Solo un usuario PROFESIONAL vinculado puede operar atenciones.",
            )
        professional_id = self._attentions.get_active_professional_id_for_user(actor_id)
        if professional_id is None:
            raise AuthorizationError(
                code="USUARIO_PROFESIONAL_SIN_VINCULO",
                message="El usuario clínico no está vinculado a un profesional activo.",
            )
        establishment_ids = self._patients.get_active_establishment_ids_for_professional(
            professional_id
        )
        return professional_id, establishment_ids

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
        """Preview and persistence must apply the same configured protocol."""
        try:
            self._clinical_protocol.validate(
                values,
                age_in_months=age_in_months,
            )
        except ValueError as exc:
            raise BusinessRuleError(code="SIGNOS_VITALES_INVALIDOS", message=str(exc)) from exc

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
    def _validate_nutrition_record(
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

    @staticmethod
    def _format_indicator(value: Decimal | None) -> str | None:
        return f"{value:.3f}" if value is not None else None

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
