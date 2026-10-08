"""Keep the preview consistent with the encounter's measurement validation."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.exceptions import BusinessRuleError
from app.schemas.attention import NutritionalIndicatorsPreviewInput
from app.services.attention import AttentionService


def preview_service():
    service = AttentionService(SimpleNamespace())
    service._ensure_patient_in_scope = lambda *args, **kwargs: None
    service._patients = SimpleNamespace(
        get_by_id=lambda _: SimpleNamespace(fecha_nacimiento=date(1994, 10, 3), sexo_codigo="F")
    )
    return service


@pytest.mark.parametrize("changes", [{"peso_kg": 501}, {"talla_cm": 301}, {"peso_kg": ".01"}, {"talla_cm": 9}])
def test_preview_rejects_measurements_outside_the_saving_protocol(changes):
    values = dict(paciente_id=1, fecha_atencion=datetime(2026, 10, 3), peso_kg=80, talla_cm=180)
    values.update(changes)
    with pytest.raises(BusinessRuleError) as error:
        preview_service().preview_nutritional_indicators(
            NutritionalIndicatorsPreviewInput(**values), actor_id=1
        )
    assert error.value.code == "SIGNOS_VITALES_INVALIDOS"


def test_preview_keeps_valid_adult_bmi_and_classification():
    result = preview_service().preview_nutritional_indicators(
        NutritionalIndicatorsPreviewInput(
            paciente_id=1, fecha_atencion=datetime(2026, 10, 3), peso_kg=80, talla_cm=180
        ), actor_id=1,
    )
    assert result.imc == Decimal("24.691")
    assert result.diagnostico_imc == "Normal"


@pytest.mark.parametrize("group", ["NINOS_ADOLESCENTES_ADULTOS_MAYORES", "PUERPERAS", "GESTANTES"])
def test_preview_pregestational_weight_requires_a_maternal_group(group):
    payload = dict(paciente_id=1, fecha_atencion=datetime(2026, 10, 3),
                   grupo_atencion_codigo=group, peso_antes_embarazo_kg=60)
    if group == "NINOS_ADOLESCENTES_ADULTOS_MAYORES":
        with pytest.raises(ValidationError, match="GESTANTES y PUERPERAS"):
            NutritionalIndicatorsPreviewInput(**payload)
    else:
        assert NutritionalIndicatorsPreviewInput(**payload).peso_antes_embarazo_kg == 60
