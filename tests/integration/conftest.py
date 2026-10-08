"""Opt-in MySQL integration fixtures.

Set TEST_DATABASE_URL to a disposable database whose name contains `test`.
This guard ensures the test suite never migrates or drops a production schema.

The fixtures below build a complete clinical scene (ubigeo, establishment,
professional, office, ADMIN and PROFESIONAL accounts) so the HTTP layer can be
exercised end to end: router -> controller -> service -> repository -> MySQL.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from itertools import count
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_password
from app.models.organization import Establishment, Office, OfficeProfessional, Ubigeo
from app.models.patient import RiskGroup
from app.models.security import Professional, Role, User, UserRole

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Every account built by these fixtures shares this password, which must keep
#: satisfying the eight-digit credential contract of the API.
TEST_PASSWORD = "12345678"

#: Prefix exposed by ``settings.api_v1_prefix``.
API = "/api/v1"

#: ``ubigeos.codigo`` is a six-character primary key.  Deriving it from a
#: session-wide counter (instead of four random hex characters) keeps every
#: scene unique: random codes collided often enough to make the suite flaky.
_UBIGEO_CODES = count(900_000)


@pytest.fixture(scope="session")
def migrated_mysql_engine() -> Engine:
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("Defina TEST_DATABASE_URL para ejecutar integración MySQL.")
    parsed = make_url(test_url)
    if not parsed.drivername.startswith("mysql") or not parsed.database or "test" not in parsed.database.lower():
        raise RuntimeError("TEST_DATABASE_URL debe apuntar a una base MySQL desechable cuyo nombre incluya 'test'.")

    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    get_settings.cache_clear()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    # Start from a known state.  An interrupted run leaves its rows behind and
    # the next session would then fail on duplicated unique keys instead of
    # testing the application.
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(test_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_settings.cache_clear()


@pytest.fixture
def db_session(migrated_mysql_engine: Engine) -> Iterator[Session]:
    """One session per test, shared with the API through ``get_db``."""

    with Session(migrated_mysql_engine) as session:
        yield session


@pytest.fixture
def api_client(db_session: Session) -> Iterator[TestClient]:
    """TestClient whose request session is the test session, never the app one."""

    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@dataclass(frozen=True)
class ClinicScene:
    """Minimal persisted world required to call every documented endpoint."""

    admin_client: TestClient
    professional_client: TestClient
    anonymous_client: TestClient
    admin_id: int
    admin_username: str
    professional_user_id: int
    professional_username: str
    profesional_id: int
    establecimiento_id: int
    consultorio_id: int
    ubigeo_codigo: str
    codigo_renaes: str
    suffix: str


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _authenticated(client: TestClient, username: str) -> TestClient:
    response = client.post(
        f"{API}/auth/login",
        json={"nombre_usuario": username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    authenticated = TestClient(client.app)
    authenticated.headers.update({"Authorization": f"Bearer {token}"})
    return authenticated


@pytest.fixture
def clinic_scene(db_session: Session, api_client: TestClient) -> ClinicScene:
    """Persist a scene and return one authenticated client per role.

    Catalog rows (ubigeo, establishment, professional, office) are inserted
    through the ORM because the API exposes no creation endpoint for them;
    users are authenticated through the real login endpoint.
    """

    session = db_session
    suffix = uuid4().hex[:8]

    ubigeo = Ubigeo(
        codigo=f"{next(_UBIGEO_CODES):06d}",
        departamento="AREQUIPA",
        provincia="AREQUIPA",
        distrito="CERCADO",
    )
    session.add(ubigeo)
    session.flush()

    codigo_renaes = f"{next(_UBIGEO_CODES):08d}"
    establecimiento = Establishment(
        nombre=f"CS Integración {suffix}",
        codigo_renaes=codigo_renaes,
        ubigeo_codigo=ubigeo.codigo,
        activo=True,
    )
    session.add(establecimiento)
    session.flush()

    professional = Professional(
        nombre_completo=f"Profesional Integración {suffix}",
        colegiatura=f"CMP-{suffix}",
    )
    session.add(professional)
    session.flush()

    consultorio = Office(
        establecimiento_id=establecimiento.id,
        codigo=f"CON-{suffix}",
        nombre=f"Consultorio {suffix}",
        activo=True,
    )
    session.add(consultorio)
    session.flush()
    session.add(
        OfficeProfessional(
            consultorio_id=consultorio.id,
            profesional_id=professional.id,
            fecha_inicio=date(2020, 1, 1),
            es_responsable=True,
        )
    )

    admin = User(
        nombre_usuario=f"admin-{suffix}",
        password_hash=hash_password(TEST_PASSWORD),
    )
    professional_user = User(
        nombre_usuario=f"prof-{suffix}",
        password_hash=hash_password(TEST_PASSWORD),
        profesional_id=professional.id,
    )
    session.add_all([admin, professional_user])
    session.flush()

    admin_role = session.scalar(select(Role).where(Role.codigo == "ADMIN"))
    professional_role = session.scalar(select(Role).where(Role.codigo == "PROFESIONAL"))
    assert admin_role is not None and professional_role is not None, "Las migraciones deben sembrar los roles."
    session.add_all(
        [
            UserRole(usuario_id=admin.id, rol_id=admin_role.id),
            UserRole(usuario_id=professional_user.id, rol_id=professional_role.id),
        ]
    )
    session.commit()

    return ClinicScene(
        admin_client=_authenticated(api_client, admin.nombre_usuario),
        professional_client=_authenticated(api_client, professional_user.nombre_usuario),
        anonymous_client=TestClient(api_client.app),
        admin_id=admin.id,
        admin_username=admin.nombre_usuario,
        professional_user_id=professional_user.id,
        professional_username=professional_user.nombre_usuario,
        profesional_id=professional.id,
        establecimiento_id=establecimiento.id,
        consultorio_id=consultorio.id,
        ubigeo_codigo=ubigeo.codigo,
        codigo_renaes=codigo_renaes,
        suffix=suffix,
    )


@pytest.fixture(scope="session")
def api_prefix() -> str:
    return API


@pytest.fixture(scope="session")
def scene_password() -> str:
    return TEST_PASSWORD


@pytest.fixture
def create_professional(db_session: Session) -> Callable[..., Professional]:
    """Persist a professional row; ``uq_usuarios_profesional`` allows one by account."""

    def factory(**overrides: object) -> Professional:
        suffix = uuid4().hex[:8]
        professional = Professional(
            nombre_completo=f"Profesional {suffix}",
            colegiatura=f"CMP-{suffix}",
            **overrides,
        )
        db_session.add(professional)
        db_session.commit()
        return professional

    return factory


@dataclass(frozen=True)
class Account:
    """A persisted account plus the client that already carries its token."""

    client: TestClient
    user_id: int
    username: str


@pytest.fixture
def create_account(
    db_session: Session, api_client: TestClient
) -> Callable[..., Account]:
    """Persist a user with roles and return it authenticated through login."""

    def factory(
        *,
        roles: tuple[str, ...] = ("PROFESIONAL",),
        profesional_id: int | None = None,
        username: str | None = None,
    ) -> Account:
        name = username or f"cuenta-{uuid4().hex[:8]}"
        user = User(
            nombre_usuario=name,
            password_hash=hash_password(TEST_PASSWORD),
            profesional_id=profesional_id,
        )
        db_session.add(user)
        db_session.flush()
        role_rows = db_session.scalars(select(Role).where(Role.codigo.in_(roles))).all()
        assert len(role_rows) == len(set(roles)), f"Roles inexistentes: {roles}"
        db_session.add_all(
            [UserRole(usuario_id=user.id, rol_id=role.id) for role in role_rows]
        )
        db_session.commit()
        return Account(
            client=_authenticated(api_client, name),
            user_id=user.id,
            username=name,
        )

    return factory


@pytest.fixture
def create_risk_group(db_session: Session) -> Callable[..., RiskGroup]:
    """The baseline migration seeds no risk group, so tests register their own."""

    def factory(**overrides: object) -> RiskGroup:
        suffix = uuid4().hex[:8]
        group = RiskGroup(
            codigo=f"RG-{suffix}",
            nombre=f"Grupo de riesgo {suffix}",
            **overrides,
        )
        db_session.add(group)
        db_session.commit()
        return group

    return factory


@pytest.fixture
def create_patient() -> Callable[..., dict]:
    """Create patients through the API and return their JSON representation."""

    def factory(client: TestClient, **overrides: object) -> dict:
        payload: dict[str, object] = {
            "tipo_documento_codigo": "DNI",
            "numero_documento": str(uuid4().int)[:8],
            "fecha_nacimiento": "1990-05-10",
            "apellido_paterno": "Quispe",
            "apellido_materno": "Mamani",
            "primer_nombre": "Ana",
            "otros_nombres": "María",
            "sexo_codigo": "F",
            "historia_clinica": _unique("HC"),
        }
        payload.update(overrides)
        response = client.post(f"{API}/patients", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return factory
