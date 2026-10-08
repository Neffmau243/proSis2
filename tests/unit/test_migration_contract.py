from alembic.config import Config
from alembic.script import ScriptDirectory

from app.models import Base

VERSION_NUM_MAX_LENGTH = 32  # alembic_version.version_num es VARCHAR(32).


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
    assert script.get_current_head() == "20261007_0028_delivery_date"


def test_every_revision_fits_the_alembic_version_column() -> None:
    """A revision id longer than the column cannot even be recorded as applied."""

    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = [revision.revision for revision in script.walk_revisions()]

    assert revisions
    assert [revision for revision in revisions if len(revision) > VERSION_NUM_MAX_LENGTH] == []
