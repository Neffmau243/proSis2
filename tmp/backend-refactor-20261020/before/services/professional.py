"""Administrator-only use cases for professional identities and specialties."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.mappers.professional import professional_to_response
from app.models.security import Professional, ProfessionalSpecialty
from app.repositories.professional import ProfessionalRepository
from app.schemas.professional import (
    ProfessionalCreate,
    ProfessionalResponse,
    ProfessionalSpecialtiesUpdate,
    ProfessionalSpecialtyInput,
    ProfessionalUpdate,
)


class ProfessionalService:
    """Owns professional lifecycle mutations and their audit trail."""

    def __init__(
        self,
        session: Session,
        audit: Callable[..., None] | None = None,
    ) -> None:
        self._session = session
        self._repository = ProfessionalRepository(session)
        self._audit = audit

    def list(self, *, include_inactive: bool = False) -> list[ProfessionalResponse]:
        return [
            professional_to_response(professional)
            for professional in self._repository.list(include_inactive=include_inactive)
        ]

    def get(self, professional_id: int) -> ProfessionalResponse:
        professional = self._repository.get_by_id(professional_id)
        if professional is None:
            raise NotFoundError(code="PROFESIONAL_NO_ENCONTRADO", message="No existe el profesional solicitado.")
        return professional_to_response(professional)

    def create(self, command: ProfessionalCreate, *, actor_id: int) -> ProfessionalResponse:
        try:
            self._validate_profession(command.profesion_id)
            self._validate_specialties(command.especialidades)
            professional = Professional(
                codigo_legacy=command.codigo_legacy,
                numero_documento=command.numero_documento,
                nombre_completo=command.nombre_completo,
                profesion_id=command.profesion_id,
                colegiatura=command.colegiatura,
            )
            self._repository.add(professional)
            self._session.flush()
            self._add_specialties(professional.id, command.especialidades)
            self._session.flush()
            self._record_audit(actor_id=actor_id, action="INSERT", professional=professional, before=None)
            self._session.commit()
            persisted = self._repository.get_by_id(professional.id)
            return professional_to_response(persisted or professional)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="PROFESIONAL_EN_CONFLICTO",
                message="El documento o código del profesional ya está registrado.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update(
        self,
        professional_id: int,
        command: ProfessionalUpdate,
        *,
        actor_id: int,
    ) -> ProfessionalResponse:
        try:
            professional = self._require_professional(professional_id, lock=True)
            before = self._snapshot(professional)
            changes = command.model_dump(exclude_unset=True)
            if "profesion_id" in changes:
                self._validate_profession(changes["profesion_id"])
            for field, value in changes.items():
                setattr(professional, field, value)
            self._session.flush()
            self._record_audit(actor_id=actor_id, action="UPDATE", professional=professional, before=before)
            self._session.commit()
            persisted = self._repository.get_by_id(professional.id)
            return professional_to_response(persisted or professional)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="PROFESIONAL_EN_CONFLICTO",
                message="El documento o código del profesional ya está registrado.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def replace_specialties(
        self,
        professional_id: int,
        command: ProfessionalSpecialtiesUpdate,
        *,
        actor_id: int,
    ) -> ProfessionalResponse:
        try:
            professional = self._require_professional(professional_id, lock=True)
            before = self._snapshot(professional)
            self._validate_specialties(command.especialidades)
            requested_codes = {item.especialidad_codigo for item in command.especialidades}
            required_codes = self._repository.required_specialties_for_nonexpired_assignments(
                professional_id,
                on_or_after=date.today(),
            )
            missing = required_codes - requested_codes
            if missing:
                raise BusinessRuleError(
                    code="ESPECIALIDAD_REQUERIDA_POR_ASIGNACION",
                    message=(
                        "No se puede retirar una especialidad requerida por asignaciones vigentes o futuras: "
                        f"{', '.join(sorted(missing))}."
                    ),
                )
            self._repository.replace_specialties(
                professional_id=professional.id,
                specialties=[
                    ProfessionalSpecialty(
                        profesional_id=professional.id,
                        especialidad_codigo=item.especialidad_codigo,
                        es_principal=item.es_principal,
                    )
                    for item in command.especialidades
                ],
            )
            self._session.flush()
            # The aggregate was loaded before the bulk replacement; expire
            # only its association so the response/audit snapshot reflects
            # the rows just written rather than a stale identity-map list.
            self._session.expire(professional, ["especialidades"])
            persisted = self._repository.get_by_id(professional.id)
            if persisted is None:  # defensive: locked row must still be present
                raise NotFoundError(code="PROFESIONAL_NO_ENCONTRADO", message="No existe el profesional solicitado.")
            self._record_audit(
                actor_id=actor_id,
                action="UPDATE_SPECIALTIES",
                professional=persisted,
                before=before,
            )
            self._session.commit()
            return professional_to_response(persisted)
        except Exception:
            self._session.rollback()
            raise

    def deactivate(self, professional_id: int, *, actor_id: int) -> ProfessionalResponse:
        try:
            professional = self._require_professional(professional_id, lock=True)
            if not professional.activo:
                raise ConflictError(
                    code="PROFESIONAL_YA_INACTIVO",
                    message="El profesional ya se encuentra inactivo.",
                )
            before = self._snapshot(professional)
            professional.activo = False
            self._session.flush()
            self._record_audit(
                actor_id=actor_id,
                action="DEACTIVATE",
                professional=professional,
                before=before,
            )
            self._session.commit()
            return professional_to_response(professional)
        except Exception:
            self._session.rollback()
            raise

    def _require_professional(self, professional_id: int, *, lock: bool) -> Professional:
        professional = self._repository.get_by_id(professional_id, lock=lock)
        if professional is None:
            raise NotFoundError(code="PROFESIONAL_NO_ENCONTRADO", message="No existe el profesional solicitado.")
        return professional

    def _validate_profession(self, profession_id: int | None) -> None:
        if profession_id is not None and self._repository.get_active_profession(profession_id) is None:
            raise NotFoundError(
                code="PROFESION_NO_ACTIVA",
                message="La profesión seleccionada no existe o está inactiva.",
            )

    def _validate_specialties(self, specialties: list[ProfessionalSpecialtyInput]) -> None:
        for specialty in specialties:
            if self._repository.get_active_specialty(specialty.especialidad_codigo) is None:
                raise NotFoundError(
                    code="ESPECIALIDAD_NO_ACTIVA",
                    message=(
                        f"La especialidad {specialty.especialidad_codigo} no existe o está inactiva."
                    ),
                )

    def _add_specialties(
        self,
        professional_id: int,
        specialties: list[ProfessionalSpecialtyInput],
    ) -> None:
        for specialty in specialties:
            self._repository.add_specialty(
                ProfessionalSpecialty(
                    profesional_id=professional_id,
                    especialidad_codigo=specialty.especialidad_codigo,
                    es_principal=specialty.es_principal,
                )
            )

    def _record_audit(
        self,
        *,
        actor_id: int,
        action: str,
        professional: Professional,
        before: dict[str, object] | None,
    ) -> None:
        if self._audit is not None:
            self._audit(
                actor_id=actor_id,
                action=action,
                table_name="profesionales",
                record_id=professional.id,
                before=before,
                after=self._snapshot(professional),
            )

    @staticmethod
    def _snapshot(professional: Professional) -> dict[str, object]:
        return {
            "id": professional.id,
            "codigo_legacy": professional.codigo_legacy,
            "numero_documento": professional.numero_documento,
            "nombre_completo": professional.nombre_completo,
            "profesion_id": professional.profesion_id,
            "colegiatura": professional.colegiatura,
            "activo": professional.activo,
            "especialidades": [
                {
                    "especialidad_codigo": item.especialidad_codigo,
                    "es_principal": item.es_principal,
                }
                for item in professional.especialidades
            ],
        }
