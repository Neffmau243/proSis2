"""Consultas de persistencia para la configuración de grupos etarios."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.catalog import AgeGroup


class AgeGroupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self, *, lock: bool = False) -> list[AgeGroup]:
        statement: Select[tuple[AgeGroup]] = select(AgeGroup).order_by(AgeGroup.codigo)
        if lock:
            statement = statement.with_for_update()
        return list(self._session.scalars(statement))

    def find_matching_active(self, age_in_months: int) -> AgeGroup | None:
        statement = (
            select(AgeGroup)
            .where(
                AgeGroup.activo.is_(True),
                AgeGroup.edad_minima_meses <= age_in_months,
                (AgeGroup.edad_maxima_meses.is_(None))
                | (AgeGroup.edad_maxima_meses >= age_in_months),
            )
            .order_by(AgeGroup.edad_minima_meses)
        )
        return self._session.scalar(statement)
