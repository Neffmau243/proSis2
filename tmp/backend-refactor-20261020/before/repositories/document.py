"""Persistence operations for clinical documents and their sequence rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session, selectinload

from app.models.audit import AuditLog
from app.models.catalog import ServiceOffering
from app.models.clinical import Attention
from app.models.documents import Certificate, CertificateService, DocumentSequence, Fua, Referral
from app.models.organization import Establishment
from app.models.security import Professional, User


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_attention(self, attention_id: int, *, lock: bool = False) -> Attention | None:
        statement = select(Attention).where(Attention.id == attention_id)
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_fua_for_attention(self, attention_id: int, *, lock: bool = False) -> Fua | None:
        statement = select(Fua).where(Fua.atencion_id == attention_id)
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_active_establishment(self, establishment_id: int) -> Establishment | None:
        return self._session.scalar(
            select(Establishment).where(Establishment.id == establishment_id, Establishment.activo.is_(True))
        )

    def get_active_professional(self, professional_id: int) -> Professional | None:
        return self._session.scalar(
            select(Professional).where(Professional.id == professional_id, Professional.activo.is_(True))
        )

    def get_active_professional_id_for_user(self, user_id: int) -> int | None:
        """Resolve the persisted professional identity behind an active account."""

        statement = (
            select(User.profesional_id)
            .join(Professional, Professional.id == User.profesional_id)
            .where(
                User.id == user_id,
                User.activo.is_(True),
                Professional.activo.is_(True),
            )
        )
        return self._session.scalar(statement)

    def get_active_service(self, code: str) -> ServiceOffering | None:
        return self._session.scalar(
            select(ServiceOffering).where(ServiceOffering.codigo == code, ServiceOffering.activo.is_(True))
        )

    def reserve_sequence_number(self, *, kind: str, establishment_id: int, period: str) -> int:
        """Atomically create-or-lock one MySQL sequence row and consume its value."""
        statement = mysql_insert(DocumentSequence).values(
            tipo=kind,
            establecimiento_id=establishment_id,
            periodo=period,
            siguiente_numero=1,
        )
        statement = statement.on_duplicate_key_update(
            siguiente_numero=DocumentSequence.siguiente_numero
        )
        self._session.execute(statement)
        sequence = self._session.scalar(
            select(DocumentSequence)
            .where(
                DocumentSequence.tipo == kind,
                DocumentSequence.establecimiento_id == establishment_id,
                DocumentSequence.periodo == period,
            )
            .with_for_update()
        )
        if sequence is None:  # Defensive: impossible after INSERT ... ON DUPLICATE KEY.
            raise RuntimeError("No se pudo reservar la serie documental.")
        current = sequence.siguiente_numero
        sequence.siguiente_numero += 1
        return current

    def add(self, entity: Fua | Certificate | Referral | CertificateService | AuditLog) -> None:
        self._session.add(entity)

    def get_fua(self, document_id: int) -> Fua | None:
        return self._session.get(Fua, document_id)

    def get_certificate(self, document_id: int) -> Certificate | None:
        return self._session.scalar(
            select(Certificate)
            .options(selectinload(Certificate.prestaciones))
            .where(Certificate.id == document_id)
        )

    def get_referral(self, document_id: int) -> Referral | None:
        return self._session.get(Referral, document_id)

    def add_audit(
        self,
        *,
        actor_id: int,
        table_name: str,
        record_id: int,
        after: dict[str, object],
    ) -> None:
        self._session.add(
            AuditLog(
                usuario_id=actor_id,
                tabla_nombre=table_name,
                registro_id=record_id,
                accion="INSERT",
                datos_anteriores=None,
                datos_nuevos=after,
            )
        )

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, entity: Fua | Certificate | Referral) -> None:
        self._session.refresh(entity)
