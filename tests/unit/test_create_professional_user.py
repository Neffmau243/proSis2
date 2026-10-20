"""Clinical account CLI validation and persistence without opening an application database."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.scripts.create_professional_user as script
from app.models.audit import AuditLog
from app.models.security import User, UserRole


@pytest.fixture
def scene(monkeypatch):
    session = Mock()
    professional = SimpleNamespace(id=3, nombre_completo="Profesional de prueba")
    role = SimpleNamespace(id=2)
    session.scalar.side_effect = [None, role, professional, None]
    added = []
    session.add.side_effect = added.append

    def flush():
        for entity in added:
            if isinstance(entity, User):
                entity.id = 7

    session.flush.side_effect = flush
    connect = Mock(return_value=session)
    monkeypatch.setattr(script, "SessionLocal", connect)
    monkeypatch.setattr(script, "hash_password", lambda value: "hashed-for-test")
    return SimpleNamespace(
        session=session, professional=professional, role=role, added=added, connect=connect
    )


@pytest.mark.parametrize("document", [None, " 00000001 "])
def test_new_account_is_linked_hashed_audited_and_committed(scene, document):
    assert script.create_professional_user(" clinico ", "12345678", numero_documento=document) == 7
    user, role, audit = scene.added
    assert isinstance(user, User) and isinstance(role, UserRole) and isinstance(audit, AuditLog)
    assert user.nombre_usuario == "clinico" and user.profesional_id == 3
    assert user.password_hash == "hashed-for-test"
    assert role.usuario_id == 7 and role.rol_id == 2
    assert audit.datos_nuevos["roles"] == ["PROFESIONAL"]
    assert "12345678" not in str(audit.datos_nuevos)
    scene.session.commit.assert_called_once()
    scene.session.close.assert_called_once()


@pytest.mark.parametrize("username,password", [(" a ", "12345678"), ("clinico", "not-valid")])
def test_invalid_credentials_never_open_a_session(scene, username, password):
    with pytest.raises(ValueError):
        script.create_professional_user(username, password)
    scene.connect.assert_not_called()


@pytest.mark.parametrize(
    "problem,message",
    [
        ("duplicate", "ya existe"),
        ("role", "rol PROFESIONAL"),
        ("document", "No existe un profesional"),
        ("unassigned", "No hay profesionales libres"),
        ("linked", "ya está vinculado"),
    ],
)
def test_unavailable_identity_or_role_rolls_back_and_closes(scene, problem, message):
    outputs = {
        "duplicate": [7],
        "role": [None, None],
        "document": [None, scene.role, None],
        "unassigned": [None, scene.role, None],
        "linked": [
            None,
            scene.role,
            scene.professional,
            SimpleNamespace(nombre_usuario="existente"),
        ],
    }
    scene.session.scalar.side_effect = outputs[problem]
    with pytest.raises((RuntimeError, ValueError), match=message):
        script.create_professional_user(
            "clinico", "12345678", numero_documento="00000001" if problem == "document" else None
        )
    scene.session.rollback.assert_called_once()
    scene.session.close.assert_called_once()
    scene.session.commit.assert_not_called()
    assert scene.added == []


def test_failed_commit_does_not_report_a_successful_creation(scene):
    scene.session.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError, match="commit failed"):
        script.create_professional_user("clinico", "12345678")
    scene.session.rollback.assert_called_once()
    scene.session.close.assert_called_once()


@pytest.mark.parametrize("interactive", [True, False])
def test_cli_accepts_hidden_confirmation_or_explicit_password(monkeypatch, capsys, interactive):
    create = Mock(return_value=7)
    prompt = Mock(return_value="12345678")
    monkeypatch.setattr(script, "create_professional_user", create)
    monkeypatch.setattr(script, "getpass", prompt)
    args = ["create_professional_user", "--username", "clinico", "--documento", "00000001"]
    if not interactive:
        args += ["--password", "12345678"]
    monkeypatch.setattr("sys.argv", args)
    script.main()
    create.assert_called_once_with("clinico", "12345678", numero_documento="00000001")
    assert prompt.call_count == (2 if interactive else 0)
    assert "creado con id 7" in capsys.readouterr().out


def test_cli_mismatched_confirmation_never_creates_account(monkeypatch):
    monkeypatch.setattr("sys.argv", ["create_professional_user", "--username", "clinico"])
    monkeypatch.setattr(script, "getpass", Mock(side_effect=["12345678", "87654321"]))
    create = Mock()
    monkeypatch.setattr(script, "create_professional_user", create)
    with pytest.raises(ValueError, match="no coinciden"):
        script.main()
    create.assert_not_called()
