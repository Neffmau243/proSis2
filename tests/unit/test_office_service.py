"""Office and assignment rejection boundaries and transactional failures."""

from datetime import date, timedelta
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.organization import Office, OfficeProfessional
from app.schemas.office import (
    OfficeAssignmentClose,
    OfficeAssignmentCreate,
    OfficeCreate,
    OfficeUpdate,
)
from app.services.office import OfficeAssignmentService, OfficeService

MED = "ESPECIALIDADES:003"
NUT = "ESPECIALIDADES:005"
PED = "ESP_MEDICINA:003"
START = date(2026, 10, 1)


def office(identifier=1, parent=None, **changes):
    values = dict(
        id=identifier,
        establecimiento_id=1,
        codigo=f"C{identifier}",
        nombre=f"Consultorio {identifier}",
        activo=True,
        area_codigo=MED if parent is None else None,
        especialidad_codigo=None,
        consultorio_padre_id=parent.id if parent else None,
        servicios_codigos=None,
    )
    values.update(changes)
    entity = Office(**values)
    entity.padre = parent
    return entity


@pytest.fixture
def scene():
    session = MagicMock()
    repository = Mock()
    current = office()
    repository.get_by_id.return_value = current
    repository.get_active_establishment.return_value = object()
    repository.get_active_specialty.return_value = object()
    repository.get_active_office.return_value = current
    repository.nonexpired_professionals.return_value = []
    repository.list_offices.return_value = []
    repository.active_specialties.return_value = {MED: "Medicina", PED: "Pediatría"}
    repository.professional_has_specialty.return_value = True
    audit = Mock()
    service = OfficeService(session, audit=audit)
    service._repository = repository
    return service, repository, session, current, audit


@pytest.mark.parametrize("operation", ["get", "update", "deactivate"])
def test_unknown_office_is_rejected_without_commit(scene, operation):
    service, repository, session, _, _ = scene
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError) as error:
        if operation == "update":
            service.update(1, OfficeUpdate(nombre="Nuevo nombre"), actor_id=7)
        elif operation == "deactivate":
            service.deactivate(1, actor_id=7)
        else:
            service.get(1)
    assert error.value.code == "CONSULTORIO_NO_ENCONTRADO"
    session.commit.assert_not_called()
    assert session.rollback.call_count == int(operation != "get")


@pytest.mark.parametrize("operation", ["create", "update"])
def test_duplicate_code_conflict_rolls_back_the_whole_office_change(scene, operation):
    service, _, session, _, _ = scene
    session.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate key"))
    with pytest.raises(ConflictError) as error:
        if operation == "create":
            service.create(
                OfficeCreate(establecimiento_id=1, codigo="MED", nombre="Medicina"), actor_id=7
            )
        else:
            service.update(1, OfficeUpdate(nombre="Modificado"), actor_id=7)
    assert error.value.code == "CONSULTORIO_EN_CONFLICTO"
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_update_revalidates_descendants_when_parent_configuration_changes(scene):
    service, repository, session, current, audit = scene
    child = office(2, current)
    repository.list_offices.return_value = [current, child]
    response = service.update(
        1, OfficeUpdate(nombre="Nuevo nombre", servicios_codigos=[PED]), actor_id=7
    )
    assert response.nombre == "Nuevo nombre" and response.servicios_codigos == [PED]
    assert response.servicios_habilitados[0].codigo == PED
    assert audit.call_args.kwargs["before"]["nombre"] == "Consultorio 1"
    assert audit.call_args.kwargs["after"]["nombre"] == "Nuevo nombre"
    session.commit.assert_called_once()


def test_reparenting_updates_the_orm_parent_and_detaching_restores_a_root(scene):
    service, repository, _, current, _ = scene
    parent = office(2)
    repository.get_by_id.side_effect = lambda identifier, **kwargs: (
        current if identifier == 1 else parent
    )
    repository.get_active_office.return_value = parent
    repository.parent_chain_contains.return_value = False
    result = service.update(1, OfficeUpdate(consultorio_padre_id=2), actor_id=7)
    assert current.padre is parent and result.consultorio_padre_id == 2
    result = service.update(1, OfficeUpdate(consultorio_padre_id=None), actor_id=7)
    assert current.padre is None and result.consultorio_padre_id is None


