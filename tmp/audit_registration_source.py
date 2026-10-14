"""Read original catalog/query metadata and anonymous registration consistency."""
import hashlib
import json
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path

from access_parser import AccessParser

logging.disable(logging.CRITICAL)
root = Path('etlSis/private/ace-source')
manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
tables = {table['name']: table for table in manifest['tables']}

def rows(name):
    for line in (root / tables[name]['file']).read_text('utf-8').splitlines():
        yield json.loads(line)

def normalized(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in text if not unicodedata.combining(c)).lower())

districts = {normalized(row['Distrito']): row for row in rows('Provincia')}
names_by_district = {name: {normalized(row['Lugar']) for row in rows(f"Z_{int(district['Codigo']):02d}")}
                     for name, district in districts.items()}
sites = {normalized(row['EESS']) for row in rows('EESS')}
official_sites = {normalized(row['EESS']) for row in rows('EESS')
                  if str(row.get('Renaes')) in {'1291','1300','1301','1302','1303','1304'}}
counts = Counter()
for patient in rows('Pacientes'):
    counts['rows'] += 1
    district = normalized(patient.get('Distrito'))
    locality = normalized(patient.get('Localidad'))
    site = normalized(patient.get('Establecimiento'))
    counts['known_district' if district in districts else 'blank_or_unknown_district'] += 1
    if district in districts and locality:
        counts['locality_equals_district_name'] += locality == district
        counts['locality_in_district_catalog' if locality in names_by_district[district]
               else 'locality_outside_district_catalog'] += 1
    counts['known_establishment' if site in sites else 'blank_or_unknown_establishment'] += 1
    if site in official_sites and district in districts and district != 'altoselvaalegre':
        counts['other_district_registered_in_asa_site'] += 1
print('registration_aggregates', json.dumps(counts))
for district_name in ('altoselvaalegre', 'cayma', 'cercado'):
    district = districts[district_name]
    name = f"Z_{int(district['Codigo']):02d}"
    print('catalog_example', json.dumps({'district': district['Distrito'], 'source_table': name,
        'localities': list(rows(name))[:4]}, ensure_ascii=True))
source = Path('etlSis/private/source.mdb')
digest = hashlib.sha256(source.read_bytes()).hexdigest()
db = AccessParser(str(source))
objects = db.parse_table('MSysObjects')
queries = {objects['Id'][i]: objects['Name'][i] for i in range(len(objects['Name']))
           if objects['Type'][i] == 5}
query = db.parse_table('MSysQueries') if 'MSysQueries' in db.catalog else {}
print('query_metadata_columns', list(query))
for index in range(len(next(iter(query.values()))) if query else 0):
    expression = query.get('Expression', [None] * len(next(iter(query.values()))))[index]
    if isinstance(expression, str) and re.search(r'distrit|localidad|establec|Provincia|EESS|Z_0', expression, re.I):
        print('query_geography', json.dumps({
            'query': queries.get(query.get('ObjectId', [None] * len(next(iter(query.values()))))[index]),
            'expression': expression}, ensure_ascii=True))
assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
