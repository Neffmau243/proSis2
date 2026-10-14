"""Link the six verified IPRESS to their own district, preserving patient residence.

Official sources, checked on 2026-10-13:
GERESA Arequipa, Horario_Atencion_GERESA.pdf, page 1:
https://pagina.saludarequipa.gob.pe/wp-content/uploads/2024/10/Horario_Atencion_GERESA.pdf
MINSA/PCRIS, table of IPRESS with UBIGEO, pages 41, 43, 44, 91, 122, 149:
https://repositorio.pcris.gob.pe/Archivos/DocumentoExpedienteMPV82401082023170156.pdf

Match numeric RENIPRESS, never an internal ID or a patient's district. Only
missing site districts are completed. Existing configuration/history is retained.
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "20261013_0035_site_district"
down_revision = "20261013_0034_locality_codes"
branch_labels = None
depends_on = None

DISTRICT = "040102"
VERIFIED_RENIPRESS = frozenset(
    {"00001291", "00001300", "00001301", "00001302", "00001303", "00001304"}
)


def normalized_renipress(value: str | None) -> str | None:
    raw = (value or "").strip()
    return raw.zfill(8) if re.fullmatch(r"[0-9]{1,8}", raw) else None


def upgrade() -> None:
    bind = op.get_bind()
    districts = sa.table(
        "ubigeos",
        sa.column("codigo", sa.String),
        sa.column("departamento", sa.String),
        sa.column("provincia", sa.String),
        sa.column("distrito", sa.String),
    )
    district = (
        bind.execute(sa.select(districts).where(districts.c.codigo == DISTRICT))
        .mappings()
        .one_or_none()
    )
    if district is None or tuple(
        district[key].strip().upper() for key in ("departamento", "provincia", "distrito")
    ) != ("AREQUIPA", "AREQUIPA", "ALTO SELVA ALEGRE"):
        raise RuntimeError(
            "Verified district 040102 is missing or inconsistent; review the catalog."
        )
    sites = sa.table(
        "establecimientos",
        sa.column("id", sa.BigInteger),
        sa.column("codigo_renaes", sa.String),
        sa.column("ubigeo_codigo", sa.String),
    )
    rows = (
        bind.execute(sa.select(sites).where(sites.c.ubigeo_codigo.is_(None)).with_for_update())
        .mappings()
        .all()
    )
    for row in rows:
        if normalized_renipress(row["codigo_renaes"]) in VERIFIED_RENIPRESS:
            bind.execute(
                sites.update()
                .where(sites.c.id == row["id"], sites.c.ubigeo_codigo.is_(None))
                .values(ubigeo_codigo=DISTRICT)
            )


def downgrade() -> None:
    # A verified geographic link must not be erased by a schema downgrade.
    pass
