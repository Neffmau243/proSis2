"""Descriptive nutrition alerts; these never create diagnoses or patient risks."""

from datetime import date
from decimal import Decimal
from typing import Any

from app.domain.nutrition import NutritionalIndicators

LEGACY_RISK_CODES = {"NUT_DELGADEZ", "NUT_DESN_AGUDA", "NUT_DESN_GLOBAL", "NUT_TALLA_BAJA"}
FOLLOWUP_GROUPS = {
    "NUT_HALLAZGO": ("Seguimiento de hallazgo nutricional", "SEGUIMIENTO"),
    "NUT_CRECIMIENTO": ("Revisión de la evolución del crecimiento", "SEGUIMIENTO"),
    "NUT_RIESGO_EVALUADO": ("Riesgo nutricional evaluado por el profesional", "RIESGO"),
}


def group_kind(code: str) -> str:
    return "LEGADO" if code in LEGACY_RISK_CODES else FOLLOWUP_GROUPS.get(code, ("", "RIESGO"))[1]


def assess_followup(
    result: NutritionalIndicators,
    *,
    measured_on: date,
    age_months: int,
    weight: Decimal | None,
    height: Decimal | None,
    previous: Any = None,
) -> dict:
    """Compare actual recorded measurements, without inferring normal growth.

    A plateau is a prompt to review the measurements and clinical context, not
    a diagnosis of malnutrition. Missing history is explicitly unevaluated.
    """
    suggestions = []
    maternal = result.grupo_referencia in {"GESTANTE", "PUERPERA"}
    finding = []
    if result.estado == "CALCULADO" and not maternal:
        for label in result.classifications.values():
            if label and label != "Normal":
                finding.append(label)
        if result.diagnostico_imc and result.diagnostico_imc != "Normal":
            finding.append(result.diagnostico_imc)
    if finding:
        suggestions.append(
            {
                "codigo": "NUT_HALLAZGO",
                "motivo": "; ".join(finding),
                "metodo": "HALLAZGO_ANTROPOMETRICO",
                "requiere_confirmacion": True,
            }
        )
    trend: dict = {
        "estado": "NO_APLICA",
        "mensaje": "Comparación de crecimiento disponible para menores de 5 años.",
    }
    if age_months < 60 and not maternal:
        trend = {
            "estado": "DATOS_INSUFICIENTES",
            "mensaje": (
                "Se requieren mediciones actuales y un control anterior comparable; "
                "no equivale a crecimiento normal."
            ),
        }
        if weight is not None and height is not None and previous is not None:
            prior_date = previous.fecha_atencion.date()
            prior_weight, prior_height = previous.peso_kg, previous.talla_cm
            if prior_date < measured_on and prior_weight is not None and prior_height is not None:
                dw, dh = weight - prior_weight, height - prior_height
                trend = {
                    "estado": "COMPARADO",
                    "atencion_anterior_id": previous.id,
                    "fecha_anterior": prior_date.isoformat(),
                    "dias": (measured_on - prior_date).days,
                    "cambio_peso_kg": str(dw),
                    "cambio_talla_cm": str(dh),
                    "mensaje": (
                        "Comparación descriptiva entre controles. El profesional valora "
                        "la tendencia, la edad, el intervalo "
                        "y la calidad de las mediciones."
                    ),
                }
                reasons = []
                if dw <= 0:
                    reasons.append("Peso sin incremento o con descenso entre controles")
                if dh <= 0:
                    reasons.append(
                        "Talla sin incremento o con descenso: verificar técnica de medición"
                    )
                if reasons:
                    suggestions.append(
                        {
                            "codigo": "NUT_CRECIMIENTO",
                            "motivo": "; ".join(reasons),
                            "metodo": "COMPARACION_CONTROLES",
                            "requiere_confirmacion": True,
                        }
                    )
    return {
        "version": "1",
        "tendencia": trend,
        "sugerencias": suggestions,
        "tamizaje": "NO_EVALUADO",
        "mensaje": (
            "Las alertas no asignan diagnósticos ni riesgos. "
            "Confirme el seguimiento tras la evaluación profesional."
        ),
    }
