"""Complete the residence and insurance data of the development patients.

Two kinds of problems are fixed here, and neither belongs in a migration:

* **Catalog names.** ``ubigeos.distrito`` was seeded by different authors with
  different labels, so ``040102`` ended up named ``Cayma`` (its neighbour) and
  the official name was lost.  This command restores the official district
  names of the Arequipa province.
* **Incomplete patients.** Rows created by hand or by early seeds can lack the
  district, the locality, the address or the insurance.  This command aligns
  the district with the text the row already carries (``Cayma`` implies the
  ``040103`` ubigeo) and links the matching row of the ``localidades`` catalog,
  which is what makes a patient residence verifiable.

Because the last group *fabricates* residence data, it is deliberately not a
migration: it refuses to run outside ``development`` and prints every change.
Running it without ``--apply`` only reports.  It is idempotent: a second run
finds nothing to change.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.catalog import Insurance
from app.models.organization import Localidad, Ubigeo
from app.models.patient import Patient

#: Official district names of the Arequipa province (INEI).  The province and
#: the department are the same value in every row of this catalog.
AREQUIPA_DISTRICTS: dict[str, str] = {
    "040101": "AREQUIPA",
    "040102": "ALTO SELVA ALEGRE",
    "040103": "CAYMA",
    "040104": "CERRO COLORADO",
    "040105": "CHARACATO",
    "040106": "CHIGUATA",
    "040107": "JACOBO HUNTER",
    "040108": "LA JOYA",
    "040109": "MARIANO MELGAR",
    "040110": "MIRAFLORES",
    "040111": "MOLLEBAYA",
    "040112": "PAUCARPATA",
    "040113": "POCSI",
    "040114": "POLOBAYA",
    "040115": "QUEQUEÑA",
    "040116": "SABANDÍA",
    "040117": "SACHACA",
    "040118": "SAN JUAN DE SIGUAS",
    "040119": "SAN JUAN DE TARUCANI",
    "040120": "SANTA ISABEL DE SIGUAS",
    "040121": "SANTA RITA DE SIGUAS",
    "040122": "SOCABAYA",
    "040123": "TIABAYA",
    "040124": "UCHUMAYO",
    "040125": "VÍTOR",
    "040126": "YANAHUARA",
    "040127": "YARABAMBA",
    "040128": "YURA",
    "040129": "JOSÉ LUIS BUSTAMANTE Y RIVERO",
}

#: District assumed when a patient carries no residence code at all.
FALLBACK_UBIGEO = "040101"

#: Address written when the row has none, so the field stays auditable instead
#: of passing for a real domicile.
PLACEHOLDER_ADDRESS = "DIRECCION NO REGISTRADA"

#: Sex assumed when the row has none (placeholder for development rows only).
PLACEHOLDER_SEX = "M"


@dataclass(frozen=True, slots=True)
class Change:
    """One field about to be written, with both values for the report."""

    target: str
    field: str
    before: object
    after: object


def _condition_for_age(birth: date | None, today: date) -> str | None:
    """Maps an age to the ``condicion`` labels the source database used."""

    if birth is None:
        return None
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    if age < 0:
        return None
    for limit, label in ((12, "NIÑO"), (18, "ADOLESCENTE"), (30, "JOVEN"), (60, "ADULTO")):
        if age < limit:
            return label
    return "ADULTO MAYOR"


def _placeholder_phone(patient_id: int) -> str:
    return f"9{patient_id:08d}"


def repair_ubigeos(session: Session, apply: bool) -> list[Change]:
    """Restore the official district names of the Arequipa province.

    ``ubigeos.localidad`` is a legacy column that early seeds filled with the
    name of a *neighbouring* district (``Cayma`` inside ``040102``), and the
    catalog search still matches it.  The locality now lives in its own
    catalog, so those stale values are cleared instead of kept.

    The corrected values are written on the session in every mode, so the
    patient pass resolves districts against the repaired catalog; a simulation
    rolls everything back before returning.
    """

    changes: list[Change] = []
    for ubigeo in session.scalars(select(Ubigeo).order_by(Ubigeo.codigo)):
        if ubigeo.codigo not in AREQUIPA_DISTRICTS:
            continue
        expected = AREQUIPA_DISTRICTS[ubigeo.codigo]
        if ubigeo.distrito != expected:
            changes.append(Change(ubigeo.codigo, "ubigeos.distrito", ubigeo.distrito, expected))
            ubigeo.distrito = expected
        if ubigeo.localidad not in (None, ""):
            changes.append(Change(ubigeo.codigo, "ubigeos.localidad", ubigeo.localidad, None))
            ubigeo.localidad = None
    return changes


def _pick_locality(patient: Patient, localities: list[Localidad], district: Ubigeo) -> Localidad:
    """Chooses the catalog locality that best matches the patient text.

    An exact (normalized) match wins; otherwise the locality that names the
    district is preferred, and the lowest code is the deterministic fallback.
    """

    stored = (patient.localidad or "").strip().casefold()
    if stored:
        for locality in localities:
            if locality.nombre_norm == stored:
                return locality
    district_name = district.distrito.casefold()
    for locality in localities:
        if district_name in locality.nombre_norm:
            return locality
    return localities[0]


def _resolve_district(patient: Patient, districts: dict[str, Ubigeo]) -> Ubigeo:
    """Keeps the stored district, or infers it from the text residence.

    The address is the domicile and wins over the locality, which is only a
    sector inside a district.  When a text names the district the row already
    points to, that code is confirmed instead of replaced.
    """

    current = districts.get(patient.ubigeo_residencia_codigo or "")
    for text in (patient.direccion, patient.localidad):
        normalized = (text or "").casefold()
        if not normalized:
            continue
        named = [
            district
            for district in districts.values()
            if district.distrito.casefold() in normalized
        ]
        if named:
            for district in named:
                if current is not None and district.codigo == current.codigo:
                    return district
            return named[0]
    return current or districts[FALLBACK_UBIGEO]


def complete_patients(session: Session, apply: bool, today: date) -> list[Change]:
    """Fills district, locality, address, insurance and contact placeholders."""

    localities_by_district: dict[str, list[Localidad]] = {}
    for locality in session.scalars(
        select(Localidad).order_by(Localidad.ubigeo_codigo, Localidad.codigo_catalogo)
    ):
        localities_by_district.setdefault(locality.ubigeo_codigo, []).append(locality)
    districts = {
        ubigeo.codigo: ubigeo for ubigeo in session.scalars(select(Ubigeo).order_by(Ubigeo.codigo))
    }
    no_insurance = session.scalar(select(Insurance).where(Insurance.codigo == "SIN_SEGURO"))
    if no_insurance is None:
        raise RuntimeError("Falta el seguro SIN_SEGURO; ejecute las migraciones primero.")

    changes: list[Change] = []
    for patient in session.scalars(select(Patient).order_by(Patient.id)):
        resident = _resolve_district(patient, districts)
        localities = localities_by_district.get(resident.codigo, [])
        if not localities:
            raise RuntimeError(
                f"El distrito {resident.codigo} no tiene localidades sembradas; "
                "ejecute las migraciones antes."
            )
        locality = _pick_locality(patient, localities, resident)

        # Canonical residence: the text and its catalog row must agree, so a
        # wrong code or name is corrected instead of preserved.
        assignments: dict[str, object] = {
            "ubigeo_residencia_codigo": resident.codigo,
            "localidad_id": locality.id,
            "localidad": locality.nombre,
        }
        # Placeholders: only for empty fields, never over real recorded data.
        for field, value in (
            ("direccion", patient.direccion or PLACEHOLDER_ADDRESS),
            ("seguro_id", patient.seguro_id or no_insurance.id),
            ("sexo_codigo", patient.sexo_codigo or PLACEHOLDER_SEX),
            (
                "telefono_principal",
                patient.telefono_principal or _placeholder_phone(patient.id),
            ),
            (
                "condicion",
                patient.condicion or _condition_for_age(patient.fecha_nacimiento, today),
            ),
        ):
            if value not in (None, ""):
                assignments[field] = value

        target = f"{patient.id} {patient.numero_documento}"
        for field, after in assignments.items():
            before = getattr(patient, field)
            if before == after:
                continue
            changes.append(Change(target, field, before, after))
            if apply:
                setattr(patient, field, after)
    return changes


def incomplete_patients(session: Session) -> list[Patient]:
    """Patients still missing any residence or insurance datum."""

    return [
        patient
        for patient in session.scalars(select(Patient).order_by(Patient.id))
        if patient.ubigeo_residencia_codigo is None
        or patient.localidad_id is None
        or not patient.localidad
        or not patient.direccion
        or patient.seguro_id is None
    ]


def _report(changes: Iterable[Change]) -> None:
    for change in changes:
        print(
            f"  {change.target:<16} {change.field:<26} "
            f"{str(change.before)[:32]!r} -> {str(change.after)[:32]!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repara el catálogo de distritos y completa la residencia y el seguro "
            "de los pacientes. Solo apto para una base de desarrollo."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribe los cambios; sin esta bandera solo informa lo que haría.",
    )
    args = parser.parse_args()

    environment = get_settings().environment.strip().casefold()
    if environment != "development":
        raise RuntimeError(
            "La reparación fabrica datos de residencia; solo corre con ENVIRONMENT=development."
        )

    session = SessionLocal()
    today = date.today()
    try:
        catalog_changes = repair_ubigeos(session, args.apply)
        patient_changes = complete_patients(session, args.apply, today)
        print(f"Valores de catálogo corregidos: {len(catalog_changes)}")
        _report(catalog_changes)
        print(f"Campos de paciente completados: {len(patient_changes)}")
        _report(patient_changes)
        if args.apply:
            session.commit()
            print("Cambios aplicados.")
        else:
            session.rollback()
            print("Simulación: nada se escribió. Repita con --apply para aplicar.")

        pending = incomplete_patients(session)
        print(f"Pacientes incompletos restantes: {len(pending)}")
        for patient in pending:
            print(f"  {patient.id} {patient.numero_documento}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
