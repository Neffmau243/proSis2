"""Disposable app on 8001; owns and cleans up its server and fresh test database."""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.security import hash_password
from app.models.security import Role, User, UserRole

name = "proysis_test_office_ui_" + datetime.now().strftime("%Y%m%d%H%M%S")
assert name.startswith("proysis_test_office_ui_") and name.replace("_", "").isalnum()
stop = Path("tmp/office-ui-qa.stop")
if stop.exists():
    stop.unlink()
admin = create_engine(engine.url.set(database=None), isolation_level="AUTOCOMMIT")
server = None
test = None
with admin.connect() as connection:
    assert not connection.scalar(text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:name"), {"name": name})
    connection.exec_driver_sql(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
try:
    environment = dict(os.environ)
    environment["DATABASE_URL"] = engine.url.set(database=name).render_as_string(hide_password=False)
    environment["SERVE_FRONTEND"] = "true"
    environment["PYTHONPATH"] = "."
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=environment, check=True)
    test = create_engine(engine.url.set(database=name))
    readme = Path("README.md").read_text(encoding="utf-8")
    with Session(test) as session:
        medical_professional = session.scalar(text("SELECT p.profesional_id FROM consultorio_profesionales p JOIN consultorios c ON c.id=p.consultorio_id WHERE c.area_codigo='ESPECIALIDADES:003' LIMIT 1"))
        for username, role in (("admin", "ADMIN"), ("medico.demo", "PROFESIONAL")):
            password = re.search(r"\| `" + re.escape(username) + r"` \| `([^`]+)`", readme).group(1)
            user = User(nombre_usuario=username, password_hash=hash_password(password),
                        profesional_id=medical_professional if role == "PROFESIONAL" else None)
            session.add(user)
            session.flush()
            role_id = session.scalar(text("SELECT id FROM roles WHERE codigo=:code"), {"code": role})
            session.add(UserRole(usuario_id=user.id, rol_id=role_id))
        session.commit()
    log = Path("tmp/office-ui-server.log").open("w", encoding="utf-8")
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        env=environment, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    for attempt in range(60):
        if server.poll() is not None:
            raise RuntimeError("QA server failed; inspect tmp/office-ui-server.log")
        try:
            if httpx.get("http://127.0.0.1:8001/api/v1/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        raise RuntimeError("QA server unavailable")
    Path("tmp/office-ui-environment.json").write_text(json.dumps({"database": name, "url": "http://127.0.0.1:8001"}), encoding="utf-8")
    print("Isolated UI ready on http://127.0.0.1:8001; cleanup runs when tmp/office-ui-qa.stop is created.", flush=True)
    while not stop.exists() and server.poll() is None:
        time.sleep(0.5)
finally:
    if server is not None and server.poll() is None:
        server.terminate()
        server.wait(timeout=15)
    if test is not None:
        test.dispose()
    with admin.connect() as connection:
        connection.exec_driver_sql(f"DROP DATABASE `{name}`")
    admin.dispose()
    print("Isolated server and database cleaned up.", flush=True)
