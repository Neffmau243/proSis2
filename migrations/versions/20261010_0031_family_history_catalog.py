"""Create and seed the family-history prefix catalog.

Revision ID: 20261010_0031_family_history
Revises: 20261009_0030_young_age_group
Create Date: 2026-10-10

The local numeric identifier remains inside ``pacientes.historia_familiar`` as
text so leading zeroes are preserved. Existing patient values are not changed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.models.base import MYSQL_TABLE_OPTIONS

revision = "20261010_0031_family_history"
down_revision = "20261009_0030_young_age_group"
branch_labels = None
depends_on = None

PREFIXES = (
    ("AM", "AMARILLO", "COLOR", "#F2C94C", 1),
    ("AZ", "AZUL", "COLOR", "#3B82F6", 2),
    ("CA", "CAFÉ", "COLOR", "#8B5E3C", 3),
    ("CE", "CELESTE", "COLOR", "#67C7E3", 4),
    ("LI", "LILA", "COLOR", "#A78BFA", 5),
    ("ME", "MELÓN", "COLOR", "#F4A261", 6),
    ("NA", "NARANJA", "COLOR", "#F97316", 7),
    ("NE", "NEGRO", "COLOR", "#1F2937", 8),
    ("PL", "PLOMO", "COLOR", "#9CA3AF", 9),
    ("RO", "ROJO", "COLOR", "#DC2626", 10),
    ("RS", "ROSADO", "COLOR", "#EC4899", 11),
    ("VC", "VERDE CLARO", "COLOR", "#86C766", 12),
    ("V1", "VERDE OSCURO 1", "COLOR", "#2F855A", 13),
    ("V2", "VERDE OSCURO 2", "COLOR", "#166534", 14),
    ("AP", "APURÍMAC", "SECTOR", None, 15),
    ("HC", "HÉROES DEL CENEPA", "SECTOR", None, 16),
    ("IA", "INDEPENDENCIA - A", "SECTOR", None, 17),
    ("IB", "INDEPENDENCIA - B", "SECTOR", None, 18),
    ("LM", "LEONES DEL MISTO", "SECTOR", None, 19),
    ("SJ", "SAN JUAN BAUTISTA", "SECTOR", None, 20),
    ("OT", "OTROS", "SECTOR", None, 21),
)


def upgrade() -> None:
    bind = op.get_bind()
    # MySQL DDL is not transactional. This guard makes a retry safe if table
    # creation succeeded but the version marker could not be updated.
    if not sa.inspect(bind).has_table("historias_familiares_catalogo"):
        op.create_table(
            "historias_familiares_catalogo",
            sa.Column("codigo", sa.String(length=4), nullable=False),
            sa.Column("nombre", sa.String(length=100), nullable=False),
            sa.Column("tipo", sa.String(length=10), nullable=False),
            sa.Column("color_hex", sa.CHAR(length=7), nullable=True),
            sa.Column("orden", sa.SmallInteger(), nullable=False),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("codigo"),
            sa.UniqueConstraint("orden", name="uq_historias_familiares_catalogo_orden"),
            **MYSQL_TABLE_OPTIONS,
        )
    table = sa.table(
        "historias_familiares_catalogo",
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("tipo", sa.String),
        sa.column("color_hex", sa.String),
        sa.column("orden", sa.SmallInteger),
        sa.column("activo", sa.Boolean),
    )
    existing = set(bind.execute(sa.select(table.c.codigo)).scalars())
    rows = [
        {
            "codigo": codigo,
            "nombre": nombre,
            "tipo": tipo,
            "color_hex": color_hex,
            "orden": orden,
            "activo": True,
        }
        for codigo, nombre, tipo, color_hex, orden in PREFIXES
        if codigo not in existing
    ]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    op.drop_table("historias_familiares_catalogo")
