"""Persist the SIS DIRESA code owned by each official establishment.

Revision ID: 20261006_0027_establishment_disa
Revises: 20261005_0026_fua_components
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261006_0027_establishment_disa"
down_revision = "20261005_0026_fua_components"
branch_labels = None
depends_on = None


# Las seis sedes promovidas desde EESS pertenecen a DIRESA Arequipa.
AREQUIPA_RENAES = ("1291", "1300", "1302", "1301", "1303", "1304")


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("establecimientos")}
    if "disa_codigo" not in columns:
        op.add_column(
            "establecimientos",
            sa.Column("disa_codigo", sa.String(length=3), nullable=True),
        )
    establishments = sa.table(
        "establecimientos",
        sa.column("codigo_renaes", sa.String),
        sa.column("disa_codigo", sa.String),
    )
    bind.execute(
        sa.update(establishments)
        .where(establishments.c.codigo_renaes.in_(AREQUIPA_RENAES))
        .values(disa_codigo="040")
    )


def downgrade() -> None:
    op.drop_column("establecimientos", "disa_codigo")
