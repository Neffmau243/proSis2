"""Políticas clínicas inyectables para validación de signos vitales."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class VitalSignPayload:
    peso_kg: Decimal | None = None
    talla_cm: Decimal | None = None
    perimetro_abdominal_cm: Decimal | None = None
    presion_sistolica: int | None = None
    presion_diastolica: int | None = None
    temperatura_c: Decimal | None = None


class ClinicalProtocolValidator(Protocol):
    """Puerto para una norma clínica versionable por la IPRESS."""

    def validate(self, values: VitalSignPayload, *, age_in_months: int) -> None: ...


@dataclass(frozen=True, slots=True)
class Range:
    minimum: Decimal
    maximum: Decimal

    def contains(self, value: Decimal) -> bool:
        return self.minimum <= value <= self.maximum


@dataclass(frozen=True, slots=True)
class ConfigurableClinicalProtocol:
    """Implementación base cuyos límites se inyectan desde configuración.

    Los límites no están embebidos como reglas normativas: cada ambiente puede
    proporcionar la política aprobada por la IPRESS sin cambiar el servicio de
    atención. Los valores predeterminados son conservadores y solo actúan como
    salvaguarda técnica hasta configurar un protocolo oficial.
    """

    weight: Range = Range(Decimal("0.10"), Decimal("500.00"))
    height: Range = Range(Decimal("10.00"), Decimal("300.00"))
    waist: Range = Range(Decimal("1.00"), Decimal("300.00"))
    temperature: Range = Range(Decimal("25.0"), Decimal("45.0"))
    systolic: Range = Range(Decimal("30"), Decimal("300"))
    diastolic: Range = Range(Decimal("20"), Decimal("200"))

    def validate(self, values: VitalSignPayload, *, age_in_months: int) -> None:
        self._validate_decimal("peso_kg", values.peso_kg, self.weight)
        self._validate_decimal("talla_cm", values.talla_cm, self.height)
        self._validate_decimal("perimetro_abdominal_cm", values.perimetro_abdominal_cm, self.waist)
        self._validate_decimal("temperatura_c", values.temperatura_c, self.temperature)
        self._validate_decimal(
            "presion_sistolica",
            Decimal(values.presion_sistolica) if values.presion_sistolica is not None else None,
            self.systolic,
        )
        self._validate_decimal(
            "presion_diastolica",
            Decimal(values.presion_diastolica) if values.presion_diastolica is not None else None,
            self.diastolic,
        )
        if (
            values.presion_sistolica is not None
            and values.presion_diastolica is not None
            and values.presion_sistolica <= values.presion_diastolica
        ):
            raise ValueError("La presión sistólica debe ser mayor que la diastólica")

    @staticmethod
    def _validate_decimal(name: str, value: Decimal | None, accepted: Range) -> None:
        if value is not None and not accepted.contains(value):
            raise ValueError(
                f"{name} debe estar entre {accepted.minimum} y {accepted.maximum} según el protocolo activo"
            )
