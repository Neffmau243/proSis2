"""Run in a new owned test schema; the application database stays untouched."""
import os
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.database import engine

name = 'proysis_test_territory_' + uuid4().hex[:12]
assert name.startswith('proysis_test_territory_') and name.replace('_', '').isalnum()
admin = create_engine(engine.url.set(database=None), isolation_level='AUTOCOMMIT')
with admin.connect() as connection:
    if connection.scalar(text('SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:name'), {'name': name}):
        raise RuntimeError('Refusing to reuse a database.')
    connection.exec_driver_sql(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
try:
    environment = dict(os.environ)
    environment['TEST_DATABASE_URL'] = engine.url.set(database=name).render_as_string(hide_password=False)
    result = subprocess.run([sys.executable, '-m', 'pytest',
        'tests/integration/test_mysql_territory_history.py',
        'tests/integration/test_mysql_patients.py', 'tests/integration/test_mysql_documents.py',
        'tests/integration/test_mysql_office_hierarchy.py',
        'tests/integration/test_mysql_attention_flow.py', 'tests/integration/test_mysql_catalogs.py',
        '-o', 'addopts=', '-q'], env=environment)
finally:
    with admin.connect() as connection:
        connection.exec_driver_sql(f'DROP DATABASE `{name}`')
    admin.dispose()
sys.exit(result.returncode)
