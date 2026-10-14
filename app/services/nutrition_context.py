"""Freeze the encounter's identity and geography without guessing legacy codes."""

from app.domain.age import CalendarAge
from app.domain.office import office_context
from app.domain.patient_insurance import is_sis_insurance
from app.schemas.encounter_context import EncounterLocationSnapshot


def nutrition_context(
    patient,
    establishment,
    age: CalendarAge,
    condition: str,
    *,
    office=None,
    professional=None,
    specialty=None,
) -> dict:
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
    site_ubigeo = getattr(establishment, "ubigeo", None)
    registration = getattr(patient, "establecimiento_registro", None)
    context = office_context(office) if office is not None else None
    location = EncounterLocationSnapshot(
        ubigeo_residencia_codigo=getattr(patient, "ubigeo_residencia_codigo", None),
        departamento=getattr(ubigeo, "departamento", None),
        provincia=getattr(ubigeo, "provincia", None),
        distrito=getattr(ubigeo, "distrito", None),
        localidad_id=getattr(patient, "localidad_id", None),
        localidad_codigo_catalogo=getattr(locality, "codigo_catalogo", None),
        localidad_codigo_sis=getattr(locality, "codigo_sis", None),
        localidad=getattr(locality, "nombre", None) or getattr(patient, "localidad", None),
        direccion=getattr(patient, "direccion", None),
        establecimiento_registro_id=getattr(patient, "establecimiento_registro_id", None),
        establecimiento_registro_nombre=getattr(registration, "nombre", None),
        establecimiento_id=getattr(establishment, "id", None),
        establecimiento_nombre=getattr(establishment, "nombre", None),
        establecimiento_ubigeo_codigo=getattr(establishment, "ubigeo_codigo", None),
        establecimiento_departamento=getattr(site_ubigeo, "departamento", None),
        establecimiento_provincia=getattr(site_ubigeo, "provincia", None),
        establecimiento_distrito=getattr(site_ubigeo, "distrito", None),
        consultorio_id=getattr(office, "id", None),
        consultorio_codigo=getattr(office, "codigo", None),
        consultorio_nombre=getattr(office, "nombre", None),
        consultorio_ruta=context.path if context else None,
        consultorio_padre_id=getattr(office, "consultorio_padre_id", None),
        consultorio_ancestros_ids=list(context.ancestor_ids) if context else [],
        area_codigo=context.area_code if context else None,
        especialidad_codigo=getattr(specialty, "codigo", None),
        especialidad_nombre=getattr(specialty, "nombre", None),
        profesional_id=getattr(professional, "id", None),
        profesional_nombre=getattr(professional, "nombre_completo", None),
    )
    data.update(location.model_dump(mode="json"))
    data.update(
        version=2,
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
