"""Build and smoke-test Docker in a fresh, disposable Compose project.

Uses only Python's standard library and the Docker CLI. Never reads .env.docker,
never publishes MySQL, and only removes resources of the generated test project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "docker-smoke")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    docker = os.environ.get("DOCKER_BIN") or shutil.which("docker")
    if not docker and os.name == "nt":
        candidate = Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")
        if candidate.is_file():
            docker = str(candidate)
    if not docker:
        raise RuntimeError("Docker CLI is not installed or not available on PATH.")
    try:
        subprocess.run([docker, "info", "--format", "{{.ServerVersion}}"], check=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        (output / "resultado.json").write_text(json.dumps({
            "status": "blocked", "reason": "Docker engine is not responding",
            "resources_created": False,
        }, indent=2), encoding="utf-8")
        print("Docker engine is not responding. Start it before running the smoke test.")
        return 1
    project = "ipress_docker_test_" + uuid4().hex[:10]
    assert re.fullmatch(r"ipress_docker_test_[0-9a-f]{10}", project)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    password = f"{secrets.randbelow(100_000_000):08d}"
    env = {
        **os.environ,
        "SECRET_KEY": secrets.token_urlsafe(48),
        "MYSQL_IMAGE": "mysql:8.4",
        "MYSQL_DATABASE": "ipress_test",
        "MYSQL_USER": "ipress_test",
        "MYSQL_PASSWORD": secrets.token_urlsafe(24),
        "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(24),
        "CREATE_ADMIN_USERNAME": "docker.test.admin",
        "CREATE_ADMIN_PASSWORD": password,
        "APP_PORT": str(port),
        "WEB_CONCURRENCY": "1",
        "RUN_MIGRATIONS": "true",
        "IPRESS_BOOTSTRAP_FILE": "",
        "FORWARDED_ALLOW_IPS": "127.0.0.1",
        "TZ": "America/Lima",
    }
    compose = [
        docker, "compose", "--env-file", str(ROOT / ".env.docker.example"),
        "-f", str(ROOT / "docker-compose.yml"), "-p", project,
    ]
    report: dict = {"project": project, "port": port, "checks": {}, "cleanup_completed": False}
    started = False
    with (output / "docker.log").open("w", encoding="utf-8") as log:
        def run(*arguments: str, timeout: int = 1200) -> str:
            result = subprocess.run(
                [*compose, *arguments], cwd=ROOT, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
            log.write(result.stdout)
            log.flush()
            if result.returncode:
                raise RuntimeError(f"Docker command failed; see {output / 'docker.log'}")
            return result.stdout.strip()

        def login() -> None:
            request = Request(
                f"http://127.0.0.1:{port}/api/v1/auth/login",
                data=json.dumps({
                    "nombre_usuario": "docker.test.admin", "password": password,
                }).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=10) as response:
                assert response.status == 200
                assert json.load(response)["access_token"]

        try:
            run("config", "--quiet")
            print("Building and starting a disposable Docker stack...", flush=True)
            started = True
            run("up", "-d", "--build", "--wait", "--wait-timeout", "240")
            report["checks"]["startup_and_database_readiness"] = True
            with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=5) as response:
                assert json.load(response) == {"status": "ok"}
            with urlopen(f"http://127.0.0.1:{port}/admision?patientId=11", timeout=5) as response:
                html = response.read().decode()
                assert '<div id="app">' in html
                asset = re.search(r'src="(/assets/[^\"]+\.js)"', html)
                assert asset is not None
            with urlopen(f"http://127.0.0.1:{port}{asset[1]}", timeout=5) as response:
                assert response.status == 200
            report["checks"]["spa_route_and_assets"] = True
            assert run("exec", "-T", "app", "id", "-u") == "10001"
            run("exec", "-T", "app", "python", "-c", (
                "import importlib.util; from zoneinfo import ZoneInfo; "
                "assert importlib.util.find_spec('pytest') is None; "
                "assert importlib.util.find_spec('ruff') is None; "
                "assert importlib.util.find_spec('cryptography') is not None; "
                "assert ZoneInfo('America/Lima').key == 'America/Lima'"
            ))
            report["checks"]["nonroot_and_runtime_dependencies"] = True
            login()
            print(
                "Frontend and login passed; checking restart with the same administrator...",
                flush=True,
            )
            run("restart", "app")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    login()
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError("Login did not recover after the container restart.")
            run("exec", "-T", "app", "python", "-c", (
                "from sqlalchemy import text; from app.core.database import engine; "
                "connection=engine.connect(); "
                "assert connection.scalar(text(\"SELECT COUNT(*) FROM usuarios WHERE "
                "nombre_usuario='docker.test.admin'\")) == 1; "
                "assert connection.scalar(text(\"SELECT COUNT(*) FROM auditoria WHERE "
                "accion='BOOTSTRAP' AND tabla_nombre='usuarios' AND registro_id="
                "(SELECT id FROM usuarios WHERE nombre_usuario='docker.test.admin')\")) == 1; "
                "connection.close()"
            ))
            report["checks"]["admin_restart_without_duplicates"] = True
            print("Docker smoke checks passed.", flush=True)
            return 0
        finally:
            try:
                if started:
                    try:
                        run("logs", "--no-color", "--tail", "100", timeout=30)
                    finally:
                        # Only our newly generated project/volume can be removed.
                        assert re.fullmatch(r"ipress_docker_test_[0-9a-f]{10}", project)
                        run("down", "--volumes", "--remove-orphans", timeout=90)
                        report["cleanup_completed"] = True
            finally:
                (output / "resultado.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )


if __name__ == "__main__":
    raise SystemExit(main())
