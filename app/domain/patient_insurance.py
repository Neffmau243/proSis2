"""Insurance family and patient-owned affiliation fields."""

SIS_FIELDS = ("sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia")


def is_sis_insurance(insurance: object | None) -> bool:
    return insurance is not None and (
        getattr(insurance, "regimen", None) == "SIS"
        or getattr(insurance, "codigo", None) == "SIS"
    )
