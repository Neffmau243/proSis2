"""Authorized, minimal historical reading for patient follow-up origins."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.schemas.attention import NutritionalIndicatorsResponse
from app.services.clinical_access import ClinicalAccessService


@dataclass(frozen=True, slots=True)
class AttentionOrigin:
    paciente_id: int
    fecha_atencion: datetime
    estado: str
    valoracion_calculada: NutritionalIndicatorsResponse | None


class AttentionOriginReader:
    def __init__(self, session: Session) -> None:
        self._attentions = AttentionRepository(session)
        self._access = ClinicalAccessService(self._attentions, PatientRepository(session))

    def get(self, attention_id, *, actor_id, actor_roles) -> AttentionOrigin:
        record = self._attentions.get_origin(attention_id)
        if record is None:
            raise NotFoundError(
                code="ATENCION_NO_ENCONTRADA", message="No existe la atención solicitada."
            )
        scope = self._access.attention_scope(actor_id=actor_id, actor_roles=actor_roles)
        self._access.ensure_attention(record, scope, actor_id=actor_id)
        return AttentionOrigin(
            paciente_id=record.paciente_id,
            fecha_atencion=record.fecha_atencion,
            estado=record.estado,
            valoracion_calculada=(
                NutritionalIndicatorsResponse.model_validate(record.valoracion_calculada)
                if record.valoracion_calculada is not None
                else None
            ),
        )
