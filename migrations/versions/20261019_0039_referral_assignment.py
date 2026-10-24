"""Allow a referral origin to replace the office/professional assignment."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261019_0039_referral_assign"
down_revision = "20261019_0038_referral_mode"
branch_labels = None
depends_on = None

# MariaDB refuses MODIFY COLUMN while either an outgoing or an incoming FK
# uses the column (1832/1833). Keep the certificate's professional/encounter
# invariant after changing nullability. MariaDB additionally rejects CASCADE
# from a nullable parent column to a NOT NULL child: use RESTRICT there so an
# issued certificate can never lose or silently change its signer.
ASSIGNMENT_FOREIGN_KEYS = (
    (
        "fk_certificados_atencion_profesional",
        "certificados",
        "atenciones",
        ["atencion_id", "profesional_id"],
        ["id", "profesional_id"],
    ),
    ("fk_atenciones_profesional", "atenciones", "profesionales", ["profesional_id"], ["id"]),
    ("fk_atenciones_consultorio", "atenciones", "consultorios", ["consultorio_id"], ["id"]),
)


def _assignment_nullable(nullable: bool) -> None:
    def existing(table: str) -> set[str]:
        # Inspect afresh: MySQL/MariaDB DDL commits independently, so a retry
        # must also recover after an interrupted drop/modify/recreate sequence.
        return {fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)}

    for name, source, _target, _columns, _references in ASSIGNMENT_FOREIGN_KEYS:
        if name in existing(source):
            op.drop_constraint(name, source, type_="foreignkey")
    try:
        for column in ("profesional_id", "consultorio_id"):
            op.alter_column(
                "atenciones", column, existing_type=mysql.BIGINT(unsigned=True), nullable=nullable
            )
    finally:
        for name, source, target, columns, references in ASSIGNMENT_FOREIGN_KEYS:
            if name not in existing(source):
                restrict_signer = (
                    nullable
                    and op.get_bind().dialect.is_mariadb
                    and name == "fk_certificados_atencion_profesional"
                )
                op.create_foreign_key(
                    name,
                    source,
                    target,
                    columns,
                    references,
                    ondelete="RESTRICT",
                    onupdate="RESTRICT" if restrict_signer else "CASCADE",
                )


def upgrade() -> None:
    _assignment_nullable(True)


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
    _assignment_nullable(False)
