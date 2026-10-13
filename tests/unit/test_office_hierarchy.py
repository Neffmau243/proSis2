from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.domain.office import areas_for_service, office_context
from app.exceptions import BusinessRuleError
from app.models.organization import Office
from app.schemas.attention import AttentionCreate
from app.services.attention import AttentionService

MED = "ESPECIALIDADES:003"
PED = "ESP_MEDICINA:003"


def test_deduplicated_etl_services_retain_all_their_original_areas():
    # VISITA DOMICILIARIA occurs in three Esp_* source catalogs, deduped by name.
    assert set(areas_for_service("ESP_ENFERMERIA:004")) == {
        "ESPECIALIDADES2:001",
        "ESPECIALIDADES:005",
        "ESPECIALIDADES:008",
    }
    assert areas_for_service("ESPECIALIDADES3:004") == []
    assert (
        office_context(office(especialidad_codigo="ESPECIALIDADES:009", area_codigo=None)).area_code
        == "ESPECIALIDADES:009"
    )


def office(id=1, parent=None, **kwargs):
    values = dict(
        id=id,
        establecimiento_id=1,
        codigo=f"C{id}",
        nombre=f"Sala {id}",
        activo=True,
        especialidad_codigo=MED if parent is None else None,
        area_codigo=MED if parent is None else None,
        consultorio_padre_id=parent.id if parent else None,
    )
    values.update(kwargs)
    item = Office(**values)
    item.padre = parent
    return item


def test_children_inherit_area_and_can_narrow_services_without_becoming_services():
    parent = office()
    child = office(2, parent, servicios_codigos=[PED])
    context = office_context(child)
    assert context.area_code == MED
    assert context.required_specialty == MED
    assert context.service_codes == (PED,)
    assert context.ancestor_ids == (1,)
    assert context.path == "Sala 1 / Sala 2"


def test_parent_constraints_and_inactive_ancestors_fail_closed():
    parent = office(servicios_codigos=["ESP_MEDICINA:001"])
    child = office(2, parent, servicios_codigos=[PED])
    assert office_context(child).service_codes == ()
    parent.activo = False
    assert office_context(child).active is False


def test_missing_parent_and_existing_cycle_are_not_available():
    broken = office(consultorio_padre_id=99)
    assert not office_context(broken).active
    parent = office()
    child = office(2, parent)
    parent.padre = child
    parent.consultorio_padre_id = 2
    assert not office_context(child).active


@pytest.mark.parametrize(
    "service,assigned,qualified,error",
    [
        (PED, True, True, None),
        ("ESP_NUTRICION:001", True, True, "ESPECIALIDAD_INCOMPATIBLE"),
        (PED, False, True, "PROFESIONAL_NO_ASIGNADO"),
        (PED, True, False, "PROFESIONAL_SIN_ESPECIALIDAD"),
    ],
)
def test_context_accepts_medical_services_but_checks_assignment_and_base_qualification(
    service, assigned, qualified, error
):
    use_case = AttentionService(Mock())
    use_case._attentions = SimpleNamespace(
        get_active_establishment=lambda _: object(),
        get_active_professional=lambda _: object(),
        get_active_office=lambda _: office(),
        get_active_mode=lambda _: object(),
        get_active_specialty=lambda _: object(),
        professional_is_assigned=lambda *args: assigned,
        professional_has_specialty=lambda *args: qualified,
    )
    command = AttentionCreate(
        paciente_id=1,
        establecimiento_id=1,
        consultorio_id=1,
        profesional_id=1,
        especialidad_codigo=service,
        modalidad_atencion_codigo="AMBULATORIA",
        fecha_atencion=datetime(2026, 10, 13, 9),
    )
    if error:
        with pytest.raises(BusinessRuleError) as exc:
            use_case._validate_clinical_context(command)
        assert exc.value.code == error
    else:
        use_case._validate_clinical_context(command)
