"""Rules for locally assigned family-history identifiers."""

from __future__ import annotations

import re

FAMILY_HISTORY_PATTERN = re.compile(r"^(?P<prefix>[A-Z0-9]{2,4})-(?P<number>[0-9]{1,24})$")


def normalize_family_history(value: str | None) -> str | None:
    """Trim and uppercase a submitted code without converting its numeric part."""

    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None


def split_family_history(value: str | None) -> tuple[str, str] | None:
    normalized = normalize_family_history(value)
    if normalized is None:
        return None
    match = FAMILY_HISTORY_PATTERN.fullmatch(normalized)
    if match is None:
        return None
    return match.group("prefix"), match.group("number")


def family_history_problem(value: str | None) -> str | None:
    if normalize_family_history(value) is None:
        return None
    if split_family_history(value) is None:
        return "Seleccione un color o sector e ingrese de 1 a 24 dígitos."
    return None
