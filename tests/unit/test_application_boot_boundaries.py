"""Application startup must keep static-file and optional-feature failures visible."""

import importlib

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings

application = importlib.import_module("app.main")
composition = importlib.import_module("app.api.router")


def test_api_only_boot_and_empty_reserved_prefixes_are_supported(monkeypatch):
    settings = Settings(
        _env_file=None,
        serve_frontend=False,
        cors_origins=[],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    monkeypatch.setattr(application, "get_settings", lambda: settings)
    with TestClient(application.create_app()) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/admision").status_code == 404
    root_settings = settings.model_copy(update={"api_v1_prefix": "/"})
    assert application._reserved_prefixes(root_settings) == ()


def test_spa_without_assets_serves_public_files_but_never_api_prefix_or_outside_files(
    tmp_path, monkeypatch
):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<div>APP</div>", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("OUTSIDE", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        serve_frontend=True,
        frontend_dist_dir=str(dist),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        cors_origins=[],
    )
    monkeypatch.setattr(application, "get_settings", lambda: settings)
    with TestClient(application.create_app()) as client:
        assert client.get("/robots.txt").text == "User-agent: *"
        assert client.get("/admision").text == "<div>APP</div>"
        assert client.get("/api/v1").status_code == 404
        assert client.get("/%2e%2e/outside.txt").text == "<div>APP</div>"


def test_missing_internal_dependency_is_not_silently_treated_as_optional_feature(monkeypatch):
    failure = ModuleNotFoundError(
        "internal dependency missing", name="dependency_of_existing_feature"
    )

    def broken_import(name):
        raise failure

    monkeypatch.setattr(composition, "import_module", broken_import)
    with pytest.raises(ModuleNotFoundError) as error:
        composition.include_optional_feature_router("existing.feature")
    assert error.value is failure
