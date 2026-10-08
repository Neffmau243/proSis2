"""The locality catalog and the affiliation codes must load deterministically.

``20260924_0018_sis_localities`` turns the source ``Z_01..Z_29`` locality lists
into the ``localidades`` catalog and annotates ``seguros`` with its SIS code.
These tests pin the seed shape and the revision chain without a database.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location(
        "sis_localities_migration",
        Path("migrations/versions/20260924_0018_sis_localities.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_extends_the_insurance_catalog(migration) -> None:
    assert migration.revision == "20260924_0018_sis_localities"
    assert migration.down_revision == "20260923_0017_insurance_plans"


def test_every_district_uses_a_unique_six_digit_ubigeo(migration) -> None:
    codes = [row[0] for row in migration.AREQUIPA_DISTRICTS]

    assert len(codes) == 29
    assert len(set(codes)) == len(codes)
    assert all(len(code) == 6 and code.isdigit() for code in codes)


def test_localities_belong_to_a_known_district_and_are_unique(migration) -> None:
    districts = {row[0] for row in migration.AREQUIPA_DISTRICTS}
    assert set(migration.AREQUIPA_LOCALITIES) <= districts

    total = 0
    for ubigeo, block in migration.AREQUIPA_LOCALITIES.items():
        names = [line.strip() for line in block.strip().splitlines() if line.strip()]
        normalized = [name.casefold() for name in names]
        assert len(set(normalized)) == len(normalized), ubigeo
        total += len(names)
    assert total == 475


def test_affiliation_codes_are_unique_and_known(migration) -> None:
    sis_codes = [code for _codigo, code, _regimen in migration.AFFILIATIONS if code]
    regimens = {regimen for _codigo, _code, regimen in migration.AFFILIATIONS}

    assert len(sis_codes) == len(set(sis_codes))
    assert regimens <= {"SIS", "ESSALUD", "SANIDAD", "PARTICULAR", "NINGUNO", "OTRO"}
    assert dict((codigo, codigo_sis) for codigo, codigo_sis, _ in migration.AFFILIATIONS) == {
        "SIN_SEGURO": "001",
        "SIS_GRATUITO": "002",
        "SIS_AFILIACION_TEMPORAL": "003",
        "SIS_SEMI_SUBSIDIADO": "004",
        "SIS_NRUS": "005",
        "SIS_PARA_TODOS": "006",
        "ESSALUD": "007",
        "SANIDAD": "008",
        "PARTICULAR": "009",
        "SIS": None,
        "OTRO": None,
    }
