"""Shared SQL visibility predicates for clinical rows and pagination totals."""

from collections.abc import Collection

from sqlalchemy import and_, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.clinical import Attention
from app.models.patient import Patient
from app.models.security import User


def recorded_referral(professional_id: int) -> ColumnElement[bool]:
    return and_(
        Attention.modalidad_atencion_codigo == "REFERENCIA",
        Attention.profesional_id.is_(None),
        Attention.created_by_usuario.has(User.profesional_id == professional_id),
    )


def attention_visibility(
    professional_id: int, establishment_ids: Collection[int] | None
) -> ColumnElement[bool]:
    conditions = [Attention.profesional_id == professional_id, recorded_referral(professional_id)]
    if establishment_ids:
        conditions.append(Attention.establecimiento_id.in_(establishment_ids))
    return or_(*conditions)


def patient_visibility(
    professional_id: int, establishment_ids: Collection[int] | None
) -> ColumnElement[bool]:
    care_relationship = (
        select(Attention.id)
        .where(
            Attention.paciente_id == Patient.id,
            or_(Attention.profesional_id == professional_id, recorded_referral(professional_id)),
            Attention.estado != "ANULADO",
        )
        .exists()
    )
    conditions = [care_relationship, Patient.profesional_registro_id == professional_id]
    if establishment_ids:
        conditions.append(Patient.establecimiento_registro_id.in_(establishment_ids))
    return or_(*conditions)
