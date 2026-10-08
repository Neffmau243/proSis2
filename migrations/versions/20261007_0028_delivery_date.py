"""Persist the delivery date declared for a puerperal encounter.

Revision ID: 20261007_0028_delivery_date
Revises: 20261006_0027_establishment_disa
Create Date: 2026-10-07

``fecha_probable_parto`` stays exclusive to GESTANTES; this column records the
real delivery date of a PUERPERAS encounter, so the two clinical meanings are
never conflated.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261007_0028_delivery_date"
down_revision = "20261006_0027_establishment_disa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("atenciones")}
    if "fecha_parto" not in columns:
        op.add_column("atenciones", sa.Column("fecha_parto", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("atenciones", "fecha_parto")
