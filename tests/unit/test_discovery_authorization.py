"""Discovery must honor clinical roles without widening the visibility scope."""

from unittest.mock import create_autospec

import pytest

from app.exceptions import AuthorizationError
from app.repositories.discovery import (
    AttentionDiscoveryRepository,
    DiscoveryPage,
    PatientDiscoveryRepository,
)
from app.schemas.discovery import AttentionSearchCriteria, PatientSearchCriteria
from app.services.discovery import AttentionDiscoveryService, PatientDiscoveryService


@pytest.mark.parametrize(
    "roles",
    [
        ["PROFESIONAL"],
        ["ADMIN", "PROFESIONAL"],
        ["PROFESIONAL", "ADMIN"],
        ["admin", "profesional"],
    ],
)
@pytest.mark.parametrize("establishment_ids", [[], [2]])
def test_attention_search_keeps_professional_scope_with_combined_roles(roles, establishment_ids):
    repository = create_autospec(AttentionDiscoveryRepository, instance=True)
    repository.active_professional_id_for_user.return_value = 7
    repository.active_establishment_ids_for_professional.return_value = establishment_ids
    repository.search.return_value = DiscoveryPage(items=[], total=0)
    # The client filter must not replace the authenticated professional's scope.
    criteria = AttentionSearchCriteria(profesional_id=99)

    result = AttentionDiscoveryService(None, repository=repository).search(
        criteria,
        actor_id=1,
        actor_roles=roles,
    )

    assert result.items == []
    assert result.total == 0
    repository.active_professional_id_for_user.assert_called_once_with(1)
    repository.active_establishment_ids_for_professional.assert_called_once_with(7)
    repository.search.assert_called_once_with(
        criteria,
        professional_id=7,
        establishment_ids=establishment_ids,
    )


@pytest.mark.parametrize(
    ("roles", "professional_id", "error_code"),
    [
        (["ADMIN"], 7, "ROL_CLINICO_REQUERIDO"),
        (["ADMIN"], None, "ROL_CLINICO_REQUERIDO"),
        ([], 7, "ROL_SIN_AMBITO_CLINICO"),
        (["AUDITOR"], 7, "ROL_SIN_AMBITO_CLINICO"),
        (["PROFESIONAL"], None, "USUARIO_PROFESIONAL_SIN_VINCULO"),
        (["ADMIN", "PROFESIONAL"], None, "USUARIO_PROFESIONAL_SIN_VINCULO"),
    ],
)
def test_attention_search_rejects_missing_clinical_role_or_active_link(
    roles, professional_id, error_code
):
    repository = create_autospec(AttentionDiscoveryRepository, instance=True)
    repository.active_professional_id_for_user.return_value = professional_id

    with pytest.raises(AuthorizationError) as error:
        AttentionDiscoveryService(None, repository=repository).search(
            AttentionSearchCriteria(),
            actor_id=1,
            actor_roles=roles,
        )

    assert error.value.code == error_code
    repository.active_establishment_ids_for_professional.assert_not_called()
    repository.search.assert_not_called()


@pytest.mark.parametrize(
    ("roles", "expected_professional_id", "expected_sites", "include_inactive"),
    [
        (["ADMIN"], None, None, True),
        (["ADMIN", "PROFESIONAL"], None, None, True),
        (["PROFESIONAL"], 7, [2], False),
    ],
)
def test_patient_search_preserves_administrative_and_clinical_visibility(
    roles, expected_professional_id, expected_sites, include_inactive
):
    repository = create_autospec(PatientDiscoveryRepository, instance=True)
    repository.active_professional_id_for_user.return_value = 7
    repository.active_establishment_ids_for_professional.return_value = [2]
    repository.search.return_value = DiscoveryPage(items=[], total=0)
    criteria = PatientSearchCriteria(incluir_inactivos=True)

    PatientDiscoveryService(None, repository=repository).search(
        criteria,
        actor_id=1,
        actor_roles=roles,
    )

    repository.search.assert_called_once_with(
        criteria,
        professional_id=expected_professional_id,
        establishment_ids=expected_sites,
        include_inactive=include_inactive,
    )
