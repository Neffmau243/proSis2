"""Run real browser/API/MySQL referral coverage in a disposable database.

Build frontend/ first, then run:
  .venv/Scripts/python.exe tests/e2e/run_referral_e2e.py --output <evidence-dir>
Requires a local MySQL account allowed to create a temporary test database and
the Chromium installed for frontend's Playwright version. No existing patient
or application database is modified.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.catalog import Insurance  # noqa: E402
from app.models.clinical import Attention  # noqa: E402
from app.models.organization import Establishment, Office, OfficeProfessional, Ubigeo  # noqa: E402
from app.models.security import Professional, Role, User, UserRole  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp" / "referral-e2e")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    database = "ipress_test_referral_e2e_" + uuid4().hex[:10]
    url = make_url(get_settings().sqlalchemy_database_url)
    root_engine = create_engine(url.set(database=None), isolation_level="AUTOCOMMIT")
    test_url = url.set(database=database)
    test_engine = None
    server = None
    server_log = None
    with root_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4"))
    try:
        env = {
            **os.environ,
            "DATABASE_URL": test_url.render_as_string(hide_password=False),
            "SERVE_FRONTEND": "true",
            "SQLALCHEMY_ECHO": "false",
        }
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True
        )
        test_engine = create_engine(test_url)
        with Session(test_engine) as session:
            territory = Ubigeo(
                codigo="999991", departamento="PRUEBA", provincia="PRUEBA", distrito="PRUEBA"
            )
            session.add(territory)
            site = Establishment(
                nombre="IPRESS DESTINO E2E",
                codigo_renaes="99000001",
                ubigeo_codigo=territory.codigo,
            )
            professional = Professional(nombre_completo="PROFESIONAL E2E", colegiatura="E2E-001")
            session.add_all([site, professional])
            session.flush()
            office = Office(establecimiento_id=site.id, codigo="E2E", nombre="CONSULTORIO E2E")
            session.add(office)
            session.flush()
            session.add(
                OfficeProfessional(
                    consultorio_id=office.id,
                    profesional_id=professional.id,
                    fecha_inicio=date(2020, 1, 1),
                )
            )
            user = User(
                nombre_usuario="referencia.e2e",
                password_hash=hash_password("12345678"),
                profesional_id=professional.id,
            )
            session.add(user)
            session.flush()
            role = session.scalar(select(Role).where(Role.codigo == "PROFESIONAL"))
            session.add(UserRole(usuario_id=user.id, rol_id=role.id))
            insurance = session.scalar(select(Insurance).where(Insurance.codigo == "SIS_GRATUITO"))
            env["REFERRAL_E2E_SITE"] = str(site.id)
            env["REFERRAL_E2E_INSURANCE"] = str(insurance.id)
            session.commit()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        env.update(REFERRAL_E2E_URL=base_url, REFERRAL_E2E_EVIDENCE=str(output))
        env['REFERRAL_E2E_DATABASE'] = database
        server_log = (output / "api.log").open("w", encoding="utf-8")
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError("The isolated API exited; see api.log")
            try:
                with urlopen(base_url + "/openapi.json", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("The isolated API did not become ready")
        result = subprocess.run(
            [
                shutil.which("npm.cmd" if os.name == "nt" else "npm"),
                "run",
                "test:e2e",
                "--",
                "referral-admission.spec.ts",
                "--workers=1",
            ],
            cwd=ROOT / "frontend",
            env=env,
        )
        if result.returncode:
            return result.returncode
        report = json.loads((output / "resultado.json").read_text(encoding="utf-8"))
        with Session(test_engine) as session:
            stored = session.get(Attention, report["attentionId"])
            assert stored is not None and stored.modalidad_atencion_codigo == "REFERENCIA"
            assert stored.profesional_id is None and stored.consultorio_id is None
            assert stored.especialidad_codigo is None
            assert stored.fua_impresion == report["snapshot"]
        report["mysql_verified"] = True
        (output / "resultado.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("Browser, API and MySQL verified. Evidence:", output)
        return 0
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        if server_log is not None:
            server_log.close()
        if test_engine is not None:
            test_engine.dispose()
        assert database.startswith("ipress_test_referral_e2e_") and len(database) == 35
        with root_engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE `{database}`"))
        root_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
