"""Linux host operations for one isolated IPRESS environment (stdlib only).

No production password travels in command arguments or GitHub. Restore drills
always use a newly generated container without network or published ports.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

HERE = Path(__file__).resolve().parent
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
DIGEST = re.compile(r"ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}\Z")
ROOT_MYSQL = (
    'export MYSQL_PWD="$(if [ -f /run/secrets/mysql_root_password ]; then '
    'cat /run/secrets/mysql_root_password; else printf %s "$MYSQL_ROOT_PASSWORD"; fi)"; '
    'exec mysql -h127.0.0.1 -uroot --connect-timeout=3 --batch --skip-column-names "$MYSQL_DATABASE"'
)
DUMP = (
    'export MYSQL_PWD="$(cat /run/secrets/mysql_password)"; '
    "exec mysqldump -h127.0.0.1 -uipress_app --single-transaction "
    "--skip-lock-tables --no-tablespaces --set-gtid-purged=OFF --hex-blob "
    '--default-character-set=utf8mb4 "$MYSQL_DATABASE"'
)


def run(arguments: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, check=True, timeout=kwargs.pop("timeout", 600), **kwargs)


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("Environment file must contain literal KEY=value lines.")
        if any(char in value for char in ("$", "`", "\x00")):
            raise ValueError("Environment values must be literal, without shell expansion.")
        values[key] = value
    if not re.fullmatch(r"ipress_[a-z0-9_]+", values.get("DEPLOY_PROJECT", "")):
        raise ValueError("DEPLOY_PROJECT must start with ipress_ and be unique per environment.")
    if not IDENTIFIER.fullmatch(values.get("MYSQL_DATABASE", "sistema_salud_ipress")):
        raise ValueError("Invalid MYSQL_DATABASE.")
    return values


def init_environment(args) -> None:
    target = args.env.resolve()
    if target.exists():
        raise ValueError("Environment already exists; existing secrets were not modified.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]+[a-z0-9]", args.domain):
        raise ValueError("Provide only the DNS hostname, without scheme or port.")
    if not re.fullmatch(r"ipress_[a-z0-9_]+", args.project):
        raise ValueError("Invalid project name.")
    admin_password = os.environ.get("IPRESS_INITIAL_ADMIN_PASSWORD", "")
    if args.admin_username and not re.fullmatch(r"[0-9]{8}", admin_password):
        raise ValueError("Set IPRESS_INITIAL_ADMIN_PASSWORD to the chosen 8-digit password.")
    base = target.parent / target.stem
    if base.exists():
        raise ValueError("Secret directory already exists; nothing was overwritten.")
    base.mkdir(parents=True, mode=0o700)
    secret_dir = base / "secrets"
    secret_dir.mkdir(mode=0o700)
    for name in ("secret_key", "mysql_password", "mysql_root_password", "admin_password"):
        value = "" if name == "admin_password" else secrets.token_urlsafe(48)
        if name == "admin_password" and args.admin_username:
            value = admin_password
        file = secret_dir / name
        file.write_text(value, encoding="utf-8")
        # Files must be readable by container UID 10001. Their HOST directory is
        # 0700; Compose mounts only each individual file read-only in /run/secrets.
        os.chmod(file, 0o444)
    (base / "bootstrap").mkdir(mode=0o700)
    for path in (args.backup_dir, args.state_dir):
        path.resolve().mkdir(parents=True, exist_ok=True, mode=0o700)
    content = (HERE / "production.env.example").read_text("utf-8")
    overrides = {
        "DEPLOY_PROJECT": args.project,
        "DOMAIN": args.domain,
        "ACME_EMAIL": args.email,
        "SECRETS_DIR": str(secret_dir),
        "BOOTSTRAP_DIR": str(base / "bootstrap"),
        "BACKUP_DIR": str(args.backup_dir.resolve()),
        "STATE_DIR": str(args.state_dir.resolve()),
        "CREATE_ADMIN_USERNAME": args.admin_username,
    }
    for key, value in overrides.items():
        if any(char in value for char in "\r\n$`"):
            raise ValueError("Unsupported character in configuration.")
        content = re.sub(rf"^{key}=.*$", lambda _: f"{key}={value}", content, flags=re.M)
    with target.open("x", encoding="utf-8") as stream:
        os.chmod(target, 0o600)
        stream.write(content)
    print(f"Created {target}; existing application accounts were not changed.")


class Operations:
    def __init__(self, env_file: Path):
        self.env_file = env_file.resolve()
        self.values = read_env(self.env_file)
        self.project = self.values["DEPLOY_PROJECT"]
        self.environment = {**os.environ, **self.values}
        self.state_dir = Path(self.values["STATE_DIR"])
        self.backup_dir = Path(self.values["BACKUP_DIR"])
        for path in (self.state_dir, self.backup_dir):
            if not path.is_absolute():
                raise ValueError("State and backup paths must be absolute.")
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_file = self.state_dir / "release.json"
        self.docker = os.environ.get("DOCKER_BIN", "docker")
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text("utf-8"))
            active = state.get("image") or state.get("target")
            if active and DIGEST.fullmatch(active):
                self.environment["APP_IMAGE"] = active
        if not (self.state_dir / "Caddyfile").exists():
            self.install_proxy_config()

    def install_proxy_config(self) -> None:
        # The runner workspace can be cleaned after a job. Container mounts must
        # reference persistent host state, never checkout files.
        target = self.state_dir / "Caddyfile"
        temporary = self.state_dir / "Caddyfile.partial"
        temporary.write_bytes((HERE / "Caddyfile").read_bytes())
        os.chmod(temporary, 0o644)
        temporary.replace(target)

    def compose(self, *arguments: str, image: str | None = None, **kwargs):
        environment = {**self.environment}
        if image:
            environment["APP_IMAGE"] = image
        return run(
            [
                self.docker,
                "compose",
                "--env-file",
                str(self.env_file),
                "-f",
                str(HERE / "compose.yml"),
                "-p",
                self.project,
                *arguments,
            ],
            env=environment,
            **kwargs,
        )

    @contextlib.contextmanager
    def lock(self):
        with (self.state_dir / "operations.lock").open("a+b") as stream:
            if os.name == "nt":
                import msvcrt

                stream.write(b"\0")
                stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def mysql(self, sql: str) -> str:
        result = self.compose(
            "exec", "-T", "db", "sh", "-ec", ROOT_MYSQL, input=sql, text=True, capture_output=True
        )
        return result.stdout.strip()

    def revision(self) -> str:
        exists = self.mysql(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema=DATABASE() AND table_name='alembic_version';"
        )
        return self.mysql("SELECT version_num FROM alembic_version;") if exists == "1" else ""

    def schema_fingerprint(self) -> str:
        result = self.compose(
            "exec",
            "-T",
            "db",
            "sh",
            "-ec",
            DUMP + " --no-data --skip-comments --skip-dump-date",
            text=True,
            capture_output=True,
        )
        # Auto-increment counters change with normal writes, not schema changes.
        schema = re.sub(r"AUTO_INCREMENT=\d+", "AUTO_INCREMENT=0", result.stdout)
        return hashlib.sha256(schema.encode()).hexdigest()

    def database_image(self) -> str:
        container = self.compose("ps", "-q", "db", capture_output=True, text=True).stdout.strip()
        inspected = json.loads(
            run([self.docker, "inspect", container], capture_output=True, text=True).stdout
        )[0]
        details = json.loads(
            run(
                [self.docker, "image", "inspect", inspected["Image"]],
                capture_output=True,
                text=True,
            ).stdout
        )[0]
        for digest in details.get("RepoDigests", []):
            if "@sha256:" in digest:
                return digest
        raise RuntimeError("The database image needs a registry digest for reproducible restore.")

    def ensure_database(self, image: str) -> None:
        existing = self.compose(
            "ps", "--all", "-q", "db", image=image, capture_output=True, text=True
        ).stdout.strip()
        if existing:
            actual = json.loads(
                run([self.docker, "inspect", existing], capture_output=True, text=True).stdout
            )[0]["Config"]["Image"]
            if actual != self.values.get("MYSQL_IMAGE", "mysql:8.4"):
                raise RuntimeError(
                    "Database image changed: perform a separate backed-up MySQL "
                    "upgrade. Application releases never upgrade MySQL automatically."
                )
        else:
            self.compose("pull", "db", image=image)
        self.compose(
            "up", "-d", "--no-recreate", "--wait", "--wait-timeout", "300", "db", image=image
        )

    def backup(self, verify: bool = False) -> Path:
        revision = self.revision()
        if not revision:
            raise RuntimeError("Refusing to back up an unmigrated/empty installation.")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = self.backup_dir / f"{self.project}-{stamp}-{uuid4().hex[:8]}.sql.gz"
        partial = target.with_suffix(".partial")
        command = [
            self.docker,
            "compose",
            "--env-file",
            str(self.env_file),
            "-f",
            str(HERE / "compose.yml"),
            "-p",
            self.project,
            "exec",
            "-T",
            "db",
            "sh",
            "-ec",
            DUMP,
        ]
        try:
            with partial.open("xb") as raw, tempfile.TemporaryFile() as errors:
                os.chmod(partial, 0o600)
                with subprocess.Popen(
                    command, env=self.environment, stdout=subprocess.PIPE, stderr=errors
                ) as process:
                    with gzip.GzipFile(fileobj=raw, mode="wb") as compressed:
                        shutil.copyfileobj(process.stdout, compressed)
                    if process.wait(timeout=3600):
                        raise RuntimeError("mysqldump failed; partial backup was discarded.")
                raw.flush()
                os.fsync(raw.fileno())
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        manifest = {
            "project": self.project,
            "database": self.values.get("MYSQL_DATABASE", "sistema_salud_ipress"),
            "created_utc": stamp,
            "revision": revision,
            "sha256": checksum(target),
            "mysql_image": self.database_image(),
            "verified_restore": False,
        }
        atomic_json(Path(str(target) + ".json"), manifest)
        if verify:
            self.drill(target)
        destination = self.values.get("BACKUP_COPY_DIR")
        if destination:
            if not Path(destination).is_absolute():
                raise ValueError("BACKUP_COPY_DIR must be absolute.")
            remote = Path(destination).resolve()
            local = self.backup_dir.resolve()
            if not remote.is_absolute() or remote == local or local in remote.parents:
                raise ValueError("BACKUP_COPY_DIR must be a separate, absolute destination.")
            # The destination MUST be pre-mounted by DevOps. Never silently
            # create a missing mount and mistake a local copy for offsite storage.
            if not remote.is_dir() or not os.path.ismount(remote):
                raise RuntimeError("Backup copy destination must be an available mount point.")
            for source in (target, Path(str(target) + ".json")):
                copy = remote / source.name
                staging = copy.with_suffix(copy.suffix + ".partial")
                shutil.copyfile(source, staging)
                os.chmod(staging, 0o600)
                if checksum(staging) != checksum(source):
                    raise RuntimeError("Backup copy checksum mismatch.")
                staging.replace(copy)
        atomic_json(self.state_dir / "last-backup.json", {"backup": str(target), "ok": True})
        self.prune()
        print(f"Backup completed: {target}", flush=True)
        return target

    def prune(self) -> None:
        keep = int(self.values.get("BACKUP_KEEP", "14"))
        if keep < 2:
            raise ValueError("Keep at least two backups.")
        protected = set()
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text("utf-8"))
            protected = {
                state.get("backup"),
                state.get("previous", {}).get("backup"),
                state.get("recovery_safety_backup"),
            }
        # Only successfully restored backups count toward the rotation limit.
        verified = []
        for path in sorted(self.backup_dir.glob(f"{self.project}-*.sql.gz"), reverse=True):
            sidecar = Path(str(path) + ".json")
            if sidecar.exists() and json.loads(sidecar.read_text("utf-8")).get("verified_restore"):
                verified.append(path)
        for path in verified[keep:]:
            if str(path) not in protected:
                path.unlink()
                Path(str(path) + ".json").unlink()

    def verify_backup(self, backup: Path) -> dict:
        manifest = json.loads(Path(str(backup) + ".json").read_text("utf-8"))
        if manifest["project"] != self.project:
            raise ValueError("Backup belongs to another environment.")
        if checksum(backup) != manifest["sha256"]:
            raise ValueError("Backup checksum mismatch; restore refused.")
        return manifest

    def import_stream(self, backup: Path, command: list[str]) -> None:
        with gzip.open(backup, "rb") as source, tempfile.TemporaryFile() as errors:
            with subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=errors,
                env=self.environment,
            ) as process:
                try:
                    shutil.copyfileobj(source, process.stdin)
                    process.stdin.close()
                except (OSError, EOFError):
                    process.kill()
                    process.wait()
                    raise RuntimeError("Restore stream failed.") from None
                if process.wait(timeout=3600):
                    raise RuntimeError("MySQL rejected the backup; restore failed.")

    def drill(self, backup: Path) -> dict:
        backup = backup.resolve()
        manifest = self.verify_backup(backup)
        container = "ipress_restore_test_" + uuid4().hex
        environment = {
            **self.environment,
            "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(48),
            "MYSQL_DATABASE": manifest["database"],
        }
        image = manifest["mysql_image"]
        try:
            run(
                [
                    self.docker,
                    "run",
                    "-d",
                    "--name",
                    container,
                    "--network",
                    "none",
                    "--label",
                    "ipress.disposable=restore-test",
                    "--env",
                    "MYSQL_ROOT_PASSWORD",
                    "--env",
                    "MYSQL_DATABASE",
                    image,
                ],
                env=environment,
                capture_output=True,
            )
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                try:
                    probe = subprocess.run(
                        [self.docker, "exec", "-i", container, "sh", "-ec", ROOT_MYSQL],
                        input="SELECT 1;",
                        text=True,
                        capture_output=True,
                        timeout=30,
                    )
                    if probe.returncode == 0:
                        break
                except subprocess.TimeoutExpired:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Disposable restore MySQL did not become ready.")
            self.import_stream(
                backup, [self.docker, "exec", "-i", container, "sh", "-ec", ROOT_MYSQL]
            )
            query = "SELECT version_num FROM alembic_version;"
            result = run(
                [self.docker, "exec", "-i", container, "sh", "-ec", ROOT_MYSQL],
                input=query,
                text=True,
                capture_output=True,
            )
            if result.stdout.strip() != manifest["revision"]:
                raise RuntimeError("Restored migration revision does not match the backup.")
            # Verify real restored clinical tables, not merely a TCP response.
            counts = {}
            for table in ("usuarios", "profesionales", "pacientes", "atenciones", "fua"):
                result = run(
                    [self.docker, "exec", "-i", container, "sh", "-ec", ROOT_MYSQL],
                    input=f"SELECT COUNT(*) FROM `{table}`;",
                    text=True,
                    capture_output=True,
                )
                counts[table] = int(result.stdout.strip())
            # The minimal official MySQL image has mysql, but not mysqlcheck.
            # CHECK TABLE performs the same server-side table validation.
            result = run(
                [self.docker, "exec", "-i", container, "sh", "-ec", ROOT_MYSQL],
                input="SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=DATABASE() AND table_type='BASE TABLE';",
                text=True,
                capture_output=True,
            )
            tables = result.stdout.splitlines()
            if not tables or any(not IDENTIFIER.fullmatch(table) for table in tables):
                raise RuntimeError("Unexpected restored table names.")
            result = run(
                [self.docker, "exec", "-i", container, "sh", "-ec", ROOT_MYSQL],
                input="CHECK TABLE " + ",".join(f"`{table}`" for table in tables) + ";",
                text=True,
                capture_output=True,
            )
            checked = result.stdout.splitlines()
            if len(checked) != len(tables) or any(
                row.split("\t")[-2:] != ["status", "OK"] for row in checked
            ):
                raise RuntimeError("Restored table integrity check failed.")
            manifest.update(
                verified_restore=True,
                restored_counts=counts,
                verified_utc=datetime.now(UTC).isoformat(),
            )
            atomic_json(Path(str(backup) + ".json"), manifest)
            atomic_json(
                self.state_dir / "last-restore-drill.json",
                {
                    "backup": str(backup),
                    "ok": True,
                    "restored_counts": counts,
                    "verified_utc": manifest["verified_utc"],
                },
            )
            print("Disposable restore passed (schema, records and CHECK TABLE).", flush=True)
            return manifest
        finally:
            assert re.fullmatch(r"ipress_restore_test_[a-f0-9]{32}", container)
            # -v removes only anonymous storage owned by THIS generated container.
            subprocess.run([self.docker, "rm", "-fv", container], capture_output=True, timeout=90)

    def public_health(self) -> None:
        domain = self.values["DOMAIN"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]+[a-z0-9]", domain):
            raise ValueError("Invalid DOMAIN.")
        port = int(self.values.get("HTTPS_PORT", "443"))
        url = f"https://{domain}" + (f":{port}" if port != 443 else "")
        last = None
        for _ in range(12):
            try:
                with urlopen(
                    url + "/api/v1/health", timeout=10, context=getattr(self, "tls_context", None)
                ) as response:
                    if response.url.startswith(url + "/") and json.load(response) == {
                        "status": "ok"
                    }:
                        with urlopen(
                            url + "/login", timeout=10, context=getattr(self, "tls_context", None)
                        ) as spa:
                            if b'<div id="app">' in spa.read():
                                return
            except (OSError, ValueError) as error:
                last = type(error).__name__
            time.sleep(5)
        raise RuntimeError(f"Public HTTPS/SPA verification failed ({last}).")

    def deploy(self, image: str) -> None:
        if not DIGEST.fullmatch(image):
            raise ValueError("Deploy an immutable ghcr.io/...@sha256:<64 hex> image.")
        # Nested schema/backup commands also need the valid candidate image;
        # the host's original template may still contain its placeholder.
        self.environment["APP_IMAGE"] = image
        state = json.loads(self.state_file.read_text("utf-8")) if self.state_file.exists() else {}
        if state.get("status") in {"failed_schema_changed", "deploying"}:
            raise RuntimeError("Resolve the previous failed schema deployment before continuing.")
        # Resolve/pull before any service is stopped.
        self.compose("config", "--quiet", image=image)
        self.compose("pull", "app", "edge", image=image)
        self.ensure_database(image)
        self.install_proxy_config()
        before = self.revision()
        schema_before = self.schema_fingerprint()
        previous = {"image": state.get("image"), "revision": before, "schema": schema_before}
        backup = None
        stopped = False
        try:
            # This single-host release has an explicit maintenance window.
            # Stop public ingress and writers before the pre-migration snapshot.
            stopped = True
            self.compose("stop", "edge", "app", image=image)
            if before:
                backup = self.backup(verify=True)
            previous["backup"] = str(backup) if backup else None
            atomic_json(
                self.state_file,
                {
                    "status": "deploying",
                    "image": state.get("image"),
                    "target": image,
                    "previous": previous,
                },
            )
            self.compose(
                "run", "--rm", "--no-deps", "app", "alembic", "upgrade", "head", image=image
            )
            self.compose(
                "up", "-d", "--no-deps", "--wait", "--wait-timeout", "240", "app", image=image
            )
            self.compose("up", "-d", "--no-deps", "--force-recreate", "edge", image=image)
            self.public_health()
            atomic_json(
                self.state_file,
                {
                    "status": "healthy",
                    "image": image,
                    "revision": self.revision(),
                    "previous": previous,
                    "deployed_utc": datetime.now(UTC).isoformat(),
                },
            )
            print("Release healthy over HTTPS.", flush=True)
        except Exception:
            if stopped:
                self.compose("stop", "edge", "app", image=image)
                after = self.revision()
                failed = {
                    "status": "failed_schema_changed",
                    "image": state.get("image"),
                    "target": image,
                    "revision": after,
                    "previous": previous,
                }
                atomic_json(self.state_file, failed)
                # MySQL DDL can commit even when Alembic's revision stays old.
                # A schema fingerprint prevents unsafe rollback after partial DDL.
                if (
                    previous.get("image")
                    and after == before
                    and self.schema_fingerprint() == schema_before
                ):
                    self.compose(
                        "up",
                        "-d",
                        "--no-deps",
                        "--wait",
                        "--wait-timeout",
                        "240",
                        "app",
                        image=previous["image"],
                    )
                    self.compose(
                        "up", "-d", "--no-deps", "--force-recreate", "edge", image=previous["image"]
                    )
                    self.public_health()
                    failed["status"] = "rolled_back"
                atomic_json(self.state_file, failed)
            raise

    def rollback(self, confirm: str, restore_database: bool) -> None:
        if confirm != self.project:
            raise ValueError("Confirm the exact DEPLOY_PROJECT before rollback/recovery.")
        state = json.loads(self.state_file.read_text("utf-8"))
        previous = state["previous"]
        image = previous.get("image")
        if not image or not DIGEST.fullmatch(image):
            raise RuntimeError("No previous immutable release is recorded.")
        changed = self.revision() != previous[
            "revision"
        ] or self.schema_fingerprint() != previous.get("schema")
        if changed and not restore_database:
            raise RuntimeError(
                "Schema changed: recovery requires --restore-database, with downtime "
                "and loss of writes since the pre-release backup."
            )
        manifest = None
        if restore_database:
            backup = Path(previous["backup"])
            manifest = self.verify_backup(backup)
            if not manifest.get("verified_restore") or manifest["revision"] != previous["revision"]:
                raise RuntimeError("The pre-release backup has not passed a restore drill.")
            if manifest["database"] != self.values.get("MYSQL_DATABASE", "sistema_salud_ipress"):
                raise RuntimeError("Backup database differs from the configured database.")
        self.compose("pull", "app", image=image)
        self.compose("stop", "edge", "app", image=image)
        safety = self.backup(verify=True)
        if manifest:
            name = manifest["database"]
            if not IDENTIFIER.fullmatch(name):
                raise ValueError("Invalid backup database name.")
            self.mysql(
                f"DROP DATABASE `{name}`; CREATE DATABASE `{name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
            )
            command = [
                self.docker,
                "compose",
                "--env-file",
                str(self.env_file),
                "-f",
                str(HERE / "compose.yml"),
                "-p",
                self.project,
                "exec",
                "-T",
                "db",
                "sh",
                "-ec",
                ROOT_MYSQL,
            ]
            self.import_stream(backup, command)
            if self.revision() != previous["revision"]:
                raise RuntimeError("Recovered schema differs from the previous release.")
        self.compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", "240", "app", image=image)
        self.compose("up", "-d", "--no-deps", "--force-recreate", "edge", image=image)
        self.public_health()
        atomic_json(
            self.state_file,
            {
                "status": "healthy",
                "image": image,
                "revision": self.revision(),
                "previous": {},
                "recovery_safety_backup": str(safety),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    initialize = sub.add_parser("init")
    initialize.add_argument("--domain", required=True)
    initialize.add_argument("--email", required=True)
    initialize.add_argument("--project", required=True)
    initialize.add_argument("--backup-dir", type=Path, required=True)
    initialize.add_argument("--state-dir", type=Path, required=True)
    initialize.add_argument("--admin-username", default="")
    backup = sub.add_parser("backup")
    backup.add_argument("--verify", action="store_true")
    drill = sub.add_parser("drill")
    drill.add_argument("--backup", required=True, type=Path)
    deploy = sub.add_parser("deploy")
    deploy.add_argument("--image", required=True)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--confirm-project", required=True)
    rollback.add_argument("--restore-database", action="store_true")
    sub.add_parser("health")
    args = parser.parse_args()
    if args.command == "init":
        init_environment(args)
        return
    operations = Operations(args.env)
    with operations.lock():
        if args.command == "backup":
            operations.backup(args.verify)
        elif args.command == "drill":
            operations.drill(args.backup)
        elif args.command == "deploy":
            operations.deploy(args.image)
        elif args.command == "rollback":
            operations.rollback(args.confirm_project, args.restore_database)
        else:
            operations.public_health()


if __name__ == "__main__":
    main()
