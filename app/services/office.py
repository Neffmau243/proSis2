"""Transactional administration and RB-04 office-assignment use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.office import AREA_SERVICES, default_services, office_context
from app.domain.staff_catalog import is_care_area, is_staff_specialty_code
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.office import office_assignment_to_response, office_to_response
from app.models.organization import Office, OfficeProfessional
from app.repositories.office import OfficeRepository
from app.schemas.office import (
    OfficeAssignmentClose,
    OfficeAssignmentCreate,
    OfficeAssignmentResponse,
    OfficeCreate,
    OfficeResponse,
    OfficeUpdate,
)


class OfficeService:
    """Administrator-owned lifecycle for care offices and sub-offices."""

    def __init__(
        self,
        session: Session,
        audit: Callable[..., None] | None = None,
    ) -> None:
        self._session = session
        self._repository = OfficeRepository(session)
        self._audit = audit

    def list(
        self,
        *,
        establishment_id: int | None = None,
        include_inactive: bool = False,
    ) -> list[OfficeResponse]:
        names = self._repository.active_specialties()
        return [
            office_to_response(office, names)
            for office in self._repository.list_offices(
                establishment_id=establishment_id,
                include_inactive=include_inactive,
            )
        ]

    def get(self, office_id: int) -> OfficeResponse:
        office = self._repository.get_by_id(office_id)
        if office is None:
            raise NotFoundError(
                code="CONSULTORIO_NO_ENCONTRADO", message="No existe el consultorio solicitado."
            )
        return office_to_response(office, self._repository.active_specialties())

    def create(self, command: OfficeCreate, *, actor_id: int) -> OfficeResponse:
        try:
            self._validate_context(
                establishment_id=command.establecimiento_id,
                specialty_code=command.especialidad_codigo,
                parent_id=command.consultorio_padre_id,
                office_id=None,
            )
            office = Office(
                establecimiento_id=command.establecimiento_id,
                consultorio_padre_id=command.consultorio_padre_id,
                codigo=command.codigo,
                nombre=command.nombre,
                especialidad_codigo=command.especialidad_codigo,
                area_codigo=command.area_codigo,
                servicios_codigos=command.servicios_codigos,
            )
            if command.consultorio_padre_id is not None:
                office.padre = self._repository.get_by_id(command.consultorio_padre_id)
            self._repository.add_office(office)
            with self._session.no_autoflush:
                self._validate_configuration(office)
            self._session.flush()
            self._record_audit(
                actor_id=actor_id,
                action="INSERT",
                office=office,
                before=None,
            )
            self._session.commit()
            return office_to_response(office, self._repository.active_specialties())
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="CONSULTORIO_EN_CONFLICTO",
                message="Ya existe un consultorio con ese código en el establecimiento.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update(self, office_id: int, command: OfficeUpdate, *, actor_id: int) -> OfficeResponse:
        try:
            office = self._lock_office(office_id)
            if office is None:
                raise NotFoundError(
                    code="CONSULTORIO_NO_ENCONTRADO", message="No existe el consultorio solicitado."
                )
            before = self._snapshot(office)
            changes = command.model_dump(exclude_unset=True)
            parent_id = changes.get("consultorio_padre_id", office.consultorio_padre_id)
            specialty_code = changes.get("especialidad_codigo", office.especialidad_codigo)
            self._validate_context(
                establishment_id=office.establecimiento_id,
                specialty_code=specialty_code,
                parent_id=parent_id,
                office_id=office.id,
            )
            for field, value in changes.items():
                setattr(office, field, value)
            if "consultorio_padre_id" in changes:
                office.padre = self._repository.get_by_id(parent_id) if parent_id else None
            self._validate_configuration(office)
            # Revalidate descendants whose inherited area/services/qualification changed.
            for descendant in self._repository.list_offices(
                establishment_id=office.establecimiento_id,
                include_inactive=True,
            ):
                if office.id in office_context(descendant).ancestor_ids:
                    self._validate_configuration(descendant)
            self._session.flush()
            self._record_audit(actor_id=actor_id, action="UPDATE", office=office, before=before)
            self._session.commit()
            return office_to_response(office, self._repository.active_specialties())
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="CONSULTORIO_EN_CONFLICTO",
                message="Ya existe un consultorio con ese código en el establecimiento.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def deactivate(self, office_id: int, *, actor_id: int) -> OfficeResponse:
        try:
            office = self._lock_office(office_id)
            if office is None:
                raise NotFoundError(
                    code="CONSULTORIO_NO_ENCONTRADO", message="No existe el consultorio solicitado."
                )
            if not office.activo:
                raise ConflictError(
                    code="CONSULTORIO_YA_INACTIVO",
                    message="El consultorio ya se encuentra inactivo.",
                )
            self._repository.get_active_establishment(office.establecimiento_id, lock=True)
            descendants = self._repository.list_offices(
                establishment_id=office.establecimiento_id,
                include_inactive=True,
            )
            if any(
                item.activo and office.id in office_context(item).ancestor_ids
                for item in descendants
            ):
                raise BusinessRuleError(
                    code="CONSULTORIO_CON_HIJOS_ACTIVOS",
                    message="Dé de baja primero los subconsultorios activos de este consultorio.",
                )
            before = self._snapshot(office)
            office.activo = False
            self._session.flush()
            self._record_audit(actor_id=actor_id, action="DEACTIVATE", office=office, before=before)
            self._session.commit()
            return office_to_response(office, self._repository.active_specialties())
        except Exception:
            self._session.rollback()
            raise

    def _validate_context(
        self,
        *,
        establishment_id: int,
        specialty_code: str | None,
        parent_id: int | None,
        office_id: int | None,
    ) -> None:
        if self._repository.get_active_establishment(establishment_id, lock=True) is None:
            raise NotFoundError(
                code="ESTABLECIMIENTO_NO_ACTIVO",
                message="El establecimiento del consultorio no existe o está inactivo.",
            )
        if (
            specialty_code is not None
            and self._repository.get_active_specialty(specialty_code) is None
        ):
            raise NotFoundError(
                code="ESPECIALIDAD_NO_ACTIVA",
                message="La especialidad del consultorio no existe o está inactiva.",
            )
        if parent_id is None:
            return
        if office_id is not None and parent_id == office_id:
            raise BusinessRuleError(
                code="CONSULTORIO_PADRE_INVALIDO",
                message="Un consultorio no puede ser su propio padre.",
            )
        parent = self._repository.get_active_office(parent_id, lock=True)
        if parent is None:
            raise NotFoundError(
                code="CONSULTORIO_PADRE_NO_ACTIVO",
                message="El consultorio padre no existe o está inactivo.",
            )
        if parent.establecimiento_id != establishment_id:
            raise BusinessRuleError(
                code="CONSULTORIO_PADRE_OTRA_SEDE",
                message="El consultorio padre debe pertenecer al mismo establecimiento.",
            )
        if not office_context(parent).active:
            raise BusinessRuleError(
                code="CONSULTORIO_PADRE_NO_ACTIVO",
                message="Active o seleccione una jerarquía de consultorios disponible.",
            )
        if office_id is not None and self._repository.parent_chain_contains(
            candidate_parent_id=parent_id,
            office_id=office_id,
        ):
            raise BusinessRuleError(
                code="JERARQUIA_CONSULTORIO_CICLICA",
                message="La relación padre/hijo propuesta forma un ciclo de consultorios.",
            )

    def _lock_office(self, office_id: int) -> Office | None:
        office = self._repository.get_by_id(office_id)
        if office is not None:
            # All hierarchy mutations lock the site before individual offices.
            self._repository.get_active_establishment(office.establecimiento_id, lock=True)
            return self._repository.get_by_id(office_id, lock=True)
        return None

    def _validate_configuration(self, office: Office) -> None:
        context = office_context(office)
        area = office.area_codigo
        area_entity = self._repository.get_active_specialty(area) if area else None
        if area is not None and (
            area_entity is None or not (area in AREA_SERVICES or is_care_area(area_entity))
        ):
            raise BusinessRuleError(
                code="AREA_CONSULTORIO_INVALIDA",
                message="Seleccione un área asistencial activa del catálogo.",
            )
        parent = office.padre
        if parent and context.area_code != office_context(parent).area_code:
            raise BusinessRuleError(
                code="AREA_CONSULTORIO_INCOMPATIBLE",
                message="El subconsultorio debe pertenecer al área de su consultorio padre.",
            )
        allowed = set(
            office_context(parent).service_codes if parent else default_services(context.area_code)
        )
        if office.servicios_codigos is not None:
            if set(office.servicios_codigos) - allowed or any(
                self._repository.get_active_specialty(code) is None
                for code in office.servicios_codigos
            ):
                raise BusinessRuleError(
                    code="SERVICIO_CONSULTORIO_INCOMPATIBLE",
                    message="Habilite servicios activos del área y del consultorio padre.",
                )
        if (
            context.required_specialty
            and context.required_specialty not in default_services(context.area_code)
            and (
                context.required_specialty in AREA_SERVICES
                or is_care_area(self._repository.get_active_specialty(context.required_specialty))
                or not is_staff_specialty_code(context.required_specialty)
            )
        ):
            raise BusinessRuleError(
                code="ESPECIALIDAD_CONSULTORIO_INCOMPATIBLE",
                message="La especialidad requerida debe pertenecer al área del consultorio.",
            )
        if context.required_specialty and office.id is not None:
            if any(
                not self._repository.professional_has_specialty(
                    professional_id, context.required_specialty
                )
                for professional_id in self._repository.nonexpired_professionals(office.id)
            ):
                raise BusinessRuleError(
                    code="ESPECIALIDAD_REQUERIDA_POR_ASIGNACION",
                    message="Ajuste las asignaciones antes de cambiar el área o especialidad.",
                )

    def _record_audit(
        self,
        *,
        actor_id: int,
        action: str,
        office: Office,
        before: dict[str, object] | None,
    ) -> None:
        if self._audit is not None:
            self._audit(
                actor_id=actor_id,
                action=action,
                table_name="consultorios",
                record_id=office.id,
                before=before,
                after=self._snapshot(office),
            )

    @staticmethod
    def _snapshot(office: Office) -> dict[str, object]:
        return {
            "id": office.id,
            "establecimiento_id": office.establecimiento_id,
            "consultorio_padre_id": office.consultorio_padre_id,
            "codigo": office.codigo,
            "nombre": office.nombre,
            "especialidad_codigo": office.especialidad_codigo,
            "area_codigo": office.area_codigo,
            "servicios_codigos": office.servicios_codigos,
            "activo": office.activo,
        }


class OfficeAssignmentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = OfficeRepository(session)

    def list(self, office_id: int) -> list[OfficeAssignmentResponse]:
        if self._repository.get_by_id(office_id) is None:
            raise NotFoundError(
                code="CONSULTORIO_NO_ACTIVO", message="El consultorio no existe o está inactivo."
            )
        return [
            office_assignment_to_response(item)
            for item in self._repository.list_assignments(office_id)
        ]

    def assign(
        self, office_id: int, command: OfficeAssignmentCreate, *, actor_id: int
    ) -> OfficeAssignmentResponse:
        try:
            candidate = self._repository.get_by_id(office_id)
            if candidate is not None:
                self._repository.get_active_establishment(candidate.establecimiento_id, lock=True)
            office = self._repository.get_active_office(office_id, lock=True)
            if office is None:
                raise NotFoundError(
                    code="CONSULTORIO_NO_ACTIVO",
                    message="El consultorio no existe o está inactivo.",
                )
            context = office_context(office)
            if not context.active:
                raise BusinessRuleError(
                    code="JERARQUIA_CONSULTORIO_NO_ACTIVA",
                    message="El consultorio o alguno de sus padres está inactivo.",
                )
            if self._repository.get_active_professional(
                command.profesional_id, lock=command.vincular_area
            ) is None:
                raise NotFoundError(
                    code="PROFESIONAL_NO_ACTIVO",
                    message="El profesional no existe o está inactivo.",
                )
            area_to_link = None
            if context.required_specialty and not self._repository.professional_has_specialty(
                command.profesional_id, context.required_specialty
            ):
                if (
                    command.vincular_area
                    and context.required_specialty == context.area_code
                    and is_care_area(self._repository.get_active_specialty(context.area_code))
                ):
                    area_to_link = context.area_code
                else:
                    raise BusinessRuleError(
                        code="PROFESIONAL_SIN_ESPECIALIDAD",
                        message="El profesional no tiene el área o requisito del consultorio.",
                    )
            if (
                self._repository.get_assignment(
                    office_id, command.profesional_id, command.fecha_inicio, lock=True
                )
                is not None
            ):
                raise ConflictError(
                    code="ASIGNACION_DUPLICADA",
                    message="Ya existe una asignación con esa fecha de inicio.",
                )
            if self._repository.has_overlapping_assignment(
                office_id=office_id,
                professional_id=command.profesional_id,
                start_date=command.fecha_inicio,
                end_date=command.fecha_fin,
            ):
                raise ConflictError(
                    code="ASIGNACION_VIGENTE_SUPERPUESTA",
                    message="Ya existe una asignación superpuesta en este consultorio.",
                )
            if command.es_responsable:
                prior = self._repository.get_current_responsible(
                    office_id, command.fecha_inicio, lock=True
                )
                if prior is not None:
                    if prior.fecha_inicio >= command.fecha_inicio:
                        raise ConflictError(
                            code="RESPONSABLE_VIGENTE_EXISTENTE",
                            message="El reemplazo debe comenzar después del responsable actual.",
                        )
                    prior.fecha_fin = command.fecha_inicio - timedelta(days=1)

            if area_to_link:
                self._repository.link_professional_area(
                    command.profesional_id, area_to_link, actor_id=actor_id
                )
            entity = OfficeProfessional(
                consultorio_id=office_id,
                profesional_id=command.profesional_id,
                fecha_inicio=command.fecha_inicio,
                fecha_fin=command.fecha_fin,
                es_responsable=command.es_responsable,
            )
            self._repository.add(entity)
            self._session.flush()
            self._repository.audit(
                actor_id=actor_id,
                action="INSERT",
                record_id=office_id,
                after=self._snapshot(entity),
            )
            self._session.commit()
            return office_assignment_to_response(entity)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="ASIGNACION_EN_CONFLICTO", message="No se pudo guardar la asignación."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def close(
        self,
        office_id: int,
        professional_id: int,
        start_date: date,
        command: OfficeAssignmentClose,
        *,
        actor_id: int,
    ) -> OfficeAssignmentResponse:
        try:
            if self._repository.get_by_id(office_id, lock=True) is None:
                raise NotFoundError(
                    code="CONSULTORIO_NO_ACTIVO",
                    message="El consultorio no existe o está inactivo.",
                )
            entity = self._repository.get_assignment(
                office_id, professional_id, start_date, lock=True
            )
            if entity is None:
                raise NotFoundError(
                    code="ASIGNACION_NO_ENCONTRADA", message="No existe la asignación indicada."
                )
            if command.fecha_fin < entity.fecha_inicio:
                raise BusinessRuleError(
                    code="FECHA_FIN_INVALIDA",
                    message="La fecha de fin no puede ser anterior al inicio.",
                )
            if entity.fecha_fin is not None and command.fecha_fin > entity.fecha_fin:
                raise BusinessRuleError(
                    code="CIERRE_AMPLIA_VIGENCIA",
                    message="El cierre no puede ampliar una vigencia ya definida.",
                )
            entity.fecha_fin = command.fecha_fin
            self._session.flush()
            self._repository.audit(
                actor_id=actor_id,
                action="UPDATE",
                record_id=office_id,
                after=self._snapshot(entity),
            )
            self._session.commit()
            return office_assignment_to_response(entity)
        except Exception:
            self._session.rollback()
            raise

    @staticmethod
    def _snapshot(entity: OfficeProfessional) -> dict[str, object]:
        return {
            "consultorio_id": entity.consultorio_id,
            "profesional_id": entity.profesional_id,
            "fecha_inicio": entity.fecha_inicio.isoformat(),
            "fecha_fin": entity.fecha_fin.isoformat() if entity.fecha_fin else None,
            "es_responsable": entity.es_responsable,
        }
