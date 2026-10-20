"""Role-to-action policy kept outside routers and persistence adapters."""

from __future__ import annotations

from collections.abc import Iterable


class Permissions:
    PATIENT_READ = "PACIENTE_LEER"
    PATIENT_WRITE = "PACIENTE_EDITAR"
    PATIENT_DEACTIVATE = "PACIENTE_DAR_BAJA"
    ATTENTION_CREATE = "ATENCION_CREAR"
    ATTENTION_READ = "ATENCION_LEER"
    ATTENTION_CANCEL = "ATENCION_ANULAR"
    FUA_ISSUE = "FUA_EMITIR"
    CERTIFICATE_ISSUE = "CERTIFICADO_EMITIR"
    REFERENCE_ISSUE = "REFERENCIA_EMITIR"
    AUDIT_READ = "AUDITORIA_LEER"
    AGE_GROUP_CONFIGURE = "GRUPO_ETARIO_CONFIGURAR"
    OFFICE_MANAGE = "CONSULTORIO_GESTIONAR"
    PROFESSIONAL_MANAGE = "PROFESIONAL_GESTIONAR"
    USER_MANAGE = "USUARIO_GESTIONAR"

    ALL = frozenset(
        {
            PATIENT_READ,
            PATIENT_WRITE,
            PATIENT_DEACTIVATE,
            ATTENTION_CREATE,
            ATTENTION_READ,
            ATTENTION_CANCEL,
            FUA_ISSUE,
            CERTIFICATE_ISSUE,
            REFERENCE_ISSUE,
            AUDIT_READ,
            AGE_GROUP_CONFIGURE,
            OFFICE_MANAGE,
            PROFESSIONAL_MANAGE,
            USER_MANAGE,
        }
    )

    # Clinical actions must be performed by the health professional linked to
    # the encounter. Keeping this group explicit makes it difficult to grant
    # them accidentally to an administrative role in a future policy change.
    CLINICAL = frozenset(
        {
            ATTENTION_CREATE,
            ATTENTION_READ,
            ATTENTION_CANCEL,
            FUA_ISSUE,
            CERTIFICATE_ISSUE,
            REFERENCE_ISSUE,
        }
    )
    ADMINISTRATIVE = ALL - CLINICAL


DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    # ADMIN maintains users, staff, configuration and patient registration.
    # It intentionally has no clinical-attention or document permission: a
    # certificate, FUA or encounter must remain attributable to the linked
    # clinician rather than to a generic system administrator.
    "ADMIN": Permissions.ADMINISTRATIVE,
    # A professional performs and documents care, but does not manage the
    # security/configuration surface.  Object-level scope is enforced by the
    # clinical services from the persisted professional and office assignment;
    # this mapping only answers whether the role may attempt the action.
    #
    # The professional is also the one who admits patients, so it may reverse a
    # mistaken admission: PATIENT_DEACTIVATE is granted here even though the
    # action is administrative elsewhere (the deactivation stays logical and
    # writes an audit entry like any other change).
    "PROFESIONAL": frozenset(
        {
            Permissions.PATIENT_READ,
            Permissions.PATIENT_WRITE,
            Permissions.PATIENT_DEACTIVATE,
            Permissions.ATTENTION_CREATE,
            Permissions.ATTENTION_READ,
            Permissions.ATTENTION_CANCEL,
            Permissions.FUA_ISSUE,
            Permissions.CERTIFICATE_ISSUE,
            Permissions.REFERENCE_ISSUE,
        }
    ),
}

# These are the only roles that the application can grant to a user.  The
# explicit catalog prevents a legacy row such as REGISTRO or AUDITOR from
# accidentally becoming an operational permission when policies evolve.
ASSIGNABLE_ROLE_CODES = frozenset(DEFAULT_ROLE_PERMISSIONS)


class RolePermissionPolicy:
    """Maps persisted role codes to action permissions for access tokens.

    The current SQL model intentionally stores roles, not a permissions table.
    This isolated policy is therefore the extension point for a future
    role-permission catalog without leaking authorization into controllers.
    """

    def __init__(self, mapping: dict[str, frozenset[str]] | None = None) -> None:
        self._mapping = mapping or DEFAULT_ROLE_PERMISSIONS

    def resolve(self, roles: Iterable[str]) -> frozenset[str]:
        granted: set[str] = set()
        for role in roles:
            granted.update(self._mapping.get(role.upper(), ()))
        return frozenset(granted)
