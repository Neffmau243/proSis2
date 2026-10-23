"""Rules shared by both administrative entry points to a care area."""

from sqlalchemy.orm import Session

from app.domain.office import AREA_NAMES
from app.exceptions import ConflictError
from app.models.catalog import Specialty
from app.repositories.care_configuration import CareConfigurationRepository
from app.repositories.staff_catalog import StaffCatalogRepository


class CareAreaRules:
    def __init__(self, session: Session):
        self.repository = CareConfigurationRepository(session)
        self.catalog = StaffCatalogRepository(session)

    def validate_name(self, entry: Specialty, name: str) -> None:
        if self.catalog.specialty_name_exists(name, exclude_code=entry.codigo):
            raise ConflictError(
                code="ESPECIALIDAD_DUPLICADA",
                message="Ya existe un área o especialidad con ese nombre.",
            )

    def validate_state(self, entry: Specialty, active: bool) -> None:
        if entry.activo == active:
            raise ConflictError(code="ESTADO_SIN_CAMBIOS", message="El área ya tiene ese estado.")
        if not active and (
            entry.codigo in AREA_NAMES or self.repository.area_is_used(entry.codigo)
        ):
            raise ConflictError(
                code="AREA_EN_USO",
                message=(
                    "El área organiza servicios existentes o tiene consultorios, servicios "
                    "o profesionales activos. Revise sus vínculos antes de darla de baja."
                ),
            )