@pytest.mark.parametrize(
    "problem,code",
    [("inactive", "CONSULTORIO_YA_INACTIVO"), ("active_child", "CONSULTORIO_CON_HIJOS_ACTIVOS")],
)
def test_deactivation_preserves_hierarchy_rules(scene, problem, code):
    service, repository, session, current, _ = scene
    if problem == "inactive":
        current.activo = False
    else:
        repository.list_offices.return_value = [office(2, current)]
    with pytest.raises((ConflictError, BusinessRuleError)) as error:
        service.deactivate(1, actor_id=7)
    assert error.value.code == code
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_inactive_child_does_not_prevent_parent_deactivation_without_audit_port(scene):
    service, repository, session, current, _ = scene
    repository.list_offices.return_value = [office(2, current, activo=False)]
    service._audit = None
    assert service.deactivate(1, actor_id=7).activo is False
    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "problem,code",
    [
        ("site", "ESTABLECIMIENTO_NO_ACTIVO"),
        ("specialty", "ESPECIALIDAD_NO_ACTIVA"),
        ("self", "CONSULTORIO_PADRE_INVALIDO"),
        ("parent", "CONSULTORIO_PADRE_NO_ACTIVO"),
        ("other_site", "CONSULTORIO_PADRE_OTRA_SEDE"),
        ("hierarchy", "CONSULTORIO_PADRE_NO_ACTIVO"),
        ("cycle", "JERARQUIA_CONSULTORIO_CICLICA"),
    ],
)
def test_parent_context_rejects_invalid_references_before_mutating(scene, problem, code):
    service, repository, _, _, _ = scene
    parent = office(2)
    repository.get_active_office.return_value = parent
    repository.parent_chain_contains.return_value = problem == "cycle"
    if problem == "site":
        repository.get_active_establishment.return_value = None
    elif problem == "specialty":
        repository.get_active_specialty.return_value = None
    elif problem == "parent":
        repository.get_active_office.return_value = None
    elif problem == "other_site":
        parent.establecimiento_id = 2
    elif problem == "hierarchy":
        parent.activo = False
    with pytest.raises((BusinessRuleError, NotFoundError)) as error:
        service._validate_context(
            establishment_id=1,
            specialty_code=MED,
            parent_id=1 if problem == "self" else 2,
            office_id=1,
        )
    assert error.value.code == code


@pytest.mark.parametrize(
    "problem,code",
    [
        ("unknown_area", "AREA_CONSULTORIO_INVALIDA"),
        ("inactive_area", "AREA_CONSULTORIO_INVALIDA"),
        ("parent_area", "AREA_CONSULTORIO_INCOMPATIBLE"),
        ("outside_service", "SERVICIO_CONSULTORIO_INCOMPATIBLE"),
        ("inactive_service", "SERVICIO_CONSULTORIO_INCOMPATIBLE"),
        ("specialty", "ESPECIALIDAD_CONSULTORIO_INCOMPATIBLE"),
        ("assigned_professional", "ESPECIALIDAD_REQUERIDA_POR_ASIGNACION"),
    ],
)
def test_office_configuration_cannot_invalidate_area_services_or_existing_assignments(
    scene, problem, code
):
    service, repository, _, current, _ = scene
    if problem == "unknown_area":
        current.area_codigo = "UNKNOWN"
    elif problem == "inactive_area":
        repository.get_active_specialty.return_value = None
    elif problem == "parent_area":
        current = office(2, office(), area_codigo=NUT)
    elif problem == "outside_service":
        current.servicios_codigos = ["ESP_NUTRICION:001"]
    elif problem == "inactive_service":
        current.servicios_codigos = [PED]
        repository.get_active_specialty.side_effect = lambda code: None if code == PED else object()
    elif problem == "specialty":
        current.especialidad_codigo = "ESP_NUTRICION:001"
    else:
        repository.nonexpired_professionals.return_value = [7]
        repository.professional_has_specialty.return_value = False
    with pytest.raises(BusinessRuleError) as error:
        service._validate_configuration(current)
    assert error.value.code == code


@pytest.fixture
def assignment_scene():
    session, repository = Mock(), Mock()
    current = office(area_codigo=None, especialidad_codigo=None)
    repository.get_by_id.return_value = current
    repository.get_active_office.return_value = current
    repository.get_active_professional.return_value = object()
    repository.get_assignment.return_value = None
    repository.has_overlapping_assignment.return_value = False
    repository.get_current_responsible.return_value = None
    service = OfficeAssignmentService(session)
    service._repository = repository
    return service, repository, session, current


