"""Freeze the encounter's identity and geography without guessing legacy codes."""

from app.domain.age import CalendarAge
from app.domain.patient_insurance import is_sis_insurance


def nutrition_context(patient, establishment, age: CalendarAge, condition: str) -> dict:
    ubigeo = getattr(patient, "ubigeo_residencia", None)
    locality = getattr(patient, "localidad_catalogo", None)
    micro = getattr(establishment, "microred", None)
    network = getattr(micro, "red", None)
    disa = getattr(network, "disa", None)
    insurance = getattr(patient, "insurance", None)
    data = {
        key: getattr(patient, key, None)
        for key in (
            "historia_clinica",
            "historia_familiar",
            "tipo_documento_codigo",
            "numero_documento",
            "sufijo_documento",
            "sexo_codigo",
            "apellido_paterno",
            "apellido_materno",
            "primer_nombre",
            "otros_nombres",
            "condicion",
            "ubigeo_residencia_codigo",
            "localidad",
            "sis_diresa",
            "sis_tipo",
            "sis_numero",
            "sis_secuencia",
        )
    }
    data.update(
        version=1,
        fecha_nacimiento=patient.fecha_nacimiento.isoformat(),
        edad_anios=age.years,
        edad_meses=age.months,
        edad_dias=age.days,
        edad_detallada=age.display,
        condicion=condition,
        provincia=getattr(ubigeo, "provincia", None),
        distrito=getattr(ubigeo, "distrito", None),
        localidad_codigo_sis=getattr(locality, "codigo_sis", None),
        altitud_catalogo_msnm=(
            str(ubigeo.altitud_msnm) if getattr(ubigeo, "altitud_msnm", None) is not None else None
        ),
        sis=is_sis_insurance(insurance) if insurance is not None else None,
        seguro_codigo=getattr(insurance, "codigo", None),
        establecimiento_nombre=getattr(establishment, "nombre", None),
        codigo_ideess=getattr(establishment, "codigo_ideess", None),
        codigo_renaes=getattr(establishment, "codigo_renaes", None),
        disa_codigo=getattr(establishment, "disa_codigo", None) or getattr(disa, "codigo", None),
        red_codigo=getattr(network, "codigo", None),
        microred_codigo=getattr(micro, "codigo", None),
    )
    return data
