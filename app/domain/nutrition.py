"""Authoritative nutritional indicators derived from clinical measurements.

The WHO 2006 tables apply to boys and girls from birth through 60 completed
months. Classifications describe anthropometric findings, not a complete
clinical diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from math import isfinite

from anthro import compute

WHO_2006_REFERENCE = "OMS 2006 (0 a 60 meses)"
_MAX_WHO_AGE_DAYS = 1826
_THREE_DECIMALS = Decimal("0.001")


@dataclass(frozen=True)
class NutritionalIndicators:
    """Calculated values and a display-safe explanation of their availability."""

    imc: Decimal | None
    pe: Decimal | None
    te: Decimal | None
    pt: Decimal | None
    estado: str
    mensaje: str
    referencia: str | None
    grupo_referencia: str = "INFANTIL"
    imc_edad: Decimal | None = None
    diagnostico_imc: str | None = None
    imc_pregestacional: Decimal | None = None
    ganancia_peso_kg: Decimal | None = None

    @property
    def classifications(self) -> dict[str, str | None]:
        # WHO Child Growth Monitoring technical guide, table on page 24:
        # https://www.emro.who.int/images/stories/nutrition/Child-growth-monitoring-a-technical-guide-for-healtcare-professionals.pdf
        return {
            "diagnostico_peso_edad": classify_score(self.pe, "pe"),
            "diagnostico_talla_edad": classify_score(self.te, "te"),
            "diagnostico_peso_talla": classify_score(self.pt, "pt"),
        }


def classify_score(score: Decimal | None, indicator: str) -> str | None:
    """Strict WHO cutoffs: a value exactly on a line is not below/above it."""
    if score is None:
        return None
    if indicator == "pe":
        if score < -3:
            return "Bajo peso severo"
        if score < -2:
            return "Bajo peso"
        return "Evaluar IMC/edad" if score > 1 else "Normal"
    if indicator == "te":
        if score < -3:
            return "Talla baja severa"
        if score < -2:
            return "Talla baja"
        return "Talla alta" if score > 3 else "Normal"
    if indicator != "pt":
        raise ValueError("Indicador desconocido")
    if score < -3:
        return "Emaciación severa"
    if score < -2:
        return "Emaciación"
    if score > 3:
        return "Obesidad"
    if score > 2:
        return "Sobrepeso"
    if score > 1:
        return "Riesgo de sobrepeso"
    return "Normal"


def calculate_nutritional_indicators(
    *,
    birth_date: date,
    sex_code: str | None,
    measured_on: date,
    weight_kg: Decimal | None,
    height_cm: Decimal | None,
    care_group: str = "NINOS_ADOLESCENTES_ADULTOS_MAYORES",
    pregestational_weight_kg: Decimal | None = None,
) -> NutritionalIndicators:
    """Calculate BMI and WHO 2006 WAZ/HAZ/WHZ when the reference applies.

    ``P/E``, ``T/E`` and ``P/T`` are respectively WAZ, HAZ and WHZ.  BMI is
    intentionally still returned for an adult, while the child-only Z scores
    are not extrapolated beyond the WHO reference range.
    """

    imc = _calculate_bmi(weight_kg, height_cm)
    age_days = (measured_on - birth_date).days
    if age_days >= 0 and (age_days > _MAX_WHO_AGE_DAYS or care_group in {"GESTANTES", "PUERPERAS"}):
        return _extended_indicators(
            birth_date,
            measured_on,
            sex_code,
            weight_kg,
            height_cm,
            care_group,
            pregestational_weight_kg,
        )
    if weight_kg is None or height_cm is None:
        return NutritionalIndicators(
            imc=imc,
            pe=None,
            te=None,
            pt=None,
            estado="DATOS_INCOMPLETOS",
            mensaje="Ingrese peso y talla para calcular los indicadores nutricionales.",
            referencia=WHO_2006_REFERENCE,
        )

    age_days = (measured_on - birth_date).days
    if age_days < 0:
        return NutritionalIndicators(
            imc=imc,
            pe=None,
            te=None,
            pt=None,
            estado="FECHA_INVALIDA",
            mensaje="La fecha de medición no puede ser anterior al nacimiento.",
            referencia=None,
        )
    normalized_sex = {"M": "m", "F": "f"}.get((sex_code or "").upper())
    if normalized_sex is None:
        return NutritionalIndicators(
            imc=imc,
            pe=None,
            te=None,
            pt=None,
            estado="SIN_REFERENCIA_SEXO",
            mensaje="La referencia OMS 2006 requiere sexo registrado como femenino o masculino.",
            referencia=WHO_2006_REFERENCE,
        )

    result = compute(
        {
            "sex": normalized_sex,
            "dob": birth_date,
            "measured": measured_on,
            "weight_kg": float(weight_kg),
            "height_cm": float(height_cm),
        }
    )
    scores = (
        _as_decimal(result.get("z_wfa")),
        _as_decimal(result.get("z_lhfa")),
        _as_decimal(result.get("z_wflh")),
    )
    if any(score is None for score in scores) or result.get("errors"):
        return NutritionalIndicators(
            imc=imc,
            pe=None,
            te=None,
            pt=None,
            estado="NO_DISPONIBLE",
            mensaje="No fue posible calcular los indicadores con la referencia OMS 2006.",
            referencia=WHO_2006_REFERENCE,
        )

    pe, te, pt = scores
    return NutritionalIndicators(
        imc=imc,
        pe=pe,
        te=te,
        pt=pt,
        estado="CALCULADO",
        mensaje=(
            "Indicadores calculados con la referencia OMS 2006; valide la interpretación clínica."
        ),
        referencia=WHO_2006_REFERENCE,
    )


def _calculate_bmi(weight_kg: Decimal | None, height_cm: Decimal | None) -> Decimal | None:
    if weight_kg is None or height_cm is None or height_cm <= 0:
        return None
    height_m = height_cm / Decimal("100")
    return (weight_kg / (height_m * height_m)).quantize(_THREE_DECIMALS, ROUND_HALF_UP)


def _as_decimal(value: object) -> Decimal | None:
    if not isinstance(value, (int, float)) or not isfinite(value):
        return None
    return Decimal(str(value)).quantize(_THREE_DECIMALS, ROUND_HALF_UP)


def classify_bmi(value: Decimal | None, *, older: bool = False) -> str | None:
    if value is None:
        return None
    below_normal = value <= 23 if older else value < Decimal("18.5")
    if below_normal:
        return "Delgadez" if older else "Bajo peso"
    if value < (28 if older else 25):
        return "Normal"
    return "Sobrepeso" if value < (32 if older else 30) else "Obesidad"


def classify_bmi_age(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value < -3:
        return "Delgadez severa"
    if value < -2:
        return "Delgadez"
    if value > 2:
        return "Obesidad"
    return "Sobrepeso" if value > 1 else "Normal"


def _extended_indicators(birth, measured, sex, weight, height, care_group, preweight):
    from app.domain.growth_reference import score

    months = (measured - birth).days / 30.4375
    years = measured.year - birth.year - ((measured.month, measured.day) < (birth.month, birth.day))
    bmi = _calculate_bmi(weight, height)
    base = dict(imc=bmi, pe=None, te=None, pt=None, estado="CALCULADO", referencia=None)
    if care_group == "GESTANTES":
        pre_bmi = _calculate_bmi(preweight, height)
        base["referencia"] = "INS/MINSA: IMC pregestacional"
        base["estado"] = "CALCULADO" if pre_bmi is not None else "DATOS_INCOMPLETOS"
        return NutritionalIndicators(
            **base,
            grupo_referencia="GESTANTE",
            imc_pregestacional=pre_bmi,
            ganancia_peso_kg=(
                weight - preweight if weight is not None and preweight is not None else None
            ),
            diagnostico_imc=classify_bmi(pre_bmi) if years >= 20 else None,
            mensaje=(
                "IMC pregestacional y cambio de peso. Interpretar según semana gestacional; "
                "adolescentes requieren valoración específica."
            ),
        )
    if care_group == "PUERPERAS":
        # El peso antes del embarazo sigue siendo la referencia materna válida:
        # el peso actual es de seguimiento del puerperio, no de clasificación.
        pre_bmi = _calculate_bmi(preweight, height)
        base["estado"] = "CALCULADO" if bmi is not None else "DATOS_INCOMPLETOS"
        base["referencia"] = "INS/MINSA: IMC pregestacional (puerperio)"
        return NutritionalIndicators(
            **base,
            grupo_referencia="PUERPERA",
            imc_pregestacional=pre_bmi,
            ganancia_peso_kg=(
                weight - preweight if weight is not None and preweight is not None else None
            ),
            diagnostico_imc=classify_bmi(pre_bmi) if years >= 20 else None,
            mensaje=(
                "IMC pregestacional y cambio de peso. El IMC actual es de seguimiento: "
                "interpretar según tiempo desde el parto y evolución clínica."
            ),
        )
    if months > 228:
        base["referencia"] = (
            "MINSA adulto mayor (60 años a más)" if years >= 60 else "OMS IMC adulto"
        )
        base["estado"] = "CALCULADO" if bmi is not None else "DATOS_INCOMPLETOS"
        return NutritionalIndicators(
            **base,
            grupo_referencia="ADULTO_MAYOR" if years >= 60 else "ADULTO",
            diagnostico_imc=classify_bmi(bmi, older=years >= 60),
            mensaje="Valoración por IMC; interpretar junto con la evaluación clínica."
            if bmi is not None
            else "Ingrese peso y talla para calcular el IMC.",
        )
    base["referencia"] = "OMS 2007 (61 a 228 meses)"
    if months < 61:
        base["estado"] = "SIN_REFERENCIA"
        return NutritionalIndicators(
            **base,
            grupo_referencia="ESCOLAR",
            mensaje=(
                "IMC disponible. Edad entre el final de OMS 2006 instalada y el inicio "
                "de OMS 2007 (61 meses); sin extrapolar puntajes."
            ),
        )
    if sex not in {"M", "F"}:
        base["estado"] = "SIN_REFERENCIA_SEXO"
    elif bmi is None:
        base["estado"] = "DATOS_INCOMPLETOS"
    if base["estado"] != "CALCULADO":
        return NutritionalIndicators(
            **base,
            grupo_referencia="ESCOLAR",
            mensaje="Se requieren peso, talla y sexo femenino o masculino para el cálculo.",
        )
    raw_bmi = float(weight / (height / 100) ** 2)
    baz = _as_decimal(score("bmi", sex, months, raw_bmi))
    base["pe"] = _as_decimal(score("weight", sex, months, float(weight)))
    base["te"] = _as_decimal(score("height", sex, months, float(height)))
    return NutritionalIndicators(
        **base,
        grupo_referencia="ESCOLAR",
        imc_edad=baz,
        diagnostico_imc=classify_bmi_age(baz),
        mensaje="OMS 2007: talla/edad e IMC/edad; peso/edad disponible hasta 120 meses.",
    )
