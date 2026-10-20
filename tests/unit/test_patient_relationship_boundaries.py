"""Patient relationships and data checks retain their contracts at service boundaries."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError
from test_patient_service import adult_command
from test_patient_service import environment as environment

from app.exceptions import BusinessRuleError, ConflictError, ValidationDomainError
from app.schemas.patient import (
    PatientResponsibleCreate,
    PatientResponsibleUpdate,
    PatientRiskCreate,
    PatientRiskUpdate,
)
from app.services.patient import RepositoryAuditWriter
from app.services.patient_data import PatientDataRules
from app.services.patient_risk import PatientRiskRules

TODAY = date(2026, 9, 9)


def test_registration_can_include_an_initial_legacy_risk_in_its_single_transaction(environment):
    service, repository, session, audit = environment
    result = service.create(
        adult_command(riesgos=[PatientRiskCreate(grupo_riesgo_id=1, fecha_inicio=TODAY)]),
        actor_id=7,
    )
    assert len(result.riesgos) == 1 and result.riesgos[0].grupo_riesgo_id == 1
    assert len(repository.patients[result.id].riesgos) == 1
    assert session.commits == 1 and len(audit.events) == 1


def test_responsible_cannot_steal_existing_principal_and_current_principal_can_be_updated(
    environment,
):
    service, _, session, _ = environment
    patient = service.create(adult_command(), actor_id=7)
    first = service.add_responsible(
        patient.id,
        PatientResponsibleCreate(
            parentesco="MADRE", nombre_completo="Principal", es_principal=True
        ),
        actor_id=7,
    )
    second = service.add_responsible(
        patient.id,
        PatientResponsibleCreate(parentesco="PADRE", nombre_completo="Segundo"),
        actor_id=7,
    )
    with pytest.raises(BusinessRuleError) as error:
        service.update_responsible(
            patient.id, second.id, PatientResponsibleUpdate(es_principal=True), actor_id=7
        )
    assert error.value.code == "RESPONSABLE_PRINCIPAL_DUPLICADO"
    updated = service.update_responsible(
        patient.id,
        first.id,
        PatientResponsibleUpdate(nombre_completo="Principal actualizado"),
        actor_id=7,
    )
    assert updated.nombre_completo == "Principal actualizado" and updated.activo
    assert session.rollbacks == 1


def test_risk_empty_patch_is_rejected_and_open_followup_cannot_keep_a_closure_reason(
    environment, monkeypatch
):
    service, repository, _, _ = environment
    patient = service.create(
        adult_command(riesgos=[PatientRiskCreate(grupo_riesgo_id=1, fecha_inicio=TODAY)]),
        actor_id=7,
    )
    with pytest.raises(ValidationDomainError) as error:
        service.update_risk(patient.id, 1, TODAY, PatientRiskUpdate(), actor_id=7)
    assert error.value.code == "ACTUALIZACION_SIN_CAMBIOS"
    monkeypatch.setattr(
        repository,
        "get_active_risk_group",
        lambda identifier: SimpleNamespace(codigo="NUT_HALLAZGO"),
    )
    result = service.update_risk(
        patient.id,
        1,
        TODAY,
        PatientRiskUpdate(
            fecha_fin=None, observacion="Se mantiene el seguimiento", motivo_cierre="Debe limpiarse"
        ),
        actor_id=7,
    )
    assert result.fecha_fin is None and result.motivo_cierre is None


@pytest.mark.parametrize(
    "constraint,code",
    [
        ("uq_pacientes_documento", "DOCUMENTO_PACIENTE_DUPLICADO"),
        ("other_constraint", "CONFLICTO_PERSISTENCIA_PACIENTE"),
    ],
)
def test_patient_integrity_failure_is_translated_and_rolled_back(
    environment, monkeypatch, constraint, code
):
    service, repository, session, _ = environment
    monkeypatch.setattr(
        repository, "flush", Mock(side_effect=IntegrityError("insert", {}, Exception(constraint)))
    )
    with pytest.raises(ConflictError) as error:
        service.create(adult_command(), actor_id=7)
    assert error.value.code == code
    assert session.commits == 0 and session.rollbacks == 1


def test_patient_audit_adapter_refuses_unrelated_aggregate():
    repository = Mock()
    with pytest.raises(ValueError, match="solo audita"):
        RepositoryAuditWriter(repository).record(
            actor_id=7, action="INSERT", table_name="usuarios", record_id=1, before=None, after={}
        )
    repository.add_audit_entry.assert_not_called()


@pytest.mark.parametrize(
    "field,method,value",
    [
        ("sexo_codigo", "get_active_sex", "M"),
        ("seguro_id", "get_active_insurance", 1),
        ("ubigeo_residencia_codigo", "get_ubigeo", "040101"),
        ("establecimiento_registro_id", "get_active_establishment", 1),
    ],
)
def test_patch_rejects_unavailable_patient_catalogs(field, method, value):
    repository = Mock()
    getattr(repository, method).return_value = None
    with pytest.raises(ValidationDomainError) as error:
        PatientDataRules(repository, lambda: TODAY).validate_changed_patient_catalogs(
            {field: value}
        )
    assert error.value.code == "CATALOGO_NO_DISPONIBLE"


@pytest.mark.parametrize("method", ["get_active_insurance", "get_ubigeo"])
def test_registration_rejects_unavailable_insurance_or_district(method):
    repository = Mock()
    getattr(repository, method).return_value = None
    with pytest.raises(ValidationDomainError) as error:
        PatientDataRules(repository, lambda: TODAY).validate_patient_catalogs(
            document_type_code="DNI",
            sex_code="M",
            insurance_id=1,
            ubigeo_code="040101",
            establishment_id=1,
        )
    assert error.value.code == "CATALOGO_NO_DISPONIBLE"


def test_patient_locality_and_registration_dates_require_valid_context():
    rules = PatientDataRules(Mock(), lambda: TODAY)
    with pytest.raises(ValidationDomainError) as error:
        rules.normalize_patient_locality({"localidad_id": 1})
    assert error.value.code == "LOCALIDAD_SIN_DISTRITO"
    with pytest.raises(ValidationDomainError) as error:
        rules.validate_birth_and_registration_dates(date(1990, 1, 1), date(2027, 1, 1))
    assert error.value.code == "FECHA_INSCRIPCION_FUTURA"


@pytest.mark.parametrize(
    "problem,code",
    [
        ("initial_origin", "ORIGEN_RIESGO_INVALIDO"),
        ("control_before_start", "CONTROL_ANTERIOR_AL_INICIO"),
        ("start_before_birth", "INICIO_ANTERIOR_NACIMIENTO"),
        ("old_child", "SEGUIMIENTO_CRECIMIENTO_NO_APLICA"),
    ],
)
def test_followup_rejects_invalid_temporal_context(problem, code):
    repository = Mock()
    repository.get_active_risk_group.return_value = SimpleNamespace(codigo="NUT_CRECIMIENTO")
    rules = PatientRiskRules(repository, Mock())
    command = PatientRiskCreate(
        grupo_riesgo_id=1, fecha_inicio=TODAY, observacion="Control profesional"
    )
    born = date(2025, 1, 1)
    if problem == "initial_origin":
        command.atencion_origen_id = 7
    elif problem == "control_before_start":
        command.fecha_proximo_control = date(2026, 9, 8)
    elif problem == "start_before_birth":
        born = date(2026, 9, 10)
    else:
        born = date(2010, 1, 1)
    with pytest.raises(ValidationDomainError) as error:
        if problem == "initial_origin":
            rules.validate_new_risks([command])
        else:
            rules.risk_origin(
                SimpleNamespace(id=1, fecha_nacimiento=born), command, 7, ["PROFESIONAL"]
            )
    assert error.value.code == code
