"""Restore the gap in Z_01 SIS codes, preserving locality IDs and patient links.

The ETL source skips 0051: PORTALES DEL MIRADOR is 0052, VISTA ALEGRE is
0089. Revision 0018 enumerated lines instead and shifted these 38 codes.
Only recognized catalog rows are corrected; historical JSON remains untouched.
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "20261013_0034_locality_codes"
down_revision = "20261013_0033_office_hierarchy"
branch_labels = None
depends_on = None

SOURCE_NAMES = """
PORTALES DEL MIRADOR
PRIMERO DE ENERO
RAMIRO PRIALET
ROCAS DEL MIRADOR A.S.A.
SAN HILARION
SAN ISIDRO EL LABRADOR
SAN JOSE
SAN LAZARO
SAN LUIS
SAN LUIS GONZAGA
SEÑOR DE LAS PIEDADES
SOLIDARIDAD
TRES BALCONES DEL MISTI
VILLA AREQUIPA
VILLA ASUNCION
VILLA CHACHAS
VILLA CONFRATERNIDAD A
VILLA CONFRATERNIDAD B
VILLA CONFRATERNIDAD C
VILLA ECOLOGICA A
VILLA ECOLOGICA B
VILLA ECOLOGICA C
VILLA ECOLOGICA D
VILLA ECOLOGICA E
VILLA EL CONQUISTADOR 1
VILLA EL CONQUISTADOR 2
VILLA EL MIRADOR
VILLA EL SALVADOR
VILLA EL SOL
VILLA FLORIDA
VILLA INDEPENDIENTE
VILLA MAGISTERIAL
VILLA PARAISITO
VILLA SAN PABLO
VILLA UNION
VILLA VITARTE
VIRGEN DE CHAPI
VISTA ALEGRE
""".strip().splitlines()


def normalized_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub('["“”]', "", value)).strip().casefold()


def upgrade() -> None:
    bind = op.get_bind()
    table = sa.table(
        "localidades",
        sa.column("id", sa.BigInteger),
        sa.column("ubigeo_codigo", sa.String),
        sa.column("codigo_sis", sa.String),
        sa.column("nombre", sa.String),
    )
    rows = (
        bind.execute(sa.select(table).where(table.c.ubigeo_codigo == "040102").with_for_update())
        .mappings()
        .all()
    )
    codes = {row["codigo_sis"]: row["id"] for row in rows}
    expected = {
        normalized_name(name): f"{index:04d}" for index, name in enumerate(SOURCE_NAMES, start=52)
    }
    changes = []
    for row in rows:
        target = expected.get(normalized_name(row["nombre"]))
        if target is None or row["codigo_sis"] == target:
            continue
        if row["codigo_sis"] != f"{int(target) - 1:04d}":
            raise RuntimeError(
                "Locality codes differ from the known seed; review before migrating."
            )
        changes.append((row["id"], target))
    changing_ids = {id for id, _target in changes}
    for _id, target in changes:
        if target in codes and codes[target] not in changing_ids:
            raise RuntimeError("A corrected locality code is already owned by another row.")
        temporary = f"R34{target}"
        if temporary in codes:
            raise RuntimeError("Reserved migration code already exists; review before migrating.")
    # Two phases avoid collisions in UNIQUE(ubigeo_codigo, codigo_sis).
    for id, target in changes:
        bind.execute(table.update().where(table.c.id == id).values(codigo_sis=f"R34{target}"))
    for id, target in changes:
        bind.execute(table.update().where(table.c.id == id).values(codigo_sis=target))


def downgrade() -> None:
    # Do not restore known wrong codes or disconnect existing patient records.
    pass
