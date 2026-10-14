"""Verify public catalog metadata with the local development physician account."""
import re
from pathlib import Path

import httpx

readme = Path('README.md').read_text('utf-8')
password = re.search(r'\| `medico\.demo` \| `([^`]+)`', readme).group(1)
with httpx.Client(base_url='http://localhost:8000/api/v1', timeout=30) as client:
    login = client.post('/auth/login', json={'nombre_usuario': 'medico.demo', 'password': password})
    login.raise_for_status()
    client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
    response = client.get('/catalogos/establecimientos', params={'limit': 100})
    response.raise_for_status()
    verified = {'1291', '1300', '1301', '1302', '1303', '1304'}
    sites = [row for row in response.json()['items'] if row['codigo_renaes'] in verified]
    assert len(sites) == 6
    assert all(row['ubigeo_codigo'] == '040102' for row in sites)
    assert all(row['distrito'].upper() == 'ALTO SELVA ALEGRE' for row in sites)
    print('Live physician catalog: all six sites expose the verified district.')
