"""Office-professional assignment lifecycle, kept independent of office CRUD."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.office import office_context
from app.domain.staff_catalog import is_care_area
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.office import office_assignment_to_response
from app.models.organization import OfficeProfessional
from app.repositories.office import OfficeRepository
from app.schemas.office import (
    OfficeAssignmentClose,
    OfficeAssignmentCreate,
    OfficeAssignmentResponse,
    OfficeAssignmentScope,
    OfficeAssignmentUpdate,
)


class OfficeAssignmentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = OfficeRepository(session)

    def list(
        self, office_id: int, *, include_inherited: bool = False, service_code: str | None = None
    ) -> list[OfficeAssignmentResponse]:
        office = self._repository.get_by_id(office_id)
        if office is None:
            raise NotFoundError(
                code="CONSULTORIO_NO_ACTIVO", message="El consultorio no existe o está inactivo."
            )
        ids = [office_id]
        if include_inherited:
            ids.extend(office_context(office).ancestor_ids)
        result = []
        for source_id in ids:
            for item in self._repository.list_assignments(source_id):
                if service_code and item.servicios_codigos is not None:
                    if service_code not in item.servicios_codigos:
                        continue
                response = office_assignment_to_response(item)
                response.heredada = source_id != office_id
                result.append(response)
        return result

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
            self._validate_scope(office, command.servicios_codigos)
            if (
                self._repository.get_active_professional(
                    command.profesional_id, lock=command.vincular_area
                )
                is None
            ):
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
                    message=(
                        "Ya existe una asignación con esa fecha de inicio. "
                        "Use «Editar servicios» para agregarle otro servicio."
                    ),
                )
            if self._repository.has_overlapping_assignment(
                office_id=office_id,
                professional_id=command.profesional_id,
                start_date=command.fecha_inicio,
                end_date=command.fecha_fin,
            ):
                raise ConflictError(
                    code="ASIGNACION_VIGENTE_SUPERPUESTA",
                    message=(
                        "El profesional ya tiene una asignación en esas fechas. "
                        "Revise las fechas o use «Editar servicios»."
                    ),
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
                servicios_codigos=command.servicios_codigos,
            )
            self._repository.add(entity)
            self._session.flush()
            self._repository.audit(
                actor_id=actor_id,
                action="INSERT",
                record_id=office_id,
                after=self._snapshot(entity),
            )
            response = office_assignment_to_response(entity)
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="ASIGNACION_EN_CONFLICTO", message="No se pudo guardar la asignación."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update(
        self,
        office_id: int,
        professional_id: int,
        start_date: date,
        command: OfficeAssignmentUpdate,
        *,
        actor_id: int,
    ) -> OfficeAssignmentResponse:
        try:
            candidate = self._repository.get_by_id(office_id)
            if candidate is not None:
                self._repository.get_active_establishment(candidate.establecimiento_id, lock=True)
            office = self._repository.get_active_office(office_id, lock=True)
            if office is None:
                raise NotFoundError(
                    code="CONSULTORIO_NO_ACTIVO", message="Seleccione un consultorio activo."
                )
            self._validate_scope(office, command.servicios_codigos)
            if self._repository.get_active_professional(professional_id) is None:
                raise NotFoundError(
                    code="PROFESIONAL_NO_ACTIVO", message="El profesional está inactivo."
                )
            required = office_context(office).required_specialty
            if required and not self._repository.professional_has_specialty(
                professional_id, required
            ):
                raise BusinessRuleError(
                    code="PROFESIONAL_SIN_ESPECIALIDAD",
                    message="El profesional debe conservar el área o requisito del consultorio.",
                )
            entity = self._repository.get_assignment(
                office_id, professional_id, start_date, lock=True
            )
            if entity is None:
                raise NotFoundError(
                    code="ASIGNACION_NO_ENCONTRADA", message="No existe la asignación indicada."
                )
            if self._repository.has_overlapping_assignment(
                office_id=office_id,
                professional_id=professional_id,
                start_date=command.fecha_inicio,
                end_date=command.fecha_fin,
                exclude_start=start_date,
            ):
                raise ConflictError(
                    code="ASIGNACION_VIGENTE_SUPERPUESTA",
                    message="Las fechas se superponen con otra asignación del profesional.",
                )
            if command.es_responsable and any(
                other.es_responsable
                and (other.profesional_id, other.fecha_inicio) != (professional_id, start_date)
                and (other.fecha_fin is None or other.fecha_fin >= command.fecha_inicio)
                and (command.fecha_fin is None or other.fecha_inicio <= command.fecha_fin)
                for other in self._repository.list_assignments(office_id)
            ):
                raise ConflictError(
                    code="RESPONSABLE_VIGENTE_EXISTENTE",
                    message="Ya hay otro responsable en ese periodo. Revise sus fechas primero.",
                )
            if (entity.fecha_inicio, entity.fecha_fin) != (command.fecha_inicio, command.fecha_fin):
                if self._repository.period_change_excludes_attention(
                    entity, command.fecha_inicio, command.fecha_fin
                ):
                    raise ConflictError(
                        code="ASIGNACION_CON_ATENCIONES",
                        message=(
                            "Las fechas dejarían atenciones registradas fuera de la asignación. "
                            "Conserve esas fechas."
                        ),
                    )
            before = self._snapshot(entity)
            entity.fecha_inicio = command.fecha_inicio
            entity.fecha_fin = command.fecha_fin
            entity.es_responsable = command.es_responsable
            entity.servicios_codigos = command.servicios_codigos
            self._session.flush()
            self._repository.audit(
                actor_id=actor_id,
                action="UPDATE",
                record_id=office_id,
                before=before,
                after=self._snapshot(entity),
            )
            response = office_assignment_to_response(entity)
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="ASIGNACION_EN_CONFLICTO",
                message="La asignación entra en conflicto con otro periodo.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update_scope(
        self,
        office_id: int,
        professional_id: int,
        start_date: date,
        command: OfficeAssignmentScope,
        *,
        actor_id: int,
    ) -> OfficeAssignmentResponse:
        try:
            office = self._repository.get_by_id(office_id, lock=True)
            if office is None:
                raise NotFoundError(
                    code="CONSULTORIO_NO_ENCONTRADO", message="No existe el consultorio."
                )
            self._validate_scope(office, command.servicios_codigos)
            entity = self._repository.get_assignment(
                office_id, professional_id, start_date, lock=True
            )
            if entity is None:
                raise NotFoundError(
                    code="ASIGNACION_NO_ENCONTRADA", message="No existe la asignación indicada."
                )
            if entity.fecha_fin is not None and entity.fecha_fin < date.today():
                raise BusinessRuleError(
                    code="ASIGNACION_FINALIZADA", message="La asignación ya finalizó."
                )
            entity.servicios_codigos = command.servicios_codigos
            self._session.flush()
            self._repository.audit(
                actor_id=actor_id,
                action="UPDATE",
                record_id=office_id,
                after=self._snapshot(entity),
            )
            response = office_assignment_to_response(entity)
            self._session.commit()
            return response
        except Exception:
            self._session.rollback()
            raise

    def _validate_scope(self, office, codes: list[str] | None) -> None:
        if not office_context(office).active:
            raise BusinessRuleError(
                code="CONSULTORIO_NO_ACTIVO", message="Seleccione un consultorio activo."
            )
        if codes is not None and (
            not codes
            or set(codes) - set(office_context(office).service_codes)
            or any(self._repository.get_active_specialty(code) is None for code in codes)
        ):
            raise BusinessRuleError(
                code="SERVICIO_ASIGNACION_INVALIDO",
                message="Seleccione servicios activos habilitados en este consultorio.",
            )

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
            if self._repository.period_change_excludes_attention(
                entity, entity.fecha_inicio, command.fecha_fin
            ):
                raise ConflictError(
                    code="ASIGNACION_CON_ATENCIONES",
                    message=(
                        "El cierre dejaría atenciones registradas fuera de la asignación. "
                        "Revise la fecha de fin."
                    ),
                )
            entity.fecha_fin = command.fecha_fin
            self._session.flush()
            self._repository.audit(
                actor_id=actor_id,
                action="UPDATE",
                record_id=office_id,
                after=self._snapshot(entity),
            )
            response = office_assignment_to_response(entity)
            self._session.commit()
            return response
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
            "servicios_codigos": entity.servicios_codigos,
        }
