import os, re, subprocess, sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from app.core.config import get_settings
from sqlalchemy.engine import make_url

base = make_url(get_settings().sqlalchemy_database_url)
name = "ipress_test_staff_" + uuid4().hex[:8]
assert re.fullmatch(r"ipress_test_staff_[0-9a-f]{8}", name)
admin_engine = create_engine(base.set(database=None), pool_pre_ping=True)
created = False
try:
    with admin_engine.begin() as con:
        con.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    created = True
    environment = dict(os.environ)
    temporary_url = base.set(database=name).render_as_string(hide_password=False)
    environment["TEST_DATABASE_URL"] = temporary_url
    environment["DATABASE_URL"] = temporary_url
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/integration/test_mysql_staff_flow.py", "--no-cov", "-q", "-x"], env=environment)
    exit_code = result.returncode
finally:
    if created:
        with admin_engine.begin() as con:
            con.execute(text(f"DROP DATABASE `{name}`"))
        print("Disposable staff-flow test schema removed; application database unchanged.")
    admin_engine.dispose()
sys.exit(exit_code)
