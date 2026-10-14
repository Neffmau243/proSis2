"""Pure rules of ``app.scripts.repair_patient_data``.

The command writes development data, so the interesting logic is how it reads
the text a row already carries to decide the district and the locality.  These
tests exercise that decision without touching a database.
"""

from __future__ import annotations

from datetime import date

from app.models.organization import Localidad, Ubigeo
from app.models.patient import Patient
from app.scripts.repair_patient_data import (
    AREQUIPA_DISTRICTS,
    FALLBACK_UBIGEO,
    _condition_for_age,
    _pick_locality,
    _placeholder_phone,
    _resolve_district,
)


def a_district(code: str, name: str) -> Ubigeo:
    return Ubigeo(codigo=code, departamento="AREQUIPA", provincia="AREQUIPA", distrito=name)


def a_locality(code: str, name: str, sis_code: str = "0001") -> Localidad:
    return Localidad(
        ubigeo_codigo=code,
        codigo_catalogo=sis_code,
        nombre=name,
        nombre_norm=name.casefold(),
    )


#: Catálogo mínimo con el error real que motivó la reparación: ``040102``
#: estaba nombrado ``Cayma`` cuando Cayma es ``040103``.
DISTRICTS = {
    "040101": a_district("040101", "AREQUIPA"),
    "040102": a_district("040102", "ALTO SELVA ALEGRE"),
    "040103": a_district("040103", "CAYMA"),
    "040104": a_district("040104", "CERRO COLORADO"),
}


def test_the_official_names_cover_the_arequipa_province() -> None:
    assert set(AREQUIPA_DISTRICTS) == {f"0401{number:02d}" for number in range(1, 30)}
    assert AREQUIPA_DISTRICTS["040102"] == "ALTO SELVA ALEGRE"
    assert AREQUIPA_DISTRICTS["040103"] == "CAYMA"


def test_condition_matches_the_labels_of_the_source_database() -> None:
    today = date(2026, 9, 24)
    assert _condition_for_age(date(2026, 9, 24), today) == "NIÑO"
    assert _condition_for_age(date(2015, 11, 25), today) == "NIÑO"
    # El día del cumpleaños ya cambia de etiqueta.
    assert _condition_for_age(date(2014, 9, 24), today) == "ADOLESCENTE"
    assert _condition_for_age(date(2007, 9, 24), today) == "JOVEN"
    assert _condition_for_age(date(1989, 9, 24), today) == "ADULTO"
    assert _condition_for_age(date(1970, 1, 1), today) == "ADULTO"
    assert _condition_for_age(date(1960, 1, 1), today) == "ADULTO MAYOR"
    # Sin fecha no hay etiqueta que inventar.
    assert _condition_for_age(None, today) is None


def test_placeholder_phone_is_deterministic_and_clearly_fake() -> None:
    assert _placeholder_phone(5) == "900000005"
    assert _placeholder_phone(33) == "900000033"


def test_the_address_wins_over_the_locality_when_both_name_a_district() -> None:
    # Dirección en Cayma con la localidad mal sembrada de Alto Selva Alegre.
    patient = Patient(
        tipo_documento_codigo="DNI",
        numero_documento="99900001",
        ubigeo_residencia_codigo="040102",
        localidad="Alto Selva Alegre",
        direccion="Calle Los Álamos 128, Cayma",
    )
    assert _resolve_district(patient, DISTRICTS).codigo == "040103"


def test_a_text_naming_the_stored_district_confirms_it() -> None:
    # La dirección dice Arequipa (040101): el código guardado se respeta.
    patient = Patient(
        tipo_documento_codigo="DNI",
        numero_documento="99900002",
        ubigeo_residencia_codigo="040101",
        localidad="CERCADO",
        direccion="Av. Ejército 455, Arequipa",
    )
    assert _resolve_district(patient, DISTRICTS).codigo == "040101"


def test_without_text_evidence_the_stored_code_or_the_fallback_is_kept() -> None:
    stored = Patient(
        tipo_documento_codigo="DNI",
        numero_documento="99900003",
        ubigeo_residencia_codigo="040104",
    )
    assert _resolve_district(stored, DISTRICTS).codigo == "040104"

    empty = Patient(tipo_documento_codigo="DNI", numero_documento="99900004")
    assert _resolve_district(empty, DISTRICTS).codigo == FALLBACK_UBIGEO

    # Un código que no existe en el catálogo no puede sobrevivir.
    unknown = Patient(
        tipo_documento_codigo="DNI",
        numero_documento="99900005",
        ubigeo_residencia_codigo="999999",
    )
    assert _resolve_district(unknown, DISTRICTS).codigo == FALLBACK_UBIGEO


def test_locality_prefers_the_exact_name_then_the_district_sector() -> None:
    localities = [
        a_locality("040102", "14 DE AGOSTO", "0001"),
        a_locality("040102", 'ALTO SELVA ALEGRE "A"', "0002"),
        a_locality("040102", "APURIMAC", "0012"),
    ]
    exact = Patient(
        tipo_documento_codigo="DNI", numero_documento="1", localidad="Apurimac"
    )
    assert _pick_locality(exact, localities, DISTRICTS["040102"]).nombre == "APURIMAC"

    # Sin coincidencia exacta se elige el sector que nombra al distrito.
    unnamed = Patient(tipo_documento_codigo="DNI", numero_documento="2", localidad="Otro")
    assert (
        _pick_locality(unnamed, localities, DISTRICTS["040102"]).nombre
        == 'ALTO SELVA ALEGRE "A"'
    )

    # Y como último recurso, el primer código del distrito, que es estable.
    barren = Patient(tipo_documento_codigo="DNI", numero_documento="3")
    assert _pick_locality(barren, localities, DISTRICTS["040103"]).nombre == "14 DE AGOSTO"
