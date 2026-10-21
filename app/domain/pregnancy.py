"""Gestational dating for a specific encounter, never for the day of reprint."""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True, slots=True)
class GestationalAge:
    weeks: int
    days: int | None
    source: Literal["VALORACION", "FPP"]


def gestational_age(
    attended_on: date, due_on: date | None, assessed_weeks: int | None = None
) -> GestationalAge | None:
    # A professional's recorded assessment takes precedence over a date estimate.
    # Match the existing nutrition capture contract; never invent residual days.
    if assessed_weeks is not None:
        if type(assessed_weeks) is int and 0 <= assessed_weeks <= 45:
            return GestationalAge(assessed_weeks, None, "VALORACION")
        return None
    if due_on is None:
        return None
    elapsed = 280 - (due_on - attended_on).days
    if not 0 <= elapsed < 46 * 7:
        return None
    weeks, days = divmod(elapsed, 7)
    return GestationalAge(weeks, days, "FPP")
