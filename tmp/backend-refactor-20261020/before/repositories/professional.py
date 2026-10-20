"""SQLAlchemy persistence gateway for administrator-managed professionals."""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.office import office_context
from app.models.catalog import Profession, Specialty
from app.models.organization import Office, OfficeProfessional
from app.models.security import Professional, ProfessionalSpecialty


class ProfessionalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, professional_id: int, *, lock: bool = False) -> Professional | None:
        statement = (
            select(Professional)
            .options(selectinload(Professional.especialidades))
            .where(Professional.id == professional_id)
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.execute(statement).unique().scalar_one_or_none()

    def list(self, *, include_inactive: bool = False) -> list[Professional]:
        statement = select(Professional).options(selectinload(Professional.especialidades))
        if not include_inactive:
            statement = statement.where(Professional.activo.is_(True))
        statement = statement.order_by(Professional.nombre_completo, Professional.id)
        return list(self._session.execute(statement).unique().scalars())

    def get_active_profession(self, profession_id: int) -> Profession | None:
        return self._session.scalar(
            select(Profession).where(Profession.id == profession_id, Profession.activo.is_(True))
        )

    def get_active_specialty(self, specialty_code: str) -> Specialty | None:
        return self._session.scalar(
            select(Specialty).where(Specialty.codigo == specialty_code, Specialty.activo.is_(True))
        )

    def add(self, professional: Professional) -> None:
        self._session.add(professional)

    def add_specialty(self, specialty: ProfessionalSpecialty) -> None:
        self._session.add(specialty)

    def replace_specialties(
        self,
        *,
        professional_id: int,
        specialties: list[ProfessionalSpecialty],
    ) -> None:
        self._session.execute(
            delete(ProfessionalSpecialty).where(
                ProfessionalSpecialty.profesional_id == professional_id,
            )
        )
        self._session.add_all(specialties)

    def required_specialties_for_nonexpired_assignments(
        self,
        professional_id: int,
        *,
        on_or_after: date,
    ) -> set[str]:
        """Specialties still needed by current or future office assignments."""

        statement = (
            select(Office)
            .join(OfficeProfessional, OfficeProfessional.consultorio_id == Office.id)
            .where(
                OfficeProfessional.profesional_id == professional_id,
                or_(
                    OfficeProfessional.fecha_fin.is_(None),
                    OfficeProfessional.fecha_fin >= on_or_after,
                ),
            )
        )
        return {
            context.required_specialty
            for item in self._session.scalars(statement)
            if (context := office_context(item)).required_specialty is not None
        }
