"""Care-service catalog lifecycle, independent of enabling a service in an office."""

from collections.abc import Callable
from hashlib import sha256

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.office import (
    CUSTOM_SERVICE_GROUP,
    areas_for_service,
    custom_service_area,
    office_context,
)
from app.domain.staff_catalog import catalog_name_key, is_care_area
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.catalog import Specialty
from app.repositories.office import OfficeRepository
from app.repositories.office_service import OfficeServiceCatalogRepository
from app.schemas.office_service import (
    CareServiceCreate,
    CareServiceItem,
    CareServiceOffice,
    CareServiceUpdate,
)
from app.services.care_area_rules import CareAreaRules


def service_areas(entry: Specialty) -> list[str]:
    custom = custom_service_area(entry)
    if custom:
        return [custom]
    return areas_for_service(entry.codigo) or ([entry.codigo] if is_care_area(entry) else [])


class CareServiceCatalog:
    def __init__(self, session: Session, audit: Callable[..., None] | None = None) -> None:
        self._session = session
        self._catalog = OfficeServiceCatalogRepository(session)
        self._offices = OfficeRepository(session)
        self._audit = audit

    def list(self, *, include_inactive: bool = False) -> list[CareServiceItem]:
        offices = self._offices.list_offices(include_inactive=True)
        usage: dict[str, list[CareServiceOffice]] = {}
        for office in offices:
            context = office_context(office)
            for code in context.service_codes:
                usage.setdefault(code, []).append(
                    CareServiceOffice(
                        id=office.id,
                        nombre=office.nombre,
                        codigo=office.codigo,
                        consultorio_padre_id=office.consultorio_padre_id,
                        consultorio_padre_nombre=office.padre.nombre if office.padre else None,
                        establecimiento_id=office.establecimiento_id,
                        establecimiento_nombre=(
                            office.establecimiento.nombre if office.establecimiento else None
                        ),
                        activo=context.active,
                    )
                )
        return [
            CareServiceItem(
                codigo=entry.codigo,
                nombre=entry.nombre,
                activo=entry.activo,
                area_codigos=service_areas(entry),
                consultorios=usage.get(entry.codigo, []),
            )
            for entry in self._catalog.entries()
            if service_areas(entry) and (include_inactive or entry.activo)
        ]

    def find_or_create(self, name: str, area: str, *, actor_id: int) -> Specialty:
        """Stage a registration in the caller's transaction, without committing."""
        area_entry = self._catalog.get(area, lock=True)
        if area_entry is None or not area_entry.activo or not is_care_area(area_entry):
            raise BusinessRuleError(
                code="AREA_CONSULTORIO_INVALIDA", message="Seleccione un área asistencial activa."
            )
        key = catalog_name_key(name)
        for entry in self._catalog.entries():
            if area in service_areas(entry) and catalog_name_key(entry.nombre) == key:
                return entry
        identity = f"{area}:{key}"
        attempt = 0
        while True:
            digest = sha256(f"{identity}:{attempt}".encode()).hexdigest()[:16].upper()
            code = f"SRV-{digest}"
            if self._catalog.get(code) is None:
                break
            attempt += 1
        entry = Specialty(
            codigo=code,
            nombre=name,
            grupo=f"{CUSTOM_SERVICE_GROUP}{area}",
            es_area=False,
            activo=True,
        )
        self._catalog.add(entry)
        self._session.flush()
        self._record(entry, actor_id=actor_id, before=None)
        return entry

    def get(self, code: str) -> CareServiceItem:
        entry = self._catalog.get(code)
        if entry is None or not service_areas(entry):
            raise NotFoundError(code="SERVICIO_NO_ENCONTRADO", message="No existe el servicio.")
        return self._item(code)

    def create(self, command: CareServiceCreate, *, actor_id: int) -> CareServiceItem:
        try:
            entry = self.find_or_create(command.nombre, command.area_codigo, actor_id=actor_id)
            if not entry.activo:
                raise ConflictError(
                    code="SERVICIO_INACTIVO",
                    message="El servicio ya existe; reactívelo en el catálogo.",
                )
            result = self._item(entry.codigo)
            self._session.commit()
            return result
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="SERVICIO_DUPLICADO", message="El servicio ya existe. Recargue el catálogo."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update(self, code: str, command: CareServiceUpdate, *, actor_id: int) -> CareServiceItem:
        try:
            entry = self._get(code)
            before = self._snapshot(entry)
            if is_care_area(entry):
                CareAreaRules(self._session).validate_name(entry, command.nombre)
            key = catalog_name_key(command.nombre)
            areas = set(service_areas(entry))
            if any(
                other.codigo != code
                and areas.intersection(service_areas(other))
                and catalog_name_key(other.nombre) == key
                for other in self._catalog.entries()
            ):
                raise ConflictError(
                    code="SERVICIO_DUPLICADO",
                    message="Ya existe un servicio con ese nombre en el área.",
                )
            entry.nombre = command.nombre
            self._session.flush()
            self._record(entry, actor_id=actor_id, before=before)
            result = self._item(code)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def set_active(self, code: str, active: bool, *, actor_id: int) -> CareServiceItem:
        try:
            entry = self._get(code)
            if is_care_area(entry):
                CareAreaRules(self._session).validate_state(entry, active)
            if not active:
                usage = [office for office in self._item(code).consultorios if office.activo]
                if usage:
                    names = ", ".join(
                        f"{office.nombre} ({office.establecimiento_nombre})"
                        if office.establecimiento_nombre
                        else office.nombre
                        for office in usage[:3]
                    )
                    raise BusinessRuleError(
                        code="SERVICIO_EN_USO",
                        message=f"Quite primero el servicio de los consultorios activos: {names}.",
                    )
            before = self._snapshot(entry)
            entry.activo = active
            self._session.flush()
            self._record(entry, actor_id=actor_id, before=before)
            result = self._item(code)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def _get(self, code: str) -> Specialty:
        entry = self._catalog.get(code, lock=True)
        if entry is None or not service_areas(entry):
            raise NotFoundError(code="SERVICIO_NO_ENCONTRADO", message="No existe el servicio.")
        return entry

    def _item(self, code: str) -> CareServiceItem:
        return next(item for item in self.list(include_inactive=True) if item.codigo == code)

    @staticmethod
    def _snapshot(entry: Specialty) -> dict[str, object]:
        return {
            "codigo": entry.codigo,
            "nombre": entry.nombre,
            "activo": entry.activo,
            "grupo": entry.grupo,
            "es_area": entry.es_area,
        }

    def _record(self, entry: Specialty, *, actor_id: int, before: dict | None) -> None:
        if self._audit:
            self._audit(
                actor_id=actor_id,
                action="INSERT" if before is None else "UPDATE",
                table_name="especialidades",
                record_id=None,
                before=before,
                after=self._snapshot(entry),
            )
