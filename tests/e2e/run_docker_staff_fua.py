"""Build an isolated Docker copy and run admin -> physician -> attention -> FUA.

Uses the private operational snapshot, a fresh Compose project/volume and a free
port. --keep-running leaves the test installation available for human review.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/docker-staff-fua")
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument(
        "--synthetic", action="store_true", help="CI: no private snapshot or .env.docker."
    )
    parser.add_argument("--image", help="Test a published image instead of rebuilding it.")
    parser.add_argument(
        "--reuse", action="store_true", help="Reuse this output's isolated test stack."
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    docker = shutil.which("docker")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not docker or not npm:
        raise RuntimeError("Docker and npm must be installed.")
    report = {"status": "starting", "resources_created": False}
    try:
        subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            check=True,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        report.update(status="blocked", reason="Docker engine is not responding")
        (output / "stack.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("Docker engine is not responding; no test resources were created.")
        return 1
    if args.synthetic and args.reuse:
        raise ValueError("Synthetic CI requires a newly generated project, not --reuse.")
    if not args.synthetic and not (ROOT / "docker/bootstrap/arequipa.json.gz").is_file():
        raise RuntimeError("Export the private Arequipa snapshot before this E2E.")
    previous = json.loads((output / "stack.json").read_text("utf-8")) if args.reuse else None
    project = previous["project"] if previous else "ipress_docker_e2e_" + uuid4().hex[:10]
    assert re.fullmatch(r"ipress_docker_e2e_[a-f0-9]{10}", project)
    if previous:
        port = int(previous["port"])
        if not 1024 <= port <= 65535:
            raise ValueError("Invalid isolated stack port.")
    else:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
    environment = {
        **os.environ,
        "APP_PORT": str(port),
        "MYSQL_DATABASE": "ipress_docker_e2e",
        "MYSQL_IMAGE": "mysql:8.4",
        "RUN_MIGRATIONS": "true",
        "WEB_CONCURRENCY": "1",
        "IPRESS_BOOTSTRAP_FILE": "/bootstrap/arequipa.json.gz",
        "CREATE_ADMIN_USERNAME": "",
        "CREATE_ADMIN_PASSWORD": "",
        "DOCKER_E2E_PROJECT": project,
        "DOCKER_E2E_URL": f"http://127.0.0.1:{port}",
        "DOCKER_E2E_EVIDENCE": str(output / "browser"),
        "DOCKER_E2E_DATE": "2026-10-23",
        "DOCKER_E2E_ADMIN_USERNAME": os.environ.get("DOCKER_E2E_ADMIN_USERNAME", "admin"),
    }
    if args.synthetic:
        environment.update(
            SECRET_KEY=secrets.token_urlsafe(48),
            MYSQL_USER="ipress_ci",
            MYSQL_PASSWORD=secrets.token_urlsafe(32),
            MYSQL_ROOT_PASSWORD=secrets.token_urlsafe(32),
            CREATE_ADMIN_USERNAME="docker.ci.admin",
            CREATE_ADMIN_PASSWORD=f"{secrets.randbelow(100_000_000):08d}",
            IPRESS_BOOTSTRAP_FILE="",
            DOCKER_E2E_ADMIN_USERNAME="docker.ci.admin",
            FORWARDED_ALLOW_IPS="127.0.0.1",
        )
        environment["DOCKER_E2E_ADMIN_PASSWORD"] = environment["CREATE_ADMIN_PASSWORD"]
    if "DOCKER_E2E_ADMIN_PASSWORD" not in environment:
        source = ast.parse((ROOT / "app/scripts/seed_demo_data.py").read_text("utf-8-sig"))
        environment["DOCKER_E2E_ADMIN_PASSWORD"] = next(
            ast.literal_eval(node.value)
            for node in source.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "DEMO_ADMIN_PASSWORD" for t in node.targets)
        )
    if os.name == "nt" and "PLAYWRIGHT_CHROMIUM_EXECUTABLE" not in environment:
        edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
        if edge.is_file():
            environment["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = str(edge)
    compose = [
        docker,
        "compose",
        "--env-file",
        str(ROOT / (".env.docker.example" if args.synthetic else ".env.docker")),
        "-f",
        str(ROOT / "docker-compose.yml"),
        "-p",
        project,
    ]
    if args.image:
        if not args.synthetic:
            raise ValueError("--image is supported only with --synthetic.")
        if not re.fullmatch(r"ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}", args.image):
            raise ValueError("Use the immutable published GHCR digest.")
        override = output / "candidate-image.json"
        override.write_text(json.dumps({"services": {"app": {"image": args.image}}}), "utf-8")
        compose.extend(["-f", str(override)])
    report.update(
        project=project,
        port=port,
        url=environment["DOCKER_E2E_URL"],
        resources_created=True,
        kept_running=args.keep_running,
    )
    with (output / "docker.log").open("a" if args.reuse else "w", encoding="utf-8") as log:

        def run(arguments: list[str], *, cwd=ROOT, timeout=1800) -> None:
            result = subprocess.run(
                arguments,
                cwd=cwd,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
            log.flush()
            if result.returncode:
                raise RuntimeError(f"Command failed; see {output / 'docker.log'}")

        try:
            print(f"Preparing isolated Docker installation: {project}", flush=True)
            run(
                [
                    *compose,
                    "up",
                    "-d",
                    *(["--no-build"] if args.image else ([] if args.reuse else ["--build"])),
                    "--wait",
                    "--wait-timeout",
                    "300",
                ]
            )
            if args.synthetic:
                fixture = subprocess.run(
                    [*compose, "exec", "-T", "-e", "IPRESS_SYNTHETIC_E2E=1", "app", "python", "-"],
                    input=(ROOT / "tests/e2e/seed_docker_ci.py").read_bytes(),
                    cwd=ROOT,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                )
                if fixture.returncode:
                    raise RuntimeError(f"Synthetic fixture failed; see {output / 'docker.log'}")
            report["status"] = "browser_testing"
            (output / "stack.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(
                f"Containers healthy at {environment['DOCKER_E2E_URL']}; starting the browser E2E...",
                flush=True,
            )
            run(
                [
                    npm,
                    "exec",
                    "--",
                    "playwright",
                    "test",
                    "--config",
                    "playwright.docker.config.ts",
                ],
                cwd=ROOT / "frontend",
                timeout=300,
            )
            report["status"] = "passed"
            print(
                "Admin, physician creation, assignment, clinical login, FUA and PDF passed.",
                flush=True,
            )
            return 0
        except Exception:
            report["status"] = "failed"
            raise
        finally:
            try:
                try:
                    run([*compose, "logs", "--no-color", "--tail", "80"], timeout=30)
                finally:
                    if not args.keep_running:
                        assert re.fullmatch(r"ipress_docker_e2e_[a-f0-9]{10}", project)
                        run([*compose, "down", "--volumes", "--remove-orphans"], timeout=90)
                        report["cleanup_completed"] = True
            finally:
                (output / "stack.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
