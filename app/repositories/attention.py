"""Persistence-only gateway for clinical attention aggregates."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.office import office_context
from app.models.audit import AuditLog
from app.models.catalog import AttentionMode, Cie10, ServiceOffering, Specialty
from app.models.clinical import Attention, AttentionDiagnosis, AttentionService
from app.models.documents import Certificate, Fua, Referral
from app.models.organization import Establishment, Office, OfficeProfessional
from app.models.security import Professional, ProfessionalSpecialty, User
from app.models.surveillance import NutritionalEvaluation
from app.repositories.attention_scope import recorded_referral


class AttentionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, attention_id: int, *, lock: bool = False) -> Attention | None:
        statement = (
            select(Attention)
            .options(
                selectinload(Attention.prestaciones),
                selectinload(Attention.diagnosticos),
                selectinload(Attention.paciente),
                selectinload(Attention.consultorio),
                selectinload(Attention.evaluaciones_nutricionales),
            )
            .where(Attention.id == attention_id)
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.execute(statement).unique().scalar_one_or_none()

    def list_by_patient(
        self,
        patient_id: int,
        *,
        professional_id: int | None = None,
        establishment_ids: set[int] | None = None,
    ) -> list[Attention]:
        statement = (
            select(Attention)
            .options(
                selectinload(Attention.prestaciones),
                selectinload(Attention.diagnosticos),
                selectinload(Attention.paciente),
                selectinload(Attention.consultorio),
                selectinload(Attention.evaluaciones_nutricionales),
            )
            .where(Attention.paciente_id == patient_id)
            .order_by(Attention.fecha_atencion.desc())
        )
        if professional_id is not None:
            visibility = [
                Attention.profesional_id == professional_id,
                recorded_referral(professional_id),
            ]
            if establishment_ids:
                visibility.append(Attention.establecimiento_id.in_(establishment_ids))
            statement = statement.where(or_(*visibility))
        return list(self._session.execute(statement).unique().scalars())

    def previous_growth_control(
        self,
        patient_id: int,
        before: date,
        *,
        birth_date: date,
        professional_id: int | None = None,
        establishment_ids: set[int] | None = None,
    ) -> Attention | None:
        statement = select(Attention).where(
            Attention.paciente_id == patient_id,
            Attention.estado == "ATENDIDO",
            Attention.grupo_atencion_codigo == "NINOS_ADOLESCENTES_ADULTOS_MAYORES",
            Attention.fecha_atencion < datetime.combine(before, time.min),
            Attention.fecha_atencion >= datetime.combine(birth_date, time.min),
            Attention.peso_kg > 0,
            Attention.talla_cm > 0,
        )
        if professional_id is not None:
            visibility = [
                Attention.profesional_id == professional_id,
                recorded_referral(professional_id),
            ]
            if establishment_ids:
                visibility.append(Attention.establecimiento_id.in_(establishment_ids))
            statement = statement.where(or_(*visibility))
        return self._session.scalar(
            statement.order_by(Attention.fecha_atencion.desc(), Attention.id.desc()).limit(1)
        )

    def get_active_establishment(self, establishment_id: int) -> Establishment | None:
        return self._session.scalar(
            select(Establishment).where(
                Establishment.id == establishment_id,
                Establishment.activo.is_(True),
            )
        )

    def get_active_professional(self, professional_id: int) -> Professional | None:
        return self._session.scalar(
            select(Professional).where(
                Professional.id == professional_id,
                Professional.activo.is_(True),
            )
        )

    def get_active_professional_id_for_user(self, user_id: int) -> int | None:
        """Return the active professional identity linked to an active user."""

        statement = (
            select(User.profesional_id)
            .join(Professional, Professional.id == User.profesional_id)
            .where(
                User.id == user_id,
                User.activo.is_(True),
                Professional.activo.is_(True),
            )
        )
        return self._session.scalar(statement)

    def get_active_office(self, office_id: int) -> Office | None:
        return self._session.scalar(
            select(Office).where(Office.id == office_id, Office.activo.is_(True))
        )

    def professional_is_assigned(self, office: Office, professional_id: int, on_date: date) -> bool:
        context = office_context(office)
        return (
            self._session.scalar(
                select(OfficeProfessional.profesional_id)
                .where(
                    OfficeProfessional.consultorio_id.in_([office.id, *context.ancestor_ids]),
                    OfficeProfessional.profesional_id == professional_id,
                    OfficeProfessional.fecha_inicio <= on_date,
                    or_(
                        OfficeProfessional.fecha_fin.is_(None),
                        OfficeProfessional.fecha_fin >= on_date,
                    ),
                )
                .limit(1)
            )
            is not None
        )

    def professional_has_specialty(self, professional_id: int, code: str) -> bool:
        return (
            self._session.scalar(
                select(ProfessionalSpecialty.profesional_id).where(
                    ProfessionalSpecialty.profesional_id == professional_id,
                    ProfessionalSpecialty.especialidad_codigo == code,
                )
            )
            is not None
        )

    def get_active_mode(self, code: str) -> AttentionMode | None:
        return self._session.scalar(
            select(AttentionMode).where(
                AttentionMode.codigo == code,
                AttentionMode.activo.is_(True),
            )
        )

    def get_active_specialty(self, code: str) -> Specialty | None:
        return self._session.scalar(
            select(Specialty).where(Specialty.codigo == code, Specialty.activo.is_(True))
        )

    def get_active_service_offering(self, code: str) -> ServiceOffering | None:
        return self._session.scalar(
            select(ServiceOffering).where(
                ServiceOffering.codigo == code,
                ServiceOffering.activo.is_(True),
            )
        )

    def get_active_cie10(self, code: str) -> Cie10 | None:
        return self._session.scalar(
            select(Cie10).where(Cie10.codigo == code, Cie10.activo.is_(True))
        )

    def add(self, entity: Attention) -> None:
        self._session.add(entity)

    def add_details(
        self,
        *,
        attention_id: int,
        service_details: Iterable[tuple[int, str, Decimal]],
        diagnosis_details: Iterable[tuple[int, str, str | None, str | None]],
    ) -> None:
        """Persist ordered child rows for an already-flushed attention.

        The use-case service validates catalog availability and builds the
        value tuples; this repository owns construction and staging of ORM
        persistence entities so services never write to ``Session`` directly.
        """

        self._session.add_all(
            [
                AttentionService(
                    atencion_id=attention_id,
                    numero_orden=order,
                    prestacion_codigo=service_code,
                    cantidad=quantity,
                )
                for order, service_code, quantity in service_details
            ]
        )
        self._session.add_all(
            [
                AttentionDiagnosis(
                    atencion_id=attention_id,
                    numero_orden=order,
                    cie10_codigo=cie10_code,
                    tipo_diagnostico=diagnosis_type,
                    observacion=observation,
                )
                for order, cie10_code, diagnosis_type, observation in diagnosis_details
            ]
        )

    def has_active_documents_for_attention(self, attention_id: int) -> bool:
        """Whether a legally/operationally effective document still exists.

        A parent attention is locked before calling this method.  Document
        issuance locks that same parent row, so the check and cancellation are
        serialized against a concurrent emission without relying on a racy
        aggregate counter.
        """

        active_fua = self._session.scalar(
            select(Fua.id).where(Fua.atencion_id == attention_id, Fua.estado == "EMITIDO").limit(1)
        )
        if active_fua is not None:
            return True
        active_certificate = self._session.scalar(
            select(Certificate.id)
            .where(Certificate.atencion_id == attention_id, Certificate.estado == "EMITIDO")
            .limit(1)
        )
        if active_certificate is not None:
            return True
        # A closed or explicitly cancelled referral no longer has an active
        # operational effect. Any other persisted state is treated
        # conservatively as active, including legacy values.
        active_referral = self._session.scalar(
            select(Referral.id)
            .where(
                Referral.atencion_id == attention_id,
                Referral.estado.not_in(("ANULADA", "CERRADA")),
            )
            .limit(1)
        )
        return active_referral is not None

    def add_nutritional_evaluation(self, entity: NutritionalEvaluation) -> None:
        self._session.add(entity)

    def add_audit(
        self,
        *,
        actor_id: int | None,
        action: str,
        record_id: int,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        self._session.add(
            AuditLog(
                usuario_id=actor_id,
                tabla_nombre="atenciones",
                registro_id=record_id,
                accion=action,
                datos_anteriores=before,
                datos_nuevos=after,
            )
        )

    def flush(self) -> None:
        self._session.flush()
