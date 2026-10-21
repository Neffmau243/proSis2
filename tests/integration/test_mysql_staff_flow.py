"""Real disposable-MySQL walkthrough of the staff/catalog/office flow."""

from datetime import date, datetime, time
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration
AREA = "ESPECIALIDADES:005"
SERVICE = "ESP_NUTRICION:001"


def test_new_profession_specialty_professional_office_and_encounter(
    clinic_scene, create_account, create_patient, api_prefix
):
    admin = clinic_scene.admin_client
    tag = uuid4().hex[:6]
    catalog = f"{api_prefix}/configuracion/catalogos-personal"
    profession = admin.post(
        f"{catalog}/profesiones", json={"nombre": f"Nutricionista prueba {tag}"}
    )
    specialty = admin.post(
        f"{catalog}/especialidades", json={"nombre": f"Nutrición clínica prueba {tag}"}
    )
    assert profession.status_code == specialty.status_code == 201
    profession, specialty = profession.json(), specialty.json()
    professional = admin.post(
        f"{api_prefix}/configuracion/profesionales",
        json={
            "nombre_completo": f"Profesional de prueba {tag}",
            "profesion_id": profession["id"],
            "especialidades": [{"especialidad_codigo": specialty["codigo"], "es_principal": True}],
        },
    )
    assert professional.status_code == 201, professional.text
    professional = professional.json()
    office = admin.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": f"TEST-{tag}",
            "nombre": "Consultorio de nutrición de prueba",
            "area_codigo": AREA,
        },
    )
    assert office.status_code == 201, office.text
    office = office.json()
    assignment_path = f"{api_prefix}/configuracion/consultorios/{office['id']}/profesionales"
    assignment = {"profesional_id": professional["id"], "fecha_inicio": date.today().isoformat()}
    rejected = admin.post(assignment_path, json=assignment)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["code"] == "PROFESIONAL_SIN_ESPECIALIDAD"
    qualifications = [
        {"especialidad_codigo": specialty["codigo"], "es_principal": True},
        {"especialidad_codigo": AREA, "es_principal": False},
    ]
    linked = admin.put(
        f"{api_prefix}/configuracion/profesionales/{professional['id']}/especialidades",
        json={"especialidades": qualifications},
    )
    assert linked.status_code == 200, linked.text
    assert admin.post(assignment_path, json=assignment).status_code == 201
    # A qualification created in Personal can be required by an existing
    # care area without becoming a service or changing that area's services.
    configured = admin.patch(
        f"{api_prefix}/configuracion/consultorios/{office['id']}",
        json={"especialidad_codigo": specialty["codigo"]},
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["especialidad_codigo"] == specialty["codigo"]
    assert configured.json()["area_codigo"] == AREA
    for kind, identifier in (
        ("profesiones", profession["id"]),
        ("especialidades", specialty["codigo"]),
    ):
        assert admin.delete(f"{catalog}/{kind}/{identifier}").status_code == 409
    account = create_account(profesional_id=professional["id"])
    patient = create_patient(account.client, fecha_nacimiento="1990-05-10")
    attention = account.client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "consultorio_id": office["id"],
            "profesional_id": professional["id"],
            "especialidad_codigo": SERVICE,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(date.today(), time(0)).isoformat(),
        },
    )
    assert attention.status_code == 201, attention.text
    assert attention.json()["profesional_id"] == professional["id"]
    assert attention.json()["especialidad_codigo"] == SERVICE
    # Name edits retain the identities already used by the staff and encounter.
    renamed = admin.patch(
        f"{catalog}/especialidades/{specialty['codigo']}",
        json={"nombre": f"Especialidad corregida {tag}"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["codigo"] == specialty["codigo"]
    assert (
        admin.patch(
            f"{catalog}/profesiones/{profession['id']}",
            json={"nombre": f"Profesión corregida {tag}"},
        ).status_code
        == 200
    )
    assert (
        admin.patch(
            f"{catalog}/especialidades/{AREA}",
            json={"nombre": "Nutrición clínica del establecimiento"},
        ).status_code
        == 200
    )
    refreshed_office = admin.get(f"{api_prefix}/configuracion/consultorios/{office['id']}").json()
    assert refreshed_office["area_nombre"] == "NUTRICIÓN CLÍNICA DEL ESTABLECIMIENTO"
    assert refreshed_office["area_codigo"] == AREA
    persisted = admin.get(f"{api_prefix}/configuracion/profesionales/{professional['id']}").json()
    assert persisted["profesion_id"] == profession["id"]
    assert persisted["especialidades"] == linked.json()["especialidades"]


def test_a_new_qualification_does_not_implicitly_create_a_care_area(clinic_scene, api_prefix):
    admin = clinic_scene.admin_client
    created = admin.post(
        f"{api_prefix}/configuracion/catalogos-personal/especialidades",
        json={"nombre": f"Rehabilitación prueba {uuid4().hex[:6]}"},
    ).json()
    assert created["es_area"] is False
    office = admin.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": f"TEST-{uuid4().hex[:6]}",
            "nombre": "Área nueva de prueba",
            "area_codigo": created["codigo"],
        },
    )
    assert office.status_code == 422
    assert office.json()["error"]["code"] == "AREA_CONSULTORIO_INVALIDA"


