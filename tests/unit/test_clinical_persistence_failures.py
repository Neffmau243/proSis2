"""Public use cases preserve safe error contracts when resources disappear or writes fail."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.repositories.document import DocumentRepository
from app.schemas.attention import (
    AttentionCancellationInput,
    AttentionCreate,
    NutritionalIndicatorsPreviewInput,
)
from app.schemas.document import CertificateIssueInput, FuaIssueInput, ReferralCreateInput
from app.services.attention import AttentionService
from app.services.attention_context import AttentionContextLoader
from app.services.attention_origin import AttentionOriginReader
from app.services.document import DocumentService
from app.services.nutrition_export import NutritionExportService

NOW = datetime(2026, 10, 20, 9)


def attention_command():
    return AttentionCreate(
        paciente_id=1,
        establecimiento_id=1,
        profesional_id=7,
        consultorio_id=1,
        modalidad_atencion_codigo="AMBULATORIA",
        fecha_atencion=NOW,
    )


@pytest.mark.parametrize("operation", ["get", "create", "preview"])
def test_missing_patient_or_attention_returns_not_found(operation):
    session = Mock()
    service = AttentionService(session)
    service._attentions = Mock()
    service._patients = Mock()
    service._attentions.get_active_professional_id_for_user.return_value = 7
    service._attentions.get_by_id.return_value = None
    service._patients.get_by_id.return_value = None
    service._patients.get_active_establishment_ids_for_professional.return_value = {1}
    if operation == "preview":
        command = NutritionalIndicatorsPreviewInput(
            paciente_id=1, fecha_atencion=NOW, peso_kg="60", talla_cm="160"
        )
    with pytest.raises(NotFoundError):
        if operation == "get":
            service.get(1, actor_id=1, actor_roles=["PROFESIONAL"])
        elif operation == "create":
            service.create(attention_command(), actor_id=1, actor_roles=["PROFESIONAL"])
        else:
            service.preview_nutritional_indicators(command, actor_id=1, actor_roles=["PROFESIONAL"])
    session.commit.assert_not_called()


def test_attention_database_conflict_is_translated_and_rolled_back():
    session = Mock()
    service = AttentionService(session)
    service._attentions = Mock()
    service._attentions.get_active_professional_id_for_user.return_value = 7
    service._patients = Mock()
    service._patients.get_by_id.side_effect = IntegrityError("read", {}, Exception("constraint"))
    with pytest.raises(ConflictError) as error:
        service.create(attention_command(), actor_id=1, actor_roles=["PROFESIONAL"])
    assert error.value.code == "ATENCION_EN_CONFLICTO"
    session.rollback.assert_called_once()


def test_preview_rejects_measurement_before_birth_without_calculating():
    service = AttentionService(Mock())
    service._attentions = Mock()
    service._attentions.get_active_professional_id_for_user.return_value = 7
    service._patients = Mock()
    service._patients.get_active_establishment_ids_for_professional.return_value = {1}
    service._patients.get_by_id.return_value = SimpleNamespace(fecha_nacimiento=NOW.date())
    command = NutritionalIndicatorsPreviewInput(
        paciente_id=1, fecha_atencion=datetime(2026, 10, 19), peso_kg="60", talla_cm="160"
    )
    with pytest.raises(BusinessRuleError) as error:
        service.preview_nutritional_indicators(command, actor_id=1, actor_roles=["PROFESIONAL"])
    assert error.value.code == "FECHA_ATENCION_ANTERIOR_NACIMIENTO"


def test_unexpected_attention_state_cannot_be_cancelled():
    session = Mock()
    service = AttentionService(session)
    service._attentions = Mock()
    service._attentions.get_active_professional_id_for_user.return_value = 7
    service._attentions.get_by_id.return_value = SimpleNamespace(
        profesional_id=7, estado="PENDIENTE"
    )
    with pytest.raises(BusinessRuleError) as error:
        service.cancel(
            1,
            AttentionCancellationInput(observaciones="Motivo de prueba"),
            actor_id=1,
            actor_roles=["PROFESIONAL"],
        )
    assert error.value.code == "TRANSICION_ESTADO_NO_PERMITIDA"
    session.rollback.assert_called_once()


def test_context_origin_and_export_handle_missing_rows_without_inventing_history():
    attentions, patients = Mock(), Mock()
    attentions.get_snapshot_establishment.return_value = None
    with pytest.raises(NotFoundError):
        AttentionContextLoader(attentions, patients).load(
            SimpleNamespace(id=1), attention_command()
        )
    reader = AttentionOriginReader(Mock())
    reader._attentions = Mock()
    reader._attentions.get_origin.return_value = None
    with pytest.raises(NotFoundError):
        reader.get(1, actor_id=1, actor_roles=["PROFESIONAL"])
    session = Mock()
    export = NutritionExportService(session)
    export._attentions = Mock()
    export._attentions.get_active_professional_id_for_user.return_value = 7
    export._attentions.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        export.export_review(1, actor_id=1, actor_roles=["PROFESIONAL"])
    session.rollback.assert_called_once()


@pytest.fixture
def document_scene():
    session, repository = Mock(), Mock()
    service = DocumentService(session)
    service._documents = repository
    attention = SimpleNamespace(
        id=1,
        profesional_id=7,
        establecimiento_id=1,
        fecha_atencion=NOW,
        consultorio_id=1,
        admision=None,
        edad_anios=35,
        estado="ATENDIDO",
        fua_impresion={"codigo_renipress": "00001234"},
    )
    repository.get_attention.return_value = attention
    repository.get_active_establishment.return_value = object()
    repository.get_fua_for_attention.return_value = None
    repository.reserve_sequence_number.return_value = 1
    return service, repository, session, attention


@pytest.mark.parametrize(
    "operation,code",
    [
        ("fua", "FUA_YA_EMITIDO"),
        ("certificate", "CERTIFICADO_EN_CONFLICTO"),
        ("referral", "REFERENCIA_EN_CONFLICTO"),
    ],
)
def test_document_constraint_failures_do_not_report_success(document_scene, operation, code):
    service, repository, session, _ = document_scene
    repository.flush.side_effect = IntegrityError("insert", {}, Exception("constraint"))
    with pytest.raises(ConflictError) as error:
        if operation == "fua":
            service.issue_fua(FuaIssueInput(atencion_id=1), actor_id=7)
        elif operation == "certificate":
            service.issue_certificate(
                CertificateIssueInput(atencion_id=1, tipo="Evaluación"), actor_id=7
            )
        else:
            service.create_referral(
                ReferralCreateInput(
                    atencion_id=1, tipo="EXTERNA", establecimiento_destino_id=2, motivo="Evaluación"
                ),
                actor_id=7,
            )
    assert error.value.code == code
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "state,code", [("ANULADO", "ATENCION_ANULADA"), ("PENDIENTE", "TRANSICION_ESTADO_NO_PERMITIDA")]
)
def test_non_attended_attention_cannot_issue_documents(document_scene, state, code):
    service, _, session, attention = document_scene
    attention.estado = state
    with pytest.raises(BusinessRuleError) as error:
        service.issue_fua(FuaIssueInput(atencion_id=1), actor_id=7)
    assert error.value.code == code
    session.commit.assert_not_called()


@pytest.mark.parametrize("vanishes_after_check", [True, False])
def test_site_disappearing_during_fua_preparation_is_rejected(document_scene, vanishes_after_check):
    service, repository, session, _ = document_scene
    repository.get_active_establishment.side_effect = (
        [object(), None] if vanishes_after_check else [None]
    )
    with pytest.raises(NotFoundError) as error:
        service.issue_fua(FuaIssueInput(atencion_id=1), actor_id=7)
    assert error.value.code == "ESTABLECIMIENTO_NO_ACTIVO"
    session.rollback.assert_called_once()


def test_inactive_signer_cannot_issue_certificate(document_scene):
    service, repository, session, _ = document_scene
    repository.get_active_professional.return_value = None
    with pytest.raises(NotFoundError) as error:
        service.issue_certificate(
            CertificateIssueInput(atencion_id=1, tipo="Evaluación", profesional_id=7), actor_id=7
        )
    assert error.value.code == "PROFESIONAL_NO_ACTIVO"
    session.commit.assert_not_called()


def test_document_number_reservation_does_not_invent_a_number_if_series_row_is_unavailable():
    session = Mock()
    session.scalar.return_value = None
    with pytest.raises(RuntimeError, match="reservar la serie"):
        DocumentRepository(session).reserve_sequence_number(
            kind="FUA_SIS", establishment_id=1, period="2026"
        )