@pytest.mark.parametrize(
    "problem,code",
    [
        ("missing_office", "CONSULTORIO_NO_ACTIVO"),
        ("inactive_hierarchy", "JERARQUIA_CONSULTORIO_NO_ACTIVA"),
        ("professional", "PROFESIONAL_NO_ACTIVO"),
        ("specialty", "PROFESIONAL_SIN_ESPECIALIDAD"),
        ("duplicate", "ASIGNACION_DUPLICADA"),
        ("overlap", "ASIGNACION_VIGENTE_SUPERPUESTA"),
        ("responsible", "RESPONSABLE_VIGENTE_EXISTENTE"),
    ],
)
def test_assignment_rejects_invalid_identity_or_overlapping_dates(assignment_scene, problem, code):
    service, repository, session, current = assignment_scene
    if problem == "missing_office":
        repository.get_by_id.return_value = None
        repository.get_active_office.return_value = None
    elif problem == "inactive_hierarchy":
        current.activo = False
    elif problem == "professional":
        repository.get_active_professional.return_value = None
    elif problem == "specialty":
        current.area_codigo = MED
        repository.professional_has_specialty.return_value = False
    elif problem == "duplicate":
        repository.get_assignment.return_value = object()
    elif problem == "overlap":
        repository.has_overlapping_assignment.return_value = True
    else:
        repository.get_current_responsible.return_value = OfficeProfessional(fecha_inicio=START)
    with pytest.raises((BusinessRuleError, ConflictError, NotFoundError)) as error:
        service.assign(
            1,
            OfficeAssignmentCreate(profesional_id=7, fecha_inicio=START, es_responsable=True),
            actor_id=7,
        )
    assert error.value.code == code
    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    repository.add.assert_not_called()


@pytest.mark.parametrize("prior_start", [None, START - timedelta(days=10)])
def test_responsible_replacement_closes_prior_period_without_overlap(assignment_scene, prior_start):
    service, repository, session, _ = assignment_scene
    prior = OfficeProfessional(fecha_inicio=prior_start) if prior_start else None
    repository.get_current_responsible.return_value = prior
    result = service.assign(
        1,
        OfficeAssignmentCreate(profesional_id=7, fecha_inicio=START, es_responsable=True),
        actor_id=7,
    )
    assert result.fecha_inicio == START and result.profesional_id == 7 and result.es_responsable
    if prior is not None:
        assert prior.fecha_fin == START - timedelta(days=1)
    session.commit.assert_called_once()


def test_assignment_integrity_conflict_rolls_back(assignment_scene):
    service, _, session, _ = assignment_scene
    session.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate"))
    with pytest.raises(ConflictError) as error:
        service.assign(1, OfficeAssignmentCreate(profesional_id=7, fecha_inicio=START), actor_id=7)
    assert error.value.code == "ASIGNACION_EN_CONFLICTO"
    session.rollback.assert_called_once()


@pytest.mark.parametrize(
    "problem,code",
    [
        ("office", "CONSULTORIO_NO_ACTIVO"),
        ("assignment", "ASIGNACION_NO_ENCONTRADA"),
        ("before_start", "FECHA_FIN_INVALIDA"),
        ("extends", "CIERRE_AMPLIA_VIGENCIA"),
    ],
)
def test_invalid_closure_never_commits(assignment_scene, problem, code):
    service, repository, session, _ = assignment_scene
    repository.get_assignment.return_value = OfficeProfessional(
        fecha_inicio=START, fecha_fin=START + timedelta(days=5)
    )
    if problem == "office":
        repository.get_by_id.return_value = None
    elif problem == "assignment":
        repository.get_assignment.return_value = None
    end = START - timedelta(days=1) if problem == "before_start" else START + timedelta(days=6)
    with pytest.raises((NotFoundError, BusinessRuleError)) as error:
        service.close(1, 7, START, OfficeAssignmentClose(fecha_fin=end), actor_id=7)
    assert error.value.code == code
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_assignment_directory_rejects_unknown_office(assignment_scene):
    service, repository, _, _ = assignment_scene
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        service.list(1)


def test_invalid_new_office_configuration_rolls_back_before_any_commit(scene):
    service, _, session, _, _ = scene
    command = OfficeCreate(
        establecimiento_id=1, codigo="INVALID", nombre="Área inválida", area_codigo="UNKNOWN"
    )
    with pytest.raises(BusinessRuleError) as error:
        service.create(command, actor_id=7)
    assert error.value.code == "AREA_CONSULTORIO_INVALIDA"
    session.rollback.assert_called_once()
    session.commit.assert_not_called()
