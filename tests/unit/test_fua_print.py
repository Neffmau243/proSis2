from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.fua_print import FuaPrintInput, FuaPrintSnapshot
from app.services.fua_print import build_fua_snapshot


def test_snapshot_converts_utc_encounter_time_to_lima_before_selecting_print_date():
    attention, patient, site, professional = fixtures()
    attention.fecha_atencion = datetime(2026, 10, 20, 2, 30, tzinfo=UTC)
    result = build_fua_snapshot(attention, patient, site, professional, None)
    assert result["fecha_atencion"] == "2026-10-19"
    assert result["hora_atencion"] == "21:30:00"


def fixtures():
    attention = SimpleNamespace(
        modalidad_atencion_codigo="AMBULATORIA",
        fecha_atencion=datetime(2026, 9, 19, 9, 30),
        historia_clinica_snapshot="HC-005",
        peso_kg=Decimal("60"),
        talla_cm=Decimal("160"),
        presion_sistolica=120,
        presion_diastolica=80,
        imc=Decimal("23.438"),
        pe=None,
        te=None,
        pt=None,
        valoracion_calculada={
            "grupo_referencia": "GESTANTE",
            "estado": "CALCULADO",
            "diagnostico_imc": "Normal",
            "imc_pregestacional": "21.484",
            "ganancia_peso_kg": "5",
        },
        perimetro_abdominal_cm=Decimal("80"),
        grupo_atencion_codigo="GESTANTES",
        fecha_probable_parto=date(2027, 1, 1),
        fecha_parto=None,
    )
    patient = SimpleNamespace(
        insurance=SimpleNamespace(codigo="SIS", regimen="SIS"),
        tipo_documento_codigo="DNI",
        numero_documento="01234567",
        apellido_paterno="Pérez",
        apellido_materno=None,
        primer_nombre="Ana",
        otros_nombres="María",
        sexo_codigo="F",
        fecha_nacimiento=date(1990, 2, 3),
    )
    site = SimpleNamespace(codigo_renaes="00001234", nombre="IPRESS de prueba")
    professional = SimpleNamespace(
        nombre_completo="Profesional de prueba", numero_documento="76543210", colegiatura="00123"
    )
    return attention, patient, site, professional


def test_snapshot_maps_official_document_code_and_keeps_server_owned_values():
    a, p, s, professional = fixtures()
    p.sis_diresa, p.sis_tipo, p.sis_numero = "001", "2", "01234567"
    p.etnia_codigo = "58"
    result = build_fua_snapshot(
        a,
        p,
        s,
        professional,
        FuaPrintInput(
            personal_atiende="IPRESS",
            lugar_atencion="INTRAMURAL",
            sis_diresa="001",
            sis_tipo="2",
            sis_numero="01234567",
            etnia_codigo="58",
        ),
    )
    assert result["tdi"] == "2"
    assert result["sis_diresa"] == "001"
    assert result["codigo_renipress"] == "00001234"
    assert result["hora_atencion"] == "09:30:00"
    assert result["imc"] == "23.438"
    assert result["grupo_referencia"] == "GESTANTE"
    assert result["estado_nutricional"] == "CALCULADO"
    assert result["imc_pregestacional"] == "21.484"
    assert result["diagnostico_imc"] == "NORMAL"
    assert result["ganancia_peso_kg"] == "5"
    assert result["historia_clinica"] == "HC-005"
    assert result["apellido_materno"] is None
    p.primer_nombre = "Cambio posterior"
    assert result["primer_nombre"] == "ANA"
    assert FuaPrintSnapshot.model_validate(result).version == 2


def test_child_snapshot_keeps_growth_indicators_and_diagnoses():
    a, p, s, professional = fixtures()
    a.grupo_atencion_codigo = "NINOS_ADOLESCENTES_ADULTOS_MAYORES"
    a.pe, a.te, a.pt = "0.125", "-0.250", "0.375"
    a.valoracion_calculada = {
        "grupo_referencia": "INFANTIL",
        "estado": "CALCULADO",
        "diagnostico_peso_edad": "Normal",
        "diagnostico_talla_edad": "Talla baja",
        "diagnostico_peso_talla": "Normal",
    }

    result = build_fua_snapshot(a, p, s, professional, None)

    assert (result["pe"], result["te"], result["pt"]) == ("0.125", "-0.250", "0.375")
    assert result["diagnostico_peso_edad"] == "NORMAL"
    assert result["diagnostico_talla_edad"] == "TALLA BAJA"
    assert result["diagnostico_peso_talla"] == "NORMAL"


def test_puerperal_snapshot_carries_the_real_delivery_date_not_the_due_date():
    """El recuadro de parto del formato sirve a ambos grupos sin confundir fechas."""

    a, p, s, professional = fixtures()
    a.grupo_atencion_codigo = "PUERPERAS"
    a.fecha_probable_parto = None
    a.fecha_parto = date(2026, 9, 20)

    result = build_fua_snapshot(a, p, s, professional, None)

    assert result["grupo_atencion_codigo"] == "PUERPERAS"
    assert result["fecha_parto"] == "2026-09-20"
    assert result["fecha_probable_parto"] is None


def test_missing_values_are_not_invented_and_internal_ids_are_not_renipress():
    a, p, s, professional = fixtures()
    s.codigo_renaes = "código no verificado"
    p.tipo_documento_codigo = "PAS"
    result = build_fua_snapshot(a, p, s, professional, None)
    assert result["codigo_renipress"] is None
    assert result["tdi"] is None
    assert result["sis_numero"] is None
    assert result["etnia_codigo"] is None
    assert result["personal_atiende"] == "IPRESS"
    assert result["lugar_atencion"] == "INTRAMURAL"
    assert result["renipress_preimpreso"] is True
    assert "numero_fua" not in result


