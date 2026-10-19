from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.nutrition import NutritionalIndicators, calculate_nutritional_indicators
from app.domain.nutrition_followup import assess_followup


def normal_child(**overrides):
    values = dict(
        imc=Decimal(16),
        pe=Decimal(0),
        te=Decimal(0),
        pt=Decimal(0),
        estado="CALCULADO",
        mensaje="",
        referencia="OMS",
    )
    values.update(overrides)
    return NutritionalIndicators(**values)


def assessment(result=None, **changes):
    values = dict(
        measured_on=date(2026, 10, 17), age_months=24, weight=Decimal(12), height=Decimal(85)
    )
    values.update(changes)
    return assess_followup(result or normal_child(), **values)


def test_first_control_is_not_reported_as_normal_growth_or_negative_screening():
    result = assessment()
    assert result["tendencia"]["estado"] == "DATOS_INSUFICIENTES"
    assert result["sugerencias"] == []
    assert result["tamizaje"] == "NO_EVALUADO"


def test_normal_current_scores_do_not_hide_a_weight_plateau():
    prior = SimpleNamespace(
        id=3, fecha_atencion=datetime(2026, 9, 17), peso_kg=Decimal(12), talla_cm=Decimal(84)
    )
    result = assessment(previous=prior)
    assert result["tendencia"]["dias"] == 30
    assert result["tendencia"]["cambio_peso_kg"] == "0"
    assert [s["codigo"] for s in result["sugerencias"]] == ["NUT_CRECIMIENTO"]
    assert result["sugerencias"][0]["requiere_confirmacion"] is True


@pytest.mark.parametrize("when", [datetime(2026, 10, 17), datetime(2026, 10, 18)])
def test_same_day_or_future_controls_cannot_establish_growth(when):
    prior = SimpleNamespace(id=3, fecha_atencion=when, peso_kg=Decimal(12), talla_cm=Decimal(84))
    assert assessment(previous=prior)["tendencia"]["estado"] == "DATOS_INSUFICIENTES"


def test_missing_current_measurement_cannot_establish_growth():
    prior = SimpleNamespace(
        id=3, fecha_atencion=datetime(2026, 9, 17), peso_kg=Decimal(12), talla_cm=Decimal(84)
    )
    result = assessment(normal_child(estado="DATOS_INCOMPLETOS"), weight=None, previous=prior)
    assert result["tendencia"]["estado"] == "DATOS_INSUFICIENTES"
    assert result["sugerencias"] == []


def test_adult_delgadez_is_a_confirmable_finding_without_child_scores():
    adult = calculate_nutritional_indicators(
        birth_date=date(1991, 10, 17),
        measured_on=date(2026, 10, 17),
        sex_code="M",
        weight_kg=Decimal(50),
        height_cm=Decimal(175),
    )
    result = assessment(adult, age_months=420, weight=Decimal(50), height=Decimal(175))
    assert adult.diagnostico_imc == "Delgadez grado II"
    assert adult.pe is adult.te is adult.pt is None
    assert result["sugerencias"][0]["motivo"] == "Delgadez grado II"
    assert result["tendencia"]["estado"] == "NO_APLICA"
    assert result["tamizaje"] == "NO_EVALUADO"


@pytest.mark.parametrize(
    "measured", [date(2026, 10, 17), date(2026, 10, 31), date(2026, 11, 16), date(2026, 11, 17)]
)
def test_fifth_birthday_transition_has_bmi_age_and_height_without_extrapolation(measured):
    result = calculate_nutritional_indicators(
        birth_date=date(2021, 10, 17),
        measured_on=measured,
        sex_code="M",
        weight_kg=Decimal(18),
        height_cm=Decimal(110),
    )
    assert result.grupo_referencia == "ESCOLAR"
    assert result.estado == "CALCULADO"
    assert result.pe is result.pt is None
    assert result.imc_edad is not None and result.te is not None
    assert result.version_calculo == "MINSA-2026.1"
    assert ("60 meses" in result.referencia) == (measured < date(2026, 11, 17))


def test_maternal_current_weight_does_not_trigger_general_nutrition_risk():
    assert (
        assessment(
            normal_child(grupo_referencia="PUERPERA", diagnostico_imc="Sobrepeso"), age_months=360
        )["sugerencias"]
        == []
    )


@pytest.mark.parametrize("group", ["GESTANTES", "PUERPERAS"])
@pytest.mark.parametrize("preweight,expected", [(40, "Bajo peso"), (90, "Obesidad")])
def test_general_adult_grades_do_not_change_maternal_classification(group, preweight, expected):
    result = calculate_nutritional_indicators(
        birth_date=date(1991, 1, 1),
        measured_on=date(2026, 10, 17),
        sex_code="F",
        weight_kg=Decimal(65),
        height_cm=Decimal(160),
        care_group=group,
        pregestational_weight_kg=Decimal(preweight),
    )
    assert result.diagnostico_imc == expected
