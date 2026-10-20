"""Configuration and API edge cases must fail before reaching persistence."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.dependencies import require_permissions, require_roles
from app.core.security import TokenValidationError, create_access_token, decode_access_token
from app.mappers.patient import responsible_update_to_entity_kwargs
from app.schemas.age_group import AgeGroupConfigurationInput, AgeGroupRangeInput
from app.schemas.attention import AttentionCancellationInput, AttentionCreate
from app.schemas.auth import UserCreate, UserRolesUpdate
from app.schemas.discovery import AttentionSearchCriteria
from app.schemas.document import CertificateIssueInput, ReferralCreateInput
from app.schemas.office import OfficeAssignmentCreate
from app.schemas.patient import (
    PatientResponsibleCreate,
    PatientResponsibleUpdate,
    PatientRiskCreate,
    PatientRiskUpdate,
)
from app.schemas.professional import ProfessionalCreate


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"database_url": "sqlite:///test"}, "dialecto MySQL"),
        ({"api_v1_prefix": "api/v1"}, "comenzar"),
        ({"jwt_algorithm": "RS256"}, "HS256"),
        ({"jwt_issuer": " "}, "vacíos"),
        ({"secret_key": "short"}, "32 caracteres"),
        ({"login_lock_max_seconds": 1, "login_lock_base_seconds": 10}, "mayor o igual"),
        ({"cors_origins": ["*"], "cors_allow_credentials": True}, "CORS_ORIGINS"),
    ],
)
def test_invalid_configuration_is_rejected(changes, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **changes)


def test_configuration_normalizes_prefix_lists_and_passwordless_mysql_url():
    config = Settings(
        _env_file=None, api_v1_prefix=" /api/v1/// ", database_url="", mysql_password=""
    )
    assert config.api_v1_prefix == "/api/v1"
    assert "mysql+pymysql://" in config.sqlalchemy_database_url
    assert Settings.parse_list_setting(None) == []
    assert Settings.parse_list_setting("") == []
    assert Settings.parse_list_setting(" GET, POST ,, ") == ["GET", "POST"]
    assert Settings.parse_list_setting('[" GET ","POST"]') == ["GET", "POST"]
    assert Settings.parse_list_setting((" X ", "")) == ["X"]
    for invalid in ("[broken", 42):
        with pytest.raises(ValueError):
            Settings.parse_list_setting(invalid)


@pytest.mark.parametrize("factory", [require_permissions, require_roles])
def test_access_dependencies_refuse_empty_policy(factory):
    with pytest.raises(ValueError, match="al menos"):
        factory(" ", "")


def test_token_preserves_non_reserved_claims_and_accepts_empty_scopes():
    token = create_access_token(
        user_id=7, roles=None, permissions=None, extra_claims={"context": "local-test"}
    )
    claims = decode_access_token(token)
    assert claims.roles == claims.permissions == frozenset()
    assert jwt.decode(token, options={"verify_signature": False})["context"] == "local-test"


def test_numeric_string_expiration_signed_by_server_is_rejected_as_invalid_type():
    token = create_access_token(user_id=7)
    values = jwt.decode(token, options={"verify_signature": False})
    values["exp"] = str(int((datetime.now(UTC) + timedelta(hours=1)).timestamp()))
    settings = get_settings()
    signed = jwt.encode(
        values, settings.secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    with pytest.raises(TokenValidationError, match="expiración"):
        decode_access_token(signed)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"hora_inicio": "10:00", "hora_fin": "09:00"}, "hora_fin"),
        ({"fecha_atendido": "2026-10-19T09:00:00"}, "fecha_atendido"),
    ],
)
def test_attention_time_order_cannot_be_reversed(changes, message):
    with pytest.raises(ValidationError, match=message):
        AttentionCreate(
            paciente_id=1,
            establecimiento_id=1,
            profesional_id=1,
            consultorio_id=1,
            modalidad_atencion_codigo="AMBULATORIA",
            fecha_atencion="2026-10-20T09:00:00",
            **changes,
        )


@pytest.mark.parametrize("reason", [None, 42, " "])
def test_attention_cancellation_requires_a_nonblank_text_reason(reason):
    with pytest.raises(ValidationError, match="justificación"):
        AttentionCancellationInput(observaciones=reason)


def test_tuple_role_and_service_inputs_remain_accepted_as_collections():
    assert UserCreate(nombre_usuario="clinico", password="12345678", roles=("ADMIN",)).roles == [
        "ADMIN"
    ]
    assert UserRolesUpdate(roles=("ADMIN",)).roles == ["ADMIN"]
    assert CertificateIssueInput(
        atencion_id=1, tipo="Certificado", prestaciones=("CONSULTA",)
    ).prestaciones == ["CONSULTA"]


def test_new_referral_cannot_choose_a_later_lifecycle_state():
    with pytest.raises(ValidationError, match="PENDIENTE"):
        ReferralCreateInput(
            atencion_id=1,
            tipo="EXTERNA",
            establecimiento_destino_id=2,
            motivo="Evaluación",
            estado="ACEPTADA",
        )


@pytest.mark.parametrize(
    "changes,message",
    [
        (
            {
                "fecha_hora_desde": "2026-10-20T07:00:00Z",
                "fecha_hora_hasta": "2026-10-20T13:00:00Z",
            },
            "sin offset",
        ),
        ({"desde": "2026-10-20", "hasta": "2026-10-19"}, "hasta no puede"),
    ],
)
def test_attention_search_rejects_ambiguous_offsets_and_reverse_dates(changes, message):
    with pytest.raises(ValidationError, match=message):
        AttentionSearchCriteria(**changes)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"codigo": "NINO"}, "requiere edad_minima"),
        ({"codigo": "NINO", "edad_minima_meses": 12, "edad_maxima_meses": 11}, "mayor o igual"),
    ],
)
def test_age_range_requires_valid_boundaries(changes, message):
    with pytest.raises(ValidationError, match=message):
        AgeGroupRangeInput(**changes)


def test_age_group_configuration_cannot_repeat_the_same_code():
    group = {"codigo": "NINO", "edad_minima_meses": 0, "edad_maxima_meses": 12}
    with pytest.raises(ValidationError, match="dos veces"):
        AgeGroupConfigurationInput(grupos=[group, group])


def test_office_assignment_cannot_end_before_it_begins():
    with pytest.raises(ValidationError, match="anterior"):
        OfficeAssignmentCreate(profesional_id=7, fecha_inicio="2026-10-20", fecha_fin="2026-10-19")


@pytest.mark.parametrize(
    "specialties,message",
    [
        (
            [{"especialidad_codigo": "MED", "es_principal": True}, {"especialidad_codigo": "MED"}],
            "repetir",
        ),
        (
            [
                {"especialidad_codigo": "MED", "es_principal": True},
                {"especialidad_codigo": "NUT", "es_principal": True},
            ],
            "Solo una",
        ),
        ([{"especialidad_codigo": "MED"}], "una debe"),
    ],
)
def test_professional_specialties_have_unambiguous_membership_and_principal(specialties, message):
    with pytest.raises(ValidationError, match=message):
        ProfessionalCreate(nombre_completo="Profesional", especialidades=specialties)


def test_optional_patient_relationship_fields_keep_explicit_null_and_normalize_parentesco():
    assert (
        PatientResponsibleCreate(
            parentesco="MADRE", nombre_completo="Responsable", telefono=None
        ).telefono
        is None
    )
    command = PatientResponsibleUpdate(
        parentesco="TUTOR", tipo_documento_codigo=None, numero_documento=None, telefono=None
    )
    assert responsible_update_to_entity_kwargs(command)["parentesco"] == "TUTOR"
    assert command.tipo_documento_codigo is None
    assert PatientResponsibleUpdate(tipo_documento_codigo="dni").tipo_documento_codigo == "DNI"
    assert (
        PatientRiskCreate(
            grupo_riesgo_id=1, fecha_inicio="2026-10-20", observacion=None
        ).observacion
        is None
    )
    assert PatientRiskUpdate(observacion=None, motivo_cierre=None).observacion is None
