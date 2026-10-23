"""One eligibility rule shared by catalog search and admission validation."""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.office import office_context
from app.models.organization import Office, OfficeProfessional


def eligible_professional_ids(
    session: Session, office: Office, on_date: date, service_code: str | None = None
) -> set[int]:
    context = office_context(office)
    if not context.active or (service_code and service_code not in context.service_codes):
        return set()
    assignments = session.scalars(
        select(OfficeProfessional).where(
            OfficeProfessional.consultorio_id.in_([office.id, *context.ancestor_ids]),
            OfficeProfessional.fecha_inicio <= on_date,
            or_(OfficeProfessional.fecha_fin.is_(None), OfficeProfessional.fecha_fin >= on_date),
        )
    )
    return {
        item.profesional_id
        for item in assignments
        if service_code is None
        or item.servicios_codigos is None
        or service_code in item.servicios_codigos
    }
