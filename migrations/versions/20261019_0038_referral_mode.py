"""Enable referral admissions; origin fields live in the saved FUA projection.

atenciones.modalidad_atencion_codigo keeps its catalog FK. The three origin
fields are already supported by atenciones.fua_impresion (JSON), saved in the
same transaction as the attention and retained unchanged for reprints.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0038_referral_mode"
down_revision = "20261017_0037_nutrition_followup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    modes = sa.table(
        "modalidades_atencion",
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("activo", sa.Boolean),
    )
    bind = op.get_bind()
    exists = bind.execute(sa.select(modes.c.codigo).where(modes.c.codigo == "REFERENCIA"))
    if exists.scalar_one_or_none() is None:
        bind.execute(modes.insert().values(codigo="REFERENCIA", nombre="Referencia", activo=True))
    else:
        bind.execute(modes.update().where(modes.c.codigo == "REFERENCIA").values(activo=True))


def downgrade() -> None:
    # Retain the catalog key used by historical encounters and their saved FUA.
    bind = op.get_bind()
    used = bind.execute(
        sa.text("SELECT 1 FROM atenciones WHERE modalidad_atencion_codigo = 'REFERENCIA' LIMIT 1")
    ).scalar_one_or_none()
    if used:
        bind.execute(
            sa.text("UPDATE modalidades_atencion SET activo = FALSE WHERE codigo = 'REFERENCIA'")
        )
    else:
        bind.execute(sa.text("DELETE FROM modalidades_atencion WHERE codigo = 'REFERENCIA'"))
