"""Catalog storage for care services, kept separate from staff qualifications."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Specialty


class OfficeServiceCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def entries(self) -> list[Specialty]:
        return list(
            self._session.scalars(select(Specialty).order_by(Specialty.nombre, Specialty.codigo))
        )

    def get(self, code: str, *, lock: bool = False) -> Specialty | None:
        statement = select(Specialty).where(Specialty.codigo == code)
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add(self, entry: Specialty) -> None:
        self._session.add(entry)
