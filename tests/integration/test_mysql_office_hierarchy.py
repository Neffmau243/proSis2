from datetime import date, datetime, time
from uuid import uuid4

import pytest

from app.models.organization import Office
from app.models.security import ProfessionalSpecialty

pytestmark = pytest.mark.integration
MED = "ESPECIALIDADES:003"
PED = "ESP_MEDICINA:003"


@pytest.fixture
def medical_office(clinic_scene, db_session):
    office = db_session.get(Office, clinic_scene.consultorio_id)
    office.area_codigo = MED
    office.especialidad_codigo = MED
    db_session.add(
        ProfessionalSpecialty(
            profesional_id=clinic_scene.profesional_id, especialidad_codigo=MED, es_principal=True
        )
    )
    db_session.commit()
    return office


def child_payload(scene, parent, **changes):
    payload = dict(
        establecimiento_id=scene.establecimiento_id,
        codigo=f"S{uuid4().hex[:8]}",
        nombre="Sala física pediatría",
        consultorio_padre_id=parent.id,
        servicios_codigos=[PED],
    )
    payload.update(changes)
    return payload


def test_physician_consumes_physical_child_and_pediatric_service(
    clinic_scene, medical_office, create_patient, api_prefix
):
    created = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios", json=child_payload(clinic_scene, medical_office)
    )
    assert created.status_code == 201, created.text
    child = created.json()
    assert child["area_codigo"] == MED
    assert [item["codigo"] for item in child["servicios_habilitados"]] == [PED]
    catalog = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/consultorios",
        params={"establecimiento_id": clinic_scene.establecimiento_id, "limit": 100},
    ).json()
    item = next(item for item in catalog["items"] if item["id"] == child["id"])
    assert item["consultorio_padre_id"] == medical_office.id
    assert item["ruta"].endswith(" / Sala física pediatría")
    staff = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/profesionales",
        params={"consultorio_id": child["id"], "fecha": date.today().isoformat()},
    ).json()
    assert clinic_scene.profesional_id in [item["id"] for item in staff["items"]]
    before_assignment = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/profesionales",
        params={"consultorio_id": child["id"], "fecha": "2019-01-01"},
    ).json()
    assert before_assignment["items"] == []
    patient = create_patient(clinic_scene.professional_client, fecha_nacimiento="1990-05-10")
    attention = clinic_scene.professional_client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "consultorio_id": child["id"],
            "profesional_id": clinic_scene.profesional_id,
            "especialidad_codigo": PED,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(date.today(), time(0)).isoformat(),
        },
    )
    assert attention.status_code == 201, attention.text
    assert attention.json()["especialidad_codigo"] == PED


def test_admin_cannot_break_child_tree_or_assignments(clinic_scene, medical_office, api_prefix):
    created = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios", json=child_payload(clinic_scene, medical_office)
    )
    child = created.json()
    base = f"{api_prefix}/configuracion/consultorios"
    deactivated = clinic_scene.admin_client.delete(f"{base}/{medical_office.id}")
    assert deactivated.status_code == 422
    assert deactivated.json()["error"]["code"] == "CONSULTORIO_CON_HIJOS_ACTIVOS"
    cyclic = clinic_scene.admin_client.patch(
        f"{base}/{medical_office.id}", json={"consultorio_padre_id": child["id"]}
    )
    assert cyclic.json()["error"]["code"] == "JERARQUIA_CONSULTORIO_CICLICA"
    incompatible = clinic_scene.admin_client.patch(
        f"{base}/{child['id']}", json={"area_codigo": "ESPECIALIDADES:008"}
    )
    assert incompatible.status_code == 422
    specialty = clinic_scene.admin_client.patch(
        f"{base}/{medical_office.id}",
        json={"area_codigo": "ESPECIALIDADES:006", "especialidad_codigo": "ESPECIALIDADES:006"},
    )
    assert specialty.json()["error"]["code"] == "ESPECIALIDAD_REQUERIDA_POR_ASIGNACION"


def test_inactive_ancestor_is_hidden_and_history_remains_readable(
    clinic_scene, medical_office, db_session, api_prefix
):
    created = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios", json=child_payload(clinic_scene, medical_office)
    )
    child = created.json()
    # Simulate old corrupt state which predates the new guarded deactivation.
    assert child["id"] != medical_office.id
    medical_office.activo = False
    db_session.commit()
    catalog = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/consultorios",
        params={"establecimiento_id": clinic_scene.establecimiento_id},
    ).json()
    assert catalog["total"] == 0
    assert catalog["items"] == []
    history = clinic_scene.admin_client.get(
        f"{api_prefix}/configuracion/consultorios/{medical_office.id}/profesionales"
    )
    assert history.status_code == 200


def test_explicit_empty_services_disable_clinical_selection(
    clinic_scene, medical_office, api_prefix
):
    updated = clinic_scene.admin_client.patch(
        f"{api_prefix}/configuracion/consultorios/{medical_office.id}",
        json={"servicios_codigos": []},
    )
    assert updated.status_code == 200
    assert updated.json()["servicios_habilitados"] == []
    catalog = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/consultorios",
        params={"establecimiento_id": clinic_scene.establecimiento_id},
    ).json()
    assert catalog["items"] == []
    assert catalog["total"] == 0
