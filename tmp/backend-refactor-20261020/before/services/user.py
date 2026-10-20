"""User lifecycle and credential-management use cases."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.domain.authorization import ASSIGNABLE_ROLE_CODES
from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.mappers.user import user_role_codes, user_to_response
from app.models.security import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    PasswordChangeRequest,
    PasswordResetRequest,
    UserCreate,
    UserResponse,
    UserRolesUpdate,
)


class UserService:
    def __init__(self, session: Session, audit: Callable[..., None] | None = None) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._audit = audit

    def list(self, *, include_inactive: bool = False) -> list[UserResponse]:
        """Return the accounts an administrator can manage.

        The route dependency already enforces the ADMIN role; this keeps the
        contract in one place without duplicating role checks per call.
        """

        return [
            user_to_response(user)
            for user in self._users.list(include_inactive=include_inactive)
        ]

    def create(self, command: UserCreate, *, actor_id: int, actor_roles: Iterable[str]) -> UserResponse:
        self._require_admin(actor_roles)
        if self._users.find_by_username(command.nombre_usuario, lock=True) is not None:
            self._session.rollback()
            raise ConflictError(
                code="USUARIO_DUPLICADO",
                message="El nombre de usuario ya está registrado.",
            )
        if (
            command.profesional_id is not None
            and self._users.get_active_professional(command.profesional_id) is None
        ):
            self._session.rollback()
            raise NotFoundError(
                code="PROFESIONAL_NO_ACTIVO",
                message="El profesional asociado no existe o está inactivo.",
            )
        roles = self._resolve_roles(command.roles)
        self._validate_professional_role(
            profesional_id=command.profesional_id,
            role_codes={role.codigo for role in roles},
        )
        entity = User(
            profesional_id=command.profesional_id,
            nombre_usuario=command.nombre_usuario,
            password_hash=hash_password(command.password),
        )
        self._users.add(entity)
        self._session.flush()
        self._users.replace_roles(entity, roles)
        return self._commit_and_map(entity, actor_id=actor_id, action="INSERT", before=None)

    def assign_roles(
        self,
        user_id: int,
        command: UserRolesUpdate,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
    ) -> UserResponse:
        self._require_admin(actor_roles)
        active_admin_ids = self._users.lock_active_admin_ids()
        entity = self._users.find_by_id(user_id, lock=True)
        if entity is None:
            self._session.rollback()
            raise NotFoundError(code="USUARIO_NO_ENCONTRADO", message="No existe el usuario solicitado.")
        before = self._snapshot(entity)
        roles = self._resolve_roles(command.roles)
        self._ensure_active_admin_remains(
            entity,
            next_role_codes={role.codigo for role in roles},
            active_admin_ids=active_admin_ids,
            account_will_remain_active=entity.activo,
        )
        self._validate_professional_role(
            profesional_id=entity.profesional_id,
            role_codes={role.codigo for role in roles},
        )
        self._users.replace_roles(entity, roles)
        return self._commit_and_map(entity, actor_id=actor_id, action="UPDATE", before=before)

    def deactivate(self, user_id: int, *, actor_id: int, actor_roles: Iterable[str]) -> UserResponse:
        self._require_admin(actor_roles)
        active_admin_ids = self._users.lock_active_admin_ids()
        entity = self._users.find_by_id(user_id, lock=True)
        if entity is None:
            self._session.rollback()
            raise NotFoundError(code="USUARIO_NO_ENCONTRADO", message="No existe el usuario solicitado.")
        if entity.id == actor_id:
            self._session.rollback()
            raise BusinessRuleError(
                code="AUTOBAJA_NO_PERMITIDA",
                message="No puede desactivar su propia cuenta; solicite la intervención de otro ADMIN.",
            )
        self._ensure_active_admin_remains(
            entity,
            next_role_codes=set(user_role_codes(entity)),
            active_admin_ids=active_admin_ids,
            account_will_remain_active=False,
        )
        before = self._snapshot(entity)
        entity.activo = False
        return self._commit_and_map(entity, actor_id=actor_id, action="DEACTIVATE", before=before)

    def change_own_password(
        self,
        command: PasswordChangeRequest,
        *,
        actor_id: int,
    ) -> None:
        """Change the current principal's password after proving the old one."""

        entity = self._users.find_by_id(actor_id, lock=True)
        if entity is None or not entity.activo:
            self._session.rollback()
            raise AuthenticationError("No se pudo validar la cuenta para cambiar la contraseña.")
        if not verify_password(command.current_password, entity.password_hash):
            self._session.rollback()
            raise AuthenticationError("La contraseña actual no es válida.")
        before = self._snapshot(entity)
        self._replace_password(entity, command.new_password)
        self._commit_security_change(
            entity,
            actor_id=actor_id,
            action="PASSWORD_CHANGE",
            before=before,
        )

    def reset_password(
        self,
        user_id: int,
        command: PasswordResetRequest,
        *,
        actor_id: int,
        actor_roles: Iterable[str],
    ) -> None:
        """Let an ADMIN reset another active account without exposing a secret."""

        self._require_admin(actor_roles)
        if user_id == actor_id:
            self._session.rollback()
            raise BusinessRuleError(
                code="RESTABLECIMIENTO_PROPIO_NO_PERMITIDO",
                message="Para su propia cuenta use el cambio de contraseña con validación de la clave actual.",
            )
        entity = self._users.find_by_id(user_id, lock=True)
        if entity is None:
            self._session.rollback()
            raise NotFoundError(code="USUARIO_NO_ENCONTRADO", message="No existe el usuario solicitado.")
        if not entity.activo:
            self._session.rollback()
            raise BusinessRuleError(
                code="USUARIO_INACTIVO",
                message="No se puede restablecer la contraseña de un usuario inactivo.",
            )
        before = self._snapshot(entity)
        self._replace_password(entity, command.new_password)
        self._commit_security_change(
            entity,
            actor_id=actor_id,
            action="PASSWORD_RESET",
            before=before,
        )

    def _resolve_roles(self, requested_codes: list[str]) -> list:
        codes = {code.upper() for code in requested_codes}
        unsupported = codes - ASSIGNABLE_ROLE_CODES
        if unsupported:
            self._session.rollback()
            allowed = ", ".join(sorted(ASSIGNABLE_ROLE_CODES))
            requested = ", ".join(sorted(unsupported))
            raise BusinessRuleError(
                code="ROL_NO_HABILITADO",
                message=(
                    f"Los roles solicitados no están habilitados: {requested}. "
                    f"Roles permitidos: {allowed}."
                ),
            )
        roles = self._users.find_roles_by_codes(codes)
        found = {role.codigo for role in roles}
        if found != codes:
            self._session.rollback()
            missing = ", ".join(sorted(codes - found))
            raise NotFoundError(code="ROL_NO_ENCONTRADO", message=f"No existen los roles: {missing}")
        return roles

    def _commit_and_map(
        self,
        entity: User,
        *,
        actor_id: int,
        action: str,
        before: dict[str, object] | None,
    ) -> UserResponse:
        try:
            self._session.flush()
            if self._audit is not None:
                self._audit(
                    actor_id=actor_id,
                    action=action,
                    table_name="usuarios",
                    record_id=entity.id,
                    before=before,
                    after=self._snapshot(entity),
                )
            self._session.commit()
            persisted = self._users.find_by_id(entity.id)
            return user_to_response(persisted or entity)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="USUARIO_EN_CONFLICTO",
                message="No se pudo guardar el usuario por una restricción de identidad.",
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def _commit_security_change(
        self,
        entity: User,
        *,
        actor_id: int,
        action: str,
        before: dict[str, object],
    ) -> None:
        try:
            self._session.flush()
            if self._audit is not None:
                self._audit(
                    actor_id=actor_id,
                    action=action,
                    table_name="usuarios",
                    record_id=entity.id,
                    before=before,
                    after=self._snapshot(entity),
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _replace_password(self, entity: User, new_password: str) -> None:
        if verify_password(new_password, entity.password_hash):
            self._session.rollback()
            raise BusinessRuleError(
                code="CONTRASENA_REUTILIZADA",
                message="La nueva contraseña debe ser diferente de la contraseña actual.",
            )
        entity.password_hash = hash_password(new_password)
        entity.version_credenciales += 1

    def _ensure_active_admin_remains(
        self,
        entity: User,
        *,
        next_role_codes: set[str],
        active_admin_ids: list[int],
        account_will_remain_active: bool,
    ) -> None:
        is_last_active_admin = entity.activo and entity.id in active_admin_ids and len(
            active_admin_ids
        ) == 1
        if is_last_active_admin and (
            not account_will_remain_active
            or "ADMIN" not in {code.upper() for code in next_role_codes}
        ):
            self._session.rollback()
            raise BusinessRuleError(
                code="ULTIMO_ADMIN_ACTIVO",
                message="Debe permanecer al menos un usuario ADMIN activo.",
            )

    @staticmethod
    def _require_admin(actor_roles: Iterable[str]) -> None:
        if "ADMIN" not in {role.upper() for role in actor_roles}:
            raise AuthorizationError("Solo ADMIN puede gestionar usuarios y roles.")

    def _validate_professional_role(
        self,
        *,
        profesional_id: int | None,
        role_codes: set[str],
    ) -> None:
        """Keep the patient-management role bound to an active professional.

        An account granted ``PROFESIONAL`` must identify a real, active
        member of the IPRESS staff.  This keeps patient-change auditing
        attributable even though the role does not grant clinical attention
        or document permissions.
        """

        if "PROFESIONAL" not in {code.upper() for code in role_codes}:
            return
        if profesional_id is None:
            raise BusinessRuleError(
                code="USUARIO_PROFESIONAL_SIN_VINCULO",
                message="Un usuario con rol PROFESIONAL debe estar vinculado a un profesional activo.",
            )
        if self._users.get_active_professional(profesional_id) is None:
            raise NotFoundError(
                code="PROFESIONAL_NO_ACTIVO",
                message="El profesional asociado no existe o está inactivo.",
            )

    @staticmethod
    def _snapshot(entity: User) -> dict[str, object]:
        return {
            "id": entity.id,
            "profesional_id": entity.profesional_id,
            "nombre_usuario": entity.nombre_usuario,
            "activo": entity.activo,
            "version_credenciales": entity.version_credenciales,
            "roles": user_role_codes(entity),
        }
