"""Run integration in a newly created disposable database, never the local app DB."""
import os
import subprocess
import sys
from datetime import datetime

from sqlalchemy import create_engine, text

from app.core.database import engine

name = "proysis_test_offices_" + datetime.now().strftime("%Y%m%d%H%M%S")
assert name.startswith("proysis_test_offices_") and name.replace("_", "").isalnum()
admin = create_engine(engine.url.set(database=None), isolation_level="AUTOCOMMIT")
with admin.connect() as connection:
    if connection.scalar(text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:name"), {"name": name}):
        raise RuntimeError("Refusing to reuse a database.")
    connection.exec_driver_sql(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
try:
    environment = dict(os.environ)
    environment["TEST_DATABASE_URL"] = engine.url.set(database=name).render_as_string(hide_password=False)
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/integration/test_mysql_office_hierarchy.py",
        "tests/integration/test_mysql_administration.py", "tests/integration/test_mysql_attention_flow.py",
        "tests/integration/test_mysql_catalogs.py", "-o", "addopts=", "-q"], env=environment)
finally:
    # Only this freshly created, validated test name is ever dropped.
    with admin.connect() as connection:
        connection.exec_driver_sql(f"DROP DATABASE `{name}`")
    admin.dispose()
sys.exit(result.returncode)
