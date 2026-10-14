"""Synthetic clinical scene in the already owned disposable UI database only."""
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text

from app.core.database import engine

environment = json.loads(Path('tmp/office-ui-environment.json').read_text('utf-8'))
name = environment['database']
assert name.startswith('proysis_test_office_ui_') and name.replace('_', '').isalnum()
assert environment['url'] == 'http://127.0.0.1:8001'
qa_url = engine.url.set(database=name)
variables = dict(os.environ, DATABASE_URL=qa_url.render_as_string(hide_password=False))
subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=variables, check=True)
readme = Path('README.md').read_text('utf-8')

def client(username):
    password = re.search(r'\| `' + re.escape(username) + r'` \| `([^`]+)`', readme).group(1)
    api = httpx.Client(base_url=environment['url'] + '/api/v1', timeout=30)
    response = api.post('/auth/login', json={'nombre_usuario': username, 'password': password})
    response.raise_for_status()
    api.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
    return api

admin, doctor = client('admin'), client('medico.demo')
professional_id = next(user['profesional_id'] for user in admin.get('/usuarios').json()
                       if user['nombre_usuario'] == 'medico.demo')
offices = doctor.get('/catalogos/consultorios', params={'limit': 100}).json()['items']
root = next(row for row in offices if row.get('area_codigo') == 'ESPECIALIDADES:003')
test = create_engine(qa_url)
with test.begin() as connection:
    # Deliberately different patient/site districts, exclusively fictitious QA data.
    connection.execute(text('UPDATE establecimientos SET ubigeo_codigo=:district WHERE id=:id'),
                       {'district': '040103', 'id': root['establecimiento_id']})
test.dispose()
child = admin.post('/configuracion/consultorios', json={
    'establecimiento_id': root['establecimiento_id'], 'codigo': 'QA-' + uuid4().hex[:6],
    'nombre': 'Sala QA territorial', 'consultorio_padre_id': root['id'],
    'servicios_codigos': ['ESP_MEDICINA:001'],
})
child.raise_for_status()
locality = next(row for row in doctor.get('/catalogos/localidades', params={
    'ubigeo_codigo': '040102', 'limit': 100,
}).json()['items'] if row['codigo_sis'] == '0052')
patient = doctor.post('/patients', json={
    'tipo_documento_codigo': 'DNI', 'numero_documento': '93800901',
    'fecha_nacimiento': '1990-05-10', 'apellido_paterno': 'QA',
    'apellido_materno': 'TERRITORIO', 'primer_nombre': 'PRUEBA', 'sexo_codigo': 'F',
    'ubigeo_residencia_codigo': '040102', 'localidad_id': locality['id'],
    'establecimiento_registro_id': root['establecimiento_id'],
})
patient.raise_for_status()
assert patient.json()['localidad'] == 'PORTALES DEL MIRADOR'
attention = doctor.post('/atenciones', json={
    'paciente_id': patient.json()['id'], 'establecimiento_id': root['establecimiento_id'],
    'consultorio_id': child.json()['id'], 'profesional_id': professional_id,
    'especialidad_codigo': 'ESP_MEDICINA:001', 'modalidad_atencion_codigo': 'AMBULATORIA',
    'fecha_atencion': datetime.combine(date.today(), time(0)).isoformat(),
})
attention.raise_for_status()
assert attention.json()['fua_impresion']['contexto_territorial']['localidad_codigo_sis'] == '0052'
state = {'patient_id': patient.json()['id'], 'attention_id': attention.json()['id'],
         'office_id': child.json()['id']}
Path('tmp/territory-ui-state.json').write_text(json.dumps(state), encoding='utf-8')
print(json.dumps(state))
