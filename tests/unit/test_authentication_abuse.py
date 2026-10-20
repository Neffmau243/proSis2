"""Login boundaries: durable locks, privacy, expiration and failed commits."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

import app.services.auth as auth
from app.exceptions import AuthenticationError
from app.schemas.auth import LoginRequest

NOW = datetime(2026, 10, 20, 12)


@pytest.fixture
def login_scene(monkeypatch):
    settings = SimpleNamespace(
        secret_key=SecretStr("authentication-test-key-with-32-characters"),
        login_rate_limit_attempts=3,
        login_rate_limit_window_seconds=90,
        login_lock_base_seconds=10,
        login_lock_max_seconds=40,
        access_token_expire_minutes=5,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    verify = Mock(return_value=True)
    monkeypatch.setattr(auth, "verify_password", verify)
    monkeypatch.setattr(auth, "create_access_token", lambda **kwargs: "signed-test-token")
    session, repository, audit = Mock(), Mock(), Mock()
    user = SimpleNamespace(
        id=7,
        nombre_usuario="clinico",
        password_hash="hash-only",
        activo=True,
        roles=[SimpleNamespace(codigo="PROFESIONAL")],
        version_credenciales=2,
        intentos_fallidos_inicio_sesion=0,
        bloqueado_inicio_sesion_hasta=None,
        ultimo_intento_fallido_inicio_sesion_at=None,
    )
    repository.find_by_username.return_value = user
    repository.find_login_rate_limit.return_value = None
    service = auth.AuthenticationService(session, audit=audit)
    service._users = repository
    monkeypatch.setattr(service, "_now", lambda: NOW)
    return SimpleNamespace(
        service=service,
        session=session,
        repository=repository,
        audit=audit,
        user=user,
        verify=verify,
        settings=settings,
    )


def command():
    return LoginRequest(nombre_usuario="clinico", password="12345678")


def test_active_source_limit_precedes_user_lookup_and_omits_personal_data(login_scene):
    scene = login_scene
    scene.repository.find_login_rate_limit.return_value = SimpleNamespace(
        bloqueado_hasta=NOW + timedelta(seconds=1, microseconds=1)
    )
    with pytest.raises(auth.LoginRateLimitError) as error:
        scene.service.login(command(), client_ip=" 192.0.2.17 ")
    assert error.value.retry_after_seconds == 2
    assert error.value.status_code == 429
    scene.repository.find_by_username.assert_not_called()
    scene.verify.assert_not_called()
    scene.session.commit.assert_called_once()
    payload = scene.audit.call_args.kwargs
    assert payload["after"]["motivo"] == "limite_de_tasa"
    assert "192.0.2.17" not in str(payload)
    assert "clinico" not in str(payload)
    assert "12345678" not in str(payload)


def test_locked_account_still_verifies_password_but_never_issues_token(login_scene):
    scene = login_scene
    scene.user.bloqueado_inicio_sesion_hasta = NOW + timedelta(seconds=20)
    with pytest.raises(AuthenticationError, match="Usuario o contraseña inválidos"):
        scene.service.login(command())
    scene.verify.assert_called_once_with("12345678", "hash-only")
    assert scene.audit.call_args.kwargs["after"]["motivo"] == "cuenta_bloqueada"
    scene.session.commit.assert_called_once()
    scene.repository.add_login_rate_limit.assert_not_called()


@pytest.mark.parametrize("user_kind", ["unknown", "inactive", "wrong_password"])
@pytest.mark.parametrize("threshold", [1, 3])
def test_failed_credentials_remain_generic_and_count_attempts(login_scene, user_kind, threshold):
    scene = login_scene
    scene.settings.login_rate_limit_attempts = threshold
    if user_kind == "unknown":
        scene.repository.find_by_username.return_value = None
    elif user_kind == "inactive":
        scene.user.activo = False
    else:
        scene.verify.return_value = False
    error_type = auth.LoginRateLimitError if threshold == 1 else AuthenticationError
    with pytest.raises(error_type):
        scene.service.login(command(), client_ip="")
    limiter = scene.repository.add_login_rate_limit.call_args.args[0]
    assert limiter.intentos == 1
    assert len(limiter.clave_hash) == 64
    assert scene.audit.call_args.kwargs["after"]["motivo"] == "credenciales_invalidas"
    scene.session.commit.assert_called_once()
    assert scene.user.intentos_fallidos_inicio_sesion == (1 if user_kind == "wrong_password" else 0)


def test_threshold_uses_the_persisted_block_expiration(login_scene):
    scene = login_scene
    scene.verify.return_value = False
    limiter = SimpleNamespace(intentos=2, ventana_inicio_at=NOW, bloqueado_hasta=None)
    scene.repository.find_login_rate_limit.return_value = limiter
    with pytest.raises(auth.LoginRateLimitError) as error:
        scene.service.login(command())
    assert error.value.retry_after_seconds == 90
    assert limiter.intentos == 3


@pytest.mark.parametrize("expired_block", [True, False])
def test_expired_limits_reset_and_valid_login_clears_account_failures(login_scene, expired_block):
    scene = login_scene
    limiter = SimpleNamespace(
        intentos=20,
        ventana_inicio_at=NOW - timedelta(seconds=100),
        bloqueado_hasta=NOW if expired_block else None,
    )
    assert scene.service._register_limiter_failure(limiter, "key", NOW) is False
    assert limiter.intentos == 1 and limiter.bloqueado_hasta is None
    scene.repository.find_login_rate_limit.return_value = limiter
    scene.user.intentos_fallidos_inicio_sesion = 8
    scene.user.bloqueado_inicio_sesion_hasta = NOW
    scene.user.ultimo_intento_fallido_inicio_sesion_at = NOW - timedelta(seconds=2)
    response = scene.service.login(command())
    assert response.access_token == "signed-test-token"
    assert response.expires_in == 300
    assert response.roles == ["PROFESIONAL"]
    assert scene.user.intentos_fallidos_inicio_sesion == 0
    assert scene.user.ultimo_intento_fallido_inicio_sesion_at is None
    assert scene.user.bloqueado_inicio_sesion_hasta is None
    assert scene.user.ultimo_acceso_at == NOW
    scene.repository.delete_login_rate_limit.assert_called_once_with(limiter)
    assert scene.audit.call_args.kwargs["action"] == "LOGIN_SUCCESS"


def test_progressive_account_lock_is_capped_and_expires_after_quiet_window(login_scene):
    scene = login_scene
    user = scene.user
    for attempts, duration in [(3, 10), (4, 20), (5, 40), (30, 40)]:
        user.intentos_fallidos_inicio_sesion = attempts - 1
        user.ultimo_intento_fallido_inicio_sesion_at = NOW
        assert scene.service._register_account_failure(user, NOW)
        assert user.bloqueado_inicio_sesion_hasta == NOW + timedelta(seconds=duration)
    user.ultimo_intento_fallido_inicio_sesion_at = NOW - timedelta(seconds=90)
    assert scene.service._register_account_failure(user, NOW) is False
    assert user.intentos_fallidos_inicio_sesion == 1
    assert scene.service._seconds_until(None, NOW) == 90
    assert scene.service._seconds_until(NOW - timedelta(seconds=1), NOW) == 1


def test_failed_login_commit_rolls_back_without_returning_a_token(login_scene):
    scene = login_scene
    scene.session.commit.side_effect = RuntimeError("storage unavailable")
    with pytest.raises(RuntimeError, match="storage unavailable"):
        scene.service.login(command())
    scene.session.rollback.assert_called_once()
