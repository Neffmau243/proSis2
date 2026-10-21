from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.scripts import container_healthcheck, create_admin


@pytest.mark.parametrize("active,is_admin", [(True, True), (False, True), (True, False)])
def test_restart_preserves_existing_credentials_and_never_grants_roles(
    monkeypatch, active, is_admin
):
    existing = SimpleNamespace(id=7, activo=active, password_hash="original-hash")
    session = MagicMock()
    session.scalar.side_effect = [existing, 1 if is_admin else None]
    monkeypatch.setattr(create_admin, "SessionLocal", lambda: session)
    if active and is_admin:
        assert create_admin.create_admin("admin", "87654321", if_not_exists=True) == 7
    else:
        with pytest.raises(ValueError, match="no es un ADMIN activo"):
            create_admin.create_admin("admin", "87654321", if_not_exists=True)
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.close.assert_called_once()
    assert existing.password_hash == "original-hash"


def test_healthcheck_requires_database_even_if_http_is_alive(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.status = 200
    monkeypatch.setattr(container_healthcheck, "urlopen", lambda *a, **kw: response)
    engine = MagicMock()
    engine.connect.side_effect = OSError("database offline")
    monkeypatch.setattr(container_healthcheck, "create_engine", lambda *a, **kw: engine)
    assert container_healthcheck.main() == 1
    engine.dispose.assert_called_once()


def test_healthcheck_http_failure_does_not_expose_connection_details(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise OSError("secret-connection-details")
    monkeypatch.setattr(container_healthcheck, "urlopen", fail)
    assert container_healthcheck.main() == 1
    assert "secret-connection-details" not in capsys.readouterr().out


def test_healthcheck_succeeds_only_after_authenticated_query(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.status = 200
    monkeypatch.setattr(container_healthcheck, "urlopen", lambda *a, **kw: response)
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.scalar.return_value = 1
    monkeypatch.setattr(container_healthcheck, "create_engine", lambda *a, **kw: engine)
    assert container_healthcheck.main() == 0
    engine.dispose.assert_called_once()
