"""Generate static source catalog metadata, never patient data."""
import json
import pprint
from pathlib import Path

root = Path('etlSis/private/ace-source')
manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
tables = {table['name']: table for table in manifest['tables']}
def rows(name):
    return [json.loads(line) for line in (root / tables[name]['file']).read_text('utf-8').splitlines()]
keys = {}
for district in rows('Provincia'):
    ubigeo = ''.join(str(district[key]).zfill(2) for key in ('IdDpto', 'IdProvincia', 'IdDistrito'))
    for row in rows(f"Z_{int(district['Codigo']):02d}"):
        key = str(row.get('Clave') or '').strip()
        if key.isascii() and key.isdigit() and len(key) == 8:
            keys[ubigeo, str(row['Codigo']).zfill(4)] = key
target = Path('migrations/versions/20261014_0036_locality_keys.py')
assert not target.exists()
prefix = '''"""Separate the internal Z_* Codigo from its legacy export Clave.

Revision 0018 called the sequential lookup key codigo_sis. The source Clave
is a different, nullable/repeated value: all 88 Z_01 rows use 00000001.
Keep IDs and patient links; historical JSON is deliberately not rewritten.
The copied keys are legacy source data, not proof of current SIS homologation.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261014_0036_locality_keys"
down_revision = "20261013_0035_site_district"
branch_labels = None
depends_on = None

'''
suffix = '''

def upgrade() -> None:
    op.alter_column("localidades", "codigo_sis", new_column_name="codigo_catalogo",
                    existing_type=sa.String(10), existing_nullable=False)
    # MySQL updates the existing unique index to reference the renamed column.
    op.add_column("localidades", sa.Column("codigo_sis", sa.String(10), nullable=True))
    table = sa.table("localidades", sa.column("ubigeo_codigo", sa.String),
                     sa.column("codigo_catalogo", sa.String), sa.column("codigo_sis", sa.String))
    for (district, catalog_code), source_key in SOURCE_KEYS.items():
        op.get_bind().execute(table.update().where(
            table.c.ubigeo_codigo == district, table.c.codigo_catalogo == catalog_code,
        ).values(codigo_sis=source_key))


def downgrade() -> None:
    op.drop_column("localidades", "codigo_sis")
    op.alter_column("localidades", "codigo_catalogo", new_column_name="codigo_sis",
                    existing_type=sa.String(10), existing_nullable=False)
'''
target.write_text(prefix + 'SOURCE_KEYS = ' + pprint.pformat(keys, width=95, sort_dicts=True) + suffix,
                  encoding='utf-8')
print(f'Generated {len(keys)} explicit source keys.')
