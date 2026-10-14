"""Build an immutable paper-print projection from server-owned clinical data."""

import re
from zoneinfo import ZoneInfo

from app.domain.patient_insurance import SIS_FIELDS, is_sis_insurance
from app.models.clinical import Attention
from app.models.organization import Establishment
from app.models.patient import Patient
from app.models.security import Professional
from app.schemas.encounter_context import EncounterLocationSnapshot
from app.schemas.fua_print import FuaPrintInput, FuaPrintSnapshot


def build_fua_snapshot(
    attention: Attention,
    patient: Patient,
    establishment: Establishment,
    professional: Professional,
    supplement: FuaPrintInput | None,
) -> dict[str, object]:
    values = FuaPrintInput().model_dump()
    values.update(
        {
            key: getattr(patient, key, None)
            for key in ("sis_diresa", "sis_tipo", "sis_numero", "etnia_codigo")
        }
    )
    has_sis = is_sis_insurance(getattr(patient, "insurance", None))
    if not has_sis:
        values.update({key: None for key in SIS_FIELDS if key != "sis_secuencia"})
    values["tipo_atencion"] = attention.modalidad_atencion_codigo
    values["personal_atiende"] = getattr(establishment, "fua_personal_atiende", None) or "IPRESS"
    values["lugar_atencion"] = getattr(establishment, "fua_lugar_atencion", None) or "INTRAMURAL"
    values["codigo_aisped"] = getattr(establishment, "fua_codigo_aisped", None)
    # Legacy clients may supply referral data, never patient identity or site defaults.
    if supplement and values["tipo_atencion"] == "REFERENCIA":
        values.update(
            {
                key: getattr(supplement, key)
                for key in ("referencia_renipress", "referencia_nombre", "referencia_hoja")
            }
        )
    # Never substitute an internal database ID for RENIPRESS or SIS affiliation.
    # The legacy catalog stores the source code as ``1291``/``0001291`` while
    # the FUA box requires eight digits, so numeric values are left-padded.
    renaes = establishment.codigo_renaes or ""
    if not values["codigo_renipress"] and re.fullmatch(r"[0-9]{1,8}", renaes):
        values["codigo_renipress"] = renaes.zfill(8)
    moment = attention.fecha_atencion
    if moment.tzinfo is not None:
        moment = moment.astimezone(ZoneInfo("America/Lima"))
    nutrition = getattr(attention, "valoracion_calculada", None) or {}
    snapshot = FuaPrintSnapshot(
        **values,
        contexto_territorial=(
            EncounterLocationSnapshot.model_validate(attention.contexto_clinico)
            if getattr(attention, "contexto_clinico", None) is not None
            else None
        ),
        version=2,
        sis_secuencia=getattr(patient, "sis_secuencia", None) if has_sis else None,
        renipress_preimpreso=getattr(establishment, "fua_renipress_preimpreso", True),
        ipress_nombre=establishment.nombre,
        profesional_nombre=professional.nombre_completo,
        profesional_documento=professional.numero_documento,
        profesional_colegiatura=professional.colegiatura,
        tipo_documento=patient.tipo_documento_codigo,
        tdi={"DNI": "2", "CE": "3"}.get(patient.tipo_documento_codigo),
        numero_documento=patient.numero_documento,
        apellido_paterno=patient.apellido_paterno,
        apellido_materno=patient.apellido_materno,
        primer_nombre=patient.primer_nombre,
        otros_nombres=patient.otros_nombres,
        sexo_codigo=patient.sexo_codigo,
        fecha_nacimiento=patient.fecha_nacimiento,
        historia_clinica=attention.historia_clinica_snapshot,
        fecha_atencion=moment.date(),
        hora_atencion=moment.time().replace(tzinfo=None),
        peso_kg=attention.peso_kg,
        talla_cm=attention.talla_cm,
        presion_sistolica=attention.presion_sistolica,
        presion_diastolica=attention.presion_diastolica,
        imc=attention.imc,
        grupo_referencia=nutrition.get("grupo_referencia"),
        estado_nutricional=nutrition.get("estado"),
        pe=getattr(attention, "pe", None),
        te=getattr(attention, "te", None),
        pt=getattr(attention, "pt", None),
        diagnostico_peso_edad=nutrition.get("diagnostico_peso_edad"),
        diagnostico_talla_edad=nutrition.get("diagnostico_talla_edad"),
        diagnostico_peso_talla=nutrition.get("diagnostico_peso_talla"),
        diagnostico_imc=nutrition.get("diagnostico_imc"),
        imc_pregestacional=nutrition.get("imc_pregestacional"),
        ganancia_peso_kg=nutrition.get("ganancia_peso_kg"),
        perimetro_abdominal_cm=attention.perimetro_abdominal_cm,
        grupo_atencion_codigo=attention.grupo_atencion_codigo,
        fecha_probable_parto=attention.fecha_probable_parto,
        fecha_parto=attention.fecha_parto,
    )
    return snapshot.model_dump(mode="json")
