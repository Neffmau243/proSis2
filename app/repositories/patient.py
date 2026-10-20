"""SQLAlchemy persistence operations for the patient aggregate.

This module deliberately contains queries and entity state changes only.  It
does not decide whether a patient may be registered, updated or deactivated;
those decisions belong to :mod:`app.services.patient`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import DocumentType, Ethnicity, FamilyHistoryPrefix, Insurance, Sex
from app.models.organization import Establishment, Localidad, Ubigeo
from app.models.patient import Patient, PatientResponsible, PatientRisk, RiskGroup
from app.repositories.attention_scope import patient_visibility
from app.repositories.clinical_access import ClinicalAccessRepository


class PatientRepository:
    """Persistence gateway for patients, child records and required catalogs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(
        self,
        patient_id: int,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> Patient | None:
        """Fetches an aggregate with the relationships used by its response DTO."""

        statement = (
            select(Patient)
            .options(
                selectinload(Patient.ubigeo_residencia),
                selectinload(Patient.responsables),
                selectinload(Patient.riesgos).selectinload(PatientRisk.grupo_riesgo),
            )
            .where(Patient.id == patient_id)
        )
        if not include_inactive:
            statement = statement.where(Patient.estado.is_(True))
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).unique().scalar_one_or_none()

    def load_snapshot_relations(self, patient_id: int) -> None:
        """Populate projection inputs on the same locked patient identity."""
        self._session.execute(
            select(Patient)
            .where(Patient.id == patient_id)
            .options(
                selectinload(Patient.insurance),
                selectinload(Patient.ubigeo_residencia),
                selectinload(Patient.localidad_catalogo),
                selectinload(Patient.establecimiento_registro),
            )
        ).scalar_one()

    def find_by_document(
        self,
        document_type_code: str,
        document_number: str,
        *,
        exclude_patient_id: int | None = None,
    ) -> Patient | None:
        """Looks up a document owner, including logically inactive patients."""

        statement = select(Patient).where(
            Patient.tipo_documento_codigo == document_type_code,
            Patient.numero_documento == document_number,
        )
        if exclude_patient_id is not None:
            statement = statement.where(Patient.id != exclude_patient_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_document_type(self, code: str) -> DocumentType | None:
        statement = select(DocumentType).where(
            DocumentType.codigo == code,
            DocumentType.activo.is_(True),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_ethnicity(self, code: str) -> Ethnicity | None:
        return self._session.scalar(
            select(Ethnicity).where(Ethnicity.codigo == code, Ethnicity.activo.is_(True))
        )

    def get_active_sex(self, code: str) -> Sex | None:
        statement = select(Sex).where(Sex.codigo == code, Sex.activo.is_(True))
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_insurance(self, insurance_id: int) -> Insurance | None:
        statement = select(Insurance).where(
            Insurance.id == insurance_id,
            Insurance.activo.is_(True),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_family_history_prefix(self, code: str) -> FamilyHistoryPrefix | None:
        statement = select(FamilyHistoryPrefix).where(
            FamilyHistoryPrefix.codigo == code,
            FamilyHistoryPrefix.activo.is_(True),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_ubigeo(self, code: str) -> Ubigeo | None:
        """Ubigeo has no active flag in the supplied schema."""

        statement = select(Ubigeo).where(Ubigeo.codigo == code)
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_localidad(self, localidad_id: int, ubigeo_code: str | None) -> Localidad | None:
        """Locality scoped to its district, so it cannot cross UBIGEOs."""

        statement = select(Localidad).where(
            Localidad.id == localidad_id,
            Localidad.activo.is_(True),
        )
        if ubigeo_code is not None:
            statement = statement.where(Localidad.ubigeo_codigo == ubigeo_code)
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_establishment(self, establishment_id: int) -> Establishment | None:
        statement = select(Establishment).where(
            Establishment.id == establishment_id,
            Establishment.activo.is_(True),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_professional_id_for_user(self, user_id: int) -> int | None:
        return ClinicalAccessRepository(self._session).professional_id(user_id)

    def get_active_establishment_ids_for_professional(
        self,
        professional_id: int,
        *,
        on_date: date | None = None,
    ) -> set[int]:
        return ClinicalAccessRepository(self._session).establishment_ids(
            professional_id, on_date=on_date
        )

    def is_patient_in_professional_scope(
        self,
        *,
        patient_id: int,
        professional_id: int,
        establishment_ids: set[int],
    ) -> bool:
        """Check a professional's minimum necessary access to one patient.

        Access is granted when the patient is registered in one of the
        professional's active assigned establishments, when the professional
        has a non-cancelled care encounter with that patient, or when the
        professional is the author of its registration/last transfer.  This
        lets a clinician start care at an assigned site -- and keep following a
        patient they registered or moved -- while preventing global patient
        browsing by identifier.
        """

        statement = select(Patient.id).where(
            Patient.id == patient_id,
            Patient.estado.is_(True),
            patient_visibility(professional_id, establishment_ids),
        )
        return self._session.scalar(statement) is not None

    def get_active_risk_group(self, risk_group_id: int) -> RiskGroup | None:
        statement = select(RiskGroup).where(
            RiskGroup.id == risk_group_id,
            RiskGroup.activo.is_(True),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_responsible(
        self,
        patient_id: int,
        responsible_id: int,
        *,
        for_update: bool = False,
    ) -> PatientResponsible | None:
        statement = select(PatientResponsible).where(
            PatientResponsible.id == responsible_id,
            PatientResponsible.paciente_id == patient_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).scalar_one_or_none()

    def get_active_responsibles(self, patient_id: int) -> list[PatientResponsible]:
        statement = select(PatientResponsible).where(
            PatientResponsible.paciente_id == patient_id,
            PatientResponsible.activo.is_(True),
        )
        return list(self._session.execute(statement).scalars())

    def find_other_active_principal(
        self,
        patient_id: int,
        *,
        exclude_responsible_id: int | None = None,
    ) -> PatientResponsible | None:
        statement = select(PatientResponsible).where(
            PatientResponsible.paciente_id == patient_id,
            PatientResponsible.activo.is_(True),
            PatientResponsible.es_principal.is_(True),
        )
        if exclude_responsible_id is not None:
            statement = statement.where(PatientResponsible.id != exclude_responsible_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_risk(
        self,
        patient_id: int,
        risk_group_id: int,
        start_date: date,
        *,
        for_update: bool = False,
    ) -> PatientRisk | None:
        statement = select(PatientRisk).where(
            PatientRisk.paciente_id == patient_id,
            PatientRisk.grupo_riesgo_id == risk_group_id,
            PatientRisk.fecha_inicio == start_date,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).scalar_one_or_none()

    def find_overlapping_risk(
        self,
        patient_id: int,
        risk_group_id: int,
        *,
        start_date: date,
        end_date: date | None,
        exclude_start_date: date | None = None,
    ) -> PatientRisk | None:
        """Returns an intersecting persisted period, if one exists.

        The SQL expresses interval intersection; deciding that an intersection
        is invalid remains the service's domain rule.
        """

        effective_end = end_date or date.max
        statement = select(PatientRisk).where(
            PatientRisk.paciente_id == patient_id,
            PatientRisk.grupo_riesgo_id == risk_group_id,
            PatientRisk.fecha_inicio <= effective_end,
            or_(PatientRisk.fecha_fin.is_(None), PatientRisk.fecha_fin >= start_date),
        )
        if exclude_start_date is not None:
            statement = statement.where(PatientRisk.fecha_inicio != exclude_start_date)
        return self._session.execute(statement).scalar_one_or_none()

    def create_patient(self, values: dict[str, Any]) -> Patient:
        patient = Patient(**values)
        self._session.add(patient)
        return patient

    def create_responsible(self, values: dict[str, Any]) -> PatientResponsible:
        responsible = PatientResponsible(**values)
        self._session.add(responsible)
        return responsible

    def create_risk(self, values: dict[str, Any]) -> PatientRisk:
        risk = PatientRisk(**values)
        self._session.add(risk)
        return risk

    def update_fields(self, entity: Any, values: dict[str, Any]) -> None:
        """Assigns already-whitelisted persistence fields to an ORM entity."""

        for field, value in values.items():
            setattr(entity, field, value)
        if isinstance(entity, Patient):
            relations = {
                "ubigeo_residencia_codigo": "ubigeo_residencia",
                "localidad_id": "localidad_catalogo",
                "establecimiento_registro_id": "establecimiento_registro",
                "seguro_id": "insurance",
            }
            changed = [relation for key, relation in relations.items() if key in values]
            if changed:
                # Responses and snapshots must resolve the new foreign keys.
                self._session.expire(entity, changed)

    @staticmethod
    def deactivate(patient: Patient) -> None:
        patient.estado = False

    def add_audit_entry(
        self,
        *,
        actor_id: int | None,
        action: str,
        record_id: int,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        """Stages an audit row in the current transaction.

        Importing lazily avoids a persistence-layer import cycle while the
        aggregate models are registered by SQLAlchemy.
        """

        from app.models.audit import AuditLog

        self._session.add(
            AuditLog(
                usuario_id=actor_id,
                tabla_nombre="pacientes",
                registro_id=record_id,
                accion=action,
                datos_anteriores=before,
                datos_nuevos=after,
            )
        )

    def flush(self) -> None:
        self._session.flush()
