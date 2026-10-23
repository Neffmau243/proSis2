"""Minimal synthetic prerequisites; pipe into a newly migrated E2E container.

No source snapshot, real patients or development seed credentials are needed.
The physician, account, assignment, patient, attention and FUA are created by
the browser test, not here.
"""

import os

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.catalog import Insurance, Profession, Specialty
from app.models.organization import Establishment, Localidad, Office, Ubigeo
from app.models.patient import Patient

if os.environ.get("IPRESS_SYNTHETIC_E2E") != "1":
    raise RuntimeError("Explicit disposable E2E marker required.")
if get_settings().mysql_database != "ipress_docker_e2e":
    raise RuntimeError("Fixture is restricted to the disposable Docker E2E database.")

with SessionLocal.begin() as session:
    if session.scalar(select(func.count()).select_from(Patient)) != 0:
        raise RuntimeError("Synthetic setup requires an empty patient table.")
    site = session.scalar(select(Establishment).where(Establishment.codigo_renaes == "1291"))
    if site is None:
        raise RuntimeError("Migration did not create the expected establishment.")
    area = session.get(Specialty, "ESPECIALIDADES:003")
    service = session.get(Specialty, "ESP_MEDICINA:001")
    if area is None or service is None:
        raise RuntimeError("Migration did not create the clinical catalog.")
    if not session.scalar(select(Profession).where(Profession.nombre == "MEDICO")):
        session.add(Profession(nombre="MEDICO"))
    if not session.scalar(select(Insurance).where(Insurance.codigo == "SIS_GRATUITO")):
        session.add(Insurance(codigo="SIS_GRATUITO", nombre="SIS GRATUITO", regimen="SIS"))
    if not session.get(Ubigeo, "040102"):
        session.add(
            Ubigeo(
                codigo="040102",
                departamento="AREQUIPA",
                provincia="AREQUIPA",
                distrito="ALTO SELVA ALEGRE",
            )
        )
        session.flush()
    if not session.scalar(select(Localidad).where(Localidad.ubigeo_codigo == "040102")):
        session.add(
            Localidad(
                ubigeo_codigo="040102",
                codigo_catalogo="E2E",
                nombre="LOCALIDAD FICTICIA E2E",
                nombre_norm="LOCALIDAD FICTICIA E2E",
            )
        )
    office = session.scalar(
        select(Office).where(Office.establecimiento_id == site.id, Office.codigo == "MED")
    )
    if office is None:
        session.add(
            Office(
                establecimiento_id=site.id,
                codigo="MED",
                nombre="MEDICINA",
                area_codigo=area.codigo,
                especialidad_codigo=area.codigo,
                servicios_codigos=[service.codigo],
            )
        )
print("Synthetic clinical prerequisites created in the disposable E2E database.")
