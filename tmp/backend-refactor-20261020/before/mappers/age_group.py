from app.models.catalog import AgeGroup
from app.schemas.age_group import AgeBoundaryResponse, AgeGroupResponse


def age_group_to_response(entity: AgeGroup) -> AgeGroupResponse:
    minimum = _boundary_from_months(entity.edad_minima_meses)
    maximum = _boundary_from_months(entity.edad_maxima_meses)
    return AgeGroupResponse(
        codigo=entity.codigo,
        nombre=entity.nombre,
        edad_minima_meses=entity.edad_minima_meses,
        edad_maxima_meses=entity.edad_maxima_meses,
        edad_minima=minimum,
        edad_maxima=maximum,
        rango_edad_legible=_format_range(minimum, maximum),
        activo=entity.activo,
    )


def _boundary_from_months(months: int | None) -> AgeBoundaryResponse | None:
    if months is None:
        return None
    years, remaining_months = divmod(months, 12)
    return AgeBoundaryResponse(anios=years, meses=remaining_months)


def _format_boundary(boundary: AgeBoundaryResponse) -> str:
    parts: list[str] = []
    if boundary.anios or boundary.meses == 0:
        unit = "año" if boundary.anios == 1 else "años"
        parts.append(f"{boundary.anios} {unit}")
    if boundary.meses:
        unit = "mes" if boundary.meses == 1 else "meses"
        parts.append(f"{boundary.meses} {unit}")
    return " y ".join(parts)


def _format_range(
    minimum: AgeBoundaryResponse | None,
    maximum: AgeBoundaryResponse | None,
) -> str:
    if minimum is None:
        return "Sin rango configurado"
    minimum_text = _format_boundary(minimum)
    if maximum is None:
        return f"Desde {minimum_text}"
    return f"De {minimum_text} a {_format_boundary(maximum)}"
