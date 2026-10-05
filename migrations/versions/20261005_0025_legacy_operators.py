"""Give the legacy SIS operators access as PROFESIONAL users.

Revision ID: 20261005_0025_legacy_operators
Revises: 20261002_0024
Create Date: 2026-10-05

The previous SIS kept its staff in the ``Operarios`` table, with the personal
document number stored in plaintext as the login secret.  Those accounts were
never imported, so this migration recreates, for the operators that do not
already exist in the professional catalog, both a ``profesionales`` row and a
``usuarios`` account linked to it.

Only the PROFESIONAL and ADMIN roles exist in the current security model, and a
PROFESIONAL account must be linked to a real, active professional; therefore the
new profile is mandatory to make these people usable at all.

Login name: lowercase first two name tokens (``DEBORA PACCO MOSCOSO`` ->
``debora.pacco``).  Initial password: the same eight-digit document number they
used in the SIS, which satisfies the numeric credential policy.
"""

from __future__ import annotations

import unicodedata

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20261005_0025_legacy_operators"
down_revision = "20261002_0024_nutrition_snapshot"
branch_labels = None
depends_on = None

#: ``(nombre_completo, numero_documento)`` recovered from ``Operarios``.  The
#: document number doubles as the initial eight-digit password.
OPERATORS = (
    ("DEBORA PACCO MOSCOSO", "24710190"),
    ("SOLEDAD COACALLA CONDORI", "29666064"),
    ("RENATO AGULAR RODRIGUEZ", "29315790"),
    ("RUTH QUISPE SURCO", "40180930"),
    ("INOCENCIO PEREZ NATALIA CRISTINA", "40216289"),
    ("SOLEDAD TAPIA CAÑARI", "46198978"),
    ("PRIETO VALENCIA JUDITH", "42852968"),
    ("RUTH MARY CARDENAS PACO", "29724099"),
    ("KATIA GUTIERREZ PILCO", "42632133"),
)


def _username_for(nombre_completo: str) -> str:
    """Return a stable lowercase login from the first two name tokens."""

    ascii_name = (
        unicodedata.normalize("NFKD", nombre_completo)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    tokens = [token for token in ascii_name.lower().split() if token]
    return ".".join(tokens[:2])


def _tables() -> dict[str, sa.TableClause]:
    return {
        "profesionales": sa.table(
            "profesionales",
            sa.column("id", mysql.BIGINT(unsigned=True)),
            sa.column("codigo_legacy", mysql.BIGINT(unsigned=True)),
            sa.column("numero_documento", sa.String),
            sa.column("nombre_completo", sa.String),
            sa.column("activo", sa.Boolean),
        ),
        "usuarios": sa.table(
            "usuarios",
            sa.column("id", mysql.BIGINT(unsigned=True)),
            sa.column("profesional_id", mysql.BIGINT(unsigned=True)),
            sa.column("nombre_usuario", sa.String),
            sa.column("password_hash", sa.String),
            sa.column("activo", sa.Boolean),
        ),
        "usuario_roles": sa.table(
            "usuario_roles",
            sa.column("usuario_id", mysql.BIGINT(unsigned=True)),
            sa.column("rol_id", mysql.BIGINT(unsigned=True)),
        ),
        "auditoria": sa.table(
            "auditoria",
            sa.column("usuario_id", mysql.BIGINT(unsigned=True)),
            sa.column("tabla_nombre", sa.String),
            sa.column("registro_id", mysql.BIGINT(unsigned=True)),
            sa.column("accion", sa.String),
            sa.column("datos_nuevos", mysql.JSON()),
        ),
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required = {"profesionales", "usuarios", "usuario_roles", "auditoria", "roles"}
    if not required <= set(inspector.get_table_names()):
        return

    role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE codigo = 'PROFESIONAL'")
    ).scalar()
    if role_id is None:
        raise RuntimeError("No existe el rol PROFESIONAL; no se crearon cuentas.")

    # Imported lazily so the module stays importable without the app settings.
    from app.core.security import hash_password

    tables = _tables()
    professionals, users = tables["profesionales"], tables["usuarios"]
    user_roles, audit = tables["usuario_roles"], tables["auditoria"]

    professional_by_document = {
        document: professional_id
        for professional_id, document in bind.execute(
            sa.select(professionals.c.id, professionals.c.numero_documento)
        ).all()
        if document is not None
    }
    existing_usernames = set(bind.execute(sa.select(users.c.nombre_usuario)).scalars())

    for nombre, documento in OPERATORS:
        professional_id = professional_by_document.get(documento)
        if professional_id is None:
            result = bind.execute(
                professionals.insert().values(
                    codigo_legacy=None,
                    numero_documento=documento,
                    nombre_completo=nombre,
                    activo=True,
                )
            )
            professional_id = result.lastrowid
            professional_by_document[documento] = professional_id

        username = _username_for(nombre)
        if username in existing_usernames:
            continue

        result = bind.execute(
            users.insert().values(
                profesional_id=professional_id,
                nombre_usuario=username,
                password_hash=hash_password(documento),
                activo=True,
            )
        )
        user_id = result.lastrowid
        existing_usernames.add(username)
        bind.execute(user_roles.insert().values(usuario_id=user_id, rol_id=role_id))
        bind.execute(
            audit.insert().values(
                usuario_id=None,
                tabla_nombre="usuarios",
                registro_id=user_id,
                accion="BOOTSTRAP",
                datos_nuevos={
                    "id": user_id,
                    "nombre_usuario": username,
                    "roles": ["PROFESIONAL"],
                    "profesional_id": professional_id,
                    "profesional": nombre,
                    "origen": "operarios_sis",
                },
            )
        )


def downgrade() -> None:
    """Remove the imported accounts but keep the professionals they reference.

    As in ``20260926_0021``, a professional row is never deleted on downgrade:
    an attention, a certificate or an office assignment may already reference
    it, and losing it would be worse than leaving an unused catalog entry.
    """

    bind = op.get_bind()
    tables = _tables()
    users, user_roles, audit = (
        tables["usuarios"],
        tables["usuario_roles"],
        tables["auditoria"],
    )
    usernames = tuple(_username_for(nombre) for nombre, _documento in OPERATORS)
    user_ids = [
        row[0]
        for row in bind.execute(
            sa.select(users.c.id).where(users.c.nombre_usuario.in_(usernames))
        ).all()
    ]
    if not user_ids:
        return
    bind.execute(sa.delete(user_roles).where(user_roles.c.usuario_id.in_(user_ids)))
    # Remove both the bootstrap entry (keyed by ``registro_id``) and any audit
    # row the account produced later (keyed by ``usuario_id``), otherwise the
    # FK ``fk_auditoria_usuario`` blocks deleting the user.
    bind.execute(sa.delete(audit).where(audit.c.usuario_id.in_(user_ids)))
    bind.execute(
        sa.delete(audit).where(
            audit.c.tabla_nombre == "usuarios",
            audit.c.registro_id.in_(user_ids),
        )
    )
    bind.execute(sa.delete(users).where(users.c.id.in_(user_ids)))
