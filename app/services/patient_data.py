"""PatientDataRules: validation only; transaction ownership remains in PatientService."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from app.domain.family_history import family_history_problem, split_family_history
from app.domain.patient_document import document_problem
from app.domain.patient_insurance import SIS_FIELDS, is_sis_insurance
from app.exceptions import (
    ConflictError,
    ValidationDomainError,
)
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.schemas.patient_sis import affiliation_problem


class PatientDataRules:
    def __init__(self, repository: PatientRepository, today_provider: Callable[[], date]) -> None:
        self._repository = repository
        self._today_provider = today_provider

    def validate_patient_catalogs(
        self,
        *,
        document_type_code: str,
        sex_code: str | None,
        insurance_id: int | None,
        ubigeo_code: str | None,
        establishment_id: int | None,
    ) -> None:
        self.require_active_document_type(document_type_code)
        if sex_code is not None and self._repository.get_active_sex(sex_code) is None:
            self.raise_unavailable_catalog("sexo", sex_code)
        if insurance_id is not None and self._repository.get_active_insurance(insurance_id) is None:
            self.raise_unavailable_catalog("seguro", insurance_id)
        if ubigeo_code is not None and self._repository.get_ubigeo(ubigeo_code) is None:
            self.raise_unavailable_catalog("ubigeo", ubigeo_code)
        if (
            establishment_id is not None
            and self._repository.get_active_establishment(establishment_id) is None
        ):
            self.raise_unavailable_catalog("establecimiento", establishment_id)

    def validate_family_history(self, value: str | None) -> None:
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
            self.raise_unavailable_catalog("prefijo de historia familiar", parts[0])

    @staticmethod
    def validate_patient_residence(
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

    def normalize_patient_locality(
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
            self.raise_unavailable_catalog("localidad", localidad_id)
        values["localidad"] = locality.nombre

    @staticmethod
    def validate_document_number(document_type: str, number: str) -> None:
        problem = document_problem(document_type, number)
        if problem:
            raise ValidationDomainError(code="DOCUMENTO_INVALIDO", message=problem)

    def validate_insurance_affiliation(self, values: dict[str, Any]) -> None:
        if not any(values.get(key) for key in SIS_FIELDS):
            return
        insurance_id = values.get("seguro_id")
        insurance = self._repository.get_active_insurance(insurance_id) if insurance_id else None
        if not is_sis_insurance(insurance):
            raise ValidationDomainError(
                code="AFILIACION_SIN_SEGURO_SIS",
                message="Seleccione un seguro del régimen SIS antes de registrar su afiliación.",
            )

    def validate_sis_and_ethnicity(self, values: dict[str, Any]) -> None:
        problem = affiliation_problem(values)
        if problem:
            raise ValidationDomainError(code="AFILIACION_SIS_INCOMPLETA", message=problem)
        ethnicity = values.get("etnia_codigo")
        if ethnicity and not self._repository.get_active_ethnicity(ethnicity):
            self.raise_unavailable_catalog("código de etnia", ethnicity)

    def validate_changed_patient_catalogs(self, values: dict[str, Any]) -> None:
        if "sexo_codigo" in values and values["sexo_codigo"] is not None:
            if self._repository.get_active_sex(values["sexo_codigo"]) is None:
                self.raise_unavailable_catalog("sexo", values["sexo_codigo"])
        if "seguro_id" in values and values["seguro_id"] is not None:
            if self._repository.get_active_insurance(values["seguro_id"]) is None:
                self.raise_unavailable_catalog("seguro", values["seguro_id"])
        if "ubigeo_residencia_codigo" in values and values["ubigeo_residencia_codigo"] is not None:
            if self._repository.get_ubigeo(values["ubigeo_residencia_codigo"]) is None:
                self.raise_unavailable_catalog("ubigeo", values["ubigeo_residencia_codigo"])
        if (
            "establecimiento_registro_id" in values
            and values["establecimiento_registro_id"] is not None
        ):
            if (
                self._repository.get_active_establishment(values["establecimiento_registro_id"])
                is None
            ):
                self.raise_unavailable_catalog(
                    "establecimiento", values["establecimiento_registro_id"]
                )

    def ensure_document_is_available(
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

    def require_active_document_type(self, code: str) -> None:
        if self._repository.get_active_document_type(code) is None:
            self.raise_unavailable_catalog("tipo de documento", code)

    @staticmethod
    def raise_unavailable_catalog(catalog: str, value: object) -> None:
        raise ValidationDomainError(
            code="CATALOGO_NO_DISPONIBLE",
            message=f"El {catalog} '{value}' no existe o no está activo.",
            details={"catalogo": catalog, "valor": value},
        )

    def validate_birth_and_registration_dates(
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
