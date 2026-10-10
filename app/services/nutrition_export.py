"""Versioned review downloads and manual, audited evidence of external sending.

There is no SIS/SIEN network integration here. Catalog codes are preserved as
IPRESS stores them; the projection is not an accredited external data contract.
"""

from datetime import UTC, datetime

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.attention import attention_to_response
from app.services.attention import AttentionService


class NutritionExportService(AttentionService):
    def _record(self, attention_id, actor_id, actor_roles):
        entity = self._attentions.get_by_id(attention_id, lock=True)
        if entity is None:
            raise NotFoundError(code="ATENCION_NO_ENCONTRADA", message="No existe la atención.")
        self._ensure_attention_in_scope(entity, actor_id=actor_id, actor_roles=actor_roles)
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
            self._ensure_actor_is_linked_professional(actor_id=actor_id, actor_roles=actor_roles)
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
            self._ensure_actor_is_linked_professional(actor_id=actor_id, actor_roles=actor_roles)
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


def legacy_projection(attention):
    context = attention.contexto_clinico
    record = attention.evaluaciones_nutricionales[0]
    row = {
        "Disa": context.get("disa_codigo"),
        "Red": context.get("red_codigo"),
        "MicroRed": context.get("microred_codigo"),
        "Establecimiento": attention.establecimiento_id,
        "IDEESS": context.get("codigo_ideess"),
        "Fecha": attention.fecha_atencion.isoformat(),
        "Hist_Clinica": attention.historia_clinica_snapshot,
        "nDNI": context.get("numero_documento"),
        "TipoDocumento": context.get("tipo_documento_codigo"),
        "SufijoDocumento": context.get("sufijo_documento"),
        "Sexo": context.get("sexo_codigo"),
        "Condicion": context.get("condicion"),
        "Edad": context.get("edad_anios"),
        "Peso": attention.peso_kg,
        "Talla": attention.talla_cm,
        "Hemoglobina": record.hemoglobina,
        "Hbc": record.hemoglobina_corregida,
        "Provincia": context.get("provincia"),
        "Distrito": context.get("distrito"),
        "Localidad": context.get("localidad_codigo_sis"),
        "Altitud": record.altitud_msnm,
        "Enviado": record.enviado,
    }
    if record.tipo == "NINO":
        row.update(
            {
                "Fec_Nacimiento": context.get("fecha_nacimiento"),
                "Edad": (context["edad_anios"] * 12 + context["edad_meses"]),
                "PerimetroAbdominal": attention.perimetro_abdominal_cm,
                "BMI": attention.imc,
                "WHZ": record.whz,
                "HAZ": record.haz,
                "WAZ": record.waz,
                "FechaHemoglobina": record.fecha_hemoglobina,
                "SIS": context.get("sis"),
                **{
                    legacy: getattr(record, field)
                    for legacy, field in (
                        ("JUNTOS", "juntos"),
                        ("PIN", "pin"),
                        ("CRECER", "crecer"),
                        ("Nro_ControlesCred", "nro_controles_cred"),
                        ("Nro_Sachets", "nro_sachets"),
                        ("Nro_Consejerias", "nro_consejerias"),
                        ("Nro_Sesiones", "nro_sesiones"),
                        ("Nro_Visitas", "nro_visitas"),
                        ("InstitucionEducativa", "institucion_educativa"),
                        ("NivelEducativo", "nivel_educativo"),
                        ("Grado", "grado"),
                        ("Turno", "turno"),
                        ("CodigoMatricula", "codigo_matricula"),
                        ("Seccion", "seccion"),
                        ("Aula", "aula"),
                        ("Flag", "flag_legacy"),
                    )
                },
            }
        )
    elif record.tipo == "ADULTO":
        row.update(
            FechaNacimiento=context.get("fecha_nacimiento"),
            PerimetroAbdominal=attention.perimetro_abdominal_cm,
            FechaResultadoHb=record.fecha_hemoglobina,
            SIS=context.get("sis"),
            P65=record.p65,
            VL=record.vl,
            CP=record.cp,
            Pending=record.pending_legacy,
        )
    else:
        row.update(
            Edad_Gestacional=record.edad_gestacional_semanas,
            Hematocrito=record.hematocrito,
            Diagnostico=record.diagnostico,
            PPG=attention.peso_antes_embarazo_kg,
            Tipo_Embarazo=attention.tipo_embarazo_codigo,
            Estado_Ganancia_Peso=record.estado_ganancia_peso,
            FechaHemoglobina=record.fecha_hemoglobina,
            Pending=record.pending_legacy,
        )
    # Keep Decimal precision and date encoding consistent with the API contracts.
    from decimal import Decimal

    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(row, custom_encoder={Decimal: str})
