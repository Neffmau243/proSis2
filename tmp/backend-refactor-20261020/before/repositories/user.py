"""Only SQLAlchemy persistence queries for users and roles."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.security import LoginRateLimit, Professional, Role, User, UserRole


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, user_id: int, *, lock: bool = False) -> User | None:
        statement: Select[tuple[User]] = (
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.roles_usuario).selectinload(UserRole.rol),
            )
            .where(User.id == user_id)
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def find_by_username(self, username: str, *, lock: bool = False) -> User | None:
        statement: Select[tuple[User]] = (
            select(User).options(
                selectinload(User.roles),
                selectinload(User.roles_usuario).selectinload(UserRole.rol),
            )
            .where(User.nombre_usuario == username)
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list(self, *, include_inactive: bool = False) -> list[User]:
        statement: Select[tuple[User]] = (
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.roles_usuario).selectinload(UserRole.rol),
            )
            .order_by(User.nombre_usuario.asc())
        )
        if not include_inactive:
            statement = statement.where(User.activo.is_(True))
        return list(self._session.scalars(statement))

    def list_active_usernames(self) -> list[str]:
        statement = (
            select(User.nombre_usuario)
            .where(User.activo.is_(True))
            .order_by(User.nombre_usuario.asc())
        )
        return list(self._session.scalars(statement))

    def find_roles_by_codes(self, codes: set[str]) -> list[Role]:
        if not codes:
            return []
        return list(self._session.scalars(select(Role).where(Role.codigo.in_(codes))))

    def lock_active_admin_ids(self) -> list[int]:
        """Lock all active ADMIN assignments before a destructive role change.

        Taking these locks in a stable ID order makes concurrent attempts to
        remove or deactivate administrators serialize around the invariant
        that at least one active ADMIN must remain.
        """

        statement = (
            select(User.id)
            .join(UserRole, UserRole.usuario_id == User.id)
            .join(Role, Role.id == UserRole.rol_id)
            .where(User.activo.is_(True), Role.codigo == "ADMIN")
            .order_by(User.id)
            .with_for_update()
        )
        return list(self._session.scalars(statement))

    def get_active_professional(self, professional_id: int) -> Professional | None:
        return self._session.scalar(
            select(Professional).where(
                Professional.id == professional_id,
                Professional.activo.is_(True),
            )
        )

    def find_login_rate_limit(
        self, key_hash: str, *, lock: bool = False
    ) -> LoginRateLimit | None:
        statement: Select[tuple[LoginRateLimit]] = select(LoginRateLimit).where(
            LoginRateLimit.clave_hash == key_hash
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add_login_rate_limit(self, entity: LoginRateLimit) -> None:
        self._session.add(entity)

    def delete_login_rate_limit(self, entity: LoginRateLimit) -> None:
        self._session.delete(entity)

    def add(self, user: User) -> None:
        self._session.add(user)

    def replace_roles(self, user: User, roles: list[Role]) -> None:
        # The association is explicit so role writes remain visible and
        # auditable rather than concealed behind a secondary relationship.
        user.roles_usuario.clear()
        user.roles_usuario.extend(UserRole(rol=role) for role in roles)
