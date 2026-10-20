"""Authentication use cases, including durable login-abuse controls."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.domain.authorization import RolePermissionPolicy
from app.exceptions import AuthenticationError, DomainError
from app.models.security import LoginRateLimit, User
from app.repositories.user import UserRepository
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.services.audit import AuditService

# A valid bcrypt hash used only to keep the unknown-user path close to the
# timing of a real password check. It is not a credential and cannot grant
# access to any account.
_DUMMY_PASSWORD_HASH = "$2b$12$jK2yLcvkqRqONlqrQNBO7uBxr69DB5/JIfyn.kUNecVcdVSlWpu1."


class LoginRateLimitError(DomainError):
    """Publicly safe 429 response for throttled login attempts."""

    status_code = 429
    error_code = "LOGIN_RATE_LIMITED"
    default_message = "Demasiados intentos de inicio de sesión. Intente nuevamente más tarde."

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__(details={"retry_after_seconds": self.retry_after_seconds})


class AuthenticationService:
    def __init__(
        self,
        session: Session,
        permissions: RolePermissionPolicy | None = None,
        audit: Callable[..., None] | None = None,
    ) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._permissions = permissions or RolePermissionPolicy()
        self._audit = audit or AuditService(session).record

    def login(
        self,
        command: LoginRequest,
        *,
        client_ip: str | None = None,
    ) -> AccessTokenResponse:
        """Authenticate an active user while throttling and auditing attempts.

        Account locks are progressive and survive application restarts. A
        second persisted limiter keyed by HMAC(username, source IP) blocks a
        burst even when the account name does not exist. Neither raw IPs nor
        submitted passwords are written to the database or audit payloads.
        """

        now = self._now()
        username = command.nombre_usuario
        source = self._normalized_client_source(client_ip)
        username_fingerprint = self._fingerprint("login-username", username.casefold())
        source_fingerprint = self._fingerprint("login-source", source)
        limiter_key = self._fingerprint("login-rate-limit", username.casefold(), source)
        limiter = self._users.find_login_rate_limit(limiter_key, lock=True)

        if self._limiter_is_active(limiter, now):
            self._record_login_failure(
                user=None,
                username_fingerprint=username_fingerprint,
                source_fingerprint=source_fingerprint,
                reason="limite_de_tasa",
            )
            self._commit()
            raise LoginRateLimitError(self._seconds_until(limiter.bloqueado_hasta, now))

        user = self._users.find_by_username(username, lock=True)
        if self._account_is_locked(user, now):
            # Keep the locked-account path timing-close to a normal credential
            # check and return the same generic response as an unknown user.
            # The per-source limiter above is the only public 429 signal.
            verify_password(command.password, user.password_hash)
            self._record_login_failure(
                user=user,
                username_fingerprint=username_fingerprint,
                source_fingerprint=source_fingerprint,
                reason="cuenta_bloqueada",
            )
            self._commit()
            raise AuthenticationError("Usuario o contraseña inválidos.")

        password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
        password_is_valid = verify_password(command.password, password_hash)
        credentials_are_valid = bool(user is not None and user.activo and password_is_valid)
        if not credentials_are_valid:
            rate_limited = self._register_limiter_failure(limiter, limiter_key, now)
            self._register_account_failure(user, now)
            self._record_login_failure(
                user=user,
                username_fingerprint=username_fingerprint,
                source_fingerprint=source_fingerprint,
                reason="credenciales_invalidas",
            )
            self._commit()
            if rate_limited:
                active_limiter = limiter or self._users.find_login_rate_limit(limiter_key)
                raise LoginRateLimitError(
                    self._seconds_until(active_limiter.bloqueado_hasta, now)
                    if active_limiter is not None
                    else get_settings().login_rate_limit_window_seconds
                )
            # Do not distinguish unknown, inactive, or password-invalid users.
            raise AuthenticationError("Usuario o contraseña inválidos.")

        if limiter is not None:
            # A valid login clears only the matching username/source window;
            # account-level failures are reset separately below.
            self._users.delete_login_rate_limit(limiter)
        user.intentos_fallidos_inicio_sesion = 0
        user.bloqueado_inicio_sesion_hasta = None
        user.ultimo_intento_fallido_inicio_sesion_at = None
        user.ultimo_acceso_at = now

        roles = frozenset(role.codigo for role in user.roles)
        permissions = self._permissions.resolve(roles)
        token = create_access_token(
            user_id=user.id,
            username=user.nombre_usuario,
            roles=roles,
            permissions=permissions,
            credential_version=user.version_credenciales,
        )
        self._record_login_success(user=user, source_fingerprint=source_fingerprint)
        self._commit()
        return AccessTokenResponse(
            access_token=token,
            expires_in=get_settings().access_token_expire_minutes * 60,
            usuario_id=user.id,
            roles=sorted(roles),
            permisos=sorted(permissions),
        )

    def list_active_usernames(self) -> list[str]:
        """Return login-eligible accounts for the internal username selector."""

        return self._users.list_active_usernames()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalized_client_source(client_ip: str | None) -> str:
        normalized = client_ip.strip() if isinstance(client_ip, str) else ""
        return normalized or "unknown"

    @staticmethod
    def _seconds_until(value: datetime | None, now: datetime) -> int:
        if value is None:
            return get_settings().login_rate_limit_window_seconds
        return max(1, math.ceil((value - now).total_seconds()))

    @staticmethod
    def _account_is_locked(user: User | None, now: datetime) -> bool:
        return bool(
            user is not None
            and user.activo
            and user.bloqueado_inicio_sesion_hasta is not None
            and user.bloqueado_inicio_sesion_hasta > now
        )

    @staticmethod
    def _limiter_is_active(limiter: LoginRateLimit | None, now: datetime) -> bool:
        return bool(
            limiter is not None
            and limiter.bloqueado_hasta is not None
            and limiter.bloqueado_hasta > now
        )

    def _fingerprint(self, purpose: str, *values: str) -> str:
        key = get_settings().secret_key.get_secret_value().encode("utf-8")
        material = "\x1f".join((purpose, *values)).encode("utf-8")
        return hmac.new(key, material, hashlib.sha256).hexdigest()

    def _register_limiter_failure(
        self,
        limiter: LoginRateLimit | None,
        key_hash: str,
        now: datetime,
    ) -> bool:
        settings = get_settings()
        window = timedelta(seconds=settings.login_rate_limit_window_seconds)
        if limiter is None:
            limiter = LoginRateLimit(
                clave_hash=key_hash,
                ventana_inicio_at=now,
                intentos=0,
            )
            self._users.add_login_rate_limit(limiter)
        elif (
            limiter.bloqueado_hasta is not None and limiter.bloqueado_hasta <= now
        ) or now - limiter.ventana_inicio_at >= window:
            limiter.ventana_inicio_at = now
            limiter.intentos = 0
            limiter.bloqueado_hasta = None

        limiter.intentos += 1
        if limiter.intentos < settings.login_rate_limit_attempts:
            return False

        limiter.bloqueado_hasta = now + window
        return True

    def _register_account_failure(self, user: User | None, now: datetime) -> bool:
        if user is None or not user.activo:
            return False

        settings = get_settings()
        window = timedelta(seconds=settings.login_rate_limit_window_seconds)
        last_failure = user.ultimo_intento_fallido_inicio_sesion_at
        failures = user.intentos_fallidos_inicio_sesion
        if last_failure is None or now - last_failure >= window:
            failures = 0

        failures += 1
        user.intentos_fallidos_inicio_sesion = failures
        user.ultimo_intento_fallido_inicio_sesion_at = now
        if failures < settings.login_rate_limit_attempts:
            return False

        exponent = min(failures - settings.login_rate_limit_attempts, 16)
        lock_seconds = min(
            settings.login_lock_base_seconds * (2**exponent),
            settings.login_lock_max_seconds,
        )
        user.bloqueado_inicio_sesion_hasta = now + timedelta(seconds=lock_seconds)
        return True

    def _record_login_success(self, *, user: User, source_fingerprint: str) -> None:
        self._audit(
            actor_id=user.id,
            action="LOGIN_SUCCESS",
            table_name="autenticacion",
            record_id=user.id,
            before=None,
            after={"resultado": "exitoso", "origen_hash": source_fingerprint},
        )

    def _record_login_failure(
        self,
        *,
        user: User | None,
        username_fingerprint: str,
        source_fingerprint: str,
        reason: str,
    ) -> None:
        self._audit(
            actor_id=user.id if user is not None else None,
            action="LOGIN_FAILURE",
            table_name="autenticacion",
            record_id=user.id if user is not None else None,
            before=None,
            after={
                "resultado": "fallido",
                "motivo": reason,
                "usuario_hash": username_fingerprint,
                "origen_hash": source_fingerprint,
            },
        )

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
