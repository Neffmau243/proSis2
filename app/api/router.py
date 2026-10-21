"""Root router where feature routers are composed.

Feature modules can import ``include_feature_router`` from here during
application assembly; this keeps the core bootable before optional modules
such as pacientes or atenciones exist.
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from types import ModuleType

from fastapi import APIRouter

from app.api.contracts import documented_error_responses


# Every operation documents the exact envelope emitted by the centralized
# exception handlers.  ``APIRouter`` applies these responses while composing
# feature routers, so their OpenAPI model fields are built correctly too.
api_router = APIRouter(responses=documented_error_responses())


@api_router.get("/health", tags=["health"], summary="Estado del servicio")
def health_check() -> dict[str, str]:
    """Liveness endpoint that intentionally does not connect to MySQL."""

    return {"status": "ok"}


def include_feature_router(
    router: APIRouter,
    *,
    prefix: str = "",
    tags: Sequence[str] | None = None,
) -> None:
    """Attach a domain router when its module is available.

    The feature itself owns its endpoints; this module only performs HTTP
    composition.  Keeping the operation explicit avoids hiding import errors
    from a feature module behind a broad ``try/except ImportError``.
    """

    api_router.include_router(router, prefix=prefix, tags=list(tags) if tags else None)


def include_optional_feature_router(
    module_path: str,
    *,
    prefix: str = "",
    tags: Sequence[str] | None = None,
) -> None:
    """Import and compose a feature router only when its module exists.

    Missing optional feature modules are normal during incremental development.
    Import failures *inside* an existing feature are deliberately re-raised so
    dependency mistakes never disappear silently at startup.
    """

    try:
        module: ModuleType = import_module(module_path)
    except ModuleNotFoundError as exc:
        if exc.name == module_path or module_path.startswith(f"{exc.name}."):
            return
        raise

    router = getattr(module, "router", None)
    if not isinstance(router, APIRouter):
        raise TypeError(f"{module_path}.router debe ser una instancia de APIRouter.")
    include_feature_router(router, prefix=prefix, tags=tags)


# Feature modules may be delivered independently.  Keep these imports at the
# composition boundary so importing the core API remains safe before a module
# has been implemented.
include_optional_feature_router("app.controllers.patient")
include_optional_feature_router("app.controllers.patient_discovery")
include_optional_feature_router("app.controllers.auth")
include_optional_feature_router("app.controllers.catalog")
include_optional_feature_router("app.controllers.age_group")
include_optional_feature_router("app.controllers.attention_discovery")
include_optional_feature_router("app.controllers.attention")
include_optional_feature_router("app.controllers.document")
include_optional_feature_router("app.controllers.office")
include_optional_feature_router("app.controllers.professional")
include_optional_feature_router("app.controllers.staff_catalog")
