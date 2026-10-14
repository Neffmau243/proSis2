"""Back up only territorial catalogs, then apply their verified correction."""
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.database import engine

with engine.connect() as connection:
    revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
    assert revision in {'20261013_0033_office_hierarchy', '20261013_0034_locality_codes'}
    rows = [dict(row) for row in connection.execute(text('SELECT * FROM localidades ORDER BY id')).mappings()]
    backup = Path('tmp/localidades_before_0034.json')
    if not backup.exists():
        backup.write_text(json.dumps(rows, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
command.upgrade(Config('alembic.ini'), 'head')
print('Catalog migration applied; locality IDs and patient links preserved.')
