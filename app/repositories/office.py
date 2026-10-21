"""SQLAlchemy queries for office-professional assignment persistence."""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.catalog import Specialty
from app.models.organization import Establishment, Office, OfficeProfessional
from app.models.security import Professional, ProfessionalSpecialty


class OfficeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(
        self,
        office_id: int,
        *,
        include_inactive: bool = True,
        lock: bool = False,
    ) -> Office | None:
        statement = select(Office).where(Office.id == office_id)
        if not include_inactive:
            statement = statement.where(Office.activo.is_(True))
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_active_office(self, office_id: int, *, lock: bool = False) -> Office | None:
        return self.get_by_id(office_id, include_inactive=False, lock=lock)

    def list_offices(
        self,
        *,
        establishment_id: int | None = None,
        include_inactive: bool = False,
    ) -> list[Office]:
        statement = select(Office)
        if establishment_id is not None:
            statement = statement.where(Office.establecimiento_id == establishment_id)
        if not include_inactive:
            statement = statement.where(Office.activo.is_(True))
        statement = statement.order_by(Office.establecimiento_id, Office.codigo)
        return list(self._session.scalars(statement))

    def get_active_establishment(
        self, establishment_id: int, *, lock: bool = False
    ) -> Establishment | None:
        statement = select(Establishment).where(
            Establishment.id == establishment_id,
            Establishment.activo.is_(True),
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def active_specialties(self) -> dict[str, str]:
        return {
            item.codigo: item.nombre
            for item in self._session.scalars(select(Specialty).where(Specialty.activo.is_(True)))
        }

    def nonexpired_professionals(self, office_id: int) -> set[int]:
        return set(
            self._session.scalars(
                select(OfficeProfessional.profesional_id).where(
                    OfficeProfessional.consultorio_id == office_id,
                    or_(
                        OfficeProfessional.fecha_fin.is_(None),
                        OfficeProfessional.fecha_fin >= date.today(),
                    ),
                )
            )
        )

    def get_active_specialty(self, specialty_code: str) -> Specialty | None:
        return self._session.scalar(
            select(Specialty).where(
                Specialty.codigo == specialty_code,
                Specialty.activo.is_(True),
            )
        )

    def get_active_professional(
        self, professional_id: int, *, lock: bool = False
    ) -> Professional | None:
        statement = select(Professional).where(
            Professional.id == professional_id, Professional.activo.is_(True)
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def link_professional_area(
        self, professional_id: int, area_code: str, *, actor_id: int
    ) -> None:
        """Caller holds the professional lock; persist the link with the assignment."""
        qualifications = list(
            self._session.scalars(
                select(ProfessionalSpecialty).where(
                    ProfessionalSpecialty.profesional_id == professional_id
                )
            )
        )
        if any(item.especialidad_codigo == area_code for item in qualifications):
            return
        primary = not any(item.es_principal for item in qualifications)
        self._session.add(
            ProfessionalSpecialty(
                profesional_id=professional_id,
                especialidad_codigo=area_code,
                es_principal=primary,
            )
        )
        self._session.add(
            AuditLog(
                usuario_id=actor_id,
                tabla_nombre="profesional_especialidades",
                registro_id=professional_id,
                accion="INSERT",
                datos_anteriores=None,
                datos_nuevos={
                    "profesional_id": professional_id,
                    "especialidad_codigo": area_code,
                    "es_principal": primary,
                    "origen": "asignacion_consultorio",
                },
            )
        )

    def professional_has_specialty(self, professional_id: int, specialty_code: str) -> bool:
        return (
            self._session.scalar(
                select(ProfessionalSpecialty.profesional_id).where(
                    ProfessionalSpecialty.profesional_id == professional_id,
                    ProfessionalSpecialty.especialidad_codigo == specialty_code,
                )
            )
            is not None
        )

    def list_assignments(self, office_id: int) -> list[OfficeProfessional]:
        return list(
            self._session.scalars(
                select(OfficeProfessional)
                .where(OfficeProfessional.consultorio_id == office_id)
                .order_by(OfficeProfessional.fecha_inicio.desc(), OfficeProfessional.profesional_id)
            )
        )

    def get_assignment(
        self, office_id: int, professional_id: int, start_date: date, *, lock: bool = False
    ) -> OfficeProfessional | None:
        statement = select(OfficeProfessional).where(
            OfficeProfessional.consultorio_id == office_id,
            OfficeProfessional.profesional_id == professional_id,
            OfficeProfessional.fecha_inicio == start_date,
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_current_responsible(
        self, office_id: int, on_date: date, *, lock: bool = False
    ) -> OfficeProfessional | None:
        statement = (
            select(OfficeProfessional)
            .where(
                OfficeProfessional.consultorio_id == office_id,
                OfficeProfessional.es_responsable.is_(True),
                OfficeProfessional.fecha_inicio <= on_date,
                or_(
                    OfficeProfessional.fecha_fin.is_(None), OfficeProfessional.fecha_fin >= on_date
                ),
            )
            .order_by(OfficeProfessional.fecha_inicio.desc())
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def has_overlapping_assignment(
        self,
        *,
        office_id: int,
        professional_id: int,
        start_date: date,
        end_date: date | None,
    ) -> bool:
        """Whether an existing period overlaps the proposed assignment period."""

        ends_after_start = OfficeProfessional.fecha_fin.is_(None)
        ends_after_start = ends_after_start | (OfficeProfessional.fecha_fin >= start_date)
        statement = select(OfficeProfessional.consultorio_id).where(
            OfficeProfessional.consultorio_id == office_id,
            OfficeProfessional.profesional_id == professional_id,
            ends_after_start,
        )
        if end_date is not None:
            statement = statement.where(OfficeProfessional.fecha_inicio <= end_date)
        return self._session.scalar(statement) is not None

    def parent_chain_contains(self, *, candidate_parent_id: int, office_id: int) -> bool:
        """Detect a parent/child cycle without relying on a database-specific CTE."""

        current_id: int | None = candidate_parent_id
        visited: set[int] = set()
        while current_id is not None:
            if current_id == office_id:
                return True
            if current_id in visited:
                # Existing corrupt parent data must not be extended with a new
                # relationship. Treat it as a cycle from the caller's view.
                return True
            visited.add(current_id)
            current = self.get_by_id(current_id, lock=True)
            if current is None:
                return False
            current_id = current.consultorio_padre_id
        return False

    def add_office(self, office: Office) -> None:
        self._session.add(office)

    def add(self, assignment: OfficeProfessional) -> None:
        self._session.add(assignment)

    def audit(
        self, *, actor_id: int, action: str, record_id: int, after: dict[str, object]
    ) -> None:
        self._session.add(
            AuditLog(
                usuario_id=actor_id,
                tabla_nombre="consultorio_profesionales",
                registro_id=record_id,
                accion=action,
                datos_anteriores=None,
                datos_nuevos=after,
            )
        )
