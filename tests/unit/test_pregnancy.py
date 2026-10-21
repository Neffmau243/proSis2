from datetime import date, timedelta

import pytest

from app.domain.pregnancy import GestationalAge, gestational_age


def test_due_date_counts_completed_weeks_and_days_at_the_encounter():
    assert gestational_age(date(2026, 10, 20), date(2026, 12, 27)) == GestationalAge(30, 2, "FPP")
    assert gestational_age(date(2026, 12, 27), date(2026, 12, 27)) == GestationalAge(40, 0, "FPP")
    assert gestational_age(date(2026, 12, 28), date(2026, 12, 27)) == GestationalAge(40, 1, "FPP")


@pytest.mark.parametrize("days_remaining", [281, -42, 1000])
def test_impossible_dates_leave_age_unknown_instead_of_clamping(days_remaining):
    attended = date(2026, 10, 20)
    assert gestational_age(attended, attended + timedelta(days=days_remaining)) is None


def test_professional_assessment_takes_precedence_without_inventing_days():
    assert gestational_age(date(2026, 10, 20), date(2026, 12, 27), 29) == GestationalAge(
        29, None, "VALORACION"
    )
    assert gestational_age(date(2026, 10, 20), None, 0) == GestationalAge(0, None, "VALORACION")
    assert gestational_age(date(2026, 10, 20), None) is None


@pytest.mark.parametrize("invalid", [-1, 46, True, 30.5])
def test_invalid_assessment_is_not_replaced_by_a_conflicting_estimate(invalid):
    assert gestational_age(date(2026, 10, 20), date(2026, 12, 27), invalid) is None
