import re
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.age import calendar_age
from app.domain.patient_condition import PATIENT_CONDITIONS, condition_for_attention
from app.mappers.patient import patient_update_to_entity_kwargs
from app.schemas.patient import PatientCreate, PatientUpdate


def create_payload(condition):
    return dict(
        tipo_documento_codigo="DNI",
        numero_documento="12345678",
        fecha_nacimiento="2000-01-01",
        condicion=condition,
    )


@pytest.mark.parametrize("condition", PATIENT_CONDITIONS)
def test_nine_conditions_are_accepted_at_registration_and_update(condition):
    assert PatientCreate(**create_payload(condition)).condicion == condition
    assert patient_update_to_entity_kwargs(PatientUpdate(condicion=condition)) == {
        "condicion": condition,
    }


@pytest.mark.parametrize("condition", ["GESTNATE", "OTRO", "CONDICION LIBRE", 123])
def test_new_condition_must_belong_to_catalog(condition):
    with pytest.raises(ValidationError):
        PatientCreate(**create_payload(condition))
    with pytest.raises(ValidationError):
        PatientUpdate(condicion=condition)


@pytest.mark.parametrize(
    "value,canonical",
    [
        (" puérpera ", "PUERPERA"),
        ("recién  nacido", "RECIEN NACIDO"),
        ("niño", "NIÑO"),
        ("nino", "NIÑO"),
        (" no gestante ", "NO GESTANTE"),
        (None, None),
        (" ", None),
    ],
)
def test_condition_normalization_and_explicit_clearing(value, canonical):
    assert PatientCreate(**create_payload(value)).condicion == canonical
    assert patient_update_to_entity_kwargs(PatientUpdate(condicion=value)) == {
        "condicion": canonical,
    }


def test_unrelated_patch_does_not_overwrite_historical_condition():
    assert patient_update_to_entity_kwargs(PatientUpdate(primer_nombre="Ana")) == {
        "primer_nombre": "Ana",
    }


def test_frontend_and_backend_condition_catalogs_match():
    source = Path(__file__).resolve().parents[2] / "frontend/src/utils/patientCondition.ts"
    assert tuple(re.findall(r"'([^']+)'", source.read_text(encoding="utf-8"))) == PATIENT_CONDITIONS


@pytest.mark.parametrize(
    "age_group,expected",
    [
        ("NINO", "NIÑO"),
        ("ADOLESCENTE", "ADOLESCENTE"),
        ("JOVEN", "JOVEN"),
        ("ADULTO", "ADULTO"),
        ("ADULTO_MAYOR", "ADULTO MAYOR"),
    ],
)
def test_general_attention_condition_follows_the_calculated_age_group(age_group, expected):
    age = calendar_age(date(1990, 1, 1), date(2026, 1, 1))

    assert (
        condition_for_attention(
            age_group_code=age_group,
            care_group_code="NINOS_ADOLESCENTES_ADULTOS_MAYORES",
            age=age,
        )
        == expected
    )


@pytest.mark.parametrize(
    "care_group,expected",
    [("GESTANTES", "GESTANTE"), ("PUERPERAS", "PUERPERA")],
)
def test_maternal_context_takes_priority_over_age_group(care_group, expected):
    age = calendar_age(date(1990, 1, 1), date(2026, 1, 1))

    assert (
        condition_for_attention(
            age_group_code="ADULTO",
            care_group_code=care_group,
            age=age,
        )
        == expected
    )


def test_newborn_condition_is_preserved_during_the_first_28_days():
    general = "NINOS_ADOLESCENTES_ADULTOS_MAYORES"

    assert (
        condition_for_attention(
            age_group_code="NINO",
            care_group_code=general,
            age=calendar_age(date(2026, 1, 1), date(2026, 1, 28)),
        )
        == "RECIEN NACIDO"
    )
    assert (
        condition_for_attention(
            age_group_code="NINO",
            care_group_code=general,
            age=calendar_age(date(2026, 1, 1), date(2026, 1, 29)),
        )
        == "NIÑO"
    )


def test_unknown_age_group_fails_instead_of_silently_assigning_a_condition():
    with pytest.raises(ValueError, match="GRUPO_DESCONOCIDO"):
        condition_for_attention(
            age_group_code="GRUPO_DESCONOCIDO",
            care_group_code="NINOS_ADOLESCENTES_ADULTOS_MAYORES",
            age=calendar_age(date(1990, 1, 1), date(2026, 1, 1)),
        )
