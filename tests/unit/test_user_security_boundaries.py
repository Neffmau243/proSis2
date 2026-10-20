"""Administrator and credential-change paths outside the successful HTTP flow."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

import app.services.user as module
from app.exceptions import AuthenticationError, AuthorizationError, ConflictError, NotFoundError
from app.schemas.auth import PasswordChangeRequest, PasswordResetRequest, UserRolesUpdate


@pytest.fixture
def scene():
    session, repository = Mock(), Mock()
    user = SimpleNamespace(
        id=7,
        nombre_usuario="cuenta",
        profesional_id=3,
        activo=True,
        password_hash="old-hash",
        version_credenciales=2,
        roles=[SimpleNamespace(codigo="ADMIN")],
        roles_usuario=[],
        ultimo_acceso_at=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    repository.find_by_id.return_value = user
    repository.lock_active_admin_ids.return_value = [7, 9]
    repository.find_roles_by_codes.return_value = [SimpleNamespace(codigo="ADMIN")]
    service = module.UserService(session)
    service._users = repository
    return service, repository, session, user


@pytest.mark.parametrize("operation", ["roles", "deactivate", "reset", "own_password"])
def test_missing_account_is_rejected_before_writes(scene, operation):
    service, repository, session, _ = scene
    repository.find_by_id.return_value = None
    with pytest.raises(AuthenticationError if operation == "own_password" else NotFoundError):
        if operation == "roles":
            service.assign_roles(
                7, UserRolesUpdate(roles=["ADMIN"]), actor_id=9, actor_roles=["ADMIN"]
            )
        elif operation == "deactivate":
            service.deactivate(7, actor_id=9, actor_roles=["ADMIN"])
        elif operation == "reset":
            service.reset_password(
                7,
                PasswordResetRequest(new_password="87654321", new_password_confirmation="87654321"),
                actor_id=9,
                actor_roles=["ADMIN"],
            )
        else:
            service.change_own_password(
                PasswordChangeRequest(
                    current_password="12345678",
                    new_password="87654321",
                    new_password_confirmation="87654321",
                ),
                actor_id=7,
            )
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_role_reassignment_commits_with_no_audit_callback_and_maps_existing_entity(scene):
    service, repository, session, user = scene
    repository.find_by_id.side_effect = [user, None]
    response = service.assign_roles(
        7, UserRolesUpdate(roles=["ADMIN"]), actor_id=9, actor_roles=["ADMIN"]
    )
    assert response.id == 7 and response.roles == ["ADMIN"]
    repository.replace_roles.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "problem,code",
    [("unknown_role", "ROL_NO_ENCONTRADO"), ("inactive_professional", "PROFESIONAL_NO_ACTIVO")],
)
def test_role_resolution_rejects_missing_catalog_or_inactive_professional(scene, problem, code):
    service, repository, session, _ = scene
    repository.find_roles_by_codes.return_value = (
        [] if problem == "unknown_role" else [SimpleNamespace(codigo="PROFESIONAL")]
    )
    repository.get_active_professional.return_value = None
    with pytest.raises(NotFoundError) as error:
        service.assign_roles(
            7, UserRolesUpdate(roles=["PROFESIONAL"]), actor_id=9, actor_roles=["ADMIN"]
        )
    assert error.value.code == code
    session.commit.assert_not_called()


def test_clinical_user_cannot_modify_roles_or_reach_repository(scene):
    service, repository, session, _ = scene
    with pytest.raises(AuthorizationError):
        service.assign_roles(
            7, UserRolesUpdate(roles=["ADMIN"]), actor_id=9, actor_roles=["PROFESIONAL"]
        )
    repository.lock_active_admin_ids.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize("integrity", [False, True])
def test_role_persistence_failure_rolls_back(scene, integrity):
    service, _, session, _ = scene
    failure = (
        IntegrityError("update", {}, Exception("constraint"))
        if integrity
        else RuntimeError("storage error")
    )
    session.flush.side_effect = failure
    with pytest.raises(ConflictError if integrity else RuntimeError):
        service.assign_roles(7, UserRolesUpdate(roles=["ADMIN"]), actor_id=9, actor_roles=["ADMIN"])
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "audit_enabled,commit_fails", [(False, False), (True, False), (True, True)]
)
def test_credential_change_increments_version_audits_without_password_and_handles_failure(
    scene, monkeypatch, audit_enabled, commit_fails
):
    service, _, session, user = scene
    audit = Mock() if audit_enabled else None
    service._audit = audit
    monkeypatch.setattr(module, "verify_password", Mock(side_effect=[True, False]))
    monkeypatch.setattr(module, "hash_password", lambda value: "new-hash")
    command = PasswordChangeRequest(
        current_password="12345678", new_password="87654321", new_password_confirmation="87654321"
    )
    if commit_fails:
        session.commit.side_effect = RuntimeError("commit error")
        with pytest.raises(RuntimeError, match="commit error"):
            service.change_own_password(command, actor_id=7)
        session.rollback.assert_called_once()
    else:
        service.change_own_password(command, actor_id=7)
    assert user.version_credenciales == 3 and user.password_hash == "new-hash"
    if audit is not None:
        payload = audit.call_args.kwargs
        assert payload["action"] == "PASSWORD_CHANGE"
        assert "87654321" not in str(payload) and "new-hash" not in str(payload)
