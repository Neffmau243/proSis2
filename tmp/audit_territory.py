"""Read only territorial catalogs and anonymous consistency counts."""
import json
import re
from pathlib import Path

from sqlalchemy import text

from app.core.database import engine

root = Path('etlSis/private/ace-source')
manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
tables = {table['name']: table for table in manifest['tables']}
def rows(name):
    return [json.loads(line) for line in (root / tables[name]['file']).read_text('utf-8').splitlines()]
expected = {}
def normalize(value):
    return re.sub(r'\s+', ' ', re.sub('["“”]', '', value)).strip().casefold()
for district in rows('Provincia'):
    code = ''.join(str(district[key]).zfill(2) for key in ('IdDpto', 'IdProvincia', 'IdDistrito'))
    for locality in rows(f"Z_{int(district['Codigo']):02d}"):
        expected[code, str(locality['Codigo']).zfill(4)] = normalize(str(locality['Lugar']))
for table in manifest['tables']:
    if table['name'] in {'EESS', 'Distrito', 'Distritos', 'Localidad', 'Localidades'}:
        print('source', table['name'], [c['name'] for c in table['columns']])
        if table['name'] == 'EESS':
            rows = [json.loads(line) for line in (root / table['file']).read_text('utf-8').splitlines()]
            print(json.dumps(rows[:6], ensure_ascii=True))
with engine.connect() as connection:
    actual = {(row.ubigeo_codigo, row.codigo_catalogo): normalize(row.nombre)
              for row in connection.execute(text('SELECT ubigeo_codigo,codigo_catalogo,nombre FROM localidades'))}
    print('etl_locality_alignment', json.dumps({
        'source': len(expected), 'database': len(actual),
        'missing': len(expected.keys() - actual.keys()),
        'extra': len(actual.keys() - expected.keys()),
        'different_names': sum(actual.get(key) != value for key, value in expected.items()),
    }))
    print('locality_differences', json.dumps([
        {'district': key[0], 'source_code': key[1], 'source': value, 'database': actual.get(key)}
        for key, value in expected.items() if actual.get(key) != value
    ], ensure_ascii=True))
    for name, query in {
        'sites': 'SELECT id,nombre,codigo_renaes,ubigeo_codigo FROM establecimientos',
        'localities': 'SELECT ubigeo_codigo,COUNT(*) total FROM localidades GROUP BY ubigeo_codigo',
        'patient_consistency': '''SELECT COUNT(*) total,
          SUM(p.localidad_id IS NOT NULL AND (l.id IS NULL OR l.ubigeo_codigo <> p.ubigeo_residencia_codigo OR p.ubigeo_residencia_codigo IS NULL)) district_mismatch,
          SUM(p.localidad_id IS NOT NULL AND (p.localidad IS NULL OR p.localidad <> l.nombre)) name_mismatch,
          SUM(p.localidad_id IS NULL AND p.localidad IS NOT NULL) legacy_text
          FROM pacientes p LEFT JOIN localidades l ON l.id=p.localidad_id''',
        'attention_consistency': '''SELECT COUNT(*) total,
          SUM(a.establecimiento_id <> c.establecimiento_id) office_site_mismatch,
          SUM(a.fua_impresion IS NOT NULL) fua_snapshots,
          SUM(a.contexto_clinico IS NOT NULL) clinical_snapshots
          FROM atenciones a JOIN consultorios c ON c.id=a.consultorio_id''',
    }.items():
        print(name, json.dumps([dict(row) for row in connection.execute(text(query)).mappings()], default=str))