@pytest.mark.parametrize("existing_area", [False, True])
def test_custom_area_can_be_created_edited_used_in_office_and_admission(
    clinic_scene, create_account, create_patient, api_prefix, existing_area
):
    admin = clinic_scene.admin_client
    tag = uuid4().hex[:6]
    catalog = f"{api_prefix}/configuracion/catalogos-personal/especialidades"
    created = admin.post(catalog, json={"nombre": f"Área nueva {tag}", "es_area": True})
    assert created.status_code == 201, created.text
    area = created.json()
    assert area["es_area"] is True and area["area_codigos"] == [area["codigo"]]
    changed = admin.patch(
        f"{catalog}/{area['codigo']}", json={"nombre": area["nombre"], "es_area": False}
    )
    assert changed.status_code == 200 and changed.json()["es_area"] is False
    assert (
        admin.patch(
            f"{catalog}/{area['codigo']}", json={"nombre": area["nombre"], "es_area": True}
        ).status_code
        == 200
    )
    professional = admin.post(
        f"{api_prefix}/configuracion/profesionales",
        json={
            "nombre_completo": f"Profesional área nueva {tag}",
            "especialidades": (
                [{"especialidad_codigo": AREA, "es_principal": True}] if existing_area else []
            ),
        },
    ).json()
    office = admin.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": f"AREA-{tag}",
            "nombre": "Consultorio de área nueva",
            "area_codigo": area["codigo"],
        },
    )
    assert office.status_code == 201, office.text
    office = office.json()
    assert [item["codigo"] for item in office["servicios_habilitados"]] == [area["codigo"]]
    root = office
    child = admin.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": clinic_scene.establecimiento_id,
            "codigo": f"SUB-{tag}",
            "nombre": "Subconsultorio del área nueva",
            "consultorio_padre_id": root["id"],
        },
    )
    assert child.status_code == 201, child.text
    office = child.json()
    assert office["area_codigo"] == area["codigo"]
    assigned = admin.post(
        f"{api_prefix}/configuracion/consultorios/{office['id']}/profesionales",
        json={
            "profesional_id": professional["id"],
            "fecha_inicio": date.today().isoformat(),
            "es_responsable": True,
            "vincular_area": True,
        },
    )
    assert assigned.status_code == 201, assigned.text
    # Assigning at another office in the same area must not duplicate the link
    # or change the principal qualification of an existing professional.
    assert admin.post(
        f"{api_prefix}/configuracion/consultorios/{root['id']}/profesionales",
        json={
            "profesional_id": professional["id"],
            "fecha_inicio": date.today().isoformat(),
            "vincular_area": True,
        },
    ).status_code == 201
    linked = admin.get(f"{api_prefix}/configuracion/profesionales/{professional['id']}").json()
    assert len(linked["especialidades"]) == (2 if existing_area else 1)
    principal = next(item for item in linked["especialidades"] if item["es_principal"])
    assert principal["especialidad_codigo"] == (AREA if existing_area else area["codigo"])
    account = create_account(profesional_id=professional["id"])
    patient = create_patient(account.client, fecha_nacimiento="1990-05-10")
    attention = account.client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "consultorio_id": office["id"],
            "profesional_id": professional["id"],
            "especialidad_codigo": area["codigo"],
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(date.today(), time(0)).isoformat(),
        },
    )
    assert attention.status_code == 201, attention.text
    assert (
        attention.json()["fua_impresion"]["contexto_territorial"]["consultorio_id"] == office["id"]
    )
    assert (
        admin.patch(
            f"{catalog}/{area['codigo']}", json={"nombre": area["nombre"], "es_area": False}
        ).status_code
        == 409
    )
