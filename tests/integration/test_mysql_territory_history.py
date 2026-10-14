"""Patient residence, care hierarchy and FUA retain their own persisted context."""

from datetime import date, datetime, time
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.catalog import Insurance
from app.models.clinical import Attention
from app.models.organization import Establishment, Localidad, Office, Ubigeo
from app.models.patient import Patient
from app.models.security import ProfessionalSpecialty

pytestmark = pytest.mark.integration


def test_new_patient_codes_reach_saved_patient_history_and_fua(
    clinic_scene, db_session, create_patient, api_prefix
):
    client = clinic_scene.professional_client
    locality = db_session.scalar(
        select(Localidad).where(
            Localidad.ubigeo_codigo == "040102", Localidad.codigo_catalogo == "0052"
        )
    )
    insurance = db_session.scalar(select(Insurance).where(Insurance.codigo == "SIS_GRATUITO"))
    codes = dict(
        sis_diresa="040",
        sis_tipo="02",
        sis_numero="001122334",
        sis_secuencia="01",
        etnia_codigo="58",
    )
    patient = create_patient(
        client,
        seguro_id=insurance.id,
        ubigeo_residencia_codigo="040102",
        localidad_id=locality.id,
        localidad="Texto sin autoridad sobre el catálogo",
        establecimiento_registro_id=clinic_scene.establecimiento_id,
        **codes,
    )
    db_session.expire_all()
    stored = db_session.get(Patient, patient["id"])
    for key, value in codes.items():
        assert patient[key] == value
        assert getattr(stored, key) == value
    assert stored.localidad_id == locality.id
    assert patient["localidad"] == "PORTALES DEL MIRADOR"
    assert stored.ubigeo_residencia_codigo == "040102"
    assert stored.establecimiento_registro_id == clinic_scene.establecimiento_id
    response = client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "consultorio_id": clinic_scene.consultorio_id,
            "profesional_id": clinic_scene.profesional_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(date.today(), time(0)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    original = response.json()
    context = original["contexto_clinico"]
    assert context["ubigeo_residencia_codigo"] == "040102"
    assert context["localidad_id"] == locality.id
    assert context["localidad_codigo_catalogo"] == "0052"
    assert context["localidad_codigo_sis"] == "00000001"
    fua = original["fua_impresion"]
    for key, value in codes.items():
        assert fua[key] == value
    assert fua["codigo_renipress"] == clinic_scene.codigo_renaes.zfill(8)
    assert fua["contexto_territorial"]["localidad_codigo_catalogo"] == "0052"
    assert fua["contexto_territorial"]["localidad_codigo_sis"] == "00000001"
    # Master-data changes must clear obsolete SIS affiliation, retain ethnicity,
    # and leave the earlier attendance's paper and territorial codes untouched.
    updated = client.patch(f"{api_prefix}/patients/{patient['id']}", json={"seguro_id": None})
    assert updated.status_code == 200, updated.text
    assert updated.json()["etnia_codigo"] == "58"
    assert all(updated.json()[key] is None for key in codes if key != "etnia_codigo")
    fetched = client.get(f"{api_prefix}/atenciones/{original['id']}")
    history = client.get(f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]})
    assert fetched.status_code == history.status_code == 200
    assert fetched.json()["fua_impresion"] == fua
    assert history.json()[0]["fua_impresion"] == fua
    assert history.json()[0]["contexto_clinico"] == context


