"""Administrative configuration without mutations of encounters or print snapshots."""

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.office import AREA_NAMES, office_context
from app.domain.staff_catalog import is_care_area
from app.exceptions import ConflictError, NotFoundError
from app.models.organization import Establishment
from app.repositories.care_configuration import CareConfigurationRepository
from app.repositories.staff_catalog import StaffCatalogRepository
from app.schemas.care_configuration import (
    AreaAdminItem,
    AreaName,
    AreaOfficeUsage,
    EstablishmentAdminItem,
    EstablishmentFields,
    EstablishmentUpdate,
)
from app.schemas.common import PageResponse
from app.schemas.office_service import CareServiceUpdate
from app.schemas.staff_catalog import SpecialtyCreate
from app.services.care_area_rules import CareAreaRules
from app.services.care_service_catalog import CareServiceCatalog
from app.services.staff_catalog import StaffCatalogService


class EstablishmentAdministration:
    def __init__(self, session: Session, audit: Callable[..., None] | None = None):
        self.session = session
        self.repository = CareConfigurationRepository(session)
        self.audit = audit

    def _item(self, entity: Establishment, count: int | None = None) -> EstablishmentAdminItem:
        district = entity.ubigeo
        return EstablishmentAdminItem(
            **{key: getattr(entity, key) for key in EstablishmentFields.model_fields},
            id=entity.id,
            activo=entity.activo,
            ubicacion=(
                f"{district.departamento} / {district.provincia} / {district.distrito}"
                if district
                else None
            ),
            consultorios_total=(
                self.repository.office_counts().get(entity.id, 0) if count is None else count
            ),
            fua_personal_atiende=entity.fua_personal_atiende,
            fua_lugar_atencion=entity.fua_lugar_atencion,
            fua_codigo_aisped=entity.fua_codigo_aisped,
            fua_renipress_preimpreso=entity.fua_renipress_preimpreso,
        )

    def list(self, *, query=None, include_inactive=False, limit=25, offset=0):
        entities, total = self.repository.establishments(query, include_inactive, limit, offset)
        counts = self.repository.office_counts()
        return PageResponse[EstablishmentAdminItem](
            items=[self._item(item, counts.get(item.id, 0)) for item in entities],
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(entities) < total,
        )

    def get(self, identifier: int):
        entity = self.repository.establishment(identifier)
        if entity is None:
            raise NotFoundError(
                code="ESTABLECIMIENTO_NO_ENCONTRADO", message="No existe el establecimiento."
            )
        return self._item(entity)

    def save(
        self, command: EstablishmentFields | EstablishmentUpdate, *, identifier=None, actor_id: int
    ):
        try:
            entity = self.repository.establishment(identifier, lock=True) if identifier else None
            if identifier and entity is None:
                raise NotFoundError(
                    code="ESTABLECIMIENTO_NO_ENCONTRADO", message="No existe el establecimiento."
                )
            before = self._item(entity).model_dump() if entity else None
            changes = command.model_dump(exclude_unset=True)
            if (
                changes.get("ubigeo_codigo")
                and self.repository.district(changes["ubigeo_codigo"]) is None
            ):
                raise NotFoundError(
                    code="UBIGEO_NO_ENCONTRADO", message="Seleccione un distrito del catálogo."
                )
            if entity is None:
                entity = Establishment(**changes, activo=True)
                self.session.add(entity)
            else:
                for field, value in changes.items():
                    setattr(entity, field, value)
                if "ubigeo_codigo" in changes:
                    entity.ubigeo = (
                        self.repository.district(changes["ubigeo_codigo"])
                        if changes["ubigeo_codigo"]
                        else None
                    )
            self.session.flush()
            response = self._item(entity)
            self._record(
                entity.id, actor_id, "UPDATE" if before else "INSERT", before, response.model_dump()
            )
            self.session.commit()
            return response
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                code="ESTABLECIMIENTO_DUPLICADO",
                message="El código RENAES o IDEESS ya está registrado.",
            ) from exc
        except Exception:
            self.session.rollback()
            raise

    def set_active(self, identifier: int, active: bool, *, actor_id: int):
        try:
            entity = self.repository.establishment(identifier, lock=True)
            if entity is None:
                raise NotFoundError(
                    code="ESTABLECIMIENTO_NO_ENCONTRADO", message="No existe el establecimiento."
                )
            if entity.activo == active:
                raise ConflictError(
                    code="ESTADO_SIN_CAMBIOS", message="El establecimiento ya tiene ese estado."
                )
            if not active and self.repository.has_active_offices(identifier):
                raise ConflictError(
                    code="ESTABLECIMIENTO_EN_USO",
                    message=(
                        "Dé de baja primero los consultorios activos de este establecimiento. "
                        "No se modificó ningún registro."
                    ),
                )
            before = self._item(entity).model_dump()
            entity.activo = active
            self.session.flush()
            response = self._item(entity)
            self._record(
                identifier,
                actor_id,
                "REACTIVATE" if active else "DEACTIVATE",
                before,
                response.model_dump(),
            )
            self.session.commit()
            return response
        except Exception:
            self.session.rollback()
            raise

    def _record(self, identifier, actor_id, action, before, after):
        if self.audit:
            self.audit(
                actor_id=actor_id,
                action=action,
                table_name="establecimientos",
                record_id=identifier,
                before=before,
                after=after,
            )


