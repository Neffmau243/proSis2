"""Read-only, paginated queries for clinical discovery endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, TypeVar

from sqlalchemy import exists, false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.office import office_context
from app.models.clinical import Attention
from app.models.organization import Office, OfficeProfessional
from app.models.patient import Patient, PatientRisk
from app.models.security import Professional, User
from app.repositories.attention_scope import recorded_referral
from app.schemas.discovery import AttentionSearchCriteria, PatientSearchCriteria

EntityT = TypeVar("EntityT")


@dataclass(frozen=True, slots=True)
class DiscoveryPage[EntityT]:
    items: list[EntityT]
    total: int


class PatientDiscoveryRepository:
    """Patient search persistence, including the clinical ownership join."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_professional_id_for_user(self, user_id: int) -> int | None:
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

    def active_establishment_ids_for_professional(self, professional_id: int) -> list[int]:
        """Return establishments from the professional's current assignments."""

        today = date.today()
        statement = (
            select(Office)
            .join(OfficeProfessional, OfficeProfessional.consultorio_id == Office.id)
            .where(
                OfficeProfessional.profesional_id == professional_id,
                Office.activo.is_(True),
                OfficeProfessional.fecha_inicio <= today,
                or_(
                    OfficeProfessional.fecha_fin.is_(None),
                    OfficeProfessional.fecha_fin >= today,
                ),
            )
            .distinct()
        )
        return sorted(
            {
                item.establecimiento_id
                for item in self._session.scalars(statement)
                if office_context(item).active and item.establecimiento.activo
            }
        )

    def search(
        self,
        criteria: PatientSearchCriteria,
        *,
        professional_id: int | None,
        establishment_ids: list[int] | None,
        include_inactive: bool,
    ) -> DiscoveryPage[Patient]:
        conditions: list[Any] = []

        if not include_inactive:
            conditions.append(Patient.estado.is_(True))
        if criteria.tipo_documento_codigo is not None:
            conditions.append(Patient.tipo_documento_codigo == criteria.tipo_documento_codigo)
        if criteria.numero_documento is not None:
            conditions.append(Patient.numero_documento == criteria.numero_documento)
        if criteria.historia_clinica is not None:
            conditions.append(Patient.historia_clinica == criteria.historia_clinica)
        if criteria.establecimiento_id is not None:
            conditions.append(Patient.establecimiento_registro_id == criteria.establecimiento_id)
        if criteria.q:
            pattern = self._contains_pattern(criteria.q)
            conditions.append(
                or_(
                    Patient.numero_documento.ilike(pattern, escape="\\"),
                    Patient.historia_clinica.ilike(pattern, escape="\\"),
                    Patient.apellido_paterno.ilike(pattern, escape="\\"),
                    Patient.apellido_materno.ilike(pattern, escape="\\"),
                    Patient.primer_nombre.ilike(pattern, escape="\\"),
                    Patient.otros_nombres.ilike(pattern, escape="\\"),
                )
            )
        if professional_id is not None:
            # A professional may discover a patient registered at one of
            # their active workplaces, one with a prior non-cancelled
            # attention of their own, or one they registered/transferred
            # themselves.  EXISTS keeps the result/count stable even when a
            # patient has many historical attentions.
            own_attention = exists(
                select(Attention.id).where(
                    Attention.paciente_id == Patient.id,
                    or_(
                        Attention.profesional_id == professional_id,
                        recorded_referral(professional_id),
                    ),
                    Attention.estado != "ANULADO",
                )
            )
            allowed_establishment = (
                Patient.establecimiento_registro_id.in_(establishment_ids or [])
                if establishment_ids
                else false()
            )
            own_registration = Patient.profesional_registro_id == professional_id
            conditions.append(or_(allowed_establishment, own_attention, own_registration))

        statement = select(Patient).options(
            selectinload(Patient.ubigeo_residencia),
            selectinload(Patient.responsables),
            selectinload(Patient.riesgos).selectinload(PatientRisk.grupo_riesgo),
        )
        count_statement = select(func.count()).select_from(Patient)
        statement = statement.where(*conditions).order_by(
            Patient.apellido_paterno,
            Patient.apellido_materno,
            Patient.primer_nombre,
            Patient.id,
        )
        count_statement = count_statement.where(*conditions)
        return DiscoveryPage(
            items=list(
                self._session.execute(statement.limit(criteria.limit).offset(criteria.offset))
                .unique()
                .scalars()
            ),
            total=int(self._session.scalar(count_statement) or 0),
        )

    @staticmethod
    def _contains_pattern(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"


class AttentionDiscoveryRepository:
    """Attention history persistence with a single, count-safe filter set."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_professional_id_for_user(self, user_id: int) -> int | None:
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

    def active_establishment_ids_for_professional(self, professional_id: int) -> list[int]:
        """Return active sites that can contribute to a clinical history."""

        today = date.today()
        statement = (
            select(Office)
            .join(OfficeProfessional, OfficeProfessional.consultorio_id == Office.id)
            .where(
                OfficeProfessional.profesional_id == professional_id,
                Office.activo.is_(True),
                OfficeProfessional.fecha_inicio <= today,
                or_(
                    OfficeProfessional.fecha_fin.is_(None),
                    OfficeProfessional.fecha_fin >= today,
                ),
            )
            .distinct()
        )
        return sorted(
            {
                item.establecimiento_id
                for item in self._session.scalars(statement)
                if office_context(item).active and item.establecimiento.activo
            }
        )

    def search(
        self,
        criteria: AttentionSearchCriteria,
        *,
        professional_id: int | None,
        establishment_ids: list[int] | None,
    ) -> DiscoveryPage[Attention]:
        conditions: list[Any] = []
        if criteria.paciente_id is not None:
            conditions.append(Attention.paciente_id == criteria.paciente_id)
        if criteria.establecimiento_id is not None:
            conditions.append(Attention.establecimiento_id == criteria.establecimiento_id)
        if criteria.profesional_id is not None:
            conditions.append(Attention.profesional_id == criteria.profesional_id)
        if criteria.consultorio_id is not None:
            conditions.append(Attention.consultorio_id == criteria.consultorio_id)
        if criteria.desde is not None:
            conditions.append(Attention.fecha_atencion >= self._day_start(criteria.desde))
        if criteria.hasta is not None:
            conditions.append(
                Attention.fecha_atencion < self._day_start(criteria.hasta + timedelta(days=1))
            )
        if criteria.fecha_hora_desde is not None:
            conditions.append(Attention.fecha_atencion >= criteria.fecha_hora_desde)
        if criteria.fecha_hora_hasta is not None:
            conditions.append(Attention.fecha_atencion < criteria.fecha_hora_hasta)
        if criteria.estado is not None:
            conditions.append(Attention.estado == criteria.estado.value)
        if professional_id is not None:
            visibility = [
                Attention.profesional_id == professional_id,
                recorded_referral(professional_id),
            ]
            if establishment_ids:
                visibility.append(Attention.establecimiento_id.in_(establishment_ids))
            conditions.append(or_(*visibility))

        statement = (
            select(Attention)
            .options(
                selectinload(Attention.prestaciones),
                selectinload(Attention.diagnosticos),
                selectinload(Attention.paciente),
                selectinload(Attention.consultorio),
                selectinload(Attention.evaluaciones_nutricionales),
            )
            .where(*conditions)
            .order_by(Attention.fecha_atencion.desc(), Attention.id.desc())
        )
        count_statement = select(func.count()).select_from(Attention).where(*conditions)
        return DiscoveryPage(
            items=list(
                self._session.execute(statement.limit(criteria.limit).offset(criteria.offset))
                .unique()
                .scalars()
            ),
            total=int(self._session.scalar(count_statement) or 0),
        )

    @staticmethod
    def _day_start(value: date) -> datetime:
        return datetime.combine(value, time.min)
