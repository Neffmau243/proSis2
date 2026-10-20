"""Versioned review downloads and manual, audited evidence of external sending.

There is no SIS/SIEN network integration here. Catalog codes are preserved as
IPRESS stores them; the projection is not an accredited external data contract.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.attention import attention_to_response
from app.mappers.nutrition_export import legacy_projection as legacy_projection
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.services.clinical_access import ClinicalAccessService


class NutritionExportService:
    """Coordinates review and manual sending in the caller's session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._attentions = AttentionRepository(session)
        self._patients = PatientRepository(session)

    @property
    def _access(self) -> ClinicalAccessService:
        return ClinicalAccessService(self._attentions, self._patients)

    def _record(self, attention_id, actor_id, actor_roles):
        entity = self._attentions.get_by_id(attention_id, lock=True)
        if entity is None:
            raise NotFoundError(code="ATENCION_NO_ENCONTRADA", message="No existe la atención.")
        scope = self._access.attention_scope(actor_id=actor_id, actor_roles=actor_roles)
        self._access.ensure_attention(entity, scope, actor_id=actor_id)
        if entity.estado != "ATENDIDO":
            raise BusinessRuleError(
                code="ATENCION_ANULADA",
                message="Una atención anulada no admite exportación o envío.",
            )
        records = entity.evaluaciones_nutricionales
        if not entity.contexto_clinico or len(records) != 1:
            raise BusinessRuleError(
                code="NUTRICION_SIN_CONTEXTO",
                message="Se requiere una valoración con contexto histórico completo. "
                "Las atenciones anteriores se conservan sin reconstruir sus datos.",
            )
        return entity, records[0]

    def export_review(self, attention_id, *, actor_id, actor_roles):
        try:
            self._access.linked_professional(actor_id=actor_id, actor_roles=actor_roles)
            entity, record = self._record(attention_id, actor_id, actor_roles)
            before = {"estado_exportacion": record.estado_exportacion}
            if record.estado_exportacion != "ENVIADO":
                record.estado_exportacion = "EXPORTADO"
            record.exportado_at = datetime.now(UTC).replace(tzinfo=None)
            self._attentions.add_audit(
                actor_id=actor_id,
                action="EXPORT",
                record_id=entity.id,
                before=before,
                after={
                    "estado_exportacion": record.estado_exportacion,
                    "formato": "IPRESS_NUTRICION_REVISION_V1",
                },
            )
            self._attentions.flush()
            response = attention_to_response(entity)
            result = {
                "formato": "IPRESS_NUTRICION_REVISION_V1",
                "trama_oficial": False,
                "aviso": "Archivo de revisión. No acredita recepción por SIS/SIEN. "
                "Códigos del catálogo IPRESS sin homologación externa.",
                "atencion": response.model_dump(mode="json"),
                "campos_legados": legacy_projection(response),
                "equivalencias_pendientes": [
                    "Disa/Red/MicroRed/Establecimiento: homologación de códigos",
                    "Condicion y Edad: codificación y unidades de la trama de destino",
                    "P65/VL/CP/Flag/SufijoDocumento: catálogo no disponible",
                    "PPG: proyectado como peso pregestacional; confirmar con receptor",
                ],
            }
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def confirm_sent(self, attention_id, command, *, actor_id, actor_roles):
        try:
            self._access.linked_professional(actor_id=actor_id, actor_roles=actor_roles)
            entity, record = self._record(attention_id, actor_id, actor_roles)
            if record.estado_exportacion == "ENVIADO":
                if record.constancia_envio == command.constancia:
                    self._session.rollback()
                    return attention_to_response(entity)
                raise ConflictError(
                    code="ENVIO_YA_REGISTRADO",
                    message="Ya existe una constancia de envío diferente.",
                )
            if record.estado_exportacion != "EXPORTADO":
                raise BusinessRuleError(
                    code="EXPORTACION_REQUERIDA",
                    message="Descargue el archivo antes de registrar su envío externo.",
                )
            record.estado_exportacion = "ENVIADO"
            record.enviado = True
            record.enviado_at = datetime.now(UTC).replace(tzinfo=None)
            record.constancia_envio = command.constancia
            self._attentions.add_audit(
                actor_id=actor_id,
                action="UPDATE",
                record_id=entity.id,
                before={"estado_exportacion": "EXPORTADO", "enviado": False},
                after={
                    "estado_exportacion": "ENVIADO",
                    "enviado": True,
                    "constancia_envio": command.constancia,
                    "confirmacion": "MANUAL",
                },
            )
            self._session.commit()
            return attention_to_response(entity)
        except Exception:
            self._session.rollback()
            raise
