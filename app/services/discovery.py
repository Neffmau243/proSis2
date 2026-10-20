"""Scoped application use cases for paginated patient and attention discovery."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from sqlalchemy.orm import Session

from app.mappers.attention import attention_to_response
from app.mappers.patient import patient_to_response
from app.repositories.discovery import (
    AttentionDiscoveryRepository,
    DiscoveryPage,
    PatientDiscoveryRepository,
)
from app.schemas.attention import AttentionResponse
from app.schemas.common import PageResponse
from app.schemas.discovery import AttentionSearchCriteria, PatientSearchCriteria
from app.schemas.patient import PatientResponse
from app.services.clinical_access import ClinicalAccessService

SourceT = TypeVar("SourceT")
ResultT = TypeVar("ResultT")


def _professional_scope(
    *,
    actor_id: int,
    actor_roles: Iterable[str],
    active_professional_id_for_user: int | None,
    allow_administrator: bool = True,
) -> int | None:
    return ClinicalAccessService.search_professional(
        actor_roles=actor_roles,
        professional_id=active_professional_id_for_user,
        allow_administrator=allow_administrator,
    )


class PatientDiscoveryService:
    """Searches patients without bypassing clinical ownership boundaries."""

    def __init__(
        self,
        session: Session,
        *,
        repository: PatientDiscoveryRepository | None = None,
    ) -> None:
        self._repository = repository or PatientDiscoveryRepository(session)

    def search(
        self,
        criteria: PatientSearchCriteria,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
    ) -> PageResponse[PatientResponse]:
        professional_id = _professional_scope(
            actor_id=actor_id,
            actor_roles=actor_roles,
            active_professional_id_for_user=self._repository.active_professional_id_for_user(
                actor_id
            ),
        )
        establishment_ids = (
            self._repository.active_establishment_ids_for_professional(professional_id)
            if professional_id is not None
            else None
        )
        # A professional never receives logically deactivated registrations,
        # even if a caller sends incluir_inactivos=true.
        page = self._repository.search(
            criteria,
            professional_id=professional_id,
            establishment_ids=establishment_ids,
            include_inactive=criteria.incluir_inactivos and professional_id is None,
        )
        return _to_page(page, patient_to_response, limit=criteria.limit, offset=criteria.offset)


class AttentionDiscoveryService:
    """Reads the longitudinal attention history with the same scope rule."""

    def __init__(
        self,
        session: Session,
        *,
        repository: AttentionDiscoveryRepository | None = None,
    ) -> None:
        self._repository = repository or AttentionDiscoveryRepository(session)

    def search(
        self,
        criteria: AttentionSearchCriteria,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
    ) -> PageResponse[AttentionResponse]:
        professional_id = _professional_scope(
            actor_id=actor_id,
            actor_roles=actor_roles,
            active_professional_id_for_user=self._repository.active_professional_id_for_user(
                actor_id
            ),
            allow_administrator=False,
        )
        establishment_ids = (
            self._repository.active_establishment_ids_for_professional(professional_id)
            if professional_id is not None
            else None
        )
        page = self._repository.search(
            criteria,
            professional_id=professional_id,
            establishment_ids=establishment_ids,
        )
        return _to_page(page, attention_to_response, limit=criteria.limit, offset=criteria.offset)


def _to_page(
    page: DiscoveryPage[SourceT],
    mapper: Callable[[SourceT], ResultT],
    *,
    limit: int,
    offset: int,
) -> PageResponse[ResultT]:
    """Convert a repository result to the shared public pagination envelope."""

    items = [mapper(item) for item in page.items]
    return PageResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < page.total,
    )
