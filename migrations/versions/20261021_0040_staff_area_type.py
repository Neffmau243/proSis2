"""Persist the area/qualification distinction instead of inferring custom types."""

import sqlalchemy as sa
from alembic import op

revision = "20261021_0040_staff_area_type"
down_revision = "20261019_0039_referral_assign"
branch_labels = None
depends_on = None

BASE_AREAS = (
    "ESPECIALIDADES:003",
    "ESPECIALIDADES2:001",
    "ESPECIALIDADES2:006",
    "ESPECIALIDADES:006",
    "ESPECIALIDADES:008",
    "ESPECIALIDADES:005",
    "ESPECIALIDADES:002",
    "ESPECIALIDADES:009",
)


def upgrade() -> None:
    op.add_column(
        "especialidades",
        sa.Column("es_area", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    specialties = sa.table(
        "especialidades", sa.column("codigo", sa.String()), sa.column("es_area", sa.Boolean())
    )
    op.execute(
        specialties.update().where(specialties.c.codigo.in_(BASE_AREAS)).values(es_area=True)
    )


def downgrade() -> None:
    op.drop_column("especialidades", "es_area")
