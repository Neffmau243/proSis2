"""Add group-specific capture and immutable encounter context.

No historical values are recalculated or assigned a default clinical meaning.
Old export states remain NULL because download/receipt evidence is unavailable.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261008_0029_nutrition_fields"
down_revision = "20261007_0028_delivery_date"
branch_labels = None
depends_on = None


def nutrition_columns():
    return [
        sa.Column("hemoglobina_corregida", mysql.DECIMAL(5, 2), nullable=True),
        sa.Column("metodo_correccion_hb", sa.String(200), nullable=True),
        sa.Column("hematocrito", mysql.DECIMAL(5, 2), nullable=True),
        sa.Column("altitud_msnm", mysql.DECIMAL(8, 2), nullable=True),
        sa.Column("estado_ganancia_peso", sa.String(100), nullable=True),
        sa.Column("juntos", sa.Boolean, nullable=True),
        sa.Column("pin", sa.Boolean, nullable=True),
        sa.Column("crecer", sa.Boolean, nullable=True),
        sa.Column("pending_legacy", sa.Boolean, nullable=True),
        sa.Column("nro_controles_cred", mysql.SMALLINT(unsigned=True), nullable=True),
        sa.Column("nro_sachets", mysql.SMALLINT(unsigned=True), nullable=True),
        sa.Column("nro_consejerias", mysql.SMALLINT(unsigned=True), nullable=True),
        sa.Column("nro_sesiones", mysql.SMALLINT(unsigned=True), nullable=True),
        sa.Column("nro_visitas", mysql.SMALLINT(unsigned=True), nullable=True),
        sa.Column("institucion_educativa", sa.String(200), nullable=True),
        sa.Column("nivel_educativo", sa.String(100), nullable=True),
        sa.Column("grado", sa.String(100), nullable=True),
        sa.Column("turno", sa.String(100), nullable=True),
        sa.Column("codigo_matricula", sa.String(100), nullable=True),
        sa.Column("seccion", sa.String(100), nullable=True),
        sa.Column("aula", sa.String(100), nullable=True),
        sa.Column("p65", mysql.INTEGER, nullable=True),
        sa.Column("vl", mysql.INTEGER, nullable=True),
        sa.Column("cp", mysql.INTEGER, nullable=True),
        sa.Column("flag_legacy", mysql.INTEGER, nullable=True),
        sa.Column("estado_exportacion", sa.String(20), nullable=True),
        sa.Column("exportado_at", sa.DateTime, nullable=True),
        sa.Column("enviado_at", sa.DateTime, nullable=True),
        sa.Column("constancia_envio", sa.String(200), nullable=True),
    ]


def upgrade() -> None:
    op.add_column("pacientes", sa.Column("sufijo_documento", sa.String(10), nullable=True))
    op.add_column("atenciones", sa.Column("contexto_clinico", mysql.JSON(), nullable=True))
    for column in nutrition_columns():
        op.add_column("evaluaciones_nutricionales", column)


def downgrade() -> None:
    for column in reversed(nutrition_columns()):
        op.drop_column("evaluaciones_nutricionales", column.name)
    op.drop_column("atenciones", "contexto_clinico")
    op.drop_column("pacientes", "sufijo_documento")
