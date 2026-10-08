"""Normalización de Historia_Familiar en el ETL (colores/ID del catálogo EESS_HF)."""

import pytest

from etlSis.historia_familiar import (
    CENTINELA,
    COLOR_SIN_NUMERO,
    HF_CATALOGO,
    NORMALIZADO,
    PREFIJO_FUERA_CATALOGO,
    SIN_PREFIJO,
    TEXTO_LIBRE,
    VACIO,
    parse_historia_familiar,
)


@pytest.mark.parametrize(
    "value,abreviatura,numero,estado,problemas",
    [
        ("NE-62340", "NE", "62340", NORMALIZADO, ()),
        (" NEGRO - 62340 ", "NE", "62340", NORMALIZADO, ()),
        ("VC-0041", "VC", "0041", NORMALIZADO, ()),
        ("verde claro-41", "VC", "41", NORMALIZADO, ()),
        ("VERDE OSCURO 1-99", "V1", "99", NORMALIZADO, ()),
        ("CAFÉ-0007", "CA", "0007", NORMALIZADO, ()),
        # El punto decimal del origen se conserva: el número es un identificador.
        ("NE-62340.74745", "NE", "62340.74745", NORMALIZADO, ("numero_no_entero",)),
        ("-", None, None, CENTINELA, ()),
        (None, None, None, VACIO, ()),
        ("   ", None, None, VACIO, ()),
        ("CAFÉ", "CA", None, COLOR_SIN_NUMERO, ()),
        ("NE", "NE", None, COLOR_SIN_NUMERO, ()),
        ("NE-", "NE", None, COLOR_SIN_NUMERO, ()),
        ("S7-15108", None, None, PREFIJO_FUERA_CATALOGO, (PREFIJO_FUERA_CATALOGO,)),
        ("S1 - CAFÉ", None, None, PREFIJO_FUERA_CATALOGO, (PREFIJO_FUERA_CATALOGO,)),
        ("-15108", None, "15108", SIN_PREFIJO, (SIN_PREFIJO,)),
        ("sin dato", None, None, TEXTO_LIBRE, (TEXTO_LIBRE,)),
    ],
)
def test_parse_historia_familiar(value, abreviatura, numero, estado, problemas):
    resultado = parse_historia_familiar(value)

    assert resultado.abreviatura == abreviatura
    assert resultado.numero == numero
    assert resultado.estado == estado
    assert resultado.problemas == problemas


def test_el_catalogo_por_defecto_reproduce_las_21_filas_de_eess_hf():
    assert len(HF_CATALOGO) == 21
    assert len({abrev for _, _, abrev in HF_CATALOGO}) == 21
    assert parse_historia_familiar("V1-100").abreviatura == "V1"
    assert parse_historia_familiar("OTROS-1").abreviatura == "OT"


def test_el_etl_puede_restringir_las_abreviaturas_al_catalogo_del_origen():
    # Con un catálogo reducido, lo que no existe se marca en vez de inventarse.
    assert parse_historia_familiar("XX-1", {"XX"}).estado == NORMALIZADO
    assert parse_historia_familiar("NE-1", {"XX"}).estado == PREFIJO_FUERA_CATALOGO
    # Un catálogo vacío vuelve al catálogo conocido.
    assert parse_historia_familiar("NE-1", set()).estado == NORMALIZADO
