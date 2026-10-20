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

from app.domain.age import completed_months
from app.domain.family_history import family_history_problem, split_family_history
from app.domain.nutrition_followup import FOLLOWUP_GROUPS
from app.domain.patient_document import document_problem
from app.domain.patient_insurance import SIS_FIELDS, is_sis_insurance
from app.exceptions import (
    AuthorizationError,
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
from app.models.patient import Patient
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
    ResponsibleRelationship,
)
from app.schemas.patient_sis import affiliation_problem


class AuditWriter(Protocol):
    """Port used to register an auditable change in the active transaction."""

    def record(
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
            self._validate_birth_and_registration_dates(
                command.fecha_nacimiento,
                command.fecha_inscripcion,
            )
            self._validate_patient_catalogs(
                document_type_code=command.tipo_documento_codigo,
                sex_code=command.sexo_codigo,
                insurance_id=command.seguro_id,
                ubigeo_code=command.ubigeo_residencia_codigo,
                establishment_id=command.establecimiento_registro_id,
            )
            self._validate_family_history(command.historia_familiar)
            self._validate_document_number(command.tipo_documento_codigo, command.numero_documento)
            self._validate_insurance_affiliation(command.model_dump())
            self._validate_sis_and_ethnicity(command.model_dump())
            values = patient_create_to_entity_kwargs(command)
            self._normalize_patient_locality(values)
            self._validate_patient_residence(
                ubigeo_code=command.ubigeo_residencia_codigo,
                locality=values.get("localidad"),
            )
            self._ensure_document_is_available(
                command.tipo_documento_codigo,
                command.numero_documento,
            )
            self._validate_new_responsibles(
                command.responsables,
                birth_date=command.fecha_nacimiento,
                registration_date=command.fecha_inscripcion,
            )
            self._validate_new_risks(command.riesgos)

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
                risk_values.update(self._risk_origin(patient, risk_command, actor_id, actor_roles))
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
            self._validate_birth_and_registration_dates(
                effective_birth_date,
                effective_registration_date,
            )

            effective_document_type = values.get(
                "tipo_documento_codigo", patient.tipo_documento_codigo
            )
            effective_document_number = values.get("numero_documento", patient.numero_documento)
            if "tipo_documento_codigo" in values or "numero_documento" in values:
                self._require_active_document_type(effective_document_type)
                self._validate_document_number(effective_document_type, effective_document_number)
                self._ensure_document_is_available(
                    effective_document_type,
                    effective_document_number,
                    exclude_patient_id=patient.id,
                )

            self._validate_changed_patient_catalogs(values)
            if "historia_familiar" in values:
                self._validate_family_history(values["historia_familiar"])
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
                self._validate_insurance_affiliation(
                    {
                        key: values.get(key, getattr(patient, key, None))
                        for key in (*SIS_FIELDS, "seguro_id")
                    }
                )
            sis_keys = ("sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia", "etnia_codigo")
            if any(key in values for key in sis_keys):
                self._validate_sis_and_ethnicity(
                    {key: values.get(key, getattr(patient, key, None)) for key in sis_keys}
                )
            effective_ubigeo_code = values.get(
                "ubigeo_residencia_codigo", patient.ubigeo_residencia_codigo
            )
            if any(
                key in values for key in ("localidad_id", "localidad", "ubigeo_residencia_codigo")
            ):
                self._normalize_patient_locality(values, patient)
            effective_locality = values.get("localidad", patient.localidad)
            self._validate_patient_residence(
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
            self._ensure_minor_has_active_responsible(
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
            self._validate_responsible(command)
            self._ensure_active_principal_limit([*active, *([command] if command.activo else [])])

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
            self._validate_responsible_update(responsible, values)

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
            self._ensure_minor_has_active_responsible(
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
            self._validate_risk_dates(command.fecha_inicio, command.fecha_fin)
            self._require_active_risk_group(command.grupo_riesgo_id)
            origin = self._risk_origin(patient, command, actor_id, actor_roles)
            self._ensure_risk_does_not_overlap(
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
            self._validate_risk_dates(risk.fecha_inicio, effective_end)
            group = self._repository.get_active_risk_group(risk_group_id)
            code = getattr(group, "codigo", None) or getattr(
                getattr(risk, "grupo_riesgo", None), "codigo", None
            )
            if code in FOLLOWUP_GROUPS:
                self._validate_followup_fields(
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
            self._ensure_risk_does_not_overlap(
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
        """Require a clinician to have an assigned-site or care relationship.

        Administrators deliberately retain break-glass access.  Public routes
        always provide the authenticated principal; a ``None`` role context is
        reserved for internal callers and preserves the framework-independent
        service API used by maintenance jobs/tests.
        """

        scope = self._resolve_professional_scope(actor_id=actor_id, actor_roles=actor_roles)
        if scope is None:
            return
        professional_id, establishment_ids = scope
        if not self._repository.is_patient_in_professional_scope(
            patient_id=patient_id,
            professional_id=professional_id,
            establishment_ids=establishment_ids,
        ):
            raise AuthorizationError(
                code="PACIENTE_FUERA_DE_AMBITO",
                message="El paciente no pertenece a su ámbito asistencial.",
            )

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
        if actor_roles is None:
            return None
        normalized_roles = {role.upper() for role in actor_roles}
        if "ADMIN" in normalized_roles:
            return None
        if actor_id is None:
            raise AuthorizationError(
                code="ACTOR_CLINICO_REQUERIDO",
                message="Se requiere una identidad clínica autenticada.",
            )
        professional_id = self._repository.get_active_professional_id_for_user(actor_id)
        if professional_id is None:
            raise AuthorizationError(
                code="USUARIO_PROFESIONAL_SIN_VINCULO",
                message="El usuario clínico no está vinculado a un profesional activo.",
            )
        return (
            professional_id,
            self._repository.get_active_establishment_ids_for_professional(professional_id),
        )

    def _validate_patient_catalogs(
        self,
        *,
        document_type_code: str,
        sex_code: str | None,
        insurance_id: int | None,
        ubigeo_code: str | None,
        establishment_id: int | None,
    ) -> None:
        self._require_active_document_type(document_type_code)
        if sex_code is not None and self._repository.get_active_sex(sex_code) is None:
            self._raise_unavailable_catalog("sexo", sex_code)
        if insurance_id is not None and self._repository.get_active_insurance(insurance_id) is None:
            self._raise_unavailable_catalog("seguro", insurance_id)
        if ubigeo_code is not None and self._repository.get_ubigeo(ubigeo_code) is None:
            self._raise_unavailable_catalog("ubigeo", ubigeo_code)
        if (
            establishment_id is not None
            and self._repository.get_active_establishment(establishment_id) is None
        ):
            self._raise_unavailable_catalog("establecimiento", establishment_id)

    def _validate_family_history(self, value: str | None) -> None:
        problem = family_history_problem(value)
        if problem:
            raise ValidationDomainError(
                code="HISTORIA_FAMILIAR_INVALIDA",
                message=problem,
                details={"campo": "historia_familiar"},
            )
        parts = split_family_history(value)
        if (
            parts is not None
            and self._repository.get_active_family_history_prefix(parts[0]) is None
        ):
            self._raise_unavailable_catalog("prefijo de historia familiar", parts[0])

    @staticmethod
    def _validate_patient_residence(
        *,
        ubigeo_code: str | None,
        locality: str | None,
    ) -> None:
        """Keep the residence hierarchy explicit: district, locality, address."""

        if not locality:
            return
        if ubigeo_code is None:
            raise ValidationDomainError(
                code="LOCALIDAD_SIN_DISTRITO",
                message="Seleccione un distrito antes de registrar la localidad.",
            )
        if locality == ubigeo_code:
            raise ValidationDomainError(
                code="LOCALIDAD_NO_PUEDE_SER_CODIGO_UBIGEO",
                message="La localidad debe ser un nombre, no el código de ubigeo.",
            )

    def _normalize_patient_locality(
        self,
        values: dict[str, Any],
        patient: Patient | None = None,
    ) -> None:
        """The catalog owns both district membership and the saved locality name."""
        localidad_id = values.get("localidad_id", getattr(patient, "localidad_id", None))
        ubigeo_code = values.get(
            "ubigeo_residencia_codigo", getattr(patient, "ubigeo_residencia_codigo", None)
        )
        if localidad_id is None:
            if "localidad_id" in values and "localidad" not in values:
                values["localidad"] = None
            return
        if ubigeo_code is None:
            raise ValidationDomainError(
                code="LOCALIDAD_SIN_DISTRITO",
                message="Seleccione un distrito antes de registrar la localidad.",
            )
        locality = self._repository.get_active_localidad(localidad_id, ubigeo_code)
        if locality is None:
            self._raise_unavailable_catalog("localidad", localidad_id)
        values["localidad"] = locality.nombre

    @staticmethod
    def _validate_document_number(document_type: str, number: str) -> None:
        problem = document_problem(document_type, number)
        if problem:
            raise ValidationDomainError(code="DOCUMENTO_INVALIDO", message=problem)

    def _validate_insurance_affiliation(self, values: dict[str, Any]) -> None:
        if not any(values.get(key) for key in SIS_FIELDS):
            return
        insurance_id = values.get("seguro_id")
        insurance = self._repository.get_active_insurance(insurance_id) if insurance_id else None
        if not is_sis_insurance(insurance):
            raise ValidationDomainError(
                code="AFILIACION_SIN_SEGURO_SIS",
                message="Seleccione un seguro del régimen SIS antes de registrar su afiliación.",
            )

    def _validate_sis_and_ethnicity(self, values: dict[str, Any]) -> None:
        problem = affiliation_problem(values)
        if problem:
            raise ValidationDomainError(code="AFILIACION_SIS_INCOMPLETA", message=problem)
        ethnicity = values.get("etnia_codigo")
        if ethnicity and not self._repository.get_active_ethnicity(ethnicity):
            self._raise_unavailable_catalog("código de etnia", ethnicity)

    def _validate_changed_patient_catalogs(self, values: dict[str, Any]) -> None:
        if "sexo_codigo" in values and values["sexo_codigo"] is not None:
            if self._repository.get_active_sex(values["sexo_codigo"]) is None:
                self._raise_unavailable_catalog("sexo", values["sexo_codigo"])
        if "seguro_id" in values and values["seguro_id"] is not None:
            if self._repository.get_active_insurance(values["seguro_id"]) is None:
                self._raise_unavailable_catalog("seguro", values["seguro_id"])
        if "ubigeo_residencia_codigo" in values and values["ubigeo_residencia_codigo"] is not None:
            if self._repository.get_ubigeo(values["ubigeo_residencia_codigo"]) is None:
                self._raise_unavailable_catalog("ubigeo", values["ubigeo_residencia_codigo"])
        if (
            "establecimiento_registro_id" in values
            and values["establecimiento_registro_id"] is not None
        ):
            if (
                self._repository.get_active_establishment(values["establecimiento_registro_id"])
                is None
            ):
                self._raise_unavailable_catalog(
                    "establecimiento", values["establecimiento_registro_id"]
                )

    def _validate_new_responsibles(
        self,
        commands: list[PatientResponsibleCreate],
        *,
        birth_date: date,
        registration_date: date | None,
    ) -> None:
        for command in commands:
            self._validate_responsible(command)
        active = [command for command in commands if command.activo]
        self._ensure_active_principal_limit(active)
        self._ensure_minor_has_active_responsible(
            birth_date=birth_date,
            registration_date=registration_date,
            active_responsibles=active,
        )

    def _validate_responsible(self, command: PatientResponsibleCreate) -> None:
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
            self._require_active_document_type(command.tipo_documento_codigo)

    def _validate_responsible_update(self, responsible: Any, values: dict[str, Any]) -> None:
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
            self._require_active_document_type(effective_type)

    @staticmethod
    def _ensure_active_principal_limit(active_responsibles: list[Any]) -> None:
        principals = [item for item in active_responsibles if item.es_principal]
        if len(principals) > 1:
            raise BusinessRuleError(
                code="RESPONSABLE_PRINCIPAL_DUPLICADO",
                message="Solo puede existir un responsable principal activo por paciente.",
            )

    def _ensure_minor_has_active_responsible(
        self,
        *,
        birth_date: date,
        registration_date: date | None,
        active_responsibles: list[Any],
    ) -> None:
        reference_date = registration_date or self._today_provider()
        if self._is_minor(birth_date, reference_date) and not active_responsibles:
            raise BusinessRuleError(
                code="MENOR_SIN_RESPONSABLE",
                message="Un paciente menor de 18 años debe tener al menos un responsable activo.",
            )

    def _validate_new_risks(self, commands: list[PatientRiskCreate]) -> None:
        by_group: dict[int, list[PatientRiskCreate]] = {}
        for command in commands:
            self._validate_risk_dates(command.fecha_inicio, command.fecha_fin)
            self._require_active_risk_group(command.grupo_riesgo_id)
            if command.atencion_origen_id is not None:
                raise ValidationDomainError(
                    code="ORIGEN_RIESGO_INVALIDO",
                    message=(
                        "Vincule el seguimiento a una atención después de registrar al paciente."
                    ),
                )
            periods = by_group.setdefault(command.grupo_riesgo_id, [])
            if any(
                self._periods_overlap(
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
    def _validate_followup_fields(start, end, reason, next_control, closure):
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

    def _risk_origin(self, patient, command, actor_id, actor_roles):
        from app.services.attention import AttentionService

        group = self._repository.get_active_risk_group(command.grupo_riesgo_id)
        code = getattr(group, "codigo", None)
        modern = code in FOLLOWUP_GROUPS
        if modern:
            self._validate_followup_fields(
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
            origin = AttentionService(self._session).get(
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
    def _validate_risk_dates(start_date: date, end_date: date | None) -> None:
        if end_date is not None and end_date < start_date:
            raise ValidationDomainError(
                code="PERIODO_RIESGO_INVALIDO",
                message="La fecha de fin del riesgo no puede ser anterior a su fecha de inicio.",
            )

    def _ensure_risk_does_not_overlap(
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

    def _ensure_document_is_available(
        self,
        document_type_code: str,
        document_number: str,
        *,
        exclude_patient_id: int | None = None,
    ) -> None:
        owner = self._repository.find_by_document(
            document_type_code,
            document_number,
            exclude_patient_id=exclude_patient_id,
        )
        if owner is not None:
            raise ConflictError(
                code="DOCUMENTO_PACIENTE_DUPLICADO",
                message="Ya existe un paciente registrado con ese tipo y número de documento.",
            )

    def _require_active_document_type(self, code: str) -> None:
        if self._repository.get_active_document_type(code) is None:
            self._raise_unavailable_catalog("tipo de documento", code)

    def _require_active_risk_group(self, risk_group_id: int) -> None:
        if self._repository.get_active_risk_group(risk_group_id) is None:
            self._raise_unavailable_catalog("grupo de riesgo", risk_group_id)

    @staticmethod
    def _raise_unavailable_catalog(catalog: str, value: object) -> None:
        raise ValidationDomainError(
            code="CATALOGO_NO_DISPONIBLE",
            message=f"El {catalog} '{value}' no existe o no está activo.",
            details={"catalogo": catalog, "valor": value},
        )

    def _validate_birth_and_registration_dates(
        self,
        birth_date: date,
        registration_date: date | None,
    ) -> None:
        today = self._today_provider()
        if birth_date > today:
            raise ValidationDomainError(
                code="FECHA_NACIMIENTO_FUTURA",
                message="La fecha de nacimiento no puede estar en el futuro.",
            )
        if registration_date is not None and registration_date > today:
            raise ValidationDomainError(
                code="FECHA_INSCRIPCION_FUTURA",
                message="La fecha de inscripción no puede estar en el futuro.",
            )
        reference_date = registration_date or today
        if birth_date > reference_date:
            raise ValidationDomainError(
                code="FECHA_NACIMIENTO_POSTERIOR_A_INSCRIPCION",
                message="La fecha de nacimiento debe ser anterior o igual a la inscripción.",
            )

    @staticmethod
    def _periods_overlap(
        first_start: date,
        first_end: date | None,
        second_start: date,
        second_end: date | None,
    ) -> bool:
        return first_start <= (second_end or date.max) and second_start <= (first_end or date.max)

    @staticmethod
    def _is_minor(birth_date: date, reference_date: date) -> bool:
        try:
            adulthood = birth_date.replace(year=birth_date.year + 18)
        except ValueError:
            # A 29-Feb birth reaches the age threshold on 28-Feb in a
            # non-leap year, avoiding an approximation by days.
            adulthood = birth_date.replace(year=birth_date.year + 18, day=28)
        return reference_date < adulthood

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
