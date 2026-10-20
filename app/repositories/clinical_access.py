"""Shared persistence queries for active clinical identity and assigned sites."""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.office import office_context
from app.models.organization import Establishment, Office, OfficeProfessional
from app.models.security import Professional, User


class ClinicalAccessRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def professional_id(self, user_id: int) -> int | None:
        return self._session.scalar(
            select(User.profesional_id)
            .join(Professional, Professional.id == User.profesional_id)
            .where(User.id == user_id, User.activo.is_(True), Professional.activo.is_(True))
        )

    def establishment_ids(self, professional_id: int, *, on_date: date | None = None) -> set[int]:
        reference = on_date or date.today()
        statement = (
            select(Office)
            .join(OfficeProfessional, OfficeProfessional.consultorio_id == Office.id)
            .join(Establishment, Establishment.id == Office.establecimiento_id)
            .where(
                OfficeProfessional.profesional_id == professional_id,
                OfficeProfessional.fecha_inicio <= reference,
                or_(
                    OfficeProfessional.fecha_fin.is_(None),
                    OfficeProfessional.fecha_fin >= reference,
                ),
                Office.activo.is_(True),
                Establishment.activo.is_(True),
            )
            .distinct()
        )
        return {
            item.establecimiento_id
            for item in self._session.scalars(statement)
            if office_context(item).active and item.establecimiento.activo
        }
