"""Add confirmed nutrition follow-up, preserving ETLSIS and saved assessments."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261017_0037_nutrition_followup"
down_revision = "20261014_0036_locality_keys"
branch_labels = None
depends_on = None

GROUPS = (
    ("NUT_HALLAZGO", "Seguimiento de hallazgo nutricional"),
    ("NUT_CRECIMIENTO", "Revisión de la evolución del crecimiento"),
    ("NUT_RIESGO_EVALUADO", "Riesgo nutricional evaluado por el profesional"),
)


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("paciente_grupos_riesgo")}
    for column in (
        sa.Column("atencion_origen_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("evaluacion_origen", sa.JSON(), nullable=True),
        sa.Column("confirmado_por_usuario_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("fecha_proximo_control", sa.Date(), nullable=True),
        sa.Column("motivo_cierre", sa.String(500), nullable=True),
    ):
        if column.name not in columns:
            op.add_column("paciente_grupos_riesgo", column)
    fks = {
        fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys("paciente_grupos_riesgo")
    }
    for name, column, target in (
        ("fk_riesgo_atencion", "atencion_origen_id", "atenciones"),
        ("fk_riesgo_confirmador", "confirmado_por_usuario_id", "usuarios"),
    ):
        if name not in fks:
            op.create_foreign_key(name, "paciente_grupos_riesgo", target, [column], ["id"])
    for code, name in GROUPS:
        op.get_bind().execute(
            sa.text(
                "INSERT INTO grupos_riesgo (codigo, nombre, descripcion, activo) "
                "SELECT :code, :name, :description, TRUE WHERE NOT EXISTS "
                "(SELECT 1 FROM grupos_riesgo WHERE codigo=:code)"
            ),
            {
                "code": code,
                "name": name,
                "description": (
                    "Categoría local de seguimiento nutricional. Requiere evaluación "
                    "y confirmación profesional; no equivale a diagnóstico CIE-10 "
                    "ni grupo HVB."
                ),
            },
        )


def downgrade():
    # Retain catalog rows and risk periods; downgrade removes the new metadata.
    for fk in ("fk_riesgo_atencion", "fk_riesgo_confirmador"):
        op.drop_constraint(fk, "paciente_grupos_riesgo", type_="foreignkey")
    for column in (
        "motivo_cierre",
        "fecha_proximo_control",
        "confirmado_por_usuario_id",
        "evaluacion_origen",
        "atencion_origen_id",
    ):
        op.drop_column("paciente_grupos_riesgo", column)