def test_doctor_saves_hierarchy_and_later_edits_cannot_rewrite_history_or_fua(
    clinic_scene,
    db_session,
    create_patient,
    api_prefix,
):
    scene = clinic_scene
    client = scene.professional_client
    area, service = "ESPECIALIDADES:003", "ESP_MEDICINA:003"
    root = db_session.get(Office, scene.consultorio_id)
    root.area_codigo = root.especialidad_codigo = area
    db_session.add(
        ProfessionalSpecialty(
            profesional_id=scene.profesional_id,
            especialidad_codigo=area,
            es_principal=True,
        )
    )
    district = db_session.get(Ubigeo, scene.ubigeo_codigo)
    locality = Localidad(
        ubigeo_codigo=district.codigo,
        codigo_catalogo="0001",
        codigo_sis="00000001",
        nombre="Sector original",
        nombre_norm="sector original",
    )
    second = Ubigeo(
        codigo="999901",
        departamento="Otra región",
        provincia="Otra provincia",
        distrito="Otro distrito",
    )
    db_session.add_all([locality, second])
    db_session.flush()
    other_locality = Localidad(
        ubigeo_codigo=second.codigo,
        codigo_catalogo="0001",
        codigo_sis=None,
        nombre="Sector posterior",
        nombre_norm="sector posterior",
    )
    other_site = Establishment(nombre="Inscripción posterior", ubigeo_codigo=second.codigo)
    db_session.add_all([other_locality, other_site])
    db_session.commit()
    child = clinic_scene.admin_client.post(
        f"{api_prefix}/configuracion/consultorios",
        json={
            "establecimiento_id": scene.establecimiento_id,
            "codigo": "QA-" + uuid4().hex[:6],
            "nombre": "Sala original",
            "consultorio_padre_id": root.id,
            "servicios_codigos": [service],
        },
    )
    assert child.status_code == 201, child.text
    patient = create_patient(
        client,
        ubigeo_residencia_codigo=district.codigo,
        localidad_id=locality.id,
        localidad="Nombre incorrecto del cliente",
        establecimiento_registro_id=other_site.id,
    )
    assert patient["localidad"] == "Sector original"
    # A patient can reside in one district, register elsewhere and attend this site.
    response = client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": scene.establecimiento_id,
            "consultorio_id": child.json()["id"],
            "especialidad_codigo": service,
            "profesional_id": scene.profesional_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(date.today(), time(0)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    original = response.json()
    context = original["contexto_clinico"]
    assert context["localidad_id"] == locality.id
    assert context["localidad_codigo_catalogo"] == "0001"
    assert context["localidad_codigo_sis"] == "00000001"
    assert context["ubigeo_residencia_codigo"] == district.codigo
    assert context["establecimiento_ubigeo_codigo"] == district.codigo
    assert context["establecimiento_registro_id"] == other_site.id
    assert context["consultorio_ancestros_ids"] == [root.id]
    assert context["consultorio_ruta"].endswith(" / Sala original")
    assert context["especialidad_codigo"] == service
    assert (
        original["fua_impresion"]["contexto_territorial"]["consultorio_ruta"]
        == context["consultorio_ruta"]
    )
    stored = db_session.get(Attention, original["id"])
    assert stored.contexto_clinico == context
    assert stored.fua_impresion["contexto_territorial"]["localidad"] == "Sector original"

    invalid = client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={
            "ubigeo_residencia_codigo": second.codigo,
            "localidad_id": locality.id,
        },
    )
    assert invalid.status_code == 422
    updated = client.patch(
        f"{api_prefix}/patients/{patient['id']}",
        json={
            "ubigeo_residencia_codigo": second.codigo,
            "localidad_id": other_locality.id,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["localidad"] == "Sector posterior"
    assert updated.json()["distrito_residencia"] == "Otro distrito"
    root.nombre = "Área renombrada"
    db_session.get(Office, child.json()["id"]).nombre = "Sala renombrada"
    site = db_session.get(Establishment, scene.establecimiento_id)
    site.nombre = "Sede renombrada"
    site.codigo_renaes = "00999999"
    db_session.commit()
    db_session.expire_all()

    fetched = client.get(f"{api_prefix}/atenciones/{original['id']}")
    assert fetched.status_code == 200, fetched.text
    for key in (
        "contexto_clinico",
        "fua_impresion",
        "consultorio_nombre",
        "consultorio_ruta",
        "establecimiento_nombre",
        "especialidad_nombre",
    ):
        assert fetched.json()[key] == original[key]
    history = client.get(f"{api_prefix}/atenciones", params={"paciente_id": patient["id"]})
    assert history.status_code == 200, history.text
    assert history.json()[0]["consultorio_ruta"] == context["consultorio_ruta"]
    issued = client.post(f"{api_prefix}/documentos/fua", json={"atencion_id": original["id"]})
    assert issued.status_code == 201, issued.text
    assert issued.json()["codigo_renipress"] == original["fua_impresion"]["codigo_renipress"]


def test_establishment_catalog_exposes_its_own_district(clinic_scene, api_prefix):
    response = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/establecimientos", params={"limit": 100}
    )
    assert response.status_code == 200
    site = next(
        row for row in response.json()["items"] if row["id"] == clinic_scene.establecimiento_id
    )
    assert site["ubigeo_codigo"] == clinic_scene.ubigeo_codigo
    assert site["distrito"] == "CERCADO"


def test_migration_keeps_the_original_sis_gap(db_session):
    portales = db_session.scalar(
        select(Localidad).where(
            Localidad.ubigeo_codigo == "040102",
            Localidad.codigo_catalogo == "0052",
        )
    )
    assert portales.nombre == "PORTALES DEL MIRADOR"
    assert (
        db_session.scalar(
            select(Localidad).where(
                Localidad.ubigeo_codigo == "040102",
                Localidad.codigo_catalogo == "0051",
            )
        )
        is None
    )


def test_verified_sites_expose_district_from_the_persisted_catalog(clinic_scene, api_prefix):
    response = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/establecimientos", params={"limit": 100}
    )
    assert response.status_code == 200
    verified = {"1291", "1300", "1301", "1302", "1303", "1304"}
    sites = [row for row in response.json()["items"] if row["codigo_renaes"] in verified]
    assert len(sites) == 6
    for site in sites:
        assert site["ubigeo_codigo"] == "040102"
        assert site["distrito"].upper() == "ALTO SELVA ALEGRE"
        assert site["provincia"].upper() == "AREQUIPA"


def test_source_lookup_code_and_export_key_are_separate_and_free_locality_is_allowed(
    clinic_scene,
    db_session,
    create_patient,
    api_prefix,
):
    localities = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/localidades", params={"ubigeo_codigo": "040102", "limit": 100}
    ).json()["items"]
    assert len(localities) == 88
    assert {row["codigo_sis"] for row in localities} == {"00000001"}
    assert len({row["codigo_catalogo"] for row in localities}) == 88
    assert (
        next(row for row in localities if row["codigo_catalogo"] == "0052")["nombre"]
        == "PORTALES DEL MIRADOR"
    )
    cayma = clinic_scene.professional_client.get(
        f"{api_prefix}/catalogos/localidades", params={"ubigeo_codigo": "040103", "limit": 100}
    ).json()["items"]
    assert all(row["codigo_sis"] is None for row in cayma)
    patient = create_patient(
        clinic_scene.professional_client,
        ubigeo_residencia_codigo="040102",
        localidad="ALTO SELVA ALEGRE",
        establecimiento_registro_id=clinic_scene.establecimiento_id,
    )
    assert patient["localidad_id"] is None
    assert patient["localidad"] == "ALTO SELVA ALEGRE"
    assert patient["establecimiento_registro_id"] == clinic_scene.establecimiento_id
