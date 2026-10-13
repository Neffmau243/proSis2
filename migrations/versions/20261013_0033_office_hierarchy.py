"""Separate care areas and available services from physical office hierarchy.

Additive migration: preserves office ids, assignments and historical encounters.
NULL service lists inherit their parent's/default area catalog; creates no rooms.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261013_0033_office_hierarchy"
down_revision = "20261012_0032_lab_references"
branch_labels = None
depends_on = None

AREAS = (
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
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("consultorios")}
    if "area_codigo" not in columns:
        op.add_column("consultorios", sa.Column("area_codigo", sa.String(20), nullable=True))
        op.create_foreign_key(
            "fk_consultorios_area", "consultorios", "especialidades", ["area_codigo"], ["codigo"]
        )
    if "servicios_codigos" not in columns:
        op.add_column("consultorios", sa.Column("servicios_codigos", sa.JSON(), nullable=True))
    offices = sa.table(
        "consultorios",
        sa.column("area_codigo", sa.String),
        sa.column("especialidad_codigo", sa.String),
    )
    op.get_bind().execute(
        offices.update()
        .where(
            offices.c.area_codigo.is_(None),
            offices.c.especialidad_codigo.in_(AREAS),
        )
        .values(area_codigo=offices.c.especialidad_codigo)
    )


def downgrade() -> None:
    op.drop_column("consultorios", "servicios_codigos")
    op.drop_constraint("fk_consultorios_area", "consultorios", type_="foreignkey")
    op.drop_column("consultorios", "area_codigo")
