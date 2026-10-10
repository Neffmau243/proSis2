"""Add the young life stage and split the former adult range.

Revision ID: 20261009_0030_young_age_group
Revises: 20261008_0029_nutrition_fields
Create Date: 2026-10-09

Historical attentions keep their stored group. The migration only changes the
catalog used to classify encounters created from this revision onward.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261009_0030_young_age_group"
down_revision = "20261008_0029_nutrition_fields"
branch_labels = None
depends_on = None

YOUNG_RANGE = (216, 359)
OLD_ADULT_RANGE = (216, 719)
ADULT_RANGE = (360, 719)


def _range(row) -> tuple[int | None, int | None] | None:
    if row is None:
        return None
    return row.edad_minima_meses, row.edad_maxima_meses


def upgrade() -> None:
    connection = op.get_bind()
    rows = {
        row.codigo: row
        for row in connection.execute(
            sa.text(
                "SELECT codigo, edad_minima_meses, edad_maxima_meses "
                "FROM grupos_etarios WHERE codigo IN ('JOVEN', 'ADULTO')"
            )
        ).mappings()
    }
    adult_range = _range(rows.get("ADULTO"))
    young_range = _range(rows.get("JOVEN"))

    if adult_range not in {OLD_ADULT_RANGE, ADULT_RANGE}:
        raise RuntimeError(
            "No se puede crear JOVEN automáticamente porque ADULTO tiene un rango "
            f"personalizado: {adult_range}. Corrija el catálogo antes de migrar."
        )
    if young_range not in {None, YOUNG_RANGE}:
        raise RuntimeError(
            "El grupo JOVEN ya existe con un rango incompatible: "
            f"{young_range}. Corrija el catálogo antes de migrar."
        )

    if adult_range == OLD_ADULT_RANGE:
        connection.execute(
            sa.text("UPDATE grupos_etarios SET edad_minima_meses = 360 WHERE codigo = 'ADULTO'")
        )
    if young_range is None:
        connection.execute(
            sa.text(
                "INSERT INTO grupos_etarios "
                "(codigo, nombre, edad_minima_meses, edad_maxima_meses, activo) "
                "VALUES ('JOVEN', 'Joven', 216, 359, TRUE)"
            )
        )


def downgrade() -> None:
    """Keep the row because historical attentions may already reference JOVEN."""

    # Recombining the ranges would overlap JOVEN, and deleting it could violate
    # the attention foreign key. This clinical data migration is irreversible.
    pass
