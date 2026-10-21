"""Explicitly loaded inputs for the historical encounter and FUA projections."""

from dataclasses import dataclass

from app.domain.age import CalendarAge
from app.domain.office import office_context
from app.exceptions import NotFoundError
from app.models.catalog import Specialty
from app.models.clinical import Attention
from app.models.organization import Establishment, Office
from app.models.patient import Patient
from app.models.security import Professional
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.schemas.attention import AttentionCreate
from app.services.fua_print import build_fua_snapshot
from app.services.nutrition_context import nutrition_context


@dataclass(frozen=True, slots=True)
class AttentionSnapshotContext:
    """ORM inputs whose projection relationships have already been loaded."""

    patient: Patient
    establishment: Establishment
    office: Office | None
    professional: Professional | None
    specialty: Specialty | None

    def apply(
        self, entity: Attention, command: AttentionCreate, age: CalendarAge, condition: str
    ) -> None:
        """Prepare snapshots on the new entity without querying or committing."""
        entity.contexto_clinico = nutrition_context(
            self.patient,
            self.establishment,
            age,
            condition,
            office=self.office,
            professional=self.professional,
            specialty=self.specialty,
        )
        entity.fua_impresion = build_fua_snapshot(
            entity, self.patient, self.establishment, self.professional, command.fua_datos,
            edad_gestacional_valorada=(
                command.valoracion_nutricional.edad_gestacional_semanas
                if command.valoracion_nutricional else None
            ),
        )


class AttentionContextLoader:
    def __init__(self, attentions: AttentionRepository, patients: PatientRepository) -> None:
        self._attentions = attentions
        self._patients = patients

    def load(self, patient: Patient, command: AttentionCreate) -> AttentionSnapshotContext:
        self._patients.load_snapshot_relations(patient.id)
        site = self._attentions.get_snapshot_establishment(command.establecimiento_id)
        if site is None:
            raise NotFoundError(
                code="ESTABLECIMIENTO_NO_ACTIVO",
                message="El establecimiento no existe o está inactivo.",
            )
        office = (
            self._attentions.get_active_office(command.consultorio_id)
            if command.consultorio_id is not None
            else None
        )
        if office is not None:
            # Traversal belongs to loading, not to the later JSON projection.
            office_context(office)
        return AttentionSnapshotContext(
            patient=patient,
            establishment=site,
            office=office,
            professional=(
                self._attentions.get_active_professional(command.profesional_id)
                if command.profesional_id is not None
                else None
            ),
            specialty=(
                self._attentions.get_active_specialty(command.especialidad_codigo)
                if command.especialidad_codigo
                else None
            ),
        )
