"""Referral modality and origin survive the HTTP -> MySQL -> FUA round trip."""

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import delete, func, select, update

from app.models.clinical import Attention
from app.models.organization import OfficeProfessional

pytestmark = pytest.mark.integration


def test_referral_origin_is_saved_atomically_and_reloaded_for_fua(
    clinic_scene,
    create_patient,
    db_session,
    api_prefix,
):
    client = clinic_scene.professional_client
    patient = create_patient(client)
    url = f"{api_prefix}/atenciones"
    payload = {
        "paciente_id": patient["id"],
        "establecimiento_id": clinic_scene.establecimiento_id,
        "modalidad_atencion_codigo": "REFERENCIA",
        "fecha_atencion": datetime.combine(date.today() - timedelta(days=1), time(9)).isoformat(),
        "fua_datos": {
            "tipo_atencion": "REFERENCIA",
            "referencia_renipress": "00001234",
            "referencia_nombre": " ipress origen ",
            "referencia_hoja": " ref-0001 ",
        },
    }
    catalog = client.get(f"{api_prefix}/catalogos/modalidades-atencion")
    assert catalog.status_code == 200
    assert "REFERENCIA" in {item["codigo"] for item in catalog.json()}
    before = db_session.scalar(select(func.count()).select_from(Attention))
    for supplement in [None, {"tipo_atencion": "REFERENCIA"}]:
        response = client.post(url, json={**payload, "fua_datos": supplement})
        assert response.status_code == 422, response.text
    for mode in ["AMBULATORIA", "EMERGENCIA"]:
        response = client.post(url, json={**payload, "modalidad_atencion_codigo": mode})
        assert response.status_code == 422, response.text
    assert db_session.scalar(select(func.count()).select_from(Attention)) == before

    created = client.post(url, json=payload)
    assert created.status_code == 201, created.text
    attention = created.json()
    expected = {
        "tipo_atencion": "REFERENCIA",
        "referencia_renipress": "00001234",
        "referencia_nombre": "IPRESS ORIGEN",
        "referencia_hoja": "REF-0001",
    }
    db_session.expire_all()
    stored = db_session.get(Attention, attention["id"])
    assert stored.modalidad_atencion_codigo == "REFERENCIA"
    assert stored.consultorio_id is None
    assert stored.profesional_id is None
    assert stored.especialidad_codigo is None
    assert stored.fua_impresion["profesional_nombre"] is None
    for key, value in expected.items():
        assert stored.fua_impresion[key] == value
    fetched = client.get(f"{url}/{attention['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["fua_impresion"] == attention["fua_impresion"]

    # Subsequent non-referral care must neither copy nor change the origin.
    for mode in ["AMBULATORIA", "EMERGENCIA"]:
        response = client.post(
            url,
            json={
                **payload,
                "modalidad_atencion_codigo": mode,
                "fua_datos": None,
                "profesional_id": clinic_scene.profesional_id,
                "consultorio_id": clinic_scene.consultorio_id,
            },
        )
        assert response.status_code == 201, response.text
        snapshot = response.json()["fua_impresion"]
        assert snapshot["tipo_atencion"] == mode
        assert all(snapshot[key] is None for key in expected if key != "tipo_atencion")
    reread = client.get(f"{url}/{attention['id']}")
    assert reread.json()["fua_impresion"] == attention["fua_impresion"]

    # The recording clinician retains ownership of an unassigned referral.
    db_session.execute(
        update(OfficeProfessional)
        .where(OfficeProfessional.profesional_id == clinic_scene.profesional_id)
        .values(fecha_fin=date(2020, 1, 2))
    )
    db_session.commit()
    assert client.get(f"{url}/{attention['id']}").status_code == 200
    history = client.get(url, params={"paciente_id": patient["id"]})
    assert history.status_code == 200
    assert attention["id"] in {item["id"] for item in history.json()}
    search = client.get(f"{url}/busqueda", params={"paciente_id": patient["id"]})
    assert search.status_code == 200, search.text
    assert attention["id"] in {item["id"] for item in search.json()["items"]}
    cancelled = client.post(
        f"{url}/{attention['id']}/anulacion",
        json={
            "observaciones": "Anulación de referencia ficticia de integración",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    # This fixture downgrades its disposable schema at teardown. Remove only
    # this synthetic unassigned row so the downgrade can restore NOT NULL.
    db_session.execute(delete(Attention).where(Attention.id == attention["id"]))
    db_session.commit()
