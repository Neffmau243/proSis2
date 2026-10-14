from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.exceptions import BusinessRuleError, ConflictError, ValidationDomainError
from app.schemas.patient import (
    PatientCreate,
    PatientResponsibleCreate,
    PatientRiskCreate,
    PatientUpdate,
    ResponsibleRelationship,
)
from app.services.patient import PatientService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RecordingAuditWriter:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, **event: Any) -> None:
        self.events.append(event)


class InMemoryPatientRepository:
    """Small repository double; service tests must not require MySQL."""

    def __init__(self) -> None:
        self.patients: dict[int, SimpleNamespace] = {}
        self.document_owner: SimpleNamespace | None = None
        self.created_patient_count = 0
        self._next_patient_id = 1
        self._next_responsible_id = 1
        self.now = datetime(2026, 9, 9, 12, 0, 0)
        # Ámbito asistencial del profesional autenticado; solo lo consulta la
        # regla de lectura/edición de pacientes, no el registro ni el traslado.
        self.professional_establishment_ids: set[int] = set()
        self.patients_in_scope: set[int] = set()

    def get_by_id(
        self,
        patient_id: int,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> SimpleNamespace | None:
        patient = self.patients.get(patient_id)
        if patient is None or (not include_inactive and not patient.estado):
            return None
        return patient

    def find_by_document(
        self,
        document_type_code: str,
        document_number: str,
        *,
        exclude_patient_id: int | None = None,
    ) -> SimpleNamespace | None:
        if self.document_owner is not None and self.document_owner.id != exclude_patient_id:
            return self.document_owner
        for patient in self.patients.values():
            if (
                patient.tipo_documento_codigo == document_type_code
                and patient.numero_documento == document_number
                and patient.id != exclude_patient_id
            ):
                return patient
        return None

    @staticmethod
    def get_active_document_type(code: str) -> object:
        return object()

    @staticmethod
    def get_active_sex(code: str) -> object:
        return object()

    @staticmethod
    def get_active_ethnicity(code: str) -> object | None:
        return object() if code in {"1", "2", "58"} else None

    @staticmethod
    def get_active_insurance(insurance_id: int) -> object:
        return SimpleNamespace(codigo="SIS" if insurance_id == 2 else "SIN_SEGURO", regimen="SIS" if insurance_id == 2 else "NINGUNO")

    @staticmethod
    def get_ubigeo(code: str) -> object:
        return object()

    @staticmethod
    def get_active_establishment(establishment_id: int) -> object:
        return object()

    @staticmethod
    def get_active_risk_group(risk_group_id: int) -> object:
        return object()

    @staticmethod
    def get_active_professional_id_for_user(user_id: int) -> int:
        return 7

    def get_active_establishment_ids_for_professional(self, professional_id: int) -> set[int]:
        return set(self.professional_establishment_ids)

    def is_patient_in_professional_scope(
        self,
        *,
        patient_id: int,
        professional_id: int,
        establishment_ids: set[int],
    ) -> bool:
        return patient_id in self.patients_in_scope

    def create_patient(self, values: dict[str, Any]) -> SimpleNamespace:
        patient = SimpleNamespace(
            **values,
            id=self._next_patient_id,
            estado=True,
            created_at=self.now,
            updated_at=self.now,
            responsables=[],
            riesgos=[],
        )
        self._next_patient_id += 1
        self.patients[patient.id] = patient
        self.created_patient_count += 1
        return patient

    def create_responsible(self, values: dict[str, Any]) -> SimpleNamespace:
        responsible = SimpleNamespace(id=self._next_responsible_id, **values)
        self._next_responsible_id += 1
        # The real repository adds the child to the session and SQLAlchemy
        # attaches it to the parent collection on flush.  The fake has to do
        # the same, otherwise the service would map an empty relationship.
        self.patients[values["paciente_id"]].responsables.append(responsible)
        return responsible

    def create_risk(self, values: dict[str, Any]) -> SimpleNamespace:
        risk = SimpleNamespace(**values)
        self.patients[values["paciente_id"]].riesgos.append(risk)
        return risk

    def get_active_responsibles(self, patient_id: int) -> list[SimpleNamespace]:
        return [
            item
            for item in self.patients[patient_id].responsables
            if item.activo
        ]

    def find_other_active_principal(
        self,
        patient_id: int,
        *,
        exclude_responsible_id: int | None = None,
    ) -> SimpleNamespace | None:
        for item in self.get_active_responsibles(patient_id):
            if item.es_principal and item.id != exclude_responsible_id:
                return item
        return None

    def get_responsible(
        self,
        patient_id: int,
        responsible_id: int,
        *,
        for_update: bool = False,
    ) -> SimpleNamespace | None:
        return next(
            (
                item
                for item in self.patients[patient_id].responsables
                if item.id == responsible_id
            ),
            None,
        )

    def find_overlapping_risk(
        self,
        patient_id: int,
        risk_group_id: int,
        *,
        start_date: date,
        end_date: date | None,
        exclude_start_date: date | None = None,
    ) -> SimpleNamespace | None:
        candidate_end = end_date or date.max
        for item in self.patients[patient_id].riesgos:
            if item.grupo_riesgo_id != risk_group_id:
                continue
            if exclude_start_date is not None and item.fecha_inicio == exclude_start_date:
                continue
            if item.fecha_inicio <= candidate_end and start_date <= (item.fecha_fin or date.max):
                return item
        return None

    def get_risk(
        self,
        patient_id: int,
        risk_group_id: int,
        start_date: date,
        *,
        for_update: bool = False,
    ) -> SimpleNamespace | None:
        return next(
            (
                item
                for item in self.patients[patient_id].riesgos
                if item.grupo_riesgo_id == risk_group_id and item.fecha_inicio == start_date
            ),
            None,
        )

    @staticmethod
    def update_fields(entity: SimpleNamespace, values: dict[str, Any]) -> None:
        for field, value in values.items():
            setattr(entity, field, value)

    @staticmethod
    def deactivate(patient: SimpleNamespace) -> None:
        patient.estado = False

    @staticmethod
    def flush() -> None:
        pass


PatientTestEnvironment = tuple[
    PatientService,
    InMemoryPatientRepository,
    FakeSession,
    RecordingAuditWriter,
]


@pytest.fixture
def environment() -> PatientTestEnvironment:
    repository = InMemoryPatientRepository()
    session = FakeSession()
    audit = RecordingAuditWriter()
    service = PatientService(
        session,  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        audit_writer=audit,
        today_provider=lambda: date(2026, 9, 9),
    )
    return service, repository, session, audit


def adult_command(**overrides: Any) -> PatientCreate:
    payload = {
        "tipo_documento_codigo": "DNI",
        "numero_documento": "12345678",
        "fecha_nacimiento": date(1990, 5, 10),
        "primer_nombre": "Ana",
    }
    payload.update(overrides)
    return PatientCreate(**payload)


def minor_command(**overrides: Any) -> PatientCreate:
    payload = {
        "tipo_documento_codigo": "DNI",
        "numero_documento": "87654321",
        "fecha_nacimiento": date(2015, 5, 10),
        "primer_nombre": "Luis",
    }
    payload.update(overrides)
    return PatientCreate(**payload)


def test_registers_unique_adult_and_audits_in_one_commit(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, audit = environment

    result = service.create(adult_command(), actor_id=41)

    assert result.id == 1
    assert result.estado is True
    assert repository.created_patient_count == 1
    assert session.commits == 1
    assert audit.events[0]["action"] == "INSERT"
    assert audit.events[0]["actor_id"] == 41


def test_locality_name_is_owned_by_the_district_catalog(environment, monkeypatch):
    service, repository, _, audit = environment
    monkeypatch.setattr(repository, "get_active_localidad", lambda id, code:
        SimpleNamespace(nombre="Localidad oficial") if (id, code) == (12, "040102") else None,
        raising=False)
    created = service.create(adult_command(
        ubigeo_residencia_codigo="040102", localidad_id=12, localidad="Nombre manipulado"
    ), actor_id=41)
    assert created.localidad == "Localidad oficial"
    changed = service.update(created.id, PatientUpdate(localidad="Otro nombre"), actor_id=41)
    assert changed.localidad == "Localidad oficial"
    assert audit.events[-1]["after"]["localidad"] == "Localidad oficial"
    with pytest.raises(ValidationDomainError):
        service.update(created.id, PatientUpdate(ubigeo_residencia_codigo="040103"), actor_id=41)
    assert repository.patients[created.id].ubigeo_residencia_codigo == "040102"
    cleared = service.update(created.id, PatientUpdate(localidad_id=None), actor_id=41)
    assert cleared.localidad_id is None
    assert cleared.localidad is None


def test_sis_patch_validates_merged_affiliation_and_audits_master_data(environment):
    service, repository, session, audit = environment
    created = service.create(adult_command(seguro_id=2, sis_diresa="001", sis_tipo="2", sis_numero="00000001", etnia_codigo="58"), actor_id=41)
    updated = service.update(created.id, PatientUpdate(sis_numero="000000002", sis_secuencia="01"), actor_id=41)
    assert updated.sis_diresa == "001"
    assert updated.sis_numero == "000000002"
    assert updated.etnia_codigo == "58"
    with pytest.raises(ValidationDomainError):
        service.update(created.id, PatientUpdate(sis_numero=None), actor_id=41)
    assert repository.patients[created.id].sis_numero == "000000002"
    assert audit.events[-1]["after"]["sis_secuencia"] == "01"
    assert session.rollbacks == 1


def test_unknown_ethnicity_is_not_created_or_assigned(environment):
    service, repository, session, _ = environment
    with pytest.raises(ValidationDomainError):
        service.create(adult_command(etnia_codigo="99"), actor_id=41)
    assert repository.created_patient_count == 0
    assert session.rollbacks == 1


def test_rejects_locality_without_a_selected_district(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment

    with pytest.raises(ValidationDomainError) as error:
        service.create(adult_command(localidad="Alto Selva Alegre"), actor_id=1)

    assert error.value.code == "LOCALIDAD_SIN_DISTRITO"
    assert repository.created_patient_count == 0
    assert session.rollbacks == 1


def test_rejects_ubigeo_code_saved_as_locality(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment

    with pytest.raises(ValidationDomainError) as error:
        service.create(
            adult_command(
                ubigeo_residencia_codigo="040101",
                localidad="040101",
            ),
            actor_id=1,
        )

    assert error.value.code == "LOCALIDAD_NO_PUEDE_SER_CODIGO_UBIGEO"
    assert repository.created_patient_count == 0
    assert session.rollbacks == 1


def test_update_rejects_ubigeo_code_saved_as_locality(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment
    created = service.create(
        adult_command(
            ubigeo_residencia_codigo="040101",
            localidad="Alto Selva Alegre",
        ),
        actor_id=1,
    )

    with pytest.raises(ValidationDomainError) as error:
        service.update(created.id, PatientUpdate(localidad="040101"), actor_id=1)

    assert error.value.code == "LOCALIDAD_NO_PUEDE_SER_CODIGO_UBIGEO"
    assert repository.patients[created.id].localidad == "Alto Selva Alegre"
    assert session.rollbacks == 1


def test_rejects_minor_without_an_active_responsible(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment

    with pytest.raises(BusinessRuleError, match="responsable activo") as error:
        service.create(minor_command(), actor_id=1)

    assert error.value.code == "MENOR_SIN_RESPONSABLE"
    assert repository.created_patient_count == 0
    assert session.rollbacks == 1


def test_registers_minor_with_allowed_primary_responsible(
    environment: PatientTestEnvironment,
) -> None:
    service, _repository, session, audit = environment
    mother = PatientResponsibleCreate(
        parentesco=ResponsibleRelationship.MOTHER,
        nombre_completo="María Pérez",
        es_principal=True,
    )

    result = service.create(minor_command(responsables=[mother]), actor_id=4)

    assert result.responsables[0].parentesco == "MADRE"
    assert result.responsables[0].es_principal is True
    assert session.commits == 1
    assert audit.events[0]["after"]["responsables"][0]["nombre_completo"] == "María Pérez"


def test_rejects_two_active_primary_responsibles(
    environment: PatientTestEnvironment,
) -> None:
    service, _repository, session, _audit = environment
    mother = PatientResponsibleCreate(
        parentesco=ResponsibleRelationship.MOTHER,
        nombre_completo="María Pérez",
        es_principal=True,
    )
    father = PatientResponsibleCreate(
        parentesco=ResponsibleRelationship.FATHER,
        nombre_completo="Juan Pérez",
        es_principal=True,
    )

    with pytest.raises(BusinessRuleError) as error:
        service.create(minor_command(responsables=[mother, father]), actor_id=1)

    assert error.value.code == "RESPONSABLE_PRINCIPAL_DUPLICADO"
    assert session.rollbacks == 1


def test_rejects_duplicate_document_before_persisting(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment
    repository.document_owner = SimpleNamespace(id=99)

    with pytest.raises(ConflictError) as error:
        service.create(adult_command(), actor_id=1)

    assert error.value.code == "DOCUMENTO_PACIENTE_DUPLICADO"
    assert repository.created_patient_count == 0
    assert session.rollbacks == 1


def test_rejects_overlapping_risk_periods_in_atomic_registration(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment
    first = PatientRiskCreate(
        grupo_riesgo_id=7,
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=date(2026, 1, 31),
    )
    second = PatientRiskCreate(
        grupo_riesgo_id=7,
        fecha_inicio=date(2026, 1, 15),
    )

    with pytest.raises(BusinessRuleError) as error:
        service.create(adult_command(riesgos=[first, second]), actor_id=1)

    assert error.value.code == "RIESGO_SUPERPUESTO"
    assert repository.created_patient_count == 0
    assert session.rollbacks == 1


def test_update_checks_document_uniqueness_without_mutating_patient(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, _audit = environment
    created = service.create(adult_command(), actor_id=1)
    repository.document_owner = SimpleNamespace(id=42)

    with pytest.raises(ConflictError):
        service.update(created.id, PatientUpdate(numero_documento="99999999"), actor_id=1)

    assert repository.patients[created.id].numero_documento == "12345678"
    assert session.rollbacks == 1


def test_professional_registers_patient_in_site_without_assignment(
    environment: PatientTestEnvironment,
) -> None:
    """La sede de registro solo debe existir y estar activa, no estar asignada."""

    service, repository, _session, _audit = environment
    repository.professional_establishment_ids = {1}

    result = service.create(
        adult_command(establecimiento_registro_id=99),
        actor_id=41,
        actor_roles={"PROFESIONAL"},
    )

    assert result.establecimiento_registro_id == 99
    assert repository.patients[result.id].profesional_registro_id == 7


def test_administrator_and_internal_callers_keep_the_registration_author_empty(
    environment: PatientTestEnvironment,
) -> None:
    """ADMIN no necesita vínculo clínico: mantiene su acceso global."""

    service, repository, _session, _audit = environment

    administrator = service.create(adult_command(), actor_id=1, actor_roles={"ADMIN"})
    internal = service.create(adult_command(numero_documento="99999998"), actor_id=1)

    assert repository.patients[administrator.id].profesional_registro_id is None
    assert repository.patients[internal.id].profesional_registro_id is None


def test_professional_transfers_patient_to_site_without_assignment(
    environment: PatientTestEnvironment,
) -> None:
    """Un traslado ya no exige asignación vigente en la sede destino."""

    service, repository, session, _audit = environment
    created = service.create(adult_command(establecimiento_registro_id=1), actor_id=41)
    repository.patients_in_scope = {created.id}
    repository.professional_establishment_ids = {1}

    result = service.update(
        created.id,
        PatientUpdate(establecimiento_registro_id=99),
        actor_id=41,
        actor_roles={"PROFESIONAL"},
    )

    assert result.establecimiento_registro_id == 99
    assert repository.patients[created.id].profesional_registro_id == 7
    assert session.commits == 2


def test_field_update_without_transfer_leaves_the_registration_link_untouched(
    environment: PatientTestEnvironment,
) -> None:
    """Solo el registro y el traslado cambian el autor del vínculo."""

    service, repository, _session, _audit = environment
    created = service.create(adult_command(establecimiento_registro_id=1), actor_id=41)
    repository.patients_in_scope = {created.id}
    repository.professional_establishment_ids = {1}

    service.update(
        created.id,
        PatientUpdate(direccion="Av. Siempre Viva 742"),
        actor_id=41,
        actor_roles={"PROFESIONAL"},
    )

    assert repository.patients[created.id].profesional_registro_id is None


def test_deactivate_marks_state_and_creates_audit_without_physical_delete(
    environment: PatientTestEnvironment,
) -> None:
    service, repository, session, audit = environment
    created = service.create(adult_command(), actor_id=1)

    result = service.deactivate(created.id, actor_id=2)

    assert result.estado is False
    assert created.id in repository.patients
    assert repository.patients[created.id].estado is False
    assert session.commits == 2
    assert audit.events[-1]["action"] == "DEACTIVATE"
