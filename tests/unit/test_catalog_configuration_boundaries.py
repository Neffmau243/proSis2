"""Age/professional configuration guards and historical display fallbacks."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.exceptions import BusinessRuleError, NotFoundError
from app.mappers.age_group import age_group_to_response
from app.mappers.attention import _age_display
from app.models.catalog import AgeGroup
from app.models.security import Professional
from app.schemas.age_group import AgeGroupConfigurationInput
from app.schemas.professional import ProfessionalCreate, ProfessionalSpecialtiesUpdate
from app.services.age_group import AgeGroupService
from app.services.professional import ProfessionalService


@pytest.mark.parametrize(
    "minimum,maximum,expected",
    [(None, None, "Sin rango configurado"), (1, 2, "De 1 mes a 2 meses")],
)
def test_age_group_display_handles_month_only_and_unconfigured_historical_ranges(
    minimum, maximum, expected
):
    entity = AgeGroup(
        codigo="NINO",
        nombre="Niño",
        activo=True,
        edad_minima_meses=minimum,
        edad_maxima_meses=maximum,
    )
    assert age_group_to_response(entity).rango_edad_legible == expected


@pytest.mark.parametrize(
    "age,patient",
    [(None, None), (20, None), (5, SimpleNamespace(fecha_nacimiento=date(2030, 1, 1)))],
)
def test_attention_age_falls_back_to_saved_age_when_legacy_patient_is_missing_or_inconsistent(
    age, patient
):
    entity = SimpleNamespace(
        paciente=patient, fecha_atencion=datetime(2026, 10, 20), edad_anios=age
    )
    assert _age_display(entity) == (f"{age} años" if age is not None else None)


@pytest.mark.parametrize(
    "problem,code",
    [
        ("open_ranges", "MULTIPLES_GRUPOS_SIN_MAXIMO"),
        ("missing_minimum", "GRUPO_ETARIO_SIN_MINIMO"),
        ("open_before_last", "RANGOS_ETARIOS_SUPERPUESTOS"),
    ],
)
def test_age_group_service_rejects_inconsistent_legacy_configuration(problem, code):
    def group(low, high):
        return SimpleNamespace(
            codigo="NINO", activo=True, edad_minima_meses=low, edad_maxima_meses=high
        )

    groups = {
        "open_ranges": [group(0, None), group(12, None)],
        "missing_minimum": [group(None, 12)],
        "open_before_last": [group(0, None), group(12, 24)],
    }[problem]
    with pytest.raises(BusinessRuleError) as error:
        AgeGroupService._validate_ranges(groups, False)
    assert error.value.code == code


def test_age_group_facade_resolves_or_reports_unconfigured_age_and_configures_without_audit():
    session, repository = Mock(), Mock()
    service = AgeGroupService(session)
    service._repository = repository
    repository.find_matching_active.return_value = None
    with pytest.raises(BusinessRuleError) as error:
        service.resolve(25)
    assert error.value.code == "GRUPO_ETARIO_NO_CONFIGURADO"
    group = AgeGroup(
        codigo="NINO", nombre="Niño", activo=True, edad_minima_meses=0, edad_maxima_meses=12
    )
    repository.find_matching_active.return_value = group
    assert service.resolve(1) is group
    repository.list_all.return_value = [group]
    command = AgeGroupConfigurationInput(
        grupos=[{"codigo": "NINO", "edad_minima_meses": 0, "edad_maxima_meses": 24}]
    )
    assert service.configure(command, actor_id=7)[0].edad_maxima_meses == 24
    session.commit.assert_called_once()


def professional():
    return Professional(
        id=7,
        nombre_completo="Profesional",
        activo=True,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def test_professional_creation_generic_failure_rolls_back():
    session = Mock()
    service = ProfessionalService(session)
    service._repository = Mock()
    session.flush.side_effect = RuntimeError("storage failure")
    with pytest.raises(RuntimeError):
        service.create(ProfessionalCreate(nombre_completo="Profesional"), actor_id=7)
    session.rollback.assert_called_once()


def test_disappearing_professional_after_specialty_replacement_rolls_back():
    session, repository = Mock(), Mock()
    service = ProfessionalService(session)
    service._repository = repository
    repository.get_by_id.side_effect = [professional(), None]
    repository.required_specialties_for_nonexpired_assignments.return_value = set()
    command = ProfessionalSpecialtiesUpdate(
        especialidades=[{"especialidad_codigo": "MED", "es_principal": True}]
    )
    with pytest.raises(NotFoundError):
        service.replace_specialties(7, command, actor_id=7)
    entity = repository.replace_specialties.call_args.kwargs["specialties"][0]
    assert (
        entity.profesional_id == 7 and entity.especialidad_codigo == "MED" and entity.es_principal
    )
    session.rollback.assert_called_once()


def test_professional_deactivation_can_run_without_optional_audit_callback():
    session, repository = Mock(), Mock()
    service = ProfessionalService(session)
    service._repository = repository
    repository.get_by_id.return_value = professional()
    assert service.deactivate(7, actor_id=7).activo is False
    session.commit.assert_called_once()


def test_professional_creation_stages_each_valid_specialty_for_the_new_identity():
    session, repository = Mock(), Mock()
    service = ProfessionalService(session)
    service._repository = repository
    staged = []
    repository.add.side_effect = staged.append
    session.flush.side_effect = lambda: setattr(staged[0], "id", 7)
    repository.get_by_id.return_value = professional()
    command = ProfessionalCreate(
        nombre_completo="Profesional",
        especialidades=[{"especialidad_codigo": "MED", "es_principal": True}],
    )
    assert service.create(command, actor_id=7).id == 7
    link = repository.add_specialty.call_args.args[0]
    assert link.profesional_id == 7 and link.especialidad_codigo == "MED" and link.es_principal
    session.commit.assert_called_once()
