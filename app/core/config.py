"""Application configuration loaded from environment variables.

This module deliberately contains no domain rules.  Its only responsibility is
to turn deployment configuration into a typed, validated object that the rest
of the application can depend on.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# This value is acceptable only for a local developer machine.  Production
# validation below prevents an application from starting with it.
_DEVELOPMENT_SECRET_KEY = "local-development-key-change-before-deployment-2026"
_PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod"})

# These values appear in starter files, common tutorials, and previous local
# deployments.  They are deliberately accepted only outside production so a
# configuration typo cannot turn a published placeholder into the JWT signing
# key for a clinical system.
_INSECURE_SECRET_KEY_VALUES = frozenset(
    {
        _DEVELOPMENT_SECRET_KEY,
        "change-me",
        "changeme",
        "secret",
        "secret-key",
        "default-secret-key",
        "your-secret-key",
        "your-secret-key-here",
    }
)
_INSECURE_SECRET_KEY_MARKERS = (
    "change-before-deployment",
    "change-me",
    "pon_aqui",
    "replace-with",
    "your-secret",
    "example-secret",
    "default-secret",
)


class Settings(BaseSettings):
    """Typed settings for the API and its MySQL connection."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # pydantic-settings matches environment variables case-insensitively
    # (case_sensitive=False), so APP_NAME/MYSQL_HOST/... resolve to these field
    # names without explicit aliases.  Avoiding validation_alias keeps the
    # field names usable as __init__ keyword arguments instead of silently
    # dropping them.
    app_name: str = Field(default="Sistema de Salud IPRESS API")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    api_v1_prefix: str = Field(default="/api/v1")

    # DATABASE_URL is useful in containers.  When it is absent, the individual
    # MYSQL_* settings below are combined into a SQLAlchemy PyMySQL URL.
    database_url: str | None = Field(default=None)
    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_user: str = Field(default="root")
    mysql_password: SecretStr = Field(default=SecretStr(""))
    mysql_database: str = Field(default="sistema_salud_ipress")
    sqlalchemy_echo: bool = Field(default=False)
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_recycle_seconds: int = Field(
        default=1800,
        ge=60,
        le=86_400,
    )

    secret_key: SecretStr = Field(default=SecretStr(_DEVELOPMENT_SECRET_KEY))
    jwt_algorithm: str = Field(default="HS256")
    jwt_issuer: str = Field(default="sistema-salud-ipress")
    jwt_audience: str = Field(default="sistema-salud-ipress-api")
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
    )
    bcrypt_rounds: int = Field(default=12, ge=10, le=16)
    login_rate_limit_attempts: int = Field(
        default=5,
        ge=1,
        le=100,
    )
    login_rate_limit_window_seconds: int = Field(
        default=900,
        ge=1,
        le=86_400,
    )
    login_lock_base_seconds: int = Field(
        default=60,
        ge=1,
        le=86_400,
    )
    login_lock_max_seconds: int = Field(
        default=3600,
        ge=1,
        le=604_800,
    )

    # CORS is off unless origins are explicitly configured.  A frontend can
    # supply JSON (recommended) or a comma-separated list in its .env file.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    cors_allow_headers: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID"],
    )

    docs_url: str | None = Field(default="/docs")
    redoc_url: str | None = Field(default="/redoc")
    openapi_url: str | None = Field(default="/openapi.json")

    # Single-server deployment: when the SPA has been built (``npm run build``)
    # Uvicorn serves it from the same origin as the API, so no second web
    # server or CORS entry is needed.  Directories are resolved relative to the
    # repository root; an absolute path is also accepted.
    serve_frontend: bool = Field(default=True)
    frontend_dist_dir: str = Field(default="frontend/dist")

    @field_validator("database_url")
    @classmethod
    def validate_mysql_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.startswith("mysql"):
            raise ValueError("DATABASE_URL debe usar un dialecto MySQL.")
        return normalized

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/"):
            raise ValueError("API_V1_PREFIX debe comenzar con '/'.")
        if normalized != "/" and normalized.endswith("/"):
            normalized = normalized.rstrip("/")
        return normalized

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM debe ser HS256, HS384 o HS512.")
        return normalized

    @field_validator("jwt_issuer", "jwt_audience")
    @classmethod
    def validate_jwt_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("JWT_ISSUER y JWT_AUDIENCE no pueden estar vacíos.")
        return normalized

    @field_validator("cors_origins", "cors_allow_methods", "cors_allow_headers", mode="before")
    @classmethod
    def parse_list_setting(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError("La configuración de lista no contiene JSON válido.") from exc
            else:
                value = raw.split(",")
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("La configuración debe ser una lista o texto separado por comas.")
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        secret = self.secret_key.get_secret_value()
        if len(secret) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres.")
        normalized_secret = secret.strip().casefold()
        if self.environment.strip().casefold() in _PRODUCTION_ENVIRONMENTS and (
            normalized_secret in _INSECURE_SECRET_KEY_VALUES
            or any(marker in normalized_secret for marker in _INSECURE_SECRET_KEY_MARKERS)
        ):
            raise ValueError(
                "SECRET_KEY de producción debe ser una clave única y no puede usar valores plantilla."
            )
        if self.login_lock_max_seconds < self.login_lock_base_seconds:
            raise ValueError(
                "LOGIN_LOCK_MAX_SECONDS debe ser mayor o igual a LOGIN_LOCK_BASE_SECONDS."
            )
        if "*" in self.cors_origins and self.cors_allow_credentials:
            raise ValueError(
                "CORS_ORIGINS no puede contener '*' cuando CORS_ALLOW_CREDENTIALS=true."
            )
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the MySQL URL used by the synchronous SQLAlchemy engine."""

        if self.database_url:
            return self.database_url

        user = quote_plus(self.mysql_user)
        password = self.mysql_password.get_secret_value()
        credentials = user
        if password:
            credentials = f"{user}:{quote_plus(password)}"
        database = quote_plus(self.mysql_database)
        return (
            f"mysql+pymysql://{credentials}@{self.mysql_host}:{self.mysql_port}/"
            f"{database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Tests that change environment variables can call ``get_settings.cache_clear``
    before constructing the application.
    """

    return Settings()
