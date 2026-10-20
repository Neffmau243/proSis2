"""Shared clinical identity and action-specific object access checks.

The caller supplies repositories bound to its current session. This collaborator
never starts or confirms transactions, and preserves legacy internal callers.
"""

from collections.abc import Iterable
from typing import NamedTuple

from app.exceptions import AuthorizationError


class ClinicalScope(NamedTuple):
    professional_id: int
    establishment_ids: set[int]


class ClinicalAccessService:
    def __init__(self, identities, patients=None) -> None:
        self._identities = identities
        self._patients = patients if patients is not None else identities

    @staticmethod
    def require_actor(actor_id: int | None) -> None:
        if actor_id is None:
            raise AuthorizationError(
                code="ACTOR_CLINICO_REQUERIDO",
                message="Se requiere una identidad clínica autenticada.",
            )

    @staticmethod
    def require_active_link(professional_id: int | None) -> int:
        if professional_id is None:
            raise AuthorizationError(
                code="USUARIO_PROFESIONAL_SIN_VINCULO",
                message="El usuario clínico no está vinculado a un profesional activo.",
            )
        return professional_id

    def linked_professional(
        self,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
        message: str = "Solo un usuario PROFESIONAL vinculado puede operar atenciones.",
    ) -> int:
        if "PROFESIONAL" not in {role.upper() for role in actor_roles}:
            raise AuthorizationError(code="ROL_CLINICO_REQUERIDO", message=message)
        return self.require_active_link(
            self._identities.get_active_professional_id_for_user(actor_id)
        )

    def patient_scope(self, *, actor_id, actor_roles) -> ClinicalScope | None:
        # None is the existing internal-maintenance contract, never an HTTP permission.
        if actor_roles is None or "ADMIN" in {role.upper() for role in actor_roles}:
            return None
        self.require_actor(actor_id)
        professional_id = self.require_active_link(
            self._identities.get_active_professional_id_for_user(actor_id)
        )
        return self._scope(professional_id)

    def attention_scope(self, *, actor_id, actor_roles) -> ClinicalScope | None:
        if actor_roles is None:
            return None
        self.require_actor(actor_id)
        return self._scope(self.linked_professional(actor_id=actor_id, actor_roles=actor_roles))

    def _scope(self, professional_id: int) -> ClinicalScope:
        return ClinicalScope(
            professional_id,
            set(self._patients.get_active_establishment_ids_for_professional(professional_id)),
        )

    def ensure_patient(self, patient_id: int, scope: ClinicalScope | None) -> None:
        if scope is not None and not self._patients.is_patient_in_professional_scope(
            patient_id=patient_id, professional_id=scope[0], establishment_ids=scope[1]
        ):
            raise AuthorizationError(
                code="PACIENTE_FUERA_DE_AMBITO",
                message="El paciente no pertenece a su ámbito asistencial.",
            )

    @staticmethod
    def ensure_attention(entity, scope: ClinicalScope | None, *, actor_id) -> None:
        if scope is None or (
            entity.profesional_id == scope[0]
            or entity.establecimiento_id in scope[1]
            or (
                entity.profesional_id is None
                and getattr(entity, "created_by_usuario_id", None) == actor_id
            )
        ):
            return
        raise AuthorizationError(
            code="ATENCION_FUERA_DE_AMBITO",
            message="La atención no pertenece a su ámbito asistencial.",
        )

    def ensure_cancellation(self, *, actor_id, actor_roles, professional_id, recorded_by_id=None):
        linked = self.linked_professional(actor_id=actor_id, actor_roles=actor_roles)
        if professional_id is None and recorded_by_id == actor_id:
            return
        if linked != professional_id:
            raise AuthorizationError(
                code="PROFESIONAL_DISTINTO_AL_USUARIO",
                message="Solo puede anular atenciones de su propio profesional.",
            )

    def ensure_document_emitter(self, professional_id, *, actor_id, actor_roles) -> None:
        if actor_roles is None:
            return
        linked = self.linked_professional(
            actor_id=actor_id,
            actor_roles=actor_roles,
            message="Solo un usuario PROFESIONAL vinculado puede emitir documentos clínicos.",
        )
        if linked != professional_id:
            raise AuthorizationError(
                code="PROFESIONAL_DISTINTO_AL_USUARIO",
                message="Solo puede emitir documentos de sus propias atenciones.",
            )

    @classmethod
    def search_professional(cls, *, actor_roles, professional_id, allow_administrator=True):
        roles = {role.upper() for role in actor_roles}
        if "ADMIN" in roles and allow_administrator:
            return None
        if "PROFESIONAL" not in roles:
            if "ADMIN" in roles:
                raise AuthorizationError(
                    code="ROL_CLINICO_REQUERIDO",
                    message="Solo un usuario PROFESIONAL vinculado puede consultar atenciones.",
                )
            raise AuthorizationError(
                code="ROL_SIN_AMBITO_CLINICO",
                message="El rol actual no tiene ámbito de consulta clínica.",
            )
        return cls.require_active_link(professional_id)
