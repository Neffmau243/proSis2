from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.age import CalendarAge
from app.exceptions import BusinessRuleError
from app.schemas.attention import AttentionCreate, NutritionalSnapshotInput
from app.schemas.nutrition_record import NutritionRecordResponse
from app.services.attention import AttentionService


def command(record, group="NINOS_ADOLESCENTES_ADULTOS_MAYORES"):
    return AttentionCreate(
        paciente_id=1,
        establecimiento_id=1,
        profesional_id=1,
        consultorio_id=1,
        modalidad_atencion_codigo="AMBULATORIA",
        fecha_atencion=datetime(2026, 10, 1),
        grupo_atencion_codigo=group,
        valoracion_nutricional=record,
    )


@pytest.mark.parametrize(
    "record",
    [
        {"hemoglobina": 0},
        {"hemoglobina": 12},
        {"fecha_hemoglobina": "2026-10-01"},
        {"hemoglobina": 31, "fecha_hemoglobina": "2026-10-01"},
        {"hemoglobina_corregida": 11},
        {"metodo_correccion_hb": "Sin resultado"},
        {"hematocrito": 101},
        {"altitud_msnm": 10000},
        {"nro_sachets": -1},
        {"nro_sachets": 1.5},
        {"edad_gestacional_semanas": 46},
        {"enviado": True},
        {"estado_exportacion": "ENVIADO"},
        {"whz": 0},
        {"waz": 0},
    ],
)
def test_rejects_incomplete_invalid_and_client_owned_results(record):
    with pytest.raises(ValidationError):
        NutritionalSnapshotInput(**record)


def test_unknown_zero_and_false_are_preserved_distinctly():
    value = NutritionalSnapshotInput(nro_sachets=0, juntos=False, pin=None, diagnostico="  ")
    assert value.nro_sachets == 0
    assert value.juntos is False
    assert value.pin is None and value.diagnostico is None
    # Historic sentinel values remain readable, not silently turned into normal results.
    old = NutritionRecordResponse(id=1, hemoglobina=Decimal(0), waz=Decimal(0))
    assert old.hemoglobina == 0 and old.waz == 0


@pytest.mark.parametrize(
    "record,group,age",
    [
        ({"juntos": False}, "NINOS_ADOLESCENTES_ADULTOS_MAYORES", 18),
        ({"p65": 0}, "NINOS_ADOLESCENTES_ADULTOS_MAYORES", 17),
        ({"pending_legacy": False}, "NINOS_ADOLESCENTES_ADULTOS_MAYORES", 3),
        ({"institucion_educativa": "PRUEBA"}, "GESTANTES", 16),
        ({"estado_ganancia_peso": "REGISTRADO"}, "PUERPERAS", 25),
    ],
)
def test_group_and_age_reject_even_false_or_zero_when_inapplicable(record, group, age):
    with pytest.raises(BusinessRuleError, match="no corresponden"):
        AttentionService._validate_nutrition_record(
            command(record, group),
            date(2026 - age, 1, 1),
            CalendarAge(age, 9, 0),
        )


@pytest.mark.parametrize("hb_date", ["2000-01-01", "2026-10-02"])
def test_result_date_must_belong_to_lifetime_and_encounter(hb_date):
    with pytest.raises(BusinessRuleError):
        AttentionService._validate_nutrition_record(
            command({"hemoglobina": 12, "fecha_hemoglobina": hb_date}),
            date(2020, 1, 1),
            CalendarAge(6, 9, 0),
        )


def test_valid_hbc_requires_documented_method_and_altitude():
    record = NutritionalSnapshotInput(
        hemoglobina=14,
        fecha_hemoglobina="2026-10-01",
        hemoglobina_corregida=12,
        metodo_correccion_hb="Resultado documentado por laboratorio",
        altitud_msnm=2500,
    )
    assert record.hemoglobina_corregida == 12
