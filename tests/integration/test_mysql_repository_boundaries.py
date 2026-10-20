"""Read variants and relationship boundaries exercised with real MySQL rows."""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.catalog import Cie10, FamilyHistoryPrefix, ServiceOffering, Specialty
from app.models.organization import Localidad, Office
from app.models.security import ProfessionalSpecialty
from app.repositories.attention import AttentionRepository
from app.repositories.catalog import CatalogRepository
from app.repositories.discovery import AttentionDiscoveryRepository
from app.repositories.document import DocumentRepository
from app.repositories.office import OfficeRepository
from app.repositories.patient import PatientRepository
from app.repositories.professional import ProfessionalRepository
from app.repositories.user import UserRepository
from app.schemas.discovery import AttentionSearchCriteria

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "method,model",
    [
        ("page_family_histories", FamilyHistoryPrefix),
        ("page_services", ServiceOffering),
        ("page_cie10", Cie10),
    ],
)
def test_unfiltered_catalog_pages_keep_total_count_and_limit(db_session, method, model):
    result = getattr(CatalogRepository(db_session), method)(query=None, limit=2, offset=0)
    expected = db_session.scalar(
        select(func.count()).select_from(model).where(model.activo.is_(True))
    )
    assert result.total == expected
    assert len(result.items) == min(2, expected)


def test_ethnicities_are_available_through_the_same_authorized_api(clinic_scene, api_prefix):
    response = clinic_scene.professional_client.get(f"{api_prefix}/catalogos/etnias")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows and all(row["activo"] for row in rows)
    assert len({row["codigo"] for row in rows}) == len(rows)


def test_office_catalog_without_qualification_and_missing_or_inactive_offices(
    db_session, clinic_scene
):
    repository = CatalogRepository(db_session)
    assert (
        repository.page_professionals(query=None, limit=10, offset=0, office_id=999999999).total
        == 0
    )
    office = db_session.get(Office, clinic_scene.consultorio_id)
    office.area_codigo = office.especialidad_codigo = None
    db_session.flush()
    result = repository.page_professionals(query=None, limit=100, offset=0, office_id=office.id)
    assert clinic_scene.profesional_id in {row.id for row in result.items}
    office.activo = False
    db_session.flush()
    assert (
        repository.page_professionals(query=None, limit=10, offset=0, office_id=office.id).items
        == []
    )
    db_session.rollback()


def test_unfiltered_territory_catalog_still_has_counted_pages(db_session):
    result = CatalogRepository(db_session).page_ubigeos(query=None, limit=2, offset=0)
    assert result.total >= 2 and len(result.items) == 2


def test_office_read_variants_and_bounded_assignment_overlap(db_session, clinic_scene):
    repository = OfficeRepository(db_session)
    office_id, professional_id = clinic_scene.consultorio_id, clinic_scene.profesional_id
    assert office_id in {item.id for item in repository.list_offices(include_inactive=True)}
    assert (
        repository.get_active_establishment(clinic_scene.establecimiento_id).id
        == clinic_scene.establecimiento_id
    )
    assignment = next(
        row
        for row in repository.list_assignments(office_id)
        if row.profesional_id == professional_id
    )
    assert (
        repository.get_assignment(office_id, professional_id, assignment.fecha_inicio) is assignment
    )
    assignment.es_responsable = True
    db_session.flush()
    assert repository.get_current_responsible(office_id, date.today()) is assignment
    assert repository.has_overlapping_assignment(
        office_id=office_id,
        professional_id=professional_id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
    )
    db_session.rollback()


def test_parent_chain_rejects_an_existing_cycle_and_handles_a_missing_ancestor(
    db_session, clinic_scene
):
    token = uuid4().hex[:8]
    first = Office(
        establecimiento_id=clinic_scene.establecimiento_id, codigo="A" + token, nombre="A"
    )
    second = Office(
        establecimiento_id=clinic_scene.establecimiento_id, codigo="B" + token, nombre="B"
    )
    db_session.add_all([first, second])
    db_session.flush()
    first.consultorio_padre_id, second.consultorio_padre_id = second.id, first.id
    db_session.flush()
    repository = OfficeRepository(db_session)
    assert repository.parent_chain_contains(candidate_parent_id=first.id, office_id=999999999)
    assert not repository.parent_chain_contains(candidate_parent_id=999999999, office_id=first.id)
    db_session.rollback()


