"""Recovery refusal paths must leave the running installation untouched."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "deploy_operations", Path(__file__).resolve().parents[2] / "deploy/ops.py"
)
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)


@pytest.fixture
def operations(tmp_path):
    env = tmp_path / "test.env"
    env.write_text(
        "DEPLOY_PROJECT=ipress_test\nMYSQL_DATABASE=ipress_test\n"
        f"STATE_DIR={tmp_path / 'state'}\nBACKUP_DIR={tmp_path / 'backups'}\n"
    )
    return ops.Operations(env)


def test_changed_or_foreign_backup_is_refused_before_restore(operations, tmp_path):
    backup = tmp_path / "copy.sql.gz"
    backup.write_bytes(b"original")
    sidecar = Path(str(backup) + ".json")
    sidecar.write_text(json.dumps({"project": "ipress_test", "sha256": ops.checksum(backup)}))
    backup.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        operations.verify_backup(backup)
    sidecar.write_text(json.dumps({"project": "ipress_other", "sha256": ops.checksum(backup)}))
    with pytest.raises(ValueError, match="another environment"):
        operations.verify_backup(backup)


def test_mutable_image_rejected_without_touching_docker(operations, monkeypatch):
    monkeypatch.setattr(operations, "compose", lambda *a, **kw: pytest.fail("Docker was touched"))
    for image in ("ghcr.io/user/app:latest", "user/app:tag", "sha256:123"):
        with pytest.raises(ValueError, match="immutable"):
            operations.deploy(image)


def test_recovery_needs_exact_environment_confirmation(operations, monkeypatch):
    monkeypatch.setattr(operations, "compose", lambda *a, **kw: pytest.fail("Docker was touched"))
    with pytest.raises(ValueError, match="Confirm the exact"):
        operations.rollback("ipress_other", restore_database=True)


def test_interrupted_deployment_cannot_be_silently_replaced(operations, monkeypatch):
    ops.atomic_json(operations.state_file, {"status": "deploying"})
    monkeypatch.setattr(operations, "compose", lambda *a, **kw: pytest.fail("Docker was touched"))
    with pytest.raises(RuntimeError, match="previous failed"):
        operations.deploy("ghcr.io/test/app@sha256:" + "a" * 64)


def test_scheduled_operations_resolve_active_image_from_persistent_state(operations):
    image = "ghcr.io/test/app@sha256:" + "a" * 64
    ops.atomic_json(operations.state_file, {"status": "healthy", "image": image})
    restored = ops.Operations(operations.env_file)
    assert restored.environment["APP_IMAGE"] == image


def test_partial_ddl_requires_database_recovery_even_when_revision_matches(operations, monkeypatch):
    ops.atomic_json(
        operations.state_file,
        {
            "previous": {
                "image": "ghcr.io/test/app@sha256:" + "a" * 64,
                "revision": "same",
                "schema": "before_ddl",
            }
        },
    )
    monkeypatch.setattr(operations, "revision", lambda: "same")
    monkeypatch.setattr(operations, "schema_fingerprint", lambda: "after_partial_ddl")
    monkeypatch.setattr(operations, "compose", lambda *a, **kw: pytest.fail("Docker was touched"))
    with pytest.raises(RuntimeError, match="Schema changed"):
        operations.rollback("ipress_test", restore_database=False)


def test_init_never_replaces_existing_environment_or_secrets(tmp_path):
    env = tmp_path / "production.env"
    env.write_text("existing")
    with pytest.raises(ValueError, match="already exists"):
        ops.init_environment(SimpleNamespace(env=env))
    assert env.read_text() == "existing"


def test_init_rejects_missing_admin_password_before_creating_anything(tmp_path, monkeypatch):
    monkeypatch.delenv("IPRESS_INITIAL_ADMIN_PASSWORD", raising=False)
    env = tmp_path / "production.env"
    with pytest.raises(ValueError, match="INITIAL_ADMIN_PASSWORD"):
        ops.init_environment(
            SimpleNamespace(
                env=env, domain="example.org", project="ipress_prod", admin_username="admin"
            )
        )
    assert list(tmp_path.iterdir()) == []
