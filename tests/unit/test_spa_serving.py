"""Single-server composition: the SPA build and the API share one origin.

The frontend job and the backend job run separately in CI, so the backend
checkout has no ``frontend/dist``.  These tests build their own throwaway build
directory and point the application at it, which also proves the fallback does
not disturb the API's error contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def spa_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!DOCTYPE html><div id=\"app\"></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

    monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist))
    monkeypatch.setenv("SERVE_FRONTEND", "true")
    get_settings.cache_clear()
    try:
        yield TestClient(create_app())
    finally:
        get_settings.cache_clear()


def test_client_routes_fall_back_to_the_spa(spa_client: TestClient) -> None:
    root = spa_client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]
    assert "id=\"app\"" in root.text

    # Vue Router history mode: deep links must return the shell, not a 404.
    deep = spa_client.get("/atenciones/42")
    assert deep.status_code == 200
    assert deep.text == root.text
    assert deep.headers.get("X-Request-ID")


def test_assets_are_served_from_the_build(spa_client: TestClient) -> None:
    response = spa_client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('ok')"


def test_api_keeps_precedence_and_its_error_envelope(spa_client: TestClient) -> None:
    assert spa_client.get("/api/v1/health").json() == {"status": "ok"}

    missing = spa_client.get("/api/v1/no-existe")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    wrong_method = spa_client.delete("/api/v1/health")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_spa_fallback_is_hidden_from_openapi(spa_client: TestClient) -> None:
    schema = spa_client.get("/openapi.json").json()
    assert not any("full_path" in path for path in schema["paths"])


def test_without_a_build_only_the_api_is_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("SERVE_FRONTEND", "true")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.get("/api/v1/health").status_code == 200
        # No SPA route is registered, so a client route resolves as a missing API path.
        assert client.get("/login").status_code == 404
    finally:
        get_settings.cache_clear()
