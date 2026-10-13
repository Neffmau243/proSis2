"""Preserve referral identifiers recorded when receiving a laboratory encounter.

These are external intake identifiers, not newly issued referral documents.
Existing encounters are preserved with NULL values.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261012_0032_lab_references"
down_revision = "20261010_0031_family_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("atenciones")}
    for name in ("numero_referencia_ingreso", "numero_contrarreferencia_ingreso"):
        if name not in existing:
            op.add_column("atenciones", sa.Column(name, sa.String(50), nullable=True))


def downgrade() -> None:
    for name in ("numero_contrarreferencia_ingreso", "numero_referencia_ingreso"):
        op.drop_column("atenciones", name)
