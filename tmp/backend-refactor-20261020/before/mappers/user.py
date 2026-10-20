from app.models.security import User
from app.schemas.auth import UserResponse


def user_role_codes(entity: User) -> list[str]:
    """Read explicit association entities, including newly assigned roles."""
    codes = {
        assignment.rol.codigo
        for assignment in entity.roles_usuario
        if assignment.rol is not None
    }
    # The view-only relation is already loaded in read repositories and makes
    # the mapper tolerant of entities obtained from existing call sites.
    codes.update(role.codigo for role in entity.roles)
    return sorted(codes)


def user_to_response(entity: User) -> UserResponse:
    return UserResponse(
        id=entity.id,
        profesional_id=entity.profesional_id,
        nombre_usuario=entity.nombre_usuario,
        activo=entity.activo,
        ultimo_acceso_at=entity.ultimo_acceso_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        roles=user_role_codes(entity),
    )
