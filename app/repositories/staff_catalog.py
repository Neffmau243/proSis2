"""Persistence for staff catalog additions and name edits."""

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.domain.staff_catalog import catalog_name_key, is_staff_specialty_code
from app.models.catalog import Profession, Specialty
from app.models.clinical import Attention
from app.models.organization import Office
from app.models.security import Professional, ProfessionalSpecialty


class StaffCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def profession_name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        key = catalog_name_key(name)
        statement = select(Profession.nombre)
        if exclude_id is not None:
            statement = statement.where(Profession.id != exclude_id)
        return any(
            catalog_name_key(existing) == key
            for existing in self._session.scalars(statement.with_for_update())
        )

    def specialty_name_exists(self, name: str, *, exclude_code: str | None = None) -> bool:
        key = catalog_name_key(name)
        statement = select(Specialty.codigo, Specialty.nombre)
        if exclude_code is not None:
            statement = statement.where(Specialty.codigo != exclude_code)
        return any(
            is_staff_specialty_code(code) and catalog_name_key(existing) == key
            for code, existing in self._session.execute(statement.with_for_update())
        )

    def get_profession(self, identifier: int, *, lock: bool = False) -> Profession | None:
        statement = select(Profession).where(Profession.id == identifier)
        return self._session.scalar(statement.with_for_update() if lock else statement)

    def get_specialty(self, code: str, *, lock: bool = False) -> Specialty | None:
        statement = select(Specialty).where(Specialty.codigo == code)
        return self._session.scalar(statement.with_for_update() if lock else statement)

    def add(self, entity: Profession | Specialty) -> None:
        self._session.add(entity)

    def profession_in_use(self, identifier: int) -> bool:
        return (
            self._session.scalar(
                select(Professional.id).where(Professional.profesion_id == identifier).limit(1)
            )
            is not None
        )

    def specialty_in_use(self, code: str) -> bool:
        return self._session.scalar(
            select(ProfessionalSpecialty.profesional_id)
            .where(ProfessionalSpecialty.especialidad_codigo == code)
            .limit(1)
        ) is not None or self.specialty_operationally_used(code)

    def specialty_operationally_used(self, code: str) -> bool:
        statements = (
            select(Office.id).where(
                or_(Office.area_codigo == code, Office.especialidad_codigo == code)
            ),
            select(Attention.id).where(Attention.especialidad_codigo == code),
        )
        return any(self._session.scalar(statement.limit(1)) is not None for statement in statements)

    def delete(self, entity: Profession | Specialty) -> None:
        # Bulk deletion leaves every dependent record untouched; FK RESTRICT
        # also protects against a new assignment made after the usage check.
        model = type(entity)
        key = (
            Profession.id == entity.id
            if isinstance(entity, Profession)
            else Specialty.codigo == entity.codigo
        )
        self._session.execute(delete(model).where(key))
