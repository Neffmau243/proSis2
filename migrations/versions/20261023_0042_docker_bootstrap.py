"""Import the explicitly configured private installation snapshot for Docker.

Without IPRESS_BOOTSTRAP_FILE this revision does not import installation data.
The data is mounted read-only, never embedded in the migration or Docker image.
"""

from alembic import op

revision = "20261023_0042_docker_bootstrap"
down_revision = "20261022_0041_assign_services"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.scripts.docker_bootstrap import migrate_from_environment

    migrate_from_environment(op.get_bind())


def downgrade() -> None:
    # These records may have acquired clinical history since deployment.
    # Rolling back a revision must never delete patients, accounts or staff.
    pass
