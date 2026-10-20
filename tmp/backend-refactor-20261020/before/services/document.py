"""Atomic document issuance cases, including safe MySQL number allocation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import AuthorizationError, BusinessRuleError, ConflictError, NotFoundError
from app.mappers.document import certificate_to_response, fua_to_response, referral_to_response
from app.models.documents import Certificate, CertificateService, Fua, Referral
from app.repositories.document import DocumentRepository
from app.schemas.document import (
    CertificateIssueInput,
    CertificateResponse,
    FuaIssueInput,
    FuaResponse,
    ReferralCreateInput,
    ReferralResponse,
)


@dataclass(frozen=True, slots=True)
class DocumentNumberFormatter:
    """Formats reserved numeric values without owning database concurrency."""

    def format(self, kind: str, establishment_id: int, period: str, sequence: int) -> str:
        return f"{kind}-{establishment_id}-{period}-{sequence:08d}"


@dataclass(frozen=True, slots=True)
class FuaNumberFormatter:
    """Format the three official-looking FUA number components.

    It does not claim to allocate a SIS-issued range.  Range assignment remains
    an operational duty of the IPRESS/DIRESA; this formatter merely prevents
    accidental reuse of the obsolete city/year/EESS layout from the legacy app.
    """

    def format(self, renipress: str, lote: str, sequence: int) -> str:
        if not re.fullmatch(r"\d{8}", renipress):
            raise ValueError("RENIPRESS debe tener ocho dígitos.")
        if not re.fullmatch(r"\d{2}", lote):
            raise ValueError("El lote FUA debe tener dos dígitos.")
        if not 1 <= sequence <= 99_999_999:
            raise ValueError("El correlativo FUA debe estar entre 1 y 99999999.")
        return f"{renipress}-{lote}-{sequence:08d}"


class DocumentService:
    def __init__(
        self,
        session: Session,
        formatter: DocumentNumberFormatter | None = None,
        fua_formatter: FuaNumberFormatter | None = None,
    ) -> None:
        self._session = session
        self._documents = DocumentRepository(session)
        self._formatter = formatter or DocumentNumberFormatter()
        self._fua_formatter = fua_formatter or FuaNumberFormatter()

    def issue_fua(
        self,
        command: FuaIssueInput,
        *,
        actor_id: int,
        actor_roles: Iterable[str] | None = None,
    ) -> FuaResponse:
        try:
            attention = self._require_emittable_attention(
                command.atencion_id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            if self._documents.get_fua_for_attention(attention.id, lock=True) is not None:
                raise ConflictError(
                    code="FUA_YA_EMITIDO", message="La atención ya tiene un FUA emitido."
                )
            establishment = self._documents.get_active_establishment(attention.establecimiento_id)
            if establishment is None:  # Defensive: _require_emittable_attention already checked it.
                raise NotFoundError(
                    code="ESTABLECIMIENTO_NO_ACTIVO",
                    message="La sede de la atención no está activa.",
                )
            issued_at = datetime.now(ZoneInfo("America/Lima"))
            period = str(issued_at.year)
            lote = issued_at.strftime("%y")
            snapshot = getattr(attention, "fua_impresion", None)
            renipress = self._renipress_for(
                snapshot.get("codigo_renipress")
                if snapshot is not None
                else establishment.codigo_renaes
            )
            sequence = self._documents.reserve_sequence_number(
                kind="FUA_SIS", establishment_id=attention.establecimiento_id, period=period
            )
            number = self._fua_formatter.format(renipress, lote, sequence)
            entity = Fua(
                atencion_id=attention.id,
                numero_fua=number,
                codigo_renipress=renipress,
                lote_fua=lote,
                correlativo_fua=f"{sequence:08d}",
                codigo_ciudad=None,
                codigo_anio=None,
                codigo_eess=None,
                edad_declarada=(
                    str(attention.edad_anios) if attention.edad_anios is not None else None
                ),
                estado="EMITIDO",
                observaciones=command.observaciones,
            )
            self._documents.add(entity)
            self._documents.flush()
            self._documents.add_audit(
                actor_id=actor_id,
                table_name="fua",
                record_id=entity.id,
                after={"atencion_id": entity.atencion_id, "numero_fua": entity.numero_fua},
            )
            self._session.commit()
            self._documents.refresh(entity)
            return fua_to_response(entity)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="FUA_YA_EMITIDO",
                message="No se pudo emitir el FUA porque la atención ya tiene uno.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def issue_certificate(
        self,
        command: CertificateIssueInput,
        *,
        actor_id: int,
        actor_roles: Iterable[str] | None = None,
    ) -> CertificateResponse:
        try:
            attention = self._require_emittable_attention(
                command.atencion_id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            if (
                command.profesional_id is not None
                and command.profesional_id != attention.profesional_id
            ):
                raise BusinessRuleError(
                    code="CERTIFICADO_PROFESIONAL_DISTINTO_ATENCION",
                    message=(
                        "El certificado debe ser emitido por el profesional de la atención. "
                        "La cofirma no está implementada."
                    ),
                )
            if (
                command.profesional_id is not None
                and self._documents.get_active_professional(command.profesional_id) is None
            ):
                raise NotFoundError(
                    code="PROFESIONAL_NO_ACTIVO",
                    message="El profesional del certificado no está activo.",
                )
            for service_code in command.prestaciones:
                if self._documents.get_active_service(service_code) is None:
                    raise NotFoundError(
                        code="PRESTACION_NO_ACTIVA",
                        message=f"La prestación {service_code} no existe o está inactiva.",
                    )
            period = str(attention.fecha_atencion.year)
            number = self._next_number("CERT", attention.establecimiento_id, period)
            entity = Certificate(
                atencion_id=attention.id,
                establecimiento_id=attention.establecimiento_id,
                profesional_id=command.profesional_id or attention.profesional_id,
                numero_certificado=number,
                tipo=command.tipo,
                consultorio=str(attention.consultorio_id),
                admision=attention.admision,
                estado="EMITIDO",
            )
            self._documents.add(entity)
            self._documents.flush()
            for order, service_code in enumerate(command.prestaciones, start=1):
                self._documents.add(
                    CertificateService(
                        certificado_id=entity.id,
                        numero_orden=order,
                        prestacion_codigo=service_code,
                    )
                )
            self._documents.flush()
            self._documents.add_audit(
                actor_id=actor_id,
                table_name="certificados",
                record_id=entity.id,
                after={
                    "atencion_id": entity.atencion_id,
                    "numero_certificado": entity.numero_certificado,
                },
            )
            self._session.commit()
            self._documents.refresh(entity)
            persisted = self._documents.get_certificate(entity.id)
            return certificate_to_response(persisted or entity)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="CERTIFICADO_EN_CONFLICTO",
                message="No se pudo emitir el certificado por una restricción de identidad.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def create_referral(
        self,
        command: ReferralCreateInput,
        *,
        actor_id: int,
        actor_roles: Iterable[str] | None = None,
    ) -> ReferralResponse:
        try:
            attention = self._require_emittable_attention(
                command.atencion_id,
                actor_id=actor_id,
                actor_roles=actor_roles,
            )
            origin_id = attention.establecimiento_id
            if command.establecimiento_destino_id == origin_id:
                raise BusinessRuleError(
                    code="REFERENCIA_MISMA_SEDE",
                    message="El establecimiento de destino debe ser distinto del origen.",
                )
            if self._documents.get_active_establishment(command.establecimiento_destino_id) is None:
                raise NotFoundError(
                    code="ESTABLECIMIENTO_DESTINO_NO_ACTIVO",
                    message="El establecimiento de destino no existe o está inactivo.",
                )
            period = str(attention.fecha_atencion.year)
            number = self._next_number("REF", origin_id, period)
            entity = Referral(
                atencion_id=attention.id,
                numero_referencia=number,
                tipo=command.tipo,
                establecimiento_origen_id=origin_id,
                establecimiento_destino_id=command.establecimiento_destino_id,
                motivo=command.motivo,
                observaciones=command.observaciones,
                estado=command.estado.value,
            )
            self._documents.add(entity)
            self._documents.flush()
            self._documents.add_audit(
                actor_id=actor_id,
                table_name="referencias",
                record_id=entity.id,
                after={
                    "atencion_id": entity.atencion_id,
                    "numero_referencia": entity.numero_referencia,
                },
            )
            self._session.commit()
            self._documents.refresh(entity)
            return referral_to_response(entity)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="REFERENCIA_EN_CONFLICTO",
                message="No se pudo crear la referencia por una restricción de identidad.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def _require_emittable_attention(
        self,
        attention_id: int,
        *,
        actor_id: int,
        actor_roles: Iterable[str] | None,
    ):
        attention = self._documents.get_attention(attention_id, lock=True)
        if attention is None:
            raise NotFoundError(
                code="ATENCION_NO_ENCONTRADA", message="No existe la atención solicitada."
            )
        self._ensure_actor_can_operate_attention(
            attention.profesional_id,
            actor_id=actor_id,
            actor_roles=actor_roles,
        )
        if attention.estado == "ANULADO":
            raise BusinessRuleError(
                code="ATENCION_ANULADA",
                message="No se pueden emitir documentos para una atención anulada.",
            )
        if attention.estado != "ATENDIDO":
            raise BusinessRuleError(
                code="TRANSICION_ESTADO_NO_PERMITIDA",
                message="El estado actual de la atención no permite emitir documentos.",
            )
        if self._documents.get_active_establishment(attention.establecimiento_id) is None:
            raise NotFoundError(
                code="ESTABLECIMIENTO_NO_ACTIVO", message="La sede de la atención no está activa."
            )
        return attention

    def _ensure_actor_can_operate_attention(
        self,
        attention_professional_id: int,
        *,
        actor_id: int,
        actor_roles: Iterable[str] | None,
    ) -> None:
        """Require the linked clinician to issue documents for own encounters.

        The policy intentionally denies generic administrative accounts here
        as a defense in depth measure. Public controllers already enforce the
        permission map, and this object-level check keeps a future router
        change from turning ADMIN into a clinical signer.
        """

        if actor_roles is None:
            return
        normalized_roles = {role.upper() for role in actor_roles}
        if "PROFESIONAL" not in normalized_roles:
            raise AuthorizationError(
                code="ROL_CLINICO_REQUERIDO",
                message="Solo un usuario PROFESIONAL vinculado puede emitir documentos clínicos.",
            )
        professional_id = self._documents.get_active_professional_id_for_user(actor_id)
        if professional_id is None:
            raise AuthorizationError(
                code="USUARIO_PROFESIONAL_SIN_VINCULO",
                message="El usuario clínico no está vinculado a un profesional activo.",
            )
        if professional_id != attention_professional_id:
            raise AuthorizationError(
                code="PROFESIONAL_DISTINTO_AL_USUARIO",
                message="Solo puede emitir documentos de sus propias atenciones.",
            )

    def _next_number(self, kind: str, establishment_id: int, period: str) -> str:
        sequence = self._documents.reserve_sequence_number(
            kind=kind, establishment_id=establishment_id, period=period
        )
        return self._formatter.format(kind, establishment_id, period, sequence)

    @staticmethod
    def _renipress_for(codigo_renaes: str | None) -> str:
        """Normalize the numeric RENAES catalog value to the 8-digit FUA field."""

        raw = (codigo_renaes or "").strip()
        if not re.fullmatch(r"\d{1,8}", raw):
            raise BusinessRuleError(
                code="FUA_RENIPRESS_NO_VALIDO",
                message=(
                    "El establecimiento no tiene un código RENAES numérico válido "
                    "para emitir el FUA. "
                    "Actualice el catálogo institucional antes de continuar."
                ),
            )
        return raw.zfill(8)
