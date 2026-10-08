from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.growth_reference import lms_z, score, tables
from app.domain.nutrition import calculate_nutritional_indicators, classify_bmi, classify_bmi_age


@pytest.mark.parametrize(
    "value,power,m,s,expected",
    [
        (30, -1.7862, 16.9392, 0.11070, 3.35),
        (14, -1.3529, 20.4951, 0.12579, -3.80),
        (19, -1.6318, 16.0490, 0.10038, 1.47),
    ],
)
def test_official_who_worked_examples(value, power, m, s, expected):
    assert lms_z(value, power, m, s) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("kind,upper", [("bmi", 228), ("height", 228), ("weight", 120)])
@pytest.mark.parametrize("sex", ["M", "F"])
def test_all_official_monthly_medians_and_limits(kind, upper, sex):
    for month in range(61, upper + 1):
        median = tables()[f"{kind}_{sex}"][str(month)][1]
        assert score(kind, sex, month, median) == pytest.approx(0, abs=1e-10)
    assert score(kind, sex, 60.999, 20) is None
    assert score(kind, sex, upper + 0.001, 20) is None


def test_interpolates_lms_for_fractional_month():
    first, second = tables()["bmi_F"]["80"], tables()["bmi_F"]["81"]
    median = (first[1] + second[1]) / 2
    assert score("bmi", "F", 80.5, median) == pytest.approx(0)


@pytest.mark.parametrize(
    "age_days,expected",
    [
        (1826, "INFANTIL"),
        (1827, "ESCOLAR"),
        (1857, "ESCOLAR"),
        (6940, "ADULTO"),
        (24000, "ADULTO_MAYOR"),
    ],
)
def test_age_routing(age_days, expected):
    birth = date(1950, 1, 1)
    result = calculate_nutritional_indicators(
        birth_date=birth,
        measured_on=birth + timedelta(days=age_days),
        sex_code="F",
        weight_kg=Decimal(20),
        height_cm=Decimal(115),
    )
    assert result.grupo_referencia == expected


def test_puerperal_follow_up_keeps_the_current_bmi_without_auto_classification():
    """Sin peso previo declarado, el puerperio se limita al seguimiento del IMC."""

    result = calculate_nutritional_indicators(
        birth_date=date(1990, 1, 1),
        measured_on=date(2026, 1, 1),
        sex_code="F",
        weight_kg=Decimal(90),
        height_cm=Decimal(160),
        care_group="PUERPERAS",
    )

    assert result.grupo_referencia == "PUERPERA"
    assert result.imc == Decimal("35.156")
    assert result.imc_pregestacional is None
    assert result.ganancia_peso_kg is None
    assert result.diagnostico_imc is None


@pytest.mark.parametrize("group", ["GESTANTES", "PUERPERAS"])
def test_maternal_groups_never_use_current_weight_for_general_bmi_classification(group):
    result = calculate_nutritional_indicators(
        birth_date=date(1990, 1, 1),
        measured_on=date(2026, 1, 1),
        sex_code="F",
        weight_kg=Decimal(90),
        height_cm=Decimal(160),
        care_group=group,
        pregestational_weight_kg=Decimal(60),
    )
    assert result.imc == Decimal("35.156")
    assert result.pt is None
    # Ambos grupos maternos clasifican con el peso previo, nunca con el actual.
    assert result.imc_pregestacional == Decimal("23.438")
    assert result.diagnostico_imc == "Normal"
    assert result.ganancia_peso_kg == 30


@pytest.mark.parametrize(
    "bmi,older,expected",
    [
        ("18.499", False, "Bajo peso"),
        ("18.5", False, "Normal"),
        ("25", False, "Sobrepeso"),
        ("30", False, "Obesidad"),
        ("23", True, "Delgadez"),
        ("23.001", True, "Normal"),
        ("28", True, "Sobrepeso"),
        ("32", True, "Obesidad"),
    ],
)
def test_adult_cutoffs(bmi, older, expected):
    assert classify_bmi(Decimal(bmi), older=older) == expected


@pytest.mark.parametrize(
    "z,expected",
    [
        ("-3.01", "Delgadez severa"),
        ("-3", "Delgadez"),
        ("-2", "Normal"),
        ("1", "Normal"),
        ("1.01", "Sobrepeso"),
        ("2", "Sobrepeso"),
        ("2.01", "Obesidad"),
    ],
)
def test_school_bmi_cutoffs(z, expected):
    assert classify_bmi_age(Decimal(z)) == expected
