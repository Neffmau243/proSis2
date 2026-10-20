"""Allow a referral origin to replace the office/professional assignment."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261019_0039_referral_assign"
down_revision = "20261019_0038_referral_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("profesional_id", "consultorio_id"):
        op.alter_column(
            "atenciones", name, existing_type=mysql.BIGINT(unsigned=True), nullable=True
        )


def downgrade() -> None:
    unassigned = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM atenciones "
                "WHERE profesional_id IS NULL OR consultorio_id IS NULL LIMIT 1"
            )
        )
        .scalar_one_or_none()
    )
    if unassigned:
        raise RuntimeError(
            "Existen referencias sin asignación. No se puede restaurar NOT NULL "
            "sin alterar registros históricos."
        )
    for name in ("consultorio_id", "profesional_id"):
        op.alter_column(
            "atenciones", name, existing_type=mysql.BIGINT(unsigned=True), nullable=False
        )
