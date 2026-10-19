from datetime import date
from decimal import Decimal

import pytest

from app.domain.nutrition import (
    WHO_2006_REFERENCE,
    calculate_nutritional_indicators,
    classify_score,
)


@pytest.mark.parametrize("kind,score,expected", [
    ("pe", "-3.001", "Bajo peso severo"), ("pe", "-3", "Bajo peso"),
    ("pe", "-2", "Normal"), ("pe", "1.001", "Normal"),
    ("pe", "2", "Normal"), ("pe", "2.001", "Sobrepeso"),
    ("te", "-3.001", "Talla baja severa"), ("te", "-3", "Talla baja"),
    ("te", "-2", "Normal"), ("te", "2", "Normal"), ("te", "2.001", "Talla alta"),
    ("pt", "-3.001", "Emaciación severa"), ("pt", "-3", "Emaciación"),
    ("pt", "-2", "Normal"), ("pt", "1", "Normal"),
    ("pt", "1.001", "Normal"), ("pt", "2", "Normal"),
    ("pt", "2.001", "Sobrepeso"), ("pt", "3", "Sobrepeso"),
    ("pt", "3.001", "Obesidad"),
])
def test_classification_thresholds(kind, score, expected):
    assert classify_score(Decimal(score), kind) == expected


def test_no_classification_without_score():
    assert classify_score(None, "pt") is None


def test_calculates_who_2006_scores_for_a_child_with_complete_measurements() -> None:
    indicators = calculate_nutritional_indicators(
        birth_date=date(2024, 1, 15),
        sex_code="M",
        measured_on=date(2025, 1, 15),
        weight_kg=Decimal("9.50"),
        height_cm=Decimal("75.20"),
    )

    assert indicators.imc == Decimal("16.799")
    assert indicators.pe == Decimal("-0.147")
    assert indicators.te == Decimal("-0.243")
    assert indicators.pt == Decimal("-0.056")
    assert indicators.estado == "CALCULADO"
    assert indicators.referencia == WHO_2006_REFERENCE


def test_calculates_who_2006_scores_on_the_day_of_birth() -> None:
    indicators = calculate_nutritional_indicators(
        birth_date=date(2026, 10, 9),
        sex_code="F",
        measured_on=date(2026, 10, 9),
        weight_kg=Decimal("3.20"),
        height_cm=Decimal("50.00"),
    )

    assert indicators.grupo_referencia == "INFANTIL"
    assert indicators.estado == "CALCULADO"
    assert indicators.imc == Decimal("12.800")
    assert (indicators.pe, indicators.te, indicators.pt) == (
        Decimal("-0.071"),
        Decimal("0.458"),
        Decimal("-0.516"),
    )
    assert indicators.classifications == {
        "diagnostico_peso_edad": "Normal",
        "diagnostico_talla_edad": "Normal",
        "diagnostico_peso_talla": "Normal",
    }


def test_keeps_bmi_but_does_not_extrapolate_child_scores_for_an_adult() -> None:
    indicators = calculate_nutritional_indicators(
        birth_date=date(1990, 5, 10),
        sex_code="F",
        measured_on=date(2026, 9, 12),
        weight_kg=Decimal("60.00"),
        height_cm=Decimal("160.00"),
    )

    assert indicators.imc == Decimal("23.438")
    assert (indicators.pe, indicators.te, indicators.pt) == (None, None, None)
    assert indicators.estado == "CALCULADO"
    assert indicators.diagnostico_imc == "Normal"
    assert indicators.grupo_referencia == "ADULTO"


def test_requires_weight_and_height_before_calculating_indicators() -> None:
    indicators = calculate_nutritional_indicators(
        birth_date=date(2024, 1, 15),
        sex_code="F",
        measured_on=date(2025, 1, 15),
        weight_kg=Decimal("9.00"),
        height_cm=None,
    )

    assert indicators.imc is None
    assert (indicators.pe, indicators.te, indicators.pt) == (None, None, None)
    assert indicators.estado == "DATOS_INCOMPLETOS"