class AreaAdministration:
    def __init__(self, session: Session, audit: Callable[..., None] | None = None):
        self.session = session
        self.repository = CareConfigurationRepository(session)
        self.catalog = StaffCatalogRepository(session)
        self.audit = audit

    def list(self, *, include_inactive=False):
        offices = self.repository.offices()
        return [
            AreaAdminItem(
                codigo=item.codigo,
                nombre=item.nombre,
                activo=item.activo,
                es_area_base=item.codigo in AREA_NAMES,
                consultorios=[
                    AreaOfficeUsage(
                        id=office.id,
                        nombre=office.nombre,
                        establecimiento_id=office.establecimiento_id,
                        establecimiento_nombre=office.establecimiento.nombre,
                        activo=office.activo,
                    )
                    for office in offices
                    if office_context(office).area_code == item.codigo
                ],
            )
            for item in self.repository.areas()
            if is_care_area(item) and (include_inactive or item.activo)
        ]

    def save(self, command: AreaName, *, code: str | None = None, actor_id: int):
        service = StaffCatalogService(self.session, self.audit)
        if code is None:
            response = service.create_specialty(
                SpecialtyCreate(nombre=command.nombre, es_area=True), actor_id=actor_id
            )
        else:
            self._get(code)
            # Areas can also be offered as services: both routes share rename rules.
            response = CareServiceCatalog(self.session, self.audit).update(
                code, CareServiceUpdate(nombre=command.nombre), actor_id=actor_id
            )
        return next(
            item for item in self.list(include_inactive=True) if item.codigo == response.codigo
        )

    def _get(self, code, *, lock=False):
        entry = self.catalog.get_specialty(code, lock=lock)
        if entry is None or not is_care_area(entry):
            raise NotFoundError(code="AREA_NO_ENCONTRADA", message="No existe el área de atención.")
        return entry

    def set_active(self, code: str, active: bool, *, actor_id: int):
        try:
            entry = self._get(code, lock=True)
            CareAreaRules(self.session).validate_state(entry, active)
            before = {"codigo": code, "nombre": entry.nombre, "activo": entry.activo}
            entry.activo = active
            self.session.flush()
            if self.audit:
                self.audit(
                    actor_id=actor_id,
                    action="REACTIVATE" if active else "DEACTIVATE",
                    table_name="especialidades",
                    record_id=None,
                    before=before,
                    after={**before, "activo": active},
                )
            self.session.commit()
            return next(item for item in self.list(include_inactive=True) if item.codigo == code)
        except Exception:
            self.session.rollback()
            raise
