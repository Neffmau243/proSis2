from app.domain.office import AREA_NAMES, office_context
from app.models.organization import Office, OfficeProfessional
from app.schemas.catalog import CodeCatalogItem
from app.schemas.office import OfficeAssignmentResponse, OfficeResponse


def office_to_response(entity: Office, specialties: dict[str, str] | None = None) -> OfficeResponse:
    context = office_context(entity)
    names = specialties or {}
    response = OfficeResponse.model_validate(entity)
    response.area_codigo = context.area_code
    response.especialidad_requerida_codigo = context.required_specialty
    response.area_nombre = names.get(context.area_code, AREA_NAMES.get(context.area_code))
    response.ruta = context.path
    response.activo_efectivo = context.active
    response.establecimiento_nombre = (
        entity.establecimiento.nombre if entity.establecimiento else None
    )
    response.consultorio_padre_nombre = entity.padre.nombre if entity.padre else None
    response.servicios_habilitados = [
        CodeCatalogItem(codigo=code, nombre=names.get(code, code), activo=True)
        for code in context.service_codes
        if specialties is None or code in names
    ]
    return response


def office_assignment_to_response(entity: OfficeProfessional) -> OfficeAssignmentResponse:
    response = OfficeAssignmentResponse.model_validate(entity)
    response.profesional_nombre = entity.profesional.nombre_completo if entity.profesional else None
    response.profesional_activo = bool(entity.profesional and entity.profesional.activo)
    response.consultorio_nombre = entity.consultorio.nombre if entity.consultorio else None
    return response
