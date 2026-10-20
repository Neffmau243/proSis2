"""Cálculos calendarios usados por los casos de uso clínicos."""

from __future__ import annotations

from dataclasses import dataclass
from calendar import monthrange
from datetime import date, datetime


def as_date(value: date | datetime) -> date:
    """Obtiene la fecha de un valor de fecha u hora sin aproximar edades."""
    return value.date() if isinstance(value, datetime) else value


def completed_months(birth_date: date, reference_date: date | datetime) -> int:
    """Devuelve meses completos entre dos fechas de calendario.

    Es deliberadamente distinto de dividir días entre 30 o 365: el grupo
    etario se asigna según meses efectivamente cumplidos en la fecha de la
    atención.
    """
    reference = as_date(reference_date)
    if reference < birth_date:
        raise ValueError("La fecha de referencia no puede ser anterior al nacimiento")

    months = (reference.year - birth_date.year) * 12 + reference.month - birth_date.month
    if reference.day < birth_date.day:
        months -= 1
    return months


@dataclass(frozen=True, slots=True)
class CalendarAge:
    """Edad expresada como diferencia de calendario, apta para una fotografía clínica."""

    years: int
    months: int
    days: int

    @property
    def display(self) -> str:
        return f"{self.years} años, {self.months} meses y {self.days} días"


def calendar_age(birth_date: date, reference_date: date | datetime) -> CalendarAge:
    """Calcula años, meses y días completos sin usar una conversión aproximada."""
    reference = as_date(reference_date)
    if reference < birth_date:
        raise ValueError("La fecha de referencia no puede ser anterior al nacimiento")

    years = reference.year - birth_date.year
    anniversary = _shift_months(birth_date, years * 12)
    if anniversary > reference:
        years -= 1
        anniversary = _shift_months(birth_date, years * 12)

    months = (reference.year - anniversary.year) * 12 + reference.month - anniversary.month
    month_anniversary = _shift_months(anniversary, months)
    if month_anniversary > reference:
        months -= 1
        month_anniversary = _shift_months(anniversary, months)

    return CalendarAge(years=years, months=months, days=(reference - month_anniversary).days)


def _shift_months(origin: date, months: int) -> date:
    """Suma meses de calendario y trata el 29 de febrero como el último día válido."""
    absolute_month = origin.year * 12 + origin.month - 1 + months
    year, zero_based_month = divmod(absolute_month, 12)
    month = zero_based_month + 1
    return date(year, month, min(origin.day, monthrange(year, month)[1]))
