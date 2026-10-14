"""Back up territorial metadata; never rewrite patient or encounter records."""
import hashlib
import importlib.util
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.database import engine

def fingerprints(connection):
    queries = {
        'patients': """SELECT id,ubigeo_residencia_codigo,localidad_id,establecimiento_registro_id,
            SHA2(COALESCE(localidad,''),256) FROM pacientes ORDER BY id""",
        'history': """SELECT id,establecimiento_id,consultorio_id,
            SHA2(CAST(contexto_clinico AS CHAR),256),SHA2(CAST(fua_impresion AS CHAR),256)
            FROM atenciones ORDER BY id""",
    }
    return {key: hashlib.sha256(repr([tuple(row) for row in connection.execute(text(sql))])
            .encode('utf-8')).hexdigest() for key, sql in queries.items()}

spec = importlib.util.spec_from_file_location('source_keys',
    Path('migrations/versions/20261014_0036_locality_keys.py'))
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
with engine.connect() as connection:
    revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
    assert revision in {'20261013_0035_site_district', '20261014_0036_locality_keys'}
    before = fingerprints(connection)
    backup = Path('tmp/localidades_before_0036.json')
    if not backup.exists():
        assert revision == '20261013_0035_site_district'
        rows = [dict(row) for row in connection.execute(text('SELECT * FROM localidades ORDER BY id')).mappings()]
        backup.write_text(json.dumps(rows, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
command.upgrade(Config('alembic.ini'), 'head')
with engine.connect() as connection:
    assert fingerprints(connection) == before, 'Patient/history data changed unexpectedly.'
    original = json.loads(backup.read_text('utf-8'))
    updated = [dict(row) for row in connection.execute(text('SELECT * FROM localidades ORDER BY id')).mappings()]
    assert len(updated) == len(original)
    for old, new in zip(original, updated, strict=True):
        assert all(new[key] == old[key] for key in ('id','ubigeo_codigo','nombre','nombre_norm','activo'))
        assert new['codigo_catalogo'] == old['codigo_sis']
        assert new['codigo_sis'] == migration.SOURCE_KEYS.get((new['ubigeo_codigo'],new['codigo_catalogo']))
print('Locality source keys corrected; IDs, patient links and historical copies unchanged.')
