"""Run backend checks against a newly allocated disposable MySQL schema."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import get_settings

WORK = Path(__file__).resolve().parent
STATE = WORK / 'database.json'
parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['prepare', 'baseline', 'baseline-fixed', 'phase-one', 'phase-two', 'final', 'coverage-final', 'cleanup', 'reset'])
parser.add_argument('checks', nargs=argparse.REMAINDER)
args = parser.parse_args()
settings = get_settings()
base = make_url(settings.sqlalchemy_database_url)
server = create_engine(base.set(database=None), isolation_level='AUTOCOMMIT')
if args.phase == 'prepare':
    if STATE.exists():
        raise SystemExit('Disposable database already allocated.')
    name = 'ipress_test_refactor_20261020_' + uuid4().hex[:8]
    with server.connect() as conn:
        conn.execute(text(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci'))
    STATE.write_text(json.dumps({'database': name}), encoding='utf-8')
    from app.main import app
    (WORK / 'openapi-before.json').write_text(json.dumps(app.openapi(), sort_keys=True, ensure_ascii=False), encoding='utf-8')
    import shutil
    for folder in ['services', 'repositories', 'mappers', 'domain']:
        destination = WORK / 'before' / folder
        shutil.copytree(ROOT / 'app' / folder, destination, ignore=shutil.ignore_patterns('__pycache__'))
    print('Disposable schema allocated:', name)
else:
    name = json.loads(STATE.read_text(encoding='utf-8'))['database']
    if not re.fullmatch(r'ipress_test_refactor_20261020_[a-f0-9]{8}', name) or name == base.database:
        raise SystemExit('Invalid disposable database identity.')
    if args.phase in {'cleanup', 'reset'}:
        with server.connect() as conn:
            for target in [name + '_bootstrap', name]:
                conn.execute(text(f'DROP DATABASE IF EXISTS `{target}`'))
            if args.phase == 'reset':
                conn.execute(text(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci'))
        print('Disposable schemas removed:', name)
    else:
        env = dict(os.environ)
        env['TEST_DATABASE_URL'] = base.set(database=name).render_as_string(hide_password=False)
        with (WORK / f'{args.phase}-pytest.log').open('w', encoding='utf-8') as output:
            result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *args.checks], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
        print('Phase:', args.phase, 'exit:', result.returncode)
        print('Log:', WORK / f'{args.phase}-pytest.log')
        raise SystemExit(result.returncode)
server.dispose()
