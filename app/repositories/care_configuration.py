"""Queries used only by administrative establishment and area maintenance."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.office import CUSTOM_SERVICE_GROUP, office_context
from app.models.catalog import Specialty
from app.models.organization import Establishment, Office, Ubigeo
from app.models.security import Professional, ProfessionalSpecialty


class CareConfigurationRepository:
    def __init__(self, session: Session):
        self.session = session

    def establishments(self, query: str | None, include_inactive: bool, limit: int, offset: int):
        filters = []
        if not include_inactive:
            filters.append(Establishment.activo.is_(True))
        if query:
            # Search is literal; '%' and '_' are not wildcard instructions.
            filters.append(
                or_(
                    Establishment.nombre.icontains(query, autoescape=True),
                    Establishment.codigo_renaes.icontains(query, autoescape=True),
                    Establishment.codigo_ideess.icontains(query, autoescape=True),
                )
            )
        total = self.session.scalar(select(func.count()).select_from(Establishment).where(*filters))
        items = list(
            self.session.scalars(
                select(Establishment)
                .where(*filters)
                .options(selectinload(Establishment.ubigeo))
                .order_by(Establishment.nombre, Establishment.id)
                .offset(offset)
                .limit(limit)
            )
        )
        return items, total or 0

    def establishment(self, identifier: int, *, lock: bool = False):
        statement = select(Establishment).where(Establishment.id == identifier)
        return self.session.scalar(statement.with_for_update() if lock else statement)

    def office_counts(self):
        return dict(
            self.session.execute(
                select(Office.establecimiento_id, func.count()).group_by(Office.establecimiento_id)
            ).all()
        )

    def has_active_offices(self, identifier: int) -> bool:
        return (
            self.session.scalar(
                select(Office.id)
                .where(Office.establecimiento_id == identifier, Office.activo.is_(True))
                .limit(1)
            )
            is not None
        )

    def district(self, code: str):
        return self.session.get(Ubigeo, code)

    def areas(self):
        return list(self.session.scalars(select(Specialty).order_by(Specialty.nombre)))

    def offices(self):
        return list(
            self.session.scalars(select(Office).options(selectinload(Office.establecimiento)))
        )

    def area_is_used(self, code: str) -> bool:
        if any(item.activo and office_context(item).area_code == code for item in self.offices()):
            return True
        professional = self.session.scalar(
            select(Professional.id)
            .join(ProfessionalSpecialty, ProfessionalSpecialty.profesional_id == Professional.id)
            .where(ProfessionalSpecialty.especialidad_codigo == code, Professional.activo.is_(True))
            .limit(1)
        )
        service = self.session.scalar(
            select(Specialty.codigo)
            .where(Specialty.grupo == f"{CUSTOM_SERVICE_GROUP}{code}", Specialty.activo.is_(True))
            .limit(1)
        )
        return professional is not None or service is not None
