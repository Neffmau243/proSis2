"""Referral admissions require a complete origin tied to the selected mode."""

import pytest
from pydantic import ValidationError

from app.schemas.attention import AttentionCreate

REFERRAL = {
    "tipo_atencion": "REFERENCIA",
    "referencia_renipress": "00001234",
    "referencia_nombre": " ipress origen ",
    "referencia_hoja": " ref-0001 ",
}


def admission(**overrides):
    return AttentionCreate.model_validate(
        {
            "paciente_id": 1,
            "establecimiento_id": 1,
            "profesional_id": 1,
            "consultorio_id": 1,
            "fecha_atencion": "2026-10-18T09:00:00",
            "modalidad_atencion_codigo": "REFERENCIA",
            "fua_datos": REFERRAL,
            **overrides,
        }
    )


def test_referral_mode_accepts_complete_origin_and_preserves_leading_zeroes():
    command = admission()
    assert command.modalidad_atencion_codigo.value == "REFERENCIA"
    assert command.fua_datos.referencia_renipress == "00001234"
    assert command.fua_datos.referencia_nombre == "IPRESS ORIGEN"
    assert command.fua_datos.referencia_hoja == "REF-0001"
    assert command.numero_referencia_ingreso == "REF-0001"


def test_referral_rejects_two_different_incoming_sheet_numbers():
    with pytest.raises(ValidationError, match="debe coincidir"):
        admission(numero_referencia_ingreso="OTRA-HOJA")


def test_referral_accepts_same_external_number_and_preserves_leading_zeroes():
    command = admission(
        numero_referencia_ingreso=" 001565 ",
        fua_datos={**REFERRAL, "referencia_hoja": "001565"},
    )
    assert command.numero_referencia_ingreso == command.fua_datos.referencia_hoja == "001565"


def test_referral_does_not_require_office_specialty_or_attending_professional():
    command = admission(consultorio_id=None, profesional_id=None)
    assert command.consultorio_id is None
    assert command.profesional_id is None
    assert command.especialidad_codigo is None


@pytest.mark.parametrize("mode", ["AMBULATORIA", "EMERGENCIA"])
@pytest.mark.parametrize("field", ["consultorio_id", "profesional_id"])
def test_non_referral_modes_still_require_clinical_assignment(mode, field):
    with pytest.raises(ValidationError, match="consultorio y profesional"):
        admission(modalidad_atencion_codigo=mode, fua_datos=None, **{field: None})


@pytest.mark.parametrize("field", ["consultorio_id", "profesional_id"])
def test_partial_legacy_referral_assignment_is_rejected(field):
    with pytest.raises(ValidationError, match="consultorio y profesional"):
        admission(**{field: None})


@pytest.mark.parametrize("data", [None, {}, {"tipo_atencion": "AMBULATORIA"}])
def test_referral_requires_origin_even_without_a_print_supplement(data):
    with pytest.raises(ValidationError, match="REFERENCIA"):
        admission(fua_datos=data)


@pytest.mark.parametrize("field", ["referencia_renipress", "referencia_nombre", "referencia_hoja"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_all_three_origin_fields_are_required(field, value):
    with pytest.raises(ValidationError):
        admission(fua_datos={**REFERRAL, field: value})


@pytest.mark.parametrize("mode", ["AMBULATORIA", "EMERGENCIA"])
def test_other_modes_do_not_require_origin_and_reject_referral_data(mode):
    assert admission(modalidad_atencion_codigo=mode, fua_datos=None)
    with pytest.raises(ValidationError, match="modalidad REFERENCIA"):
        admission(modalidad_atencion_codigo=mode)


@pytest.mark.parametrize("code", ["123", "123456789", "AB001234"])
def test_renipress_requires_eight_digits(code):
    with pytest.raises(ValidationError):
        admission(fua_datos={**REFERRAL, "referencia_renipress": code})
