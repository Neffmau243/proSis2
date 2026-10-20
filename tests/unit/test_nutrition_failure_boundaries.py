"""Insufficient, invalid or external-calculator failures must not invent clinical results."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

import app.domain.nutrition as nutrition
from app.domain.age import calendar_age
from app.domain.nutrition_followup import assess_followup


def calculate(**changes):
    values = dict(
        birth_date=date(2024, 1, 1),
        measured_on=date(2025, 1, 1),
        sex_code="M",
        weight_kg=Decimal("10"),
        height_cm=Decimal("75"),
    )
    return nutrition.calculate_nutritional_indicators(**{**values, **changes})


def test_invalid_age_and_unknown_sex_return_explicit_unavailable_results():
    with pytest.raises(ValueError, match="anterior"):
        calendar_age(date(2026, 1, 1), date(2025, 1, 1))
    assert calculate(measured_on=date(2023, 12, 31)).estado == "FECHA_INVALIDA"
    assert calculate(sex_code=None).estado == "SIN_REFERENCIA_SEXO"
    assert calculate(birth_date=date(2014, 1, 1), sex_code="X").estado == "SIN_REFERENCIA_SEXO"
    with pytest.raises(ValueError, match="desconocido"):
        nutrition.classify_score(Decimal("1"), "unknown")
    assert nutrition.classify_bmi_age(None) is None


@pytest.mark.parametrize(
    "external",
    [
        {"z_wfa": None, "z_lhfa": 0, "z_wflh": 0},
        {"z_wfa": float("nan"), "z_lhfa": 0, "z_wflh": 0},
        {"z_wfa": float("inf"), "z_lhfa": 0, "z_wflh": 0},
        {"z_wfa": "0", "z_lhfa": 0, "z_wflh": 0},
        {"z_wfa": 0, "z_lhfa": 0, "z_wflh": 0, "errors": ["invalid measurement"]},
    ],
)
def test_unusable_calculator_output_does_not_publish_scores(monkeypatch, external):
    monkeypatch.setattr(nutrition, "compute", lambda values: external)
    result = calculate()
    assert result.estado == "NO_DISPONIBLE"
    assert result.pe is result.te is result.pt is None
    assert result.imc == Decimal("17.778")


def test_nonincreasing_height_requires_technique_review_in_growth_followup():
    prior = SimpleNamespace(
        id=7, fecha_atencion=datetime(2025, 1, 1), peso_kg=Decimal("10"), talla_cm=Decimal("75")
    )
    result = assess_followup(
        calculate(),
        measured_on=date(2025, 2, 1),
        age_months=13,
        weight=Decimal("11"),
        height=Decimal("74"),
        previous=prior,
    )
    growth = next(item for item in result["sugerencias"] if item["codigo"] == "NUT_CRECIMIENTO")
    assert "Talla sin incremento" in growth["motivo"]
    assert "técnica de medición" in growth["motivo"]
