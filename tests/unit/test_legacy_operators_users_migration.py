"""Contract tests for the legacy SIS operators account migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.models.security import Professional, User


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location(
        "legacy_operators_users_migration",
        Path("migrations/versions/20261005_0025_legacy_operators.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_extends_the_current_head(migration) -> None:
    assert migration.revision == "20261005_0025_legacy_operators"
    assert migration.down_revision == "20261002_0024_nutrition_snapshot"


def test_declared_operators_are_unique_and_fit_the_schema(migration) -> None:
    names = [nombre for nombre, _documento in migration.OPERATORS]
    documents = [documento for _nombre, documento in migration.OPERATORS]

    assert len(migration.OPERATORS) == 9
    assert len(set(names)) == len(names)
    assert len(set(documents)) == len(documents)
    assert all(len(documento) == 8 and documento.isdecimal() for documento in documents)
    assert all(
        len(nombre) <= Professional.__table__.c.nombre_completo.type.length
        for nombre in names
    )


def test_derived_usernames_are_unique_and_within_the_column(migration) -> None:
    usernames = [migration._username_for(nombre) for nombre, _documento in migration.OPERATORS]

    assert len(set(usernames)) == len(usernames)
    assert all(
        len(username) <= User.__table__.c.nombre_usuario.type.length
        for username in usernames
    )
    assert all(username == username.lower() for username in usernames)


def test_username_uses_lowercase_first_two_tokens_without_accents(migration) -> None:
    assert migration._username_for("DEBORA PACCO MOSCOSO") == "debora.pacco"
    assert migration._username_for("SOLEDAD TAPIA CAÑARI") == "soledad.tapia"
    assert migration._username_for("RENATO AGULAR RODRIGUEZ") == "renato.agular"
