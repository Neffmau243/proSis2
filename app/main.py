"""FastAPI application factory and HTTP cross-cutting configuration."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.exceptions import register_exception_handlers

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

logger = logging.getLogger(__name__)


def _request_id_from(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if _SAFE_REQUEST_ID.fullmatch(supplied):
        return supplied
    return uuid4().hex


def _frontend_directory(settings: Settings) -> Path | None:
    """Resolve the configured SPA build directory when it actually exists."""

    configured = Path(settings.frontend_dist_dir)
    directory = (
        configured
        if configured.is_absolute()
        else Path(__file__).resolve().parent.parent / configured
    )
    if directory.is_dir():
        return directory
    return None


def _reserved_prefixes(settings: Settings) -> tuple[str, ...]:
    """URL prefixes owned by the API and its documentation.

    A request below one of these must keep receiving the JSON error envelope;
    it is never resolved as a client-side SPA route.
    """

    prefixes = {settings.api_v1_prefix.strip("/")}
    for url in (settings.docs_url, settings.redoc_url, settings.openapi_url):
        if url:
            prefixes.add(url.strip("/"))
    return tuple(sorted(prefix for prefix in prefixes if prefix))


def _mount_frontend(application: FastAPI, settings: Settings) -> None:
    """Serve the built SPA from the same origin as the API.

    The Vite build is served from ``/assets`` and every other non-API GET falls
    back to ``index.html`` so Vue Router (history mode) can resolve its own
    routes.  The catch-all is a GET route instead of a root mount precisely so
    a wrong method on an API path keeps answering 405 instead of being
    swallowed as a client-side route.  It is hidden from the OpenAPI schema.
    """

    directory = _frontend_directory(settings)
    if directory is None:
        logger.warning(
            "SPA build not found at %s; serving the API only. "
            "Run 'npm run build' inside frontend/ to serve the interface.",
            settings.frontend_dist_dir,
        )
        return

    assets = directory / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index_file = directory / "index.html"
    reserved = _reserved_prefixes(settings)

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        normalized = full_path.strip("/")
        for prefix in reserved:
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                raise HTTPException(
                    status_code=404,
                    detail="El recurso solicitado no fue encontrado.",
                )

        candidate = (directory / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(directory.resolve()):
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app() -> FastAPI:
    """Build the API without opening a database connection at import time."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
    )

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    @application.middleware("http")
    async def attach_request_id(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request.state.request_id = _request_id_from(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    # The SPA is registered last so the API prefix and the documentation keep
    # precedence.  Without a build the application still boots and serves the
    # API only, which is the normal state while developing with the Vite dev
    # server on another port.
    if settings.serve_frontend:
        _mount_frontend(application, settings)

    return application


app = create_app()
