"""Model registry used by Alembic and the application persistence layer.

Importing this package is intentional: it registers every mapped table in
``Base.metadata`` without creating or mutating the database.
"""

from .audit import AuditLog
from .base import Base
from .catalog import (
    AgeGroup,
    AttentionMode,
    Cie10,
    DocumentType,
    Ethnicity,
    FamilyHistoryPrefix,
    Insurance,
    Profession,
    ServiceOffering,
    Sex,
    Specialty,
)
from .clinical import Attention, AttentionDiagnosis, AttentionService
from .documents import Certificate, CertificateService, DocumentSequence, Fua, Referral
from .legacy import LegacyAttention, LegacyImport, LegacyRecord
from .organization import (
    Disa,
    Establishment,
    Localidad,
    MicroNetwork,
    Network,
    Office,
    OfficeProfessional,
    Ubigeo,
)
from .patient import (
    Patient,
    PatientExternalCode,
    PatientLegacyAnnex,
    PatientResponsible,
    PatientRisk,
    RiskGroup,
)
from .security import LoginRateLimit, Professional, ProfessionalSpecialty, Role, User, UserRole
from .surveillance import NutritionalEvaluation, SurveillanceSien

__all__ = [
    "LegacyAttention",
    "LegacyImport",
    "LegacyRecord",
    "AgeGroup",
    "Attention",
    "AttentionDiagnosis",
    "AttentionMode",
    "AttentionService",
    "AuditLog",
    "Base",
    "Certificate",
    "CertificateService",
    "Cie10",
    "Disa",
    "DocumentType",
    "DocumentSequence",
    "Establishment",
    "Ethnicity",
    "FamilyHistoryPrefix",
    "Fua",
    "Insurance",
    "Localidad",
    "LoginRateLimit",
    "MicroNetwork",
    "Network",
    "NutritionalEvaluation",
    "Office",
    "OfficeProfessional",
    "Patient",
    "PatientExternalCode",
    "PatientLegacyAnnex",
    "PatientResponsible",
    "PatientRisk",
    "Profession",
    "Professional",
    "ProfessionalSpecialty",
    "Referral",
    "RiskGroup",
    "Role",
    "ServiceOffering",
    "Sex",
    "Specialty",
    "SurveillanceSien",
    "Ubigeo",
    "User",
    "UserRole",
]
