"""Exercise production Compose, secret files, TLS, backup and release recovery.

Everything is synthetic and owned by one generated project. The test maps two
fake immutable registry digests to a locally built image; no registry credentials
or public domain are needed. TLS uses Caddy's LOCAL test CA, explicitly trusted
only by this test's client. Production never disables certificate verification.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import ssl
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ipress_ops", ROOT / "deploy/ops.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/recovery-ci")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    suffix = uuid4().hex[:10]
    project = "ipress_ops_test_" + suffix
    image = "ipress-ops-test:" + suffix
    first = "ghcr.io/test/ipress@sha256:" + "1" * 64
    second = "ghcr.io/test/ipress@sha256:" + "2" * 64
    env_file = output / f"{suffix}.env"
    ops.init_environment(
        SimpleNamespace(
            env=env_file,
            domain="localhost",
            email="test@example.org",
            project=project,
            backup_dir=output / f"{suffix}-backups",
            state_dir=output / f"{suffix}-state",
            admin_username="",
        )
    )
    with env_file.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\nMYSQL_DATABASE=ipress_ops_test\nAPP_IMAGE={image}\n"
            f"HTTP_PORT={free_port()}\nHTTPS_PORT={free_port()}\n"
            f"PROXY_SUBNET=172.30.{int(suffix[:2], 16)}.0/28\n"
        )
    report = {"project": project, "checks": {}, "cleanup": False, "status": "running"}

    class LocalRegistryOperations(ops.Operations):
        fail_probe = False
        schema_failure = False

        def compose(self, *arguments, image=None, **kwargs):
            # Real Docker operations, with only the remote registry transport
            # substituted. Both candidate digests map to this reviewed local image.
            if arguments[:1] == ("pull",):
                arguments = tuple(value for value in arguments if value != "app")
                if arguments == ("pull",):
                    return subprocess.CompletedProcess([], 0)
            if self.schema_failure and arguments[:2] == ("run", "--rm"):
                self.mysql("CREATE TABLE e2e_partial_ddl (id INT PRIMARY KEY);")
                raise RuntimeError("Synthetic partial DDL failure")
            return super().compose(*arguments, image=image_map.get(image, image), **kwargs)

        def public_health(self):
            if self.fail_probe:
                self.fail_probe = False
                raise RuntimeError("Synthetic failed candidate probe")
            certificate = output / f"{suffix}-ca.crt"
            for _ in range(30):
                try:
                    result = self.compose(
                        "exec",
                        "-T",
                        "edge",
                        "cat",
                        "/data/caddy/pki/authorities/local/root.crt",
                        capture_output=True,
                        image=first,
                    )
                except subprocess.CalledProcessError:
                    time.sleep(1)
                    continue
                if result.stdout:
                    certificate.write_bytes(result.stdout)
                    self.tls_context = ssl.create_default_context(cafile=str(certificate))
                    break
                time.sleep(1)
            return super().public_health()

    image_map = {first: image, second: image}
    operations = LocalRegistryOperations(env_file)
    try:
        subprocess.run(
            [operations.docker, "build", "-t", image, "."],
            cwd=ROOT,
            check=True,
            timeout=1200,
            stdout=subprocess.DEVNULL,
        )
        operations.deploy(first)
        report["checks"]["production_compose_https_and_file_secrets"] = True
        assert operations.mysql("SELECT COUNT(*) FROM usuarios;") == "9"
        # Verify the secret loader rejects conflicting env/_FILE configuration.
        try:
            operations.compose(
                "run",
                "--rm",
                "--no-deps",
                "-e",
                "SECRET_KEY=conflict",
                "app",
                "python",
                "-c",
                "raise SystemExit(0)",
                image=first,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            report["checks"]["ambiguous_secret_source_rejected"] = True
        else:
            raise AssertionError("Secret source conflict should have been refused")
        # A synthetic marker proves that real records, not only tables, survive.
        operations.mysql(
            "CREATE TABLE e2e_recovery_marker (id INT PRIMARY KEY, note VARCHAR(80));"
            "INSERT INTO e2e_recovery_marker VALUES (1,'synthetic backup marker');"
        )
        source = operations.mysql("SELECT COUNT(*) FROM usuarios;")
        backup = operations.backup(verify=True)
        manifest = json.loads(Path(str(backup) + ".json").read_text("utf-8"))
        assert manifest["restored_counts"]["usuarios"] == int(source)
        report["checks"]["backup_restored_and_check_table_passed"] = True
        # A good second deployment records the previous digest and schema.
        operations.deploy(second)
        operations.rollback(project, restore_database=False)
        assert json.loads(operations.state_file.read_text())["image"] == first
        report["checks"]["manual_application_rollback"] = True
        operations.fail_probe = True
        try:
            operations.deploy(second)
        except RuntimeError as error:
            assert "Synthetic failed candidate" in str(error)
        else:
            raise AssertionError("Expected synthetic probe failure")
        assert json.loads(operations.state_file.read_text())["status"] == "rolled_back"
        report["checks"]["automatic_rollback_without_schema_change"] = True
        # MySQL can commit DDL before Alembic advances its revision. Verify that
        # this is detected and never automatically restores/deletes newer data.
        operations.schema_failure = True
        try:
            operations.deploy(second)
        except RuntimeError as error:
            assert "partial DDL" in str(error)
        else:
            raise AssertionError("Expected partial DDL failure")
        operations.schema_failure = False
        assert json.loads(operations.state_file.read_text())["status"] == "failed_schema_changed"
        try:
            operations.rollback(project, restore_database=False)
        except RuntimeError as error:
            assert "Schema changed" in str(error)
        else:
            raise AssertionError("Unsafe schema rollback should have been refused")
        operations.rollback(project, restore_database=True)
        assert (
            operations.mysql("SELECT note FROM e2e_recovery_marker WHERE id=1;")
            == "synthetic backup marker"
        )
        assert (
            operations.mysql(
                "SELECT COUNT(*) FROM information_schema.tables WHERE "
                "table_schema=DATABASE() AND table_name='e2e_partial_ddl';"
            )
            == "0"
        )
        report["checks"]["partial_ddl_guard_and_explicit_database_recovery"] = True
        # Check public exposure from Docker's actual configuration.
        for service in ("app", "db"):
            identity = operations.compose(
                "ps", "-q", service, image=first, capture_output=True, text=True
            ).stdout.strip()
            inspected = json.loads(
                subprocess.check_output([operations.docker, "inspect", identity])
            )[0]
            assert not inspected["HostConfig"]["PortBindings"]
            assert not any(
                value.startswith(("SECRET_KEY=", "MYSQL_PASSWORD=", "MYSQL_ROOT_PASSWORD="))
                for value in inspected["Config"]["Env"]
            )
        report["checks"]["no_app_db_ports_or_plaintext_secrets_in_inspect"] = True
        report["status"] = "passed"
    finally:
        operations.compose("down", "--volumes", "--remove-orphans", image=first)
        report["cleanup"] = True
        (output / "result.json").write_text(json.dumps(report, indent=2), "utf-8")
        subprocess.run([operations.docker, "image", "rm", image], capture_output=True, timeout=60)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
