"""Back up site metadata and verify patient/history fingerprints during upgrade."""

import hashlib
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.database import engine


def fingerprints(connection):
    queries = {
        "patient_links": """SELECT id,ubigeo_residencia_codigo,localidad_id,
            establecimiento_registro_id,SHA2(COALESCE(localidad,''),256)
            FROM pacientes ORDER BY id""",
        "attention_context": """SELECT id,establecimiento_id,consultorio_id,
            profesional_id,especialidad_codigo,SHA2(CAST(contexto_clinico AS CHAR),256),
            SHA2(CAST(fua_impresion AS CHAR),256) FROM atenciones ORDER BY id""",
    }
    # Read only hashes and links; never print/store patient identifiers or contents.
    return {key: hashlib.sha256(repr([tuple(row) for row in connection.execute(text(query))])
            .encode('utf-8')).hexdigest() for key, query in queries.items()}


with engine.connect() as connection:
    revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
    assert revision in {'20261013_0034_locality_codes', '20261013_0035_site_district'}
    sites = [dict(row) for row in connection.execute(text(
        'SELECT id,nombre,codigo_renaes,ubigeo_codigo FROM establecimientos ORDER BY id'
    )).mappings()]
    before = fingerprints(connection)
    backup = Path('tmp/establecimientos_before_0035.json')
    if not backup.exists():
        backup.write_text(json.dumps(sites, ensure_ascii=False, indent=2), encoding='utf-8')
command.upgrade(Config('alembic.ini'), 'head')
with engine.connect() as connection:
    after = fingerprints(connection)
    assert before == after, 'Patient or historical attention data changed unexpectedly.'
    sites = [dict(row) for row in connection.execute(text(
        'SELECT e.codigo_renaes,e.nombre,e.ubigeo_codigo,u.distrito,u.provincia '
        'FROM establecimientos e LEFT JOIN ubigeos u ON u.codigo=e.ubigeo_codigo ORDER BY e.id'
    )).mappings()]
    expected = {'1291', '1300', '1301', '1302', '1303', '1304'}
    verified = [row for row in sites if row['codigo_renaes'] in expected]
    assert len(verified) == 6
    assert all(row['ubigeo_codigo'] == '040102' for row in verified)
report = {'checked_on': '2026-10-13', 'revision': '20261013_0035_site_district',
    'sources': [
        'https://pagina.saludarequipa.gob.pe/wp-content/uploads/2024/10/Horario_Atencion_GERESA.pdf',
        'https://repositorio.pcris.gob.pe/Archivos/DocumentoExpedienteMPV82401082023170156.pdf',
    ], 'sites': verified, 'patient_and_history_unchanged': before == after}
Path('docs/audits/establishment_district_20261013.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('Six verified sites linked to 040102; patient links and historical copies unchanged.')
