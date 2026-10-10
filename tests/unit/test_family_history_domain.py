import pytest

from app.domain.family_history import (
    family_history_problem,
    normalize_family_history,
    split_family_history,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" am-0007 ", "AM-0007"),
        ("V1-9", "V1-9"),
        (None, None),
        ("  ", None),
    ],
)
def test_normalize_family_history_preserves_the_numeric_text(value, expected):
    assert normalize_family_history(value) == expected


def test_split_family_history_returns_prefix_and_number():
    assert split_family_history("sj-001") == ("SJ", "001")


@pytest.mark.parametrize("value", ["AM-", "-123", "AM-12A", "AM-" + "1" * 25])
def test_family_history_rejects_incomplete_or_non_numeric_identifiers(value):
    assert family_history_problem(value)
