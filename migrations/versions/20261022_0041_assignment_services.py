"""Optional service scope for existing office assignments; preserve legacy access."""

import sqlalchemy as sa
from alembic import op

revision = "20261022_0041_assign_services"
down_revision = "20261021_0040_staff_area_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultorio_profesionales",
        sa.Column("servicios_codigos", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consultorio_profesionales", "servicios_codigos")