def test_numeric_source_renipress_is_normalized_to_the_eight_digit_fua_box():
    a, p, s, professional = fixtures()
    s.codigo_renaes = "0001291"

    assert build_fua_snapshot(a, p, s, professional, None)["codigo_renipress"] == "00001291"


@pytest.mark.parametrize(
    "value",
    [
        {"sis_diresa": "001"},
        {"sis_componente": "RN1"},
        {"personal_atiende": "AISPED"},
        {"codigo_aisped": "A001"},
        {"tipo_atencion": "REFERENCIA"},
        {"referencia_hoja": "0023"},
        {"codigo_renipress": "123"},
        {"etnia_codigo": "MESTIZO"},
        {"imc": 99},
        {"tdi": "2"},
        {"numero_documento": "12345678"},
    ],
)
def test_invalid_or_client_owned_clinical_data_is_rejected(value):
    with pytest.raises(ValidationError):
        FuaPrintInput.model_validate(value)


def test_valid_reference_and_normalization():
    result = FuaPrintInput(
        personal_atiende="aisped",
        codigo_aisped=" a001 ",
        tipo_atencion="REFERENCIA",
        referencia_renipress="00000001",
        referencia_nombre="Origen",
        referencia_hoja="0002",
        sis_diresa="001",
        sis_tipo="e",
        sis_numero="00042",
        etnia_codigo="  ",
    )
    assert result.codigo_aisped == "A001"
    assert result.sis_tipo == "E"
    assert result.etnia_codigo is None


def test_referral_snapshot_retains_origin_for_reprinting():
    a, p, s, professional = fixtures()
    a.modalidad_atencion_codigo = "REFERENCIA"
    supplement = FuaPrintInput(
        tipo_atencion="REFERENCIA",
        referencia_renipress="00001234",
        referencia_nombre=" ipress origen ",
        referencia_hoja=" ref-0001 ",
    )
    result = build_fua_snapshot(a, p, s, professional, supplement)
    assert result["tipo_atencion"] == "REFERENCIA"
    assert result["referencia_renipress"] == "00001234"
    assert result["referencia_nombre"] == "IPRESS ORIGEN"
    assert result["referencia_hoja"] == "REF-0001"
    supplement.referencia_nombre = "CAMBIO POSTERIOR"
    assert result["referencia_nombre"] == "IPRESS ORIGEN"


def test_referral_snapshot_without_an_attending_clinician_keeps_signature_fields_blank():
    a, p, s, _ = fixtures()
    a.modalidad_atencion_codigo = "REFERENCIA"
    supplement = FuaPrintInput(
        tipo_atencion="REFERENCIA",
        referencia_renipress="00001234",
        referencia_nombre="IPRESS ORIGEN",
        referencia_hoja="REF-0001",
    )
    result = build_fua_snapshot(a, p, s, None, supplement)
    assert result["tipo_atencion"] == "REFERENCIA"
    assert result["referencia_hoja"] == "REF-0001"
    assert result["profesional_nombre"] is None
    assert result["profesional_documento"] is None
    assert result["profesional_colegiatura"] is None


def test_patient_site_and_modality_override_old_client_supplements():
    a, p, s, professional = fixtures()
    a.modalidad_atencion_codigo = "EMERGENCIA"
    p.sis_diresa, p.sis_tipo, p.sis_numero = "001", "E1", "000000001"
    p.sis_secuencia, p.etnia_codigo = "01", "2"
    s.fua_personal_atiende, s.fua_lugar_atencion = "ITINERANTE", "EXTRAMURAL"
    result = build_fua_snapshot(
        a,
        p,
        s,
        professional,
        FuaPrintInput(
            personal_atiende="IPRESS",
            lugar_atencion="INTRAMURAL",
            tipo_atencion="AMBULATORIA",
            sis_diresa="999",
            sis_tipo="9",
            sis_numero="99999999",
            etnia_codigo="58",
        ),
    )
    assert result["tipo_atencion"] == "EMERGENCIA"
    assert result["personal_atiende"] == "ITINERANTE"
    assert result["lugar_atencion"] == "EXTRAMURAL"
    assert result["sis_numero"] == "000000001"
    assert result["sis_secuencia"] == "01"
    assert result["sis_componente"] is None
    assert result["etnia_codigo"] == "2"
    p.sis_numero = "11111111"
    assert result["sis_numero"] == "000000001"


def test_sis_affiliation_keeps_diresa_separate_from_tipo_and_numero():
    a, p, s, professional = fixtures()
    # Valores reales del origen: DISA Arequipa 040, régimen subsidiado 2, número de 8 dígitos.
    p.sis_diresa, p.sis_tipo, p.sis_numero = "040", "2", "72769512"
    result = build_fua_snapshot(a, p, s, professional, None)
    # La ficha guarda las tres casillas por separado: el número nunca absorbe la DIRESA.
    assert result["sis_diresa"] == "040"
    assert result["sis_tipo"] == "2"
    assert result["sis_numero"] == "72769512"
    assert "sis_numero_completo" not in result
    assert not result["sis_numero"].startswith(result["sis_diresa"])
    assert FuaPrintSnapshot.model_validate(result).sis_diresa == "040"
    # El número con ceros iniciales se conserva como texto, no se interpreta como entero.
    p.sis_numero = "00067954"
    assert build_fua_snapshot(a, p, s, professional, None)["sis_numero"] == "00067954"
