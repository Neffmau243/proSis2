"""Insurance family and patient-owned affiliation fields."""

SIS_FIELDS = ("sis_diresa", "sis_tipo", "sis_numero", "sis_secuencia")


def is_sis_insurance(insurance: object | None) -> bool:
    return insurance is not None and (
        getattr(insurance, "regimen", None) == "SIS"
        or getattr(insurance, "codigo", None) == "SIS"
    )


def sis_type_for_insurance(insurance: object | None) -> str | None:
    """Return the two-digit operational SIS type from its ETLSIS catalog code.

    ETLSIS stores the plan as three digits (``005`` for NRUS), while the
    established admission workflow stores the patient's type as two (``05``).
    Generic SIS rows without a source code intentionally keep the declared
    patient value unchanged.
    """

    code = getattr(insurance, "codigo_sis", None)
    if not is_sis_insurance(insurance) or not isinstance(code, str):
        return None
    normalized = code.strip()
    return normalized[-2:] if normalized.isdigit() and len(normalized) == 3 else None