def test_patient_relationship_reads_and_inactive_inclusion_are_explicit(
    db_session, clinic_scene, create_patient, create_risk_group
):
    group = create_risk_group()
    patient = create_patient(
        clinic_scene.professional_client,
        responsables=[
            {"parentesco": "MADRE", "nombre_completo": "Responsable", "es_principal": True}
        ],
        riesgos=[{"grupo_riesgo_id": group.id, "fecha_inicio": date.today().isoformat()}],
    )
    repository = PatientRepository(db_session)
    responsible = repository.get_responsible(patient["id"], patient["responsables"][0]["id"])
    assert responsible.nombre_completo == "Responsable"
    assert repository.find_other_active_principal(patient["id"]) is responsible
    assert (
        repository.find_other_active_principal(patient["id"], exclude_responsible_id=responsible.id)
        is None
    )
    assert repository.get_risk(patient["id"], group.id, date.today()).grupo_riesgo_id == group.id
    locality = db_session.scalar(select(Localidad).limit(1))
    assert repository.get_active_localidad(locality.id, None).id == locality.id
    entity = repository.get_by_id(patient["id"])
    entity.estado = False
    db_session.flush()
    assert repository.get_by_id(patient["id"]) is None
    assert repository.get_by_id(patient["id"], include_inactive=True) is entity
    db_session.rollback()


def test_document_reads_and_certificate_blocks_attention_cancellation(
    db_session, clinic_scene, create_patient, api_prefix
):
    client = clinic_scene.professional_client
    patient = create_patient(client)
    created = client.post(
        f"{api_prefix}/atenciones",
        json={
            "paciente_id": patient["id"],
            "establecimiento_id": clinic_scene.establecimiento_id,
            "profesional_id": clinic_scene.profesional_id,
            "consultorio_id": clinic_scene.consultorio_id,
            "modalidad_atencion_codigo": "AMBULATORIA",
            "fecha_atencion": datetime.combine(date.today(), datetime.min.time()).isoformat(),
            "peso_kg": "60",
            "talla_cm": "160",
        },
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    documents = DocumentRepository(db_session)
    assert documents.get_attention(identifier).id == identifier
    assert documents.get_fua_for_attention(identifier) is None
    assert (
        documents.get_active_professional(clinic_scene.profesional_id).id
        == clinic_scene.profesional_id
    )
    certificate = client.post(
        f"{api_prefix}/documentos/certificados",
        json={
            "atencion_id": identifier,
            "tipo": "Evaluación",
            "profesional_id": clinic_scene.profesional_id,
        },
    )
    assert certificate.status_code == 201, certificate.text
    assert AttentionRepository(db_session).has_active_documents_for_attention(identifier)
    assert documents.get_fua(999999999) is None
    assert documents.get_referral(999999999) is None
    previous = AttentionRepository(db_session).previous_growth_control(
        patient["id"], date.today() + timedelta(days=1), birth_date=date(1990, 5, 10)
    )
    assert previous.id == identifier
    result = AttentionDiscoveryRepository(db_session).search(
        AttentionSearchCriteria(
            paciente_id=patient["id"], establecimiento_id=clinic_scene.establecimiento_id
        ),
        professional_id=None,
        establishment_ids=None,
    )
    assert result.total == 1 and result.items[0].id == identifier


def test_staff_read_and_new_specialty_link_are_persisted_in_same_session(db_session, clinic_scene):
    repository = ProfessionalRepository(db_session)
    assert clinic_scene.profesional_id in {item.id for item in repository.list()}
    code = "T" + uuid4().hex[:8].upper()
    db_session.add(Specialty(codigo=code, nombre="Especialidad de prueba"))
    db_session.flush()
    repository.add_specialty(
        ProfessionalSpecialty(profesional_id=clinic_scene.profesional_id, especialidad_codigo=code)
    )
    db_session.flush()
    assert db_session.get(ProfessionalSpecialty, (clinic_scene.profesional_id, code)) is not None
    users = UserRepository(db_session)
    user = users.find_by_id(clinic_scene.professional_user_id)
    assert users.find_by_username(user.nombre_usuario).id == user.id
    assert users.find_roles_by_codes(set()) == []
    assert users.find_login_rate_limit("0" * 64) is None
    db_session.rollback()
