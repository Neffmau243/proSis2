"""Transactional addition of catalog services to a root office's whitelist."""

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.office import (
    custom_service_area,
    default_services,
    office_context,
)
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.office import office_to_response
from app.models.catalog import Specialty
from app.models.organization import Office
from app.repositories.office import OfficeRepository
from app.repositories.office_service import OfficeServiceCatalogRepository
from app.schemas.catalog import CodeCatalogItem
from app.schemas.office_service import OfficeServiceAdd, OfficeServiceAdded
from app.services.care_service_catalog import CareServiceCatalog
from app.services.office import OfficeService


class OfficeCareService:
    def __init__(self, session: Session, audit: Callable[..., None] | None = None) -> None:
        self._session = session
        self._offices = OfficeRepository(session)
        self._catalog = OfficeServiceCatalogRepository(session)
        self._audit = audit

    def _root(self, office_id: int, *, lock: bool = False) -> Office:
        office = self._offices.get_by_id(office_id)
        if office is None:
            raise NotFoundError(
                code="CONSULTORIO_NO_ENCONTRADO", message="No existe el consultorio."
            )
        if self._offices.get_active_establishment(office.establecimiento_id, lock=lock) is None:
            raise BusinessRuleError(
                code="ESTABLECIMIENTO_NO_ACTIVO",
                message="El establecimiento del consultorio está inactivo.",
            )
        if lock:
            self._session.refresh(office, with_for_update=True)
        if not office_context(office).active:
            raise BusinessRuleError(
                code="CONSULTORIO_NO_ACTIVO", message="Seleccione un consultorio activo."
            )
        if office.consultorio_padre_id is not None:
            raise BusinessRuleError(
                code="SERVICIOS_DESDE_PADRE",
                message="Agregue el servicio desde el consultorio principal de esta área.",
            )
        return office

    def _allowed(self, entry: Specialty, area: str | None) -> bool:
        return entry.codigo in default_services(area) or (
            area is not None and custom_service_area(entry) == area
        )

    def list(self, office_id: int) -> list[CodeCatalogItem]:
        area = office_context(self._root(office_id)).area_code
        return [
            CodeCatalogItem.model_validate(entry, from_attributes=True)
            for entry in self._catalog.entries()
            if entry.activo and self._allowed(entry, area)
        ]

    def add(
        self, office_id: int, command: OfficeServiceAdd, *, actor_id: int
    ) -> OfficeServiceAdded:
        try:
            office = self._root(office_id, lock=True)
            context = office_context(office)
            if context.area_code is None:
                raise BusinessRuleError(
                    code="AREA_CONSULTORIO_INVALIDA",
                    message="Configure el área del consultorio antes de agregar servicios.",
                )
            before = OfficeService.snapshot(office)
            if command.codigo is not None:
                entry = self._catalog.get(command.codigo)
                if entry is None or not self._allowed(entry, context.area_code):
                    raise BusinessRuleError(
                        code="SERVICIO_OTRA_AREA",
                        message="Seleccione un servicio del área de este consultorio.",
                    )
            else:
                entry = CareServiceCatalog(self._session, self._audit).find_or_create(
                    command.nombre, context.area_code, actor_id=actor_id
                )
            if not entry.activo:
                raise ConflictError(
                    code="SERVICIO_INACTIVO",
                    message="El servicio ya existe y está inactivo. Revise su catálogo.",
                )
            enabled = [
                code
                for code in context.service_codes
                if self._offices.get_active_specialty(code) is not None
            ]
            office.servicios_codigos = list(dict.fromkeys([*enabled, entry.codigo]))
            validator = OfficeService(self._session)
            validator.validate_configuration(office)
            self._session.flush()
            service = CodeCatalogItem.model_validate(entry, from_attributes=True)
            if self._audit:
                self._audit(
                    actor_id=actor_id,
                    action="UPDATE",
                    table_name="consultorios",
                    record_id=office.id,
                    before=before,
                    after=OfficeService.snapshot(office),
                )
            response = OfficeServiceAdded(
                consultorio=office_to_response(office, self._offices.active_specialties()),
                servicio=service,
            )
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="SERVICIO_DUPLICADO",
                message=(
                    "El servicio se registró en otra solicitud. "
                    "Recargue el catálogo y selecciónelo."
                ),
            ) from exc
        except Exception:
            self._session.rollback()
            raise
