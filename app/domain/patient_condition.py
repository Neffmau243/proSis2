"""Catálogo y resolución de la condición vigente del paciente.

La condición sigue siendo editable al registrar la ficha, pero cada atención
aceptada la sincroniza con la etapa de vida calculada. Gestación y puerperio
tienen prioridad porque describen el contexto clínico actual.
"""

from typing import Annotated, Any, Literal, get_args
from unicodedata import normalize

from pydantic import BeforeValidator

from app.domain.age import CalendarAge

PatientConditionLabel = Literal[
    "ADULTO",
    "ADOLESCENTE",
    "NIÑO",
    "JOVEN",
    "PUERPERA",
    "RECIEN NACIDO",
    "ADULTO MAYOR",
    "GESTANTE",
    "NO GESTANTE",
]
PATIENT_CONDITIONS = get_args(PatientConditionLabel)

AGE_GROUP_CONDITIONS: dict[str, PatientConditionLabel] = {
    "NINO": "NIÑO",
    "ADOLESCENTE": "ADOLESCENTE",
    "JOVEN": "JOVEN",
    "ADULTO": "ADULTO",
    "ADULTO_MAYOR": "ADULTO MAYOR",
}
CARE_GROUP_CONDITIONS: dict[str, PatientConditionLabel] = {
    "GESTANTES": "GESTANTE",
    "PUERPERAS": "PUERPERA",
}


def _comparison_key(value: str) -> str:
    return "".join(
        char
        for char in normalize("NFD", " ".join(value.upper().split()))
        if not 0x0300 <= ord(char) <= 0x036F
    )


def normalize_patient_condition(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    if not value.strip():
        return None
    for condition in PATIENT_CONDITIONS:
        if _comparison_key(value) == _comparison_key(condition):
            return condition
    raise ValueError("Seleccione una condición del catálogo ETLSIS.")


PatientCondition = Annotated[
    PatientConditionLabel | None, BeforeValidator(normalize_patient_condition)
]


def condition_for_attention(
    *,
    age_group_code: str,
    care_group_code: str,
    age: CalendarAge,
) -> PatientConditionLabel:
    """Return the master condition produced by a successfully saved encounter."""

    contextual_condition = CARE_GROUP_CONDITIONS.get(care_group_code)
    if contextual_condition is not None:
        return contextual_condition
    if age_group_code == "NINO" and (age.years, age.months, age.days) < (0, 0, 28):
        return "RECIEN NACIDO"
    try:
        return AGE_GROUP_CONDITIONS[age_group_code]
    except KeyError as exc:
        raise ValueError(f"No existe condición para el grupo etario {age_group_code}.") from exc
