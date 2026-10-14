"""Only catalog reads with the local physician account; no patient records."""
import re
from pathlib import Path

import httpx

readme = Path('README.md').read_text('utf-8')
password = re.search(r'\| `medico\.demo` \| `([^`]+)`', readme).group(1)
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=30) as client:
    login = client.post('/auth/login', json={'nombre_usuario':'medico.demo','password':password})
    login.raise_for_status()
    client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
    districts = client.get('/catalogos/ubigeos', params={'limit':100})
    districts.raise_for_status()
    assert len(districts.json()['items']) == 29
    localities = client.get('/catalogos/localidades', params={'ubigeo_codigo':'040102','limit':100})
    localities.raise_for_status()
    items = localities.json()['items']
    assert len(items) == 88
    assert {item['codigo_sis'] for item in items} == {'00000001'}
    assert len({item['codigo_catalogo'] for item in items}) == 88
    print('Physician catalog verified: 29 districts, 88 ASA localities, separate lookup/export keys.')
