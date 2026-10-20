"""Load repeatable development fixtures required by the API demonstration.

This command is deliberately separate from Alembic migrations: migrations
define the production schema and its minimum reference catalogs, whereas these
records are fictional data intended only for local development and Postman.
It is safe to run more than once; it never deletes or overwrites user data.

Besides the two original patients, the seed loads a small but realistic cohort
(spread over both demo sites, every age group and several insurances) plus its
clinical history: encounters registered through ``AttentionService`` and the
FUA/certificate/referral issued through ``DocumentService``. Going through the
services instead of raw inserts keeps every business rule -- assignment,
age group calculation, document numbering -- exercised by the same code the
API uses.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.catalog import AgeGroup, Cie10, Insurance, ServiceOffering
from app.models.clinical import Attention
from app.models.documents import Certificate, Fua, Referral
from app.models.organization import Establishment, Localidad, Office, Ubigeo
from app.models.patient import Patient, PatientResponsible, PatientRisk, RiskGroup
from app.models.security import Professional, ProfessionalSpecialty, Role, User, UserRole
from app.schemas.attention import (
    AttentionCreate,
    AttentionDiagnosisInput,
    AttentionModeCode,
    AttentionServiceInput,
)
from app.schemas.document import CertificateIssueInput, FuaIssueInput, ReferralCreateInput
from app.services.attention import AttentionService
from app.services.document import DocumentService

Entity = TypeVar("Entity")

# These credentials are deliberately limited to fictional development data.
# ``seed_demo_data`` refuses every environment other than ``development``.
# Never reuse them outside a disposable local database.
DEMO_ADMIN_USERNAME = "admin"
DEMO_ADMIN_PASSWORD = "74028519"
DEMO_PROFESSIONAL_USERNAME = "medico.demo"
DEMO_PROFESSIONAL_PASSWORD = "18594027"

#: Fechas fijas para que la semilla siga siendo idempotente entre ejecuciones.
DEMO_REGISTRATION_DATE = date(2024, 1, 15)
DEMO_RISK_START = date(2024, 3, 1)

#: Distritos que albergan a la cohorte ficticia, con el nombre oficial (INEI)
#: que usa el catálogo ``ubigeos``.  El nombre no se inventa: si la dirección
#: dice Cayma, el código tiene que ser 040103 y no el del distrito vecino.
DEMO_DISTRICTS: tuple[tuple[str, str], ...] = (
    ("040101", "AREQUIPA"),
    ("040102", "ALTO SELVA ALEGRE"),
    ("040103", "CAYMA"),
    ("040104", "CERRO COLORADO"),
)

# La residencia se registra con tres niveles distintos. El código de ubigeo
# identifica el distrito; la localidad es el sector dentro de ese distrito; la
# dirección es el domicilio puntual. Nunca se persiste el código como localidad.

DEMO_RISK_GROUPS: tuple[tuple[str, str], ...] = (
    ("RIESGO_CARDIO", "Riesgo cardiovascular"),
    ("RIESGO_METABOLICO", "Riesgo metabólico"),
)

#: Sedes reales que usa la semilla: la central y una alterna para la regla de
#: ámbito. Las siembra ``20260924_0019_eess_catalog``; la semilla solo las usa.
DEMO_SITE_RENAES = "1291"
DEMO_DESTINATION_RENAES = "1302"

#: Especialidad del consultorio de medicina (``cat_especialidad`` de origen).
DEMO_MEDICINE_SPECIALTY = "Especialidades:003"


@dataclass(frozen=True, slots=True)
class DemoPatient:
    """One fictional patient of the development cohort."""

    document_number: str
    clinical_history: str
    birth_date: date
    paternal_surname: str
    maternal_surname: str
    first_name: str
    #: Código de ``sexos`` (F/M).
    sex_code: str
    address: str
    phone: str
    district_code: str
    #: Sector dentro del distrito; debe existir en el catálogo ``localidades``.
    locality: str
    #: Código de ``seguros``.
    insurance_code: str
    #: True cuando la sede de registro es IPRESS Demo Destino (fuera del
    #: ámbito del profesional demo, para ejercitar la regla de ámbito).
    at_destination: bool = False
    #: True cuando ``profesional_registro_id`` apunta al clínico demo.
    registered_by_clinician: bool = False
    #: (parentesco, nombre completo, teléfono) del responsable activo.
    responsible: tuple[str, str, str] | None = None
    risk_code: str | None = None


@dataclass(frozen=True, slots=True)
class DemoEncounter:
    """One historical encounter, optionally with its clinical document."""

    document_number: str
    days_ago: int
    at_time: time
    weight_kg: Decimal
    height_cm: Decimal
    waist_cm: Decimal | None = None
    systolic: int | None = None
    diastolic: int | None = None
    temperature_c: Decimal | None = None
    diagnosis_code: str | None = None
    #: ``FUA`` | ``CERTIFICADO`` | ``REFERENCIA``.
    document: str | None = None


DEMO_PATIENTS: tuple[DemoPatient, ...] = (
    DemoPatient(
        document_number="40123456",
        clinical_history="HC-DEMO-0001",
        birth_date=date(2019, 3, 14),
        paternal_surname="Quispe",
        maternal_surname="Mamani",
        first_name="Diego Alonso",
        sex_code="M",
        address="Calle Los Álamos 128, Cayma",
        phone="954112233",
        district_code="040103",
        locality="PUEBLO TRADICIONAL CAYMA",
        insurance_code="SIS",
        responsible=("MADRE", "Rosa Mamani Quispe", "954112234"),
    ),
    DemoPatient(
        document_number="41234567",
        clinical_history="HC-DEMO-0002",
        birth_date=date(2021, 11, 2),
        paternal_surname="Flores",
        maternal_surname="Huamán",
        first_name="Camila Valentina",
        sex_code="F",
        address="Av. Ejército 455, Arequipa",
        phone="954223344",
        district_code="040101",
        locality="CERCADO",
        insurance_code="SIS",
        responsible=("MADRE", "Elena Huamán Ccahuana", "954223345"),
    ),
    DemoPatient(
        document_number="42345678",
        clinical_history="HC-DEMO-0003",
        birth_date=date(2023, 7, 21),
        paternal_surname="Ramos",
        maternal_surname="Chávez",
        first_name="Thiago Mateo",
        sex_code="M",
        address="Pasaje Los Sauces 15, Cerro Colorado",
        phone="954334455",
        district_code="040104",
        locality="CERRO COLORADO",
        insurance_code="SIS",
        responsible=("MADRE", "Karina Chávez Delgado", "954334456"),
    ),
    DemoPatient(
        document_number="43456789",
        clinical_history="HC-DEMO-0004",
        birth_date=date(2016, 1, 30),
        paternal_surname="Sánchez",
        maternal_surname="Loayza",
        first_name="Luciana Fernanda",
        sex_code="F",
        address="Urb. Villa Hermosa Mz. B, Cayma",
        phone="954445566",
        district_code="040103",
        locality="RESIDENCIA DE CAYMA",
        insurance_code="ESSALUD",
        at_destination=True,
        responsible=("PADRE", "Hugo Sánchez Rojas", "954445567"),
    ),
    DemoPatient(
        document_number="44567890",
        clinical_history="HC-DEMO-0005",
        birth_date=date(2010, 9, 18),
        paternal_surname="Mendoza",
        maternal_surname="Torres",
        first_name="José Fernando",
        sex_code="M",
        address="Calle Perú 210, Arequipa",
        phone="954556677",
        district_code="040101",
        locality="COOP. UNIVERSITARIA",
        insurance_code="SIS",
        responsible=("MADRE", "Silvia Torres Valencia", "954556678"),
        risk_code="RIESGO_METABOLICO",
    ),
    DemoPatient(
        document_number="45678901",
        clinical_history="HC-DEMO-0006",
        birth_date=date(2012, 5, 6),
        paternal_surname="Paredes",
        maternal_surname="Ríos",
        first_name="Ariana Nicole",
        sex_code="F",
        address="Av. Los Estados 88, Cerro Colorado",
        phone="954667788",
        district_code="040104",
        locality="CERRO VIEJO",
        insurance_code="SIS",
        responsible=("MADRE", "Norma Ríos Salas", "954667789"),
    ),
    DemoPatient(
        document_number="46789012",
        clinical_history="HC-DEMO-0007",
        birth_date=date(1985, 2, 11),
        paternal_surname="Vargas",
        maternal_surname="Ccahuana",
        first_name="Miguel Ángel",
        sex_code="M",
        address="Calle Mercaderes 320, Arequipa",
        phone="954778899",
        district_code="040101",
        locality="CERCADO",
        insurance_code="PARTICULAR",
        registered_by_clinician=True,
    ),
    DemoPatient(
        document_number="47890123",
        clinical_history="HC-DEMO-0008",
        birth_date=date(1978, 12, 25),
        paternal_surname="Rodríguez",
        maternal_surname="Salazar",
        first_name="Patricia Elena",
        sex_code="F",
        address="Av. Goyeneche 512, Arequipa",
        phone="954889900",
        district_code="040101",
        locality="LA NEGRITA",
        insurance_code="ESSALUD",
        registered_by_clinician=True,
        risk_code="RIESGO_CARDIO",
    ),
    DemoPatient(
        document_number="48901234",
        clinical_history="HC-DEMO-0009",
        birth_date=date(1994, 6, 8),
        paternal_surname="Cárdenas",
        maternal_surname="Béjar",
        first_name="Luis Alberto",
        sex_code="M",
        address="Calle San Camilo 147, Arequipa",
        phone="955001122",
        district_code="040101",
        locality="COOP. UNIVERSITARIA",
        insurance_code="SIS",
    ),
    DemoPatient(
        document_number="49012345",
        clinical_history="HC-DEMO-0010",
        birth_date=date(2000, 10, 17),
        paternal_surname="Vilca",
        maternal_surname="Choque",
        first_name="Marisol",
        sex_code="F",
        address="Asoc. Los Portales Mz. C, Cayma",
        phone="955002233",
        district_code="040103",
        locality="URBANIZACION LEON XIII",
        insurance_code="SIN_SEGURO",
        at_destination=True,
    ),
    DemoPatient(
        document_number="50123456",
        clinical_history="HC-DEMO-0011",
        birth_date=date(1948, 4, 3),
        paternal_surname="Chávez",
        maternal_surname="Delgado",
        first_name="Gregorio",
        sex_code="M",
        address="Calle Rivero 205, Arequipa",
        phone="955003344",
        district_code="040101",
        locality="LA NEGRITA",
        insurance_code="ESSALUD",
        risk_code="RIESGO_CARDIO",
    ),
    DemoPatient(
        document_number="51234567",
        clinical_history="HC-DEMO-0012",
        birth_date=date(1952, 8, 29),
        paternal_surname="Salas",
        maternal_surname="Ibáñez",
        first_name="Elvira",
        sex_code="F",
        address="Urb. Los Cipreses 74, Cerro Colorado",
        phone="955004455",
        district_code="040104",
        locality="PACHACUTEC",
        insurance_code="SIN_SEGURO",
        at_destination=True,
    ),
    DemoPatient(
        document_number="52345678",
        clinical_history="HC-DEMO-0013",
        birth_date=date(1996, 6, 12),
        paternal_surname="Cahuide",
        maternal_surname="Quispe",
        first_name="María Elena",
        sex_code="F",
        address="Calle Cahuide 504",
        phone="955005566",
        district_code="040102",
        locality='ALTO SELVA ALEGRE "A"',
        insurance_code="SIS",
    ),
)

DEMO_ENCOUNTERS: tuple[DemoEncounter, ...] = (
    DemoEncounter(
        document_number="46789012",
        days_ago=40,
        at_time=time(9, 15),
        weight_kg=Decimal("82.50"),
        height_cm=Decimal("172.00"),
        waist_cm=Decimal("96.00"),
        systolic=128,
        diastolic=84,
        temperature_c=Decimal("36.7"),
        diagnosis_code="Z00.0",
        document="FUA",
    ),
    DemoEncounter(
        document_number="46789012",
        days_ago=12,
        at_time=time(11, 30),
        weight_kg=Decimal("83.10"),
        height_cm=Decimal("172.00"),
        waist_cm=Decimal("97.50"),
        systolic=142,
        diastolic=91,
        temperature_c=Decimal("36.5"),
        document="REFERENCIA",
    ),
    DemoEncounter(
        document_number="50123456",
        days_ago=25,
        at_time=time(8, 45),
        weight_kg=Decimal("71.20"),
        height_cm=Decimal("165.00"),
        waist_cm=Decimal("99.00"),
        systolic=138,
        diastolic=82,
        temperature_c=Decimal("36.4"),
        diagnosis_code="Z00.0",
        document="CERTIFICADO",
    ),
    DemoEncounter(
        document_number="44567890",
        days_ago=5,
        at_time=time(10, 5),
        weight_kg=Decimal("58.40"),
        height_cm=Decimal("168.00"),
        waist_cm=Decimal("78.00"),
        temperature_c=Decimal("36.8"),
    ),
    DemoEncounter(
        document_number="40123456",
        days_ago=3,
        at_time=time(16, 20),
        weight_kg=Decimal("21.40"),
        height_cm=Decimal("118.00"),
        temperature_c=Decimal("36.9"),
        diagnosis_code="Z00.0",
    ),
)


#: Trece registros reales del origen (``Data_base.mdb``) elegidos por tener
#: identidad, residencia y localidad dentro del distrito sembrado. Los cinco
#: primeros traen la afiliación SIS completa; los siguientes cubren un tipo de
#: seguro cada uno (afiliación temporal, semi-subsidiado, NRUS, EsSalud y
#: sanidad) y tres sin seguro, para ejercitar cada rama de la admisión.
#: Son datos reales del origen: no deben salir de desarrollo.
#: ``establecimiento`` es el RENAES; ``diresa``/``tipo``/``numero`` son la
#: afiliación SIS y quedan vacíos cuando el seguro no es del SIS.
SOURCE_DEMO_PATIENTS: tuple[dict[str, Any], ...] = (
    {
        "documento": "77023409", "historia": "22",
        "paterno": "ESCALANTE", "materno": "CCURO", "nombre": "ALEJANDRO", "otros": "SERAPIO",
        "sexo": "M", "nacimiento": date(2000, 8, 26), "direccion": "ARTESANOS MISTI F5",
        "localidad": "ARTESANOS EL MISTI", "establecimiento": "1291",
        "seguro": "SIS_GRATUITO", "diresa": "040", "tipo": "2", "numero": "77023409",
    },
    {
        "documento": "02016585", "historia": "02016585",
        "paterno": "MASIAS", "materno": "MAMANI", "nombre": "MARCELINA", "otros": None,
        "sexo": "F", "nacimiento": date(1966, 4, 26), "direccion": "LA ESTRELLA E 7",
        "localidad": "LA ESTRELLA", "establecimiento": "1304",
        "seguro": "SIS_PARA_TODOS", "diresa": "040", "tipo": "2", "numero": "02016585",
    },
    {
        "documento": "45715716", "historia": "45715716",
        "paterno": "SALAS", "materno": "SERRANO", "nombre": "JONATHAN", "otros": "FERNNADO",
        "sexo": "M", "nacimiento": date(1989, 5, 18), "direccion": "V. UNION X-2 LEONES MISTI",
        "localidad": "LEONES DEL MISTI", "establecimiento": "1301",
        "seguro": "SIS_PARA_TODOS", "diresa": "040", "tipo": "2", "numero": "45715716",
    },
    {
        "documento": "40727174", "historia": "85",
        "paterno": "SALINAS", "materno": "PULCHA", "nombre": "EVELIN", "otros": None,
        "sexo": "F", "nacimiento": date(1980, 9, 27), "direccion": "AV. ROOSVELTH 707 GRAFICO",
        "localidad": "GRAFICOS", "establecimiento": "1291",
        "seguro": "SIS_GRATUITO", "diresa": "040", "tipo": "2", "numero": "40727174",
    },
    {
        "documento": "29470940", "historia": "94",
        "paterno": "SILVA", "materno": "SOTO", "nombre": "ROCIO", "otros": "ANTONIETA",
        "sexo": "F", "nacimiento": date(1969, 6, 21), "direccion": "LOS CLAVELES B2 APURIMAC",
        "localidad": "APURIMAC", "establecimiento": "1302",
        "seguro": "SIS_GRATUITO", "diresa": "040", "tipo": "2", "numero": "29470940",
    },
    # --- Un ejemplo por tipo de seguro (identidad y residencia del origen) ---
    {
        "documento": "75239016", "historia": "69915",
        "paterno": "SANCHEZ", "materno": "PILA", "nombre": "LUIS", "otros": "ANGEL",
        "sexo": "M", "nacimiento": date(2005, 6, 29), "direccion": "CRUCE CHILINA D-5",
        "localidad": "BALCONES DE CHILINA", "establecimiento": "1302",
        "seguro": "SIS_AFILIACION_TEMPORAL", "diresa": "040", "tipo": "E", "numero": "24233929",
    },
    {
        "documento": "48383475", "historia": "57275",
        "paterno": "PRIETO", "materno": "VILLENA", "nombre": "ISABEL", "otros": None,
        "sexo": "F", "nacimiento": date(1994, 8, 6), "direccion": "LA ESTRELLA D8",
        "localidad": "LA ESTRELLA", "establecimiento": "1291",
        "seguro": "SIS_SEMI_SUBSIDIADO", "diresa": "040", "tipo": "6", "numero": "10760571",
    },
    {
        "documento": "47689237", "historia": "7783",
        "paterno": "RAMIREZ", "materno": "TORRES", "nombre": "SHESSIRA", "otros": "SHIRLEY",
        "sexo": "F", "nacimiento": date(1993, 1, 9), "direccion": "SAN LUIS E3-4",
        "localidad": "LEONES DEL MISTI", "establecimiento": "1303",
        "seguro": "SIS_NRUS", "diresa": "040", "tipo": "R", "numero": "00700955",
    },
    {
        "documento": "45769780", "historia": "9150",
        "paterno": "PHOCCO", "materno": "SALAZAR", "nombre": "CARLOS", "otros": "EMRIQUE",
        "sexo": "M", "nacimiento": date(1989, 6, 9), "direccion": "CALLE CAJAMARCA N°326",
        "localidad": "APURIMAC", "establecimiento": "1291",
        "seguro": "ESSALUD", "diresa": None, "tipo": None, "numero": None,
    },
    {
        "documento": "29253988", "historia": "84315",
        "paterno": "VALLE", "materno": "ARREDONDO", "nombre": "LUCY",
        "otros": "ALEJANDRINA CONSUELO",
        "sexo": "F", "nacimiento": date(1956, 4, 18), "direccion": "FRANCISCO BOLOGNESI 111",
        "localidad": "LEONES DEL MISTI", "establecimiento": "1291",
        "seguro": "SANIDAD", "diresa": None, "tipo": None, "numero": None,
    },
    # --- Tres sin seguro, para ver el formulario sin afiliación ---
    {
        "documento": "73099640", "historia": "42",
        "paterno": "MAMANI", "materno": "TORRES", "nombre": "LUCIA", "otros": None,
        "sexo": "F", "nacimiento": date(2002, 6, 7), "direccion": "COOP VILLA EL SOL M 8",
        "localidad": "VILLA EL SOL", "establecimiento": "1291",
        "seguro": "SIN_SEGURO", "diresa": None, "tipo": None, "numero": None,
    },
    {
        "documento": "29702163", "historia": "88",
        "paterno": "USCAMAYTA", "materno": "LUQUE", "nombre": "MARIA", "otros": None,
        "sexo": "F", "nacimiento": date(1952, 3, 25), "direccion": "CALLE MISTI 125 APURIMAC",
        "localidad": "APURIMAC", "establecimiento": "1291",
        "seguro": "SIN_SEGURO", "diresa": None, "tipo": None, "numero": None,
    },
    {
        "documento": "76362674", "historia": "273",
        "paterno": "PALOMINO", "materno": "OCON", "nombre": "MARICARME", "otros": "ELIZABETH",
        "sexo": "F", "nacimiento": date(1999, 5, 24), "direccion": "JAVIER HERAUD J 10",
        "localidad": "LEONES DEL MISTI", "establecimiento": "1291",
        "seguro": "SIN_SEGURO", "diresa": None, "tipo": None, "numero": None,
    },
)


def _get_or_create(
    session: Session,
    model: type[Entity],
    lookup: dict[str, Any],
    values: dict[str, Any] | None = None,
) -> Entity:
    """Return a natural-key record, creating it without changing existing data."""

    entity = session.scalar(select(model).filter_by(**lookup))
    if entity is not None:
        return entity
    entity = model(**lookup, **(values or {}))
    session.add(entity)
    session.flush()
    return entity


def _catalog_locality(session: Session, ubigeo_codigo: str, nombre: str) -> Localidad:
    """Returns the catalog locality of a district, failing loudly when absent."""

    locality = session.scalar(
        select(Localidad).where(
            Localidad.ubigeo_codigo == ubigeo_codigo,
            Localidad.nombre_norm == nombre.casefold(),
        )
    )
    if locality is None:
        raise RuntimeError(
            f"Falta la localidad {nombre!r} del distrito {ubigeo_codigo}; "
            "ejecute las migraciones antes de la semilla."
        )
    return locality


def _real_establishment(session: Session, renaes: str) -> Establishment:
    """Returns a migration-seeded site, failing loudly when absent."""

    establishment = session.scalar(
        select(Establishment).where(Establishment.codigo_renaes == renaes)
    )
    if establishment is None:
        raise RuntimeError(
            f"Falta la sede {renaes}; ejecute las migraciones antes de la semilla."
        )
    return establishment


def _ensure_demo_professional_user(session: Session, professional: Professional) -> User:
    """Create the fixed local clinician account without changing existing credentials."""

    professional_role = session.scalar(select(Role).where(Role.codigo == "PROFESIONAL"))
    if professional_role is None:
        raise RuntimeError("No existe el rol PROFESIONAL. Ejecute las migraciones primero.")

    user = session.scalar(
        select(User).where(User.nombre_usuario == DEMO_PROFESSIONAL_USERNAME)
    )
    if user is None:
        linked_user = session.scalar(
            select(User).where(User.profesional_id == professional.id)
        )
        if linked_user is not None:
            raise RuntimeError(
                "El profesional demo ya está vinculado a otro usuario; "
                "no se puede crear medico.demo de forma segura."
            )
        user = User(
            profesional_id=professional.id,
            nombre_usuario=DEMO_PROFESSIONAL_USERNAME,
            password_hash=hash_password(DEMO_PROFESSIONAL_PASSWORD),
        )
        session.add(user)
        session.flush()
        session.add(UserRole(usuario_id=user.id, rol_id=professional_role.id))
        return user

    if user.profesional_id != professional.id:
        raise RuntimeError(
            "El usuario medico.demo ya está vinculado a otro profesional; "
            "no se puede reutilizar como cuenta demo."
        )
    return user


def _seed_demo_patients(
    session: Session,
    *,
    origin: Establishment,
    destination: Establishment,
    districts: dict[str, str],
    insurances: dict[str, Insurance],
    risk_groups: dict[str, RiskGroup],
    professional: Professional,
) -> dict[str, Patient]:
    """Create the fictional cohort and return it keyed by document number."""

    patients: dict[str, Patient] = {}
    for demo in DEMO_PATIENTS:
        locality = _catalog_locality(session, districts[demo.district_code], demo.locality)
        patient = session.scalar(
            select(Patient).where(
                Patient.tipo_documento_codigo == "DNI",
                Patient.numero_documento == demo.document_number,
            )
        )
        if patient is None:
            establishment = destination if demo.at_destination else origin
            patient = Patient(
                tipo_documento_codigo="DNI",
                numero_documento=demo.document_number,
                historia_clinica=demo.clinical_history,
                fecha_inscripcion=DEMO_REGISTRATION_DATE,
                fecha_nacimiento=demo.birth_date,
                apellido_paterno=demo.paternal_surname,
                apellido_materno=demo.maternal_surname,
                primer_nombre=demo.first_name,
                sexo_codigo=demo.sex_code,
                ubigeo_residencia_codigo=districts[demo.district_code],
                localidad=locality.nombre,
                localidad_id=locality.id,
                direccion=demo.address,
                telefono_principal=demo.phone,
                seguro_id=insurances[demo.insurance_code].id,
                establecimiento_registro_id=establishment.id,
                profesional_registro_id=(professional.id if demo.registered_by_clinician else None),
            )
            session.add(patient)
            session.flush()
        elif patient.localidad_id != locality.id:
            # Repara semillas antiguas que dejaban la localidad sin enlazar o
            # guardaban el nombre del distrito o su código de ubigeo.
            patient.localidad = locality.nombre
            patient.localidad_id = locality.id
        patients[demo.document_number] = patient

        if demo.responsible is not None:
            relationship, full_name, phone = demo.responsible
            _get_or_create(
                session,
                PatientResponsible,
                {"paciente_id": patient.id, "nombre_completo": full_name},
                {
                    "parentesco": relationship,
                    "telefono": phone,
                    "es_principal": True,
                },
            )
        if demo.risk_code is not None:
            _get_or_create(
                session,
                PatientRisk,
                {
                    "paciente_id": patient.id,
                    "grupo_riesgo_id": risk_groups[demo.risk_code].id,
                    "fecha_inicio": DEMO_RISK_START,
                },
                {"observacion": "Antecedente ficticio cargado por seed_demo_data."},
            )
    return patients


def _seed_source_examples(
    session: Session,
    *,
    ubigeo_codigo: str,
    professional: Professional,
) -> dict[str, Patient]:
    """Create the real source patients used as admission-form examples."""

    patients: dict[str, Patient] = {}
    ubigeo = session.get(Ubigeo, ubigeo_codigo)
    if ubigeo is None:
        raise RuntimeError(
            f"Falta el ubigeo {ubigeo_codigo}; ejecute las migraciones antes de la semilla."
        )
    for demo in SOURCE_DEMO_PATIENTS:
        existing = session.scalar(
            select(Patient).where(
                Patient.tipo_documento_codigo == "DNI",
                Patient.numero_documento == demo["documento"],
            )
        )
        if existing is not None:
            patients[demo["documento"]] = existing
            continue
        localidad = session.scalar(
            select(Localidad).where(
                Localidad.ubigeo_codigo == ubigeo_codigo,
                Localidad.nombre_norm == str(demo["localidad"]).casefold(),
            )
        )
        establishment = session.scalar(
            select(Establishment).where(
                Establishment.codigo_renaes == demo["establecimiento"]
            )
        )
        insurance = session.scalar(select(Insurance).where(Insurance.codigo == demo["seguro"]))
        if localidad is None or establishment is None or insurance is None:
            raise RuntimeError(
                f"Faltan catálogos para el paciente de ejemplo {demo['documento']}; "
                "ejecute las migraciones antes de la semilla."
            )
        patient = Patient(
            tipo_documento_codigo="DNI",
            numero_documento=demo["documento"],
            historia_clinica=demo["historia"],
            fecha_nacimiento=demo["nacimiento"],
            fecha_inscripcion=DEMO_REGISTRATION_DATE,
            apellido_paterno=demo["paterno"],
            apellido_materno=demo["materno"],
            primer_nombre=demo["nombre"],
            otros_nombres=demo["otros"],
            sexo_codigo=demo["sexo"],
            ubigeo_residencia_codigo=ubigeo.codigo,
            localidad=localidad.nombre,
            localidad_id=localidad.id,
            direccion=demo["direccion"],
            seguro_id=insurance.id,
            establecimiento_registro_id=establishment.id,
            profesional_registro_id=professional.id,
            sis_diresa=demo.get("diresa"),
            sis_tipo=demo.get("tipo"),
            sis_numero=demo.get("numero"),
        )
        session.add(patient)
        session.flush()
        patients[demo["documento"]] = patient
    return patients


def _issue_demo_document(
    session: Session,
    documents: DocumentService,
    *,
    encounter: DemoEncounter,
    attention_id: int,
    destination: Establishment,
    actor_id: int,
) -> int | None:
    """Issue the encounter document once, returning its id when it exists."""

    kind = encounter.document
    if kind is None:
        return None
    roles = ("PROFESIONAL",)
    if kind == "FUA":
        existing = session.scalar(select(Fua).where(Fua.atencion_id == attention_id))
        if existing is not None:
            return existing.id
        issued = documents.issue_fua(
            FuaIssueInput(
                atencion_id=attention_id,
                observaciones="FUA ficticio cargado por seed_demo_data.",
            ),
            actor_id=actor_id,
            actor_roles=roles,
        )
        return issued.id
    if kind == "CERTIFICADO":
        existing = session.scalar(
            select(Certificate).where(Certificate.atencion_id == attention_id)
        )
        if existing is not None:
            return existing.id
        issued = documents.issue_certificate(
            CertificateIssueInput(
                atencion_id=attention_id,
                tipo="CERTIFICADO_MEDICO",
                prestaciones=["CONSULTA_MED"],
            ),
            actor_id=actor_id,
            actor_roles=roles,
        )
        return issued.id
    if kind == "REFERENCIA":
        existing = session.scalar(
            select(Referral).where(
                Referral.atencion_id == attention_id,
                Referral.establecimiento_destino_id == destination.id,
            )
        )
        if existing is not None:
            return existing.id
        issued = documents.create_referral(
            ReferralCreateInput(
                atencion_id=attention_id,
                tipo="ESPECIALIDAD",
                establecimiento_destino_id=destination.id,
                motivo=(
                    "Paciente con cifras de presión arterial elevadas en controles "
                    "sucesivos; se solicita evaluación por especialidad."
                ),
                observaciones="Referencia ficticia cargada por seed_demo_data.",
            ),
            actor_id=actor_id,
            actor_roles=roles,
        )
        return issued.id
    raise RuntimeError(f"Tipo de documento demo no soportado: {kind}")


def _seed_demo_encounters(
    session: Session,
    *,
    origin: Establishment,
    destination: Establishment,
    office: Office,
    professional: Professional,
    actor_id: int,
    patients: dict[str, Patient],
) -> dict[str, int]:
    """Register the historical encounters and their documents through the services."""

    attentions = AttentionService(session)
    documents = DocumentService(session)
    identifiers: dict[str, int] = {}
    for order, encounter in enumerate(DEMO_ENCOUNTERS, start=1):
        patient = patients[encounter.document_number]
        taken_on = datetime.combine(
            date.today() - timedelta(days=encounter.days_ago),
            encounter.at_time,
        )
        existing = session.scalar(
            select(Attention).where(
                Attention.paciente_id == patient.id,
                Attention.profesional_id == professional.id,
                Attention.fecha_atencion == taken_on,
            )
        )
        if existing is None:
            created = attentions.create(
                AttentionCreate(
                    paciente_id=patient.id,
                    establecimiento_id=origin.id,
                    profesional_id=professional.id,
                    especialidad_codigo=office.especialidad_codigo,
                    consultorio_id=office.id,
                    modalidad_atencion_codigo=AttentionModeCode.AMBULATORY,
                    fecha_atencion=taken_on,
                    fecha_atendido=taken_on + timedelta(minutes=30),
                    peso_kg=encounter.weight_kg,
                    talla_cm=encounter.height_cm,
                    perimetro_abdominal_cm=encounter.waist_cm,
                    presion_sistolica=encounter.systolic,
                    presion_diastolica=encounter.diastolic,
                    temperatura_c=encounter.temperature_c,
                    hora_inicio=encounter.at_time,
                    hora_fin=(taken_on + timedelta(minutes=30)).time(),
                    admision=f"DEMO-ADM-{order:04d}",
                    observaciones="Atención ficticia cargada por seed_demo_data.",
                    prestaciones=[AttentionServiceInput(prestacion_codigo="CONSULTA_MED")],
                    diagnosticos=(
                        [
                            AttentionDiagnosisInput(
                                cie10_codigo=encounter.diagnosis_code,
                                tipo_diagnostico="PRESUNTIVO",
                            )
                        ]
                        if encounter.diagnosis_code is not None
                        else []
                    ),
                ),
                actor_id=actor_id,
                actor_roles=("PROFESIONAL",),
            )
            attention_id = created.id
        else:
            attention_id = existing.id

        identifiers[f"attention_{order}"] = attention_id
        document_id = _issue_demo_document(
            session,
            documents,
            encounter=encounter,
            attention_id=attention_id,
            destination=destination,
            actor_id=actor_id,
        )
        if document_id is not None:
            identifiers[f"{encounter.document.lower()}_{order}"] = document_id
    return identifiers


def seed_demo_data() -> dict[str, int]:
    """Create the development-only prerequisites for all exposed API workflows."""

    environment = get_settings().environment.strip().casefold()
    if environment != "development":
        raise RuntimeError(
            "Las semillas de demostración solo pueden ejecutarse con ENVIRONMENT=development."
        )

    session = SessionLocal()
    try:
        # The initial migration creates these codes but deliberately has no
        # clinical ranges.  Fill only entirely unset ranges, preserving any
        # configuration that an ADMIN has already established.
        for code, name, minimum, maximum in (
            ("NINO", "Niño", 0, 143),
            ("ADOLESCENTE", "Adolescente", 144, 215),
            ("JOVEN", "Joven", 216, 359),
            ("ADULTO", "Adulto", 360, 719),
            ("ADULTO_MAYOR", "Adulto mayor", 720, None),
        ):
            group = session.get(AgeGroup, code)
            if group is None:
                group = AgeGroup(
                    codigo=code,
                    nombre=name,
                    edad_minima_meses=minimum,
                    edad_maxima_meses=maximum,
                )
                session.add(group)
            elif group.edad_minima_meses is None and group.edad_maxima_meses is None:
                group.edad_minima_meses = minimum
                group.edad_maxima_meses = maximum

        _get_or_create(
            session,
            ServiceOffering,
            {"codigo": "CONSULTA_MED"},
            {"descripcion": "Consulta médica general", "grupo": "Consulta"},
        )
        _get_or_create(
            session,
            Cie10,
            {"codigo": "Z00.0"},
            {"descripcion": "Examen médico general", "categoria": "Factores que influyen en el estado de salud"},
        )
        risk = _get_or_create(
            session,
            RiskGroup,
            {"codigo": "RIESGO_DEMO"},
            {"nombre": "Riesgo de demostración", "descripcion": "Registro ficticio para pruebas locales."},
        )
        risk_groups = {
            risk.codigo: risk,
            **{
                code: _get_or_create(
                    session,
                    RiskGroup,
                    {"codigo": code},
                    {"nombre": name, "descripcion": "Registro ficticio para pruebas locales."},
                )
                for code, name in DEMO_RISK_GROUPS
            },
        }
        insurances = {
            insurance.codigo: insurance
            for insurance in session.scalars(select(Insurance)).all()
        }

        # Los catálogos territoriales, las sedes y los consultorios los siembran
        # las migraciones con datos reales; la semilla los resuelve y nunca crea
        # filas ``DEMO_*``. La cuenta clínica se vincula a un profesional real.
        districts: dict[str, str] = {}
        for code, _name in DEMO_DISTRICTS:
            district = session.get(Ubigeo, code)
            if district is None:
                raise RuntimeError(
                    f"Falta el ubigeo {code}; ejecute las migraciones antes de la semilla."
                )
            districts[code] = district.codigo

        origin = _real_establishment(session, DEMO_SITE_RENAES)
        destination = _real_establishment(session, DEMO_DESTINATION_RENAES)
        office = session.scalar(
            select(Office)
            .where(
                Office.establecimiento_id == origin.id,
                Office.especialidad_codigo == DEMO_MEDICINE_SPECIALTY,
            )
            .order_by(Office.id)
        )
        if office is None:
            raise RuntimeError(
                "Falta el consultorio de medicina; ejecute las migraciones antes de la semilla."
            )
        professional = session.scalar(
            select(Professional)
            .join(ProfessionalSpecialty)
            .where(ProfessionalSpecialty.especialidad_codigo == DEMO_MEDICINE_SPECIALTY)
            .order_by(Professional.id)
        )
        if professional is None:
            raise RuntimeError(
                "Falta un profesional de medicina; ejecute las migraciones antes de la semilla."
            )
        registration_professional = (
            session.scalar(
                select(Professional)
                .where(Professional.id != professional.id)
                .order_by(Professional.id)
            )
            or professional
        )
        demo_professional_user = _ensure_demo_professional_user(session, professional)

        # Los dos pacientes originales viven en Alto Selva Alegre, el mismo
        # sector que les da la localidad del catálogo SIS.
        demo_localidad = _catalog_locality(
            session, districts["040102"], 'ALTO SELVA ALEGRE "A"'
        )

        adult = _get_or_create(
            session,
            Patient,
            {"tipo_documento_codigo": "DNI", "numero_documento": "99900001"},
            {
                "historia_clinica": "HC-DEMO-ADULTO",
                "fecha_nacimiento": date(1990, 5, 10),
                "apellido_paterno": "Prueba",
                "apellido_materno": "Demo",
                "primer_nombre": "Ana",
                "sexo_codigo": "F",
                "ubigeo_residencia_codigo": districts["040102"],
                "localidad": demo_localidad.nombre,
                "localidad_id": demo_localidad.id,
                "direccion": "Calle Cahuide 504",
                "establecimiento_registro_id": origin.id,
                "telefono_principal": "999888777",
            },
        )
        minor = _get_or_create(
            session,
            Patient,
            {"tipo_documento_codigo": "DNI", "numero_documento": "99900002"},
            {
                "historia_clinica": "HC-DEMO-MENOR",
                "fecha_nacimiento": date(2017, 5, 10),
                "apellido_paterno": "Prueba",
                "apellido_materno": "Demo",
                "primer_nombre": "Luis",
                "sexo_codigo": "M",
                "ubigeo_residencia_codigo": districts["040102"],
                "localidad": demo_localidad.nombre,
                "localidad_id": demo_localidad.id,
                "direccion": "Pasaje Los Pinos 120",
                "establecimiento_registro_id": origin.id,
            },
        )
        for demo_patient, address in (
            (adult, "Calle Cahuide 504"),
            (minor, "Pasaje Los Pinos 120"),
        ):
            if demo_patient.localidad_id != demo_localidad.id:
                demo_patient.ubigeo_residencia_codigo = districts["040102"]
                demo_patient.localidad = demo_localidad.nombre
                demo_patient.localidad_id = demo_localidad.id
            if demo_patient.direccion is None:
                demo_patient.direccion = address
        _get_or_create(
            session,
            PatientResponsible,
            {"paciente_id": minor.id, "nombre_completo": "María Responsable Demo"},
            {"parentesco": "MADRE", "telefono": "988777666", "es_principal": True},
        )

        cohort = _seed_demo_patients(
            session,
            origin=origin,
            destination=destination,
            districts=districts,
            insurances=insurances,
            risk_groups=risk_groups,
            professional=professional,
        )
        source_examples = _seed_source_examples(
            session,
            ubigeo_codigo="040102",
            professional=professional,
        )
        session.commit()

        identifiers = _seed_demo_encounters(
            session,
            origin=origin,
            destination=destination,
            office=office,
            professional=professional,
            actor_id=demo_professional_user.id,
            patients=cohort,
        )

        return {
            "establishment_id": origin.id,
            "destination_establishment_id": destination.id,
            "office_id": office.id,
            "professional_id": professional.id,
            "professional_user_id": demo_professional_user.id,
            "registration_professional_id": registration_professional.id,
            "risk_group_id": risk.id,
            "adult_patient_id": adult.id,
            "minor_patient_id": minor.id,
            "demo_patient_count": len(cohort),
            "source_example_patient_count": len(source_examples),
            **identifiers,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_real_patients() -> dict[str, int]:
    """Create only the real source patients, without the fictional cohort.

    The rows come from the origin ``Data_base.mdb`` (real identity and
    residence), so they stay in development environments. The clinician account
    is created separately with ``create_professional_user``.
    """

    environment = get_settings().environment.strip().casefold()
    if environment != "development":
        raise RuntimeError(
            "Las semillas de demostración solo pueden ejecutarse con ENVIRONMENT=development."
        )

    session = SessionLocal()
    try:
        professional = session.scalar(
            select(Professional)
            .where(Professional.activo.is_(True))
            .order_by(Professional.id)
        )
        if professional is None:
            raise RuntimeError(
                "No hay profesionales sembrados; ejecute las migraciones antes de la semilla."
            )
        patients = _seed_source_examples(
            session, ubigeo_codigo="040102", professional=professional
        )
        session.commit()
        identifiers = {
            "professional_id": professional.id,
            "real_patient_count": len(patients),
        }
        for document, patient in patients.items():
            identifiers[f"patient_{document}"] = patient.id
        return identifiers
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga datos de desarrollo: cohorte ficticio o solo pacientes reales."
    )
    parser.add_argument(
        "--real-only",
        action="store_true",
        help=(
            "Carga solo los pacientes reales del origen, sin cohorte ficticio "
            "ni cuenta clínica."
        ),
    )
    args = parser.parse_args()

    if args.real_only:
        identifiers = seed_real_patients()
        print("Pacientes reales del origen creados o verificados.")
    else:
        identifiers = seed_demo_data()
        print("Semillas de demostración creadas o verificadas.")
    for key, value in identifiers.items():
        print(f"{key}={value}")
    if not args.real_only:
        print(f"professional_username={DEMO_PROFESSIONAL_USERNAME}")
        print(f"professional_password={DEMO_PROFESSIONAL_PASSWORD}")


if __name__ == "__main__":
    main()
