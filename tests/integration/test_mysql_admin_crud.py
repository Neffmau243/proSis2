"""CRUD fixes on real SQL, including admission snapshots unaffected by corrections."""

from datetime import datetime
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


def test_shared_area_rules_and_assignment_edit_preserve_admission_snapshot(
    clinic_scene, create_patient, api_prefix
):
    admin = clinic_scene.admin_client
    root = f"{api_prefix}/configuracion"
    area = admin.post(f"{root}/areas", json={"nombre": f"Área CRUD {uuid4().hex[:8]}"}).json()
    med = "ESPECIALIDADES:003"
    assert admin.delete(f"{root}/servicios/{med}").status_code == 409
    for catalog in ("areas", "servicios"):
        assert (
            admin.patch(f"{root}/{catalog}/{med}", json={"nombre": area["nombre"]}).status_code
            == 409
        )
    assert admin.get(f"{root}/servicios/{area['codigo']}").status_code == 200
    assert admin.delete(f"{root}/areas/{area['codigo']}").status_code == 200
    assert admin.post(f"{root}/servicios/{area['codigo']}/reactivar").status_code == 200

    assignments = f"{root}/consultorios/{clinic_scene.consultorio_id}/profesionales"
    old = f"{assignments}/{clinic_scene.profesional_id}/2020-01-01"
    command = {
        "fecha_inicio": "2021-01-01",
        "fecha_fin": None,
        "es_responsable": True,
        "servicios_codigos": None,
    }
    edited = admin.patch(old, json=command)
    assert edited.status_code == 200, edited.text
    assert edited.json()["fecha_inicio"] == "2021-01-01"
    clinician = clinic_scene.professional_client
    patient = create_patient(clinician)
    attention = clinician.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "consultorio_id": clinic_scene.consultorio_id,
            "profesional_id": clinic_scene.profesional_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime(2026, 10, 22, 12).isoformat(),
        },
    )
    assert attention.status_code == 201, attention.text
    before = attention.json()
    assert before["fua_impresion"] is not None
    path = f"{assignments}/{clinic_scene.profesional_id}/2021-01-01"
    rejected = admin.patch(path, json={**command, "fecha_inicio": "2026-10-23"})
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "ASIGNACION_CON_ATENCIONES"
    after = clinician.get(f"{api_prefix}/atenciones/{before['id']}").json()
    assert after["fua_impresion"] == before["fua_impresion"]
    assert after["fecha_atencion"] == before["fecha_atencion"]
