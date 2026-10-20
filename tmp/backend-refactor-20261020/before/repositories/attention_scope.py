"""Ownership predicate for references that have no attending clinician."""

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from app.models.clinical import Attention
from app.models.security import User


def recorded_referral(professional_id: int) -> ColumnElement[bool]:
    return and_(
        Attention.modalidad_atencion_codigo == "REFERENCIA",
        Attention.profesional_id.is_(None),
        Attention.created_by_usuario.has(User.profesional_id == professional_id),
    )
