from alembic.config import Config
from alembic.script import ScriptDirectory

from app.models import Base


def test_metadata_and_alembic_head_cover_the_bootstrap_schema() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert len(Base.metadata.tables) == 44
    assert {
        "pacientes",
        "atenciones",
        "fua",
        "auditoria",
        "documento_series",
        "limites_inicio_sesion",
    } <= set(
        Base.metadata.tables
    )
    assert script.get_current_head() == "20261005_0025_legacy_operators"
