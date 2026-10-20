"""Shared append-only audit writer used inside service transactions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

_SENSITIVE_KEY_PARTS = frozenset({"password", "secret", "token", "credential", "authorization"})


class AuditService:
    """Stages a sanitized audit record without committing the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        actor_id: int | None,
        action: str,
        table_name: str,
        record_id: int | None,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
    ) -> None:
        self._session.add(
            AuditLog(
                usuario_id=actor_id,
                tabla_nombre=table_name,
                registro_id=record_id,
                accion=action,
                datos_anteriores=self._sanitize(before),
                datos_nuevos=self._sanitize(after),
            )
        )

    def _sanitize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Mapping):
            safe: dict[str, Any] = {}
            for key, child in value.items():
                normalized_key = str(key).lower()
                safe[str(key)] = (
                    "[REDACTED]"
                    if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)
                    else self._sanitize(child)
                )
            return safe
        if isinstance(value, list | tuple):
            return [self._sanitize(item) for item in value]
        return value
