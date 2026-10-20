"""Service-level rejection rules, including legacy callers outside HTTP DTO validation."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.exceptions import BusinessRuleError, NotFoundError, ValidationDomainError
from app.models.organization import Office
from app.schemas.attention import AttentionCreate
from app.schemas.patient import PatientResponsibleCreate
from app.services.attention_validation import AttentionContextValidator
from app.services.patient_responsible import PatientResponsibleRules


def clinical_scene():
    office = Office(
        id=1,
        establecimiento_id=1,
        codigo="MED",
        nombre="Medicina",
        activo=True,
        area_codigo="ESPECIALIDADES:003",
        especialidad_codigo="ESPECIALIDADES:003",
    )
    office.padre = None
    repository = Mock()
    repository.get_active_establishment.return_value = object()
    repository.get_active_mode.return_value = object()
    repository.get_active_professional.return_value = object()
    repository.get_active_office.return_value = office
    repository.get_active_specialty.return_value = object()
    repository.professional_is_assigned.return_value = True
    repository.professional_has_specialty.return_value = True
    command = AttentionCreate(
        paciente_id=1,
        establecimiento_id=1,
        profesional_id=1,
        consultorio_id=1,
        especialidad_codigo="ESP_MEDICINA:003",
        modalidad_atencion_codigo="AMBULATORIA",
        fecha_atencion=datetime(2026, 10, 20, 9),
    )
    return repository, office, command


@pytest.mark.parametrize(
    "method,code",
    [
        ("get_active_establishment", "ESTABLECIMIENTO_NO_ACTIVO"),
        ("get_active_mode", "MODALIDAD_NO_ACTIVA"),
        ("get_active_professional", "PROFESIONAL_NO_ACTIVO"),
        ("get_active_office", "CONSULTORIO_NO_ACTIVO"),
        ("get_active_specialty", "ESPECIALIDAD_NO_ACTIVA"),
    ],
)
def test_clinical_catalog_rejection_identifies_the_unavailable_resource(method, code):
    repository, _, command = clinical_scene()
    getattr(repository, method).return_value = None
    with pytest.raises(NotFoundError) as error:
        AttentionContextValidator(repository).validate(command)
    assert error.value.code == code
    repository.professional_is_assigned.assert_not_called()


@pytest.mark.parametrize(
    "change,code",
    [
        ("another_site", "CONSULTORIO_OTRA_SEDE"),
        ("inactive", "JERARQUIA_CONSULTORIO_NO_ACTIVA"),
        ("empty_services", "ESPECIALIDAD_INCOMPATIBLE"),
        ("wrong_service", "ESPECIALIDAD_INCOMPATIBLE"),
        ("unassigned", "PROFESIONAL_NO_ASIGNADO"),
        ("unqualified", "PROFESIONAL_SIN_ESPECIALIDAD"),
    ],
)
def test_clinical_context_rejects_invalid_office_or_assignment(change, code):
    repository, office, command = clinical_scene()
    if change == "another_site":
        office.establecimiento_id = 2
    elif change == "inactive":
        office.activo = False
    elif change == "empty_services":
        office.servicios_codigos = []
    elif change == "wrong_service":
        command.especialidad_codigo = "ESP_NUTRICION:001"
    elif change == "unassigned":
        repository.professional_is_assigned.return_value = False
    else:
        repository.professional_has_specialty.return_value = False
    with pytest.raises(BusinessRuleError) as error:
        AttentionContextValidator(repository).validate(command)
    assert error.value.code == code


def test_reference_without_assignment_still_checks_site_and_mode_only():
    repository, _, _ = clinical_scene()
    command = AttentionCreate(
        paciente_id=1,
        establecimiento_id=1,
        modalidad_atencion_codigo="REFERENCIA",
        fecha_atencion=datetime(2026, 10, 20, 9),
        fua_datos={
            "tipo_atencion": "REFERENCIA",
            "referencia_renipress": "00001234",
            "referencia_nombre": "Origen",
            "referencia_hoja": "00042",
        },
    )
    AttentionContextValidator(repository).validate(command)
    repository.get_active_professional.assert_not_called()
    repository.get_active_office.assert_not_called()


def test_office_without_area_or_specialty_still_checks_assignment():
    repository, office, command = clinical_scene()
    office.area_codigo = office.especialidad_codigo = None
    command.especialidad_codigo = None
    AttentionContextValidator(repository).validate(command)
    repository.professional_is_assigned.assert_called_once()
    repository.get_active_specialty.assert_not_called()
    repository.professional_has_specialty.assert_not_called()


@pytest.fixture
def responsible_rules():
    return PatientResponsibleRules(Mock(), lambda: date(2026, 10, 20))


@pytest.mark.parametrize(
    "relationship,document_type,number,code",
    [
        ("ABUELO", None, None, "PARENTESCO_NO_PERMITIDO"),
        ("MADRE", "DNI", None, "DOCUMENTO_RESPONSABLE_INCOMPLETO"),
        ("PADRE", None, "00000001", "DOCUMENTO_RESPONSABLE_INCOMPLETO"),
    ],
)
def test_legacy_responsible_input_cannot_bypass_relationship_or_document_pair(
    responsible_rules, relationship, document_type, number, code
):
    legacy = SimpleNamespace(
        parentesco=SimpleNamespace(value=relationship),
        tipo_documento_codigo=document_type,
        numero_documento=number,
    )
    with pytest.raises(ValidationDomainError) as error:
        responsible_rules.validate_responsible(legacy)
    assert error.value.code == code
    responsible_rules._data.require_active_document_type.assert_not_called()


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"parentesco": "OTRO"}, "PARENTESCO_NO_PERMITIDO"),
        ({"tipo_documento_codigo": None}, "DOCUMENTO_RESPONSABLE_INCOMPLETO"),
        ({"numero_documento": None}, "DOCUMENTO_RESPONSABLE_INCOMPLETO"),
    ],
)
def test_responsible_update_rejects_inconsistent_effective_data(responsible_rules, changes, code):
    existing = SimpleNamespace(
        parentesco="TUTOR", tipo_documento_codigo="DNI", numero_documento="00000001"
    )
    with pytest.raises(ValidationDomainError) as error:
        responsible_rules.validate_responsible_update(existing, changes)
    assert error.value.code == code


def test_responsible_document_catalog_is_checked_on_create_and_when_changed(responsible_rules):
    command = PatientResponsibleCreate(
        parentesco="MADRE",
        nombre_completo="Responsable",
        tipo_documento_codigo="DNI",
        numero_documento="00000001",
    )
    responsible_rules.validate_responsible(command)
    responsible_rules.validate_responsible_update(command, {"tipo_documento_codigo": "CE"})
    assert [
        call.args[0] for call in responsible_rules._data.require_active_document_type.call_args_list
    ] == ["DNI", "CE"]
    responsible_rules.validate_responsible_update(
        command, {"nombre_completo": "Nombre actualizado"}
    )
    responsible_rules._data.require_active_document_type.assert_called_with("CE")


def test_leap_day_birth_reaches_adulthood_on_february_28(responsible_rules):
    born = date(2008, 2, 29)
    assert responsible_rules.is_minor(born, date(2026, 2, 27))
    assert not responsible_rules.is_minor(born, date(2026, 2, 28))
    responsible_rules.validate_new_responsibles(
        [], birth_date=born, registration_date=date(2026, 2, 28)
    )
    with pytest.raises(BusinessRuleError) as error:
        responsible_rules.validate_new_responsibles(
            [], birth_date=born, registration_date=date(2026, 2, 27)
        )
    assert error.value.code == "MENOR_SIN_RESPONSABLE"


def test_only_active_responsibles_count_and_only_one_can_be_principal(responsible_rules):
    inactive = PatientResponsibleCreate(
        parentesco="TUTOR", nombre_completo="Tutor", activo=False, es_principal=True
    )
    active = PatientResponsibleCreate(
        parentesco="MADRE", nombre_completo="Madre", es_principal=True
    )
    responsible_rules.validate_new_responsibles(
        [inactive, active], birth_date=date(2020, 1, 1), registration_date=None
    )
    with pytest.raises(BusinessRuleError, match="principal"):
        responsible_rules.validate_new_responsibles(
            [active, active], birth_date=date(2020, 1, 1), registration_date=None
        )
