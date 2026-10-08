"""Persist current FUA number components separately from legacy configuration.

Revision ID: 20261005_0026_fua_components
Revises: 20261005_0025_legacy_operators
Create Date: 2026-10-05

El identificador debe entrar en ``alembic_version.version_num`` (VARCHAR(32)).
"""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0026_fua_components"
down_revision = "20261005_0025_legacy_operators"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fua", sa.Column("codigo_renipress", sa.String(length=8), nullable=True))
    op.add_column("fua", sa.Column("lote_fua", sa.String(length=2), nullable=True))
    op.add_column("fua", sa.Column("correlativo_fua", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("fua", "correlativo_fua")
    op.drop_column("fua", "lote_fua")
    op.drop_column("fua", "codigo_renipress")
