"""Access boundaries that must survive moving policies between services."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.exceptions import AuthorizationError
from app.services.clinical_access import ClinicalAccessService, ClinicalScope


def policy(professional_id=7):
    repository = Mock()
    repository.get_active_professional_id_for_user.return_value = professional_id
    repository.get_active_establishment_ids_for_professional.return_value = {2}
    repository.is_patient_in_professional_scope.return_value = True
    return ClinicalAccessService(repository)


@pytest.mark.parametrize("roles", [("PROFESIONAL",), ("ADMIN", "PROFESIONAL"), ("profesional",)])
def test_active_clinical_identity_is_shared_by_detail_and_search(roles):
    access = policy()
    assert access.attention_scope(actor_id=11, actor_roles=roles) == ClinicalScope(7, {2})
    assert (
        access.search_professional(actor_roles=roles, professional_id=7, allow_administrator=False)
        == 7
    )


@pytest.mark.parametrize(
    "action", ["attention_scope", "ensure_cancellation", "ensure_document_emitter"]
)
def test_admin_alone_does_not_gain_clinical_write_or_read_access(action):
    access = policy()
    arguments = dict(actor_id=11, actor_roles=("ADMIN",))
    if action == "ensure_cancellation":
        arguments["professional_id"] = 7
    with pytest.raises(AuthorizationError) as error:
        if action == "ensure_document_emitter":
            access.ensure_document_emitter(7, **arguments)
        else:
            getattr(access, action)(**arguments)
    assert error.value.code == "ROL_CLINICO_REQUERIDO"


def test_internal_legacy_reads_and_administrative_patient_access_remain_explicit():
    access = policy(None)
    assert access.patient_scope(actor_id=None, actor_roles=None) is None
    assert access.attention_scope(actor_id=None, actor_roles=None) is None
    assert access.patient_scope(actor_id=11, actor_roles=("ADMIN",)) is None
    access.ensure_document_emitter(99, actor_id=None, actor_roles=None)


@pytest.mark.parametrize(
    "actor,professional,code",
    [(None, 7, "ACTOR_CLINICO_REQUERIDO"), (11, None, "USUARIO_PROFESIONAL_SIN_VINCULO")],
)
def test_clinical_access_requires_actor_and_active_professional(actor, professional, code):
    with pytest.raises(AuthorizationError) as error:
        policy(professional).attention_scope(actor_id=actor, actor_roles=("PROFESIONAL",))
    assert error.value.code == code


def test_site_read_permission_does_not_grant_cancellation_or_document_ownership():
    access = policy()
    entity = SimpleNamespace(profesional_id=99, establecimiento_id=2, created_by_usuario_id=11)
    access.ensure_attention(entity, ClinicalScope(7, {2}), actor_id=11)
    for action in [
        lambda: access.ensure_cancellation(
            actor_id=11, actor_roles=("PROFESIONAL",), professional_id=99, recorded_by_id=11
        ),
        lambda: access.ensure_document_emitter(99, actor_id=11, actor_roles=("PROFESIONAL",)),
    ]:
        with pytest.raises(AuthorizationError) as error:
            action()
        assert error.value.code == "PROFESIONAL_DISTINTO_AL_USUARIO"


def test_unassigned_attention_remains_visible_and_cancellable_by_its_recorder():
    access = policy()
    entity = SimpleNamespace(profesional_id=None, establecimiento_id=99, created_by_usuario_id=11)
    access.ensure_attention(entity, ClinicalScope(7, set()), actor_id=11)
    access.ensure_cancellation(
        actor_id=11, actor_roles=("PROFESIONAL",), professional_id=None, recorded_by_id=11
    )
    with pytest.raises(AuthorizationError) as error:
        access.ensure_attention(entity, ClinicalScope(7, set()), actor_id=12)
    assert error.value.code == "ATENCION_FUERA_DE_AMBITO"


def test_patient_outside_scope_is_rejected_before_persistence():
    access = policy()
    access._patients.is_patient_in_professional_scope.return_value = False
    with pytest.raises(AuthorizationError) as error:
        access.ensure_patient(90, ClinicalScope(7, {2}))
    assert error.value.code == "PACIENTE_FUERA_DE_AMBITO"
