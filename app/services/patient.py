"""Business use cases for the patient aggregate.

The service is intentionally framework-agnostic: it receives DTOs, a
repository/session and an audit port, and raises domain exceptions.  FastAPI
dependencies live exclusively in the controller module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from typing import Any, Protocol, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.nutrition_followup import FOLLOWUP_GROUPS
from app.domain.patient_insurance import SIS_FIELDS, is_sis_insurance
from app.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationDomainError,
)
from app.mappers.patient import (
    patient_create_to_entity_kwargs,
    patient_to_response,
    patient_update_to_entity_kwargs,
    responsible_create_to_entity_kwargs,
    responsible_to_response,
    responsible_update_to_entity_kwargs,
    risk_create_to_entity_kwargs,
    risk_to_response,
    risk_update_to_entity_kwargs,
)
from app.repositories.patient import PatientRepository
from app.schemas.patient import (
    PatientCreate,
    PatientDeactivationResponse,
    PatientResponse,
    PatientResponsibleCreate,
    PatientResponsibleResponse,
    PatientResponsibleUpdate,
    PatientRiskCreate,
    PatientRiskResponse,
    PatientRiskUpdate,
    PatientUpdate,
)
from app.services.attention_origin import AttentionOriginReader
from app.services.clinical_access import ClinicalAccessService
from app.services.patient_data import PatientDataRules
from app.services.patient_responsible import PatientResponsibleRules
from app.services.patient_risk import PatientRiskRules


class AuditWriter(Protocol):
    """Port used to register an auditable change in the active transaction."""

    # Typing-only declaration: executable audit adapters are covered separately.
    def record(  # pragma: no branch
        self,
        *,
        actor_id: int | None,
        action: str,
        table_name: str,
        record_id: int,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None: ...


class RepositoryAuditWriter:
    """Adapter that persists patient audit rows through ``PatientRepository``."""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    def record(
        self,
        *,
        actor_id: int | None,
        action: str,
        table_name: str,
        record_id: int,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        # The adapter is narrowly scoped to this aggregate.  A shared audit
        # service can implement the same protocol later without changing any
        # patient business rule.
        if table_name != "pacientes":
            raise ValueError("El adaptador de pacientes solo audita la tabla pacientes")
        self._repository.add_audit_entry(
            actor_id=actor_id,
            action=action,
            record_id=record_id,
            before=before,
            after=after,
        )


T = TypeVar("T")


class PatientService:
    """Coordinates patient rules, persistence and transactional auditing."""

    def __init__(
        self,
        session: Session,
        *,
        repository: PatientRepository | None = None,
        audit_writer: AuditWriter | None = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self._session = session
        self._repository = repository or PatientRepository(session)
        self._audit_writer = audit_writer or RepositoryAuditWriter(self._repository)
        self._today_provider = today_provider

    def get(
        self,
        patient_id: int,
        *,
        actor_id: int | None = None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientResponse:
        patient = self._repository.get_by_id(patient_id)
        if patient is None:
            raise NotFoundError(
                code="PACIENTE_NO_ENCONTRADO",
                message="No existe un paciente activo con el identificador indicado.",
            )
        self._ensure_patient_in_scope(
            patient.id,
            actor_id=actor_id,
            actor_roles=actor_roles,
        )
        return patient_to_response(patient)

    def create(
        self,
        command: PatientCreate,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientResponse:
        """Registers an adult or minor patient as one atomic operation."""

        def operation() -> PatientResponse:
            professional_id = self._registration_professional_id(
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            self._data_rules.validate_birth_and_registration_dates(
                command.fecha_nacimiento,
                command.fecha_inscripcion,
            )
            self._data_rules.validate_patient_catalogs(
                document_type_code=command.tipo_documento_codigo,
                sex_code=command.sexo_codigo,
                insurance_id=command.seguro_id,
                ubigeo_code=command.ubigeo_residencia_codigo,
                establishment_id=command.establecimiento_registro_id,
            )
            self._data_rules.validate_family_history(command.historia_familiar)
            self._data_rules.validate_document_number(
                command.tipo_documento_codigo, command.numero_documento
            )
            self._data_rules.validate_insurance_affiliation(command.model_dump())
            self._data_rules.validate_sis_and_ethnicity(command.model_dump())
            values = patient_create_to_entity_kwargs(command)
            self._data_rules.normalize_patient_locality(values)
            self._data_rules.validate_patient_residence(
                ubigeo_code=command.ubigeo_residencia_codigo,
                locality=values.get("localidad"),
            )
            self._data_rules.ensure_document_is_available(
                command.tipo_documento_codigo,
                command.numero_documento,
            )
            self._responsible_rules.validate_new_responsibles(
                command.responsables,
                birth_date=command.fecha_nacimiento,
                registration_date=command.fecha_inscripcion,
            )
            self._risk_rules.validate_new_risks(command.riesgos)

            # El autor clínico del registro conserva el acceso al paciente
            # aunque la sede elegida no esté entre sus asignaciones vigentes.
            values["profesional_registro_id"] = professional_id
            patient = self._repository.create_patient(values)
            self._repository.flush()

            for responsible_command in command.responsables:
                self._repository.create_responsible(
                    responsible_create_to_entity_kwargs(
                        responsible_command,
                        patient_id=patient.id,
                    )
                )

            for risk_command in command.riesgos:
                risk_values = risk_create_to_entity_kwargs(risk_command, patient_id=patient.id)
                risk_values.update(
                    self._risk_rules.risk_origin(patient, risk_command, actor_id, actor_roles)
                )
                self._repository.create_risk(risk_values)

            self._repository.flush()
            # The children are read straight from persistence. Manually appending
            # them to the collection duplicated every row in the response, because
            # the flush had already loaded those instances into the relationship.
            response = patient_to_response(patient)
            self._write_audit(
                actor_id=actor_id,
                action="INSERT",
                patient_id=patient.id,
                before=None,
                after=self._snapshot(response),
            )
            return response

        return self._in_transaction(operation)

    def update(
        self,
        patient_id: int,
        command: PatientUpdate,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientResponse:
        """Safely patches only permitted patient fields under a row lock."""

        def operation() -> PatientResponse:
            patient = self._require_active_patient(patient_id, for_update=True)
            self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            values = patient_update_to_entity_kwargs(command)
            if not values:
                raise ValidationDomainError(
                    code="ACTUALIZACION_SIN_CAMBIOS",
                    message=(
                        "Debe enviar al menos un campo modificable para actualizar al paciente."
                    ),
                )

            effective_birth_date = values.get("fecha_nacimiento", patient.fecha_nacimiento)
            effective_registration_date = values.get("fecha_inscripcion", patient.fecha_inscripcion)
            self._data_rules.validate_birth_and_registration_dates(
                effective_birth_date,
                effective_registration_date,
            )

            effective_document_type = values.get(
                "tipo_documento_codigo", patient.tipo_documento_codigo
            )
            effective_document_number = values.get("numero_documento", patient.numero_documento)
            if "tipo_documento_codigo" in values or "numero_documento" in values:
                self._data_rules.require_active_document_type(effective_document_type)
                self._data_rules.validate_document_number(
                    effective_document_type, effective_document_number
                )
                self._data_rules.ensure_document_is_available(
                    effective_document_type,
                    effective_document_number,
                    exclude_patient_id=patient.id,
                )

            self._data_rules.validate_changed_patient_catalogs(values)
            if "historia_familiar" in values:
                self._data_rules.validate_family_history(values["historia_familiar"])
            insurance = None
            if "seguro_id" in values:
                insurance = (
                    self._repository.get_active_insurance(values["seguro_id"])
                    if values["seguro_id"]
                    else None
                )
                if not is_sis_insurance(insurance):
                    # Changing insurer clears the current affiliation, never historic FUAs.
                    values.update(dict.fromkeys(SIS_FIELDS))
            # DISA/formato pertenecen al contrato del asegurado (trama FUA SIS,
            # campos afi#25 y afi#26), no al plan ETLSIS ni a la sede de registro.
            if "seguro_id" in values or any(key in values for key in SIS_FIELDS):
                self._data_rules.validate_insurance_affiliation(
                    {
                        key: values.get(key, getattr(patient, key, None))
                        for key in (*SIS_FIELDS, "seguro_id")
                    }
                )
            sis_keys = ("sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia", "etnia_codigo")
            if any(key in values for key in sis_keys):
                self._data_rules.validate_sis_and_ethnicity(
                    {key: values.get(key, getattr(patient, key, None)) for key in sis_keys}
                )
            effective_ubigeo_code = values.get(
                "ubigeo_residencia_codigo", patient.ubigeo_residencia_codigo
            )
            if any(
                key in values for key in ("localidad_id", "localidad", "ubigeo_residencia_codigo")
            ):
                self._data_rules.normalize_patient_locality(values, patient)
            effective_locality = values.get("localidad", patient.localidad)
            self._data_rules.validate_patient_residence(
                ubigeo_code=effective_ubigeo_code,
                locality=effective_locality,
            )
            if "establecimiento_registro_id" in values:
                # Trasladar la inscripción no debe dejar al autor del traslado
                # sin acceso al paciente que acaba de mover de sede.
                values["profesional_registro_id"] = self._registration_professional_id(
                    actor_id=actor_id,
                    actor_roles=actor_roles,
                )
            self._responsible_rules.ensure_minor_has_active_responsible(
                birth_date=effective_birth_date,
                registration_date=effective_registration_date,
                active_responsibles=self._repository.get_active_responsibles(patient.id),
            )

            before = self._snapshot(patient_to_response(patient))
            self._repository.update_fields(patient, values)
            self._repository.flush()
            response = patient_to_response(patient)
            self._write_audit(
                actor_id=actor_id,
                action="UPDATE",
                patient_id=patient.id,
                before=before,
                after=self._snapshot(response),
            )
            return response

        return self._in_transaction(operation)

    def deactivate(
        self,
        patient_id: int,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientDeactivationResponse:
        """Performs a logical deletion and writes its audit event."""

        def operation() -> PatientDeactivationResponse:
            patient = self._require_active_patient(patient_id, for_update=True)
            self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            before = self._snapshot(patient_to_response(patient))
            self._repository.deactivate(patient)
            self._repository.flush()
            after_response = patient_to_response(patient)
            self._write_audit(
                actor_id=actor_id,
                action="DEACTIVATE",
                patient_id=patient.id,
                before=before,
                after=self._snapshot(after_response),
            )
            return PatientDeactivationResponse(
                id=patient.id,
                estado=False,
                mensaje="Paciente dado de baja de forma lógica.",
            )

        return self._in_transaction(operation)

    def add_responsible(
        self,
        patient_id: int,
        command: PatientResponsibleCreate,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientResponsibleResponse:
        """Adds a responsible person without replacing historical records."""

        def operation() -> PatientResponsibleResponse:
            patient = self._require_active_patient(patient_id, for_update=True)
            self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            active = self._repository.get_active_responsibles(patient.id)
            self._responsible_rules.validate_responsible(command)
            self._responsible_rules.ensure_active_principal_limit(
                [*active, *([command] if command.activo else [])]
            )

            responsible = self._repository.create_responsible(
                responsible_create_to_entity_kwargs(command, patient_id=patient.id)
            )
            # Attaching the child by hand here would duplicate the row that the
            # flush already places in the collection.
            self._repository.flush()
            response = responsible_to_response(responsible)
            self._write_audit(
                actor_id=actor_id,
                action="UPDATE",
                patient_id=patient.id,
                before=None,
                after={"responsable_agregado": response.model_dump(mode="json")},
            )
            return response

        return self._in_transaction(operation)

    def update_responsible(
        self,
        patient_id: int,
        responsible_id: int,
        command: PatientResponsibleUpdate,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientResponsibleResponse:
        """Updates an existing responsible while preserving minor safeguards."""

        def operation() -> PatientResponsibleResponse:
            patient = self._require_active_patient(patient_id, for_update=True)
            self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            responsible = self._repository.get_responsible(
                patient.id,
                responsible_id,
                for_update=True,
            )
            if responsible is None:
                raise NotFoundError(
                    code="RESPONSABLE_NO_ENCONTRADO",
                    message="No existe el responsable indicado para este paciente.",
                )

            values = responsible_update_to_entity_kwargs(command)
            if not values:
                raise ValidationDomainError(
                    code="ACTUALIZACION_SIN_CAMBIOS",
                    message=(
                        "Debe enviar al menos un campo modificable para actualizar al responsable."
                    ),
                )
            self._responsible_rules.validate_responsible_update(responsible, values)

            effective_active = values.get("activo", responsible.activo)
            effective_principal = values.get("es_principal", responsible.es_principal)
            if effective_active and effective_principal:
                other = self._repository.find_other_active_principal(
                    patient.id,
                    exclude_responsible_id=responsible.id,
                )
                if other is not None:
                    raise BusinessRuleError(
                        code="RESPONSABLE_PRINCIPAL_DUPLICADO",
                        message="Solo puede existir un responsable principal activo por paciente.",
                    )

            remaining_active = [
                item
                for item in self._repository.get_active_responsibles(patient.id)
                if item.id != responsible.id
            ]
            if effective_active:
                remaining_active.append(responsible)
            self._responsible_rules.ensure_minor_has_active_responsible(
                birth_date=patient.fecha_nacimiento,
                registration_date=patient.fecha_inscripcion,
                active_responsibles=remaining_active,
            )

            before = responsible_to_response(responsible).model_dump(mode="json")
            self._repository.update_fields(responsible, values)
            self._repository.flush()
            response = responsible_to_response(responsible)
            self._write_audit(
                actor_id=actor_id,
                action="UPDATE",
                patient_id=patient.id,
                before={"responsable": before},
                after={"responsable": response.model_dump(mode="json")},
            )
            return response

        return self._in_transaction(operation)

    def add_risk(
        self,
        patient_id: int,
        command: PatientRiskCreate,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientRiskResponse:
        """Adds a non-overlapping risk interval for one patient and group."""

        def operation() -> PatientRiskResponse:
            patient = self._require_active_patient(patient_id, for_update=True)
            self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            self._risk_rules.validate_risk_dates(command.fecha_inicio, command.fecha_fin)
            self._risk_rules.require_active_risk_group(command.grupo_riesgo_id)
            origin = self._risk_rules.risk_origin(patient, command, actor_id, actor_roles)
            self._risk_rules.ensure_risk_does_not_overlap(
                patient.id,
                command.grupo_riesgo_id,
                start_date=command.fecha_inicio,
                end_date=command.fecha_fin,
            )

            risk = self._repository.create_risk(
                {**risk_create_to_entity_kwargs(command, patient_id=patient.id), **origin}
            )
            patient.riesgos.append(risk)
            self._repository.flush()
            response = risk_to_response(risk)
            self._write_audit(
                actor_id=actor_id,
                action="UPDATE",
                patient_id=patient.id,
                before=None,
                after={"riesgo_agregado": response.model_dump(mode="json")},
            )
            return response

        return self._in_transaction(operation)

    def update_risk(
        self,
        patient_id: int,
        risk_group_id: int,
        start_date: date,
        command: PatientRiskUpdate,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None = None,
    ) -> PatientRiskResponse:
        """Closes/annotates a risk period without mutating its composite key."""

        def operation() -> PatientRiskResponse:
            patient = self._require_active_patient(patient_id, for_update=True)
            self._ensure_patient_in_scope(
                patient.id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            risk = self._repository.get_risk(
                patient.id,
                risk_group_id,
                start_date,
                for_update=True,
            )
            if risk is None:
                raise NotFoundError(
                    code="RIESGO_NO_ENCONTRADO",
                    message="No existe el periodo de riesgo indicado para este paciente.",
                )
            values = risk_update_to_entity_kwargs(command)
            if not values:
                raise ValidationDomainError(
                    code="ACTUALIZACION_SIN_CAMBIOS",
                    message="Debe enviar al menos un campo modificable para actualizar el riesgo.",
                )
            effective_end = values.get("fecha_fin", risk.fecha_fin)
            self._risk_rules.validate_risk_dates(risk.fecha_inicio, effective_end)
            group = self._repository.get_active_risk_group(risk_group_id)
            code = getattr(group, "codigo", None) or getattr(
                getattr(risk, "grupo_riesgo", None), "codigo", None
            )
            if code in FOLLOWUP_GROUPS:
                self._risk_rules.validate_followup_fields(
                    risk.fecha_inicio,
                    effective_end,
                    values.get("observacion", risk.observacion),
                    values.get(
                        "fecha_proximo_control", getattr(risk, "fecha_proximo_control", None)
                    ),
                    values.get("motivo_cierre", getattr(risk, "motivo_cierre", None)),
                )
                if effective_end is None:
                    values["motivo_cierre"] = None
                else:
                    values["fecha_proximo_control"] = None
            self._risk_rules.ensure_risk_does_not_overlap(
                patient.id,
                risk.grupo_riesgo_id,
                start_date=risk.fecha_inicio,
                end_date=effective_end,
                exclude_start_date=risk.fecha_inicio,
            )

            before = risk_to_response(risk).model_dump(mode="json")
            self._repository.update_fields(risk, values)
            self._repository.flush()
            response = risk_to_response(risk)
            self._write_audit(
                actor_id=actor_id,
                action="UPDATE",
                patient_id=patient.id,
                before={"riesgo": before},
                after={"riesgo": response.model_dump(mode="json")},
            )
            return response

        return self._in_transaction(operation)

    def _in_transaction(self, operation: Callable[[], T]) -> T:
        """Commits all validation, persistence and audit work atomically."""

        try:
            result = operation()
            self._session.commit()
            return result
        except IntegrityError as exc:
            self._session.rollback()
            raise self._translate_integrity_error(exc) from exc
        except Exception:
            self._session.rollback()
            raise

    def _require_active_patient(self, patient_id: int, *, for_update: bool):
        patient = self._repository.get_by_id(patient_id, for_update=for_update)
        if patient is None:
            raise NotFoundError(
                code="PACIENTE_NO_ENCONTRADO",
                message="No existe un paciente activo con el identificador indicado.",
            )
        return patient

    def _ensure_patient_in_scope(
        self,
        patient_id: int,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> None:
        scope = self._resolve_professional_scope(actor_id=actor_id, actor_roles=actor_roles)
        self._access.ensure_patient(patient_id, scope)

    def _registration_professional_id(
        self,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> int | None:
        """Resolver el clínico que firma el registro o el traslado.

        Los administradores y los llamadores internos (``actor_roles`` nulo)
        mantienen el vínculo previo, igual que conservan el acceso global.
        """

        scope = self._resolve_professional_scope(actor_id=actor_id, actor_roles=actor_roles)
        return None if scope is None else scope[0]

    def _resolve_professional_scope(
        self,
        *,
        actor_id: int | None,
        actor_roles: Iterable[str] | None,
    ) -> tuple[int, set[int]] | None:
        return self._access.patient_scope(actor_id=actor_id, actor_roles=actor_roles)

    def _write_audit(
        self,
        *,
        actor_id: int | None,
        action: str,
        patient_id: int,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        self._audit_writer.record(
            actor_id=actor_id,
            action=action,
            table_name="pacientes",
            record_id=patient_id,
            before=before,
            after=after,
        )

    @staticmethod
    def _snapshot(response: PatientResponse) -> dict[str, Any]:
        """JSON-compatible representation suitable for the MySQL JSON columns."""

        return response.model_dump(mode="json")

    @staticmethod
    def _translate_integrity_error(error: IntegrityError) -> ConflictError:
        message = str(error.orig).lower() if error.orig is not None else str(error).lower()
        if "uq_pacientes_documento" in message or "tipo_documento_codigo" in message:
            return ConflictError(
                code="DOCUMENTO_PACIENTE_DUPLICADO",
                message="Ya existe un paciente registrado con ese tipo y número de documento.",
            )
        return ConflictError(
            code="CONFLICTO_PERSISTENCIA_PACIENTE",
            message=(
                "No se pudo guardar el paciente porque otro cambio dejó los datos en conflicto."
            ),
        )

    @property
    def _access(self) -> ClinicalAccessService:
        return ClinicalAccessService(self._repository)

    @property
    def _data_rules(self) -> PatientDataRules:
        return PatientDataRules(self._repository, self._today_provider)

    @property
    def _responsible_rules(self) -> PatientResponsibleRules:
        return PatientResponsibleRules(self._data_rules, self._today_provider)

    @property
    def _risk_rules(self) -> PatientRiskRules:
        return PatientRiskRules(self._repository, AttentionOriginReader(self._session))
