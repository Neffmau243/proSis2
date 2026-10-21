"""Conservative patient-only Access mapping; no database writes or identity merges."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.family_history import family_history_problem, normalize_family_history
from app.domain.patient_document import document_problem
from app.schemas.patient import PatientCreate
from app.services.patient_responsible import PatientResponsibleRules

VERSION = "patients-arequipa-1.0"
NAME_FIELDS = ("Apellido_Paterno", "Apellido_Materno", "Primer_Nombre", "Otros_Nombres")
TEXT_FIELDS = {
    "Historia_Clinica": ("historia_clinica", 255),
    "Apellido_Paterno": ("apellido_paterno", 100),
    "Apellido_Materno": ("apellido_materno", 100),
    "Primer_Nombre": ("primer_nombre", 100),
    "Otros_Nombres": ("otros_nombres", 150),
    "Dirección": ("direccion", 300),
    "Localidad": ("localidad", 150),
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_source(directory: Path, source: Path) -> tuple[dict, dict[str, list[dict]]]:
    """Verify the MDB and every snapshot file; read only the required tables."""
    directory = directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    if manifest.get("version") != 1 or manifest.get("reader") != "Microsoft.ACE.OLEDB.16.0":
        raise ValueError("Formato de snapshot no compatible.")
    if file_digest(source) != manifest["source_sha256"]:
        raise ValueError("La huella del MDB no coincide con el snapshot.")
    wanted = {"Pacientes", "Provincia", "EESS"}
    tables = {}
    seen = set()
    for table in manifest["tables"]:
        name = table["name"]
        path = (directory / table["file"]).resolve()
        if path.parent != directory or name in seen:
            raise ValueError("Tabla o ruta repetida/inválida en snapshot.")
        seen.add(name)
        if file_digest(path) != table["sha256"]:
            raise ValueError(f"Huella de tabla no coincide: {name}")
        if name not in wanted:
            continue
        columns = [c["name"] for c in table["columns"]]
        if len(columns) != len(set(columns)):
            raise ValueError(f"Columnas repetidas: {name}")
        rows = []
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if not isinstance(row, dict) or set(row) != set(columns):
                    raise ValueError(f"Estructura inesperada: {name}")
                rows.append(row)
        if len(rows) != table["rows"]:
            raise ValueError(f"Recuento inesperado: {name}")
        tables[name] = rows
    if tables.keys() != wanted:
        raise ValueError("Faltan tablas necesarias para pacientes.")
    return manifest, tables


def key(value: Any) -> str:
    """Catalog/name comparison only; never rewrite identifiers or merge identities."""
    return " ".join(str(value or "").strip().upper().split())


def damaged(value: str) -> bool:
    return (
        "\ufffd" in value
        or any(unicodedata.category(c) in {"Cs", "Co", "Cc", "Cf"} for c in value)
        or bool(re.search(r"(?:Ã[\x80-\xbf]|Â[\x80-\xbf]|â[€\x80-\xbf])", value))
    )


def source_text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def source_date(value: Any, as_of: date) -> date | None:
    try:
        parsed = datetime.fromisoformat(value)
        result = parsed.date()
        return result if parsed.tzinfo is None and date(1900, 1, 1) <= result <= as_of else None
    except (ValueError, TypeError):
        return None


def positive_id(value: Any) -> int | None:
    return value if type(value) is int and 0 < value <= 18446744073709551615 else None


def unique_index(rows: list[dict], fields: tuple[str, ...], value_field: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(key(row.get(f)) for f in fields)].append(row[value_field])
    return {k: v[0] for k, v in groups.items() if len(v) == 1}


@dataclass
class Catalogs:
    districts: dict[str, str]
    establishments: dict[str, int]
    insurances: dict[str, tuple[int, bool]]
    localities: dict[tuple[str, str], tuple[int, str]]
    family_prefixes: set[str]
    sexes: set[str]
    document_types: set[str]


@dataclass
class Decision:
    row_number: int
    source: dict
    payload: PatientCreate | None = None
    state: str = "PENDIENTE"
    issues: list[str] = field(default_factory=list)
    patient_id: int | None = None


def build_plan(
    tables: dict[str, list[dict]],
    catalogs: Catalogs,
    existing: list[dict],
    archived: dict[int, dict],
    *,
    as_of: date,
) -> list[Decision]:
    patients = tables["Pacientes"]
    # Duplicates are evaluated against the entire source, even outside Arequipa/pilot.
    documents = Counter(source_text(r.get("N°_DNI")) for r in patients)
    codes = Counter(positive_id(r.get("Codclie")) for r in patients)
    identities = Counter(
        tuple(key(r.get(f)) for f in (*NAME_FIELDS, "Fecha_nacimiento")) for r in patients
    )
    existing_docs = {
        (key(r["tipo_documento_codigo"]), key(r["numero_documento"])): r for r in existing
    }
    existing_codes = {r["codclie_legacy"]: r for r in existing if r["codclie_legacy"]}
    decisions = []
    for number, row in enumerate(patients, 1):
        d = Decision(number, row)
        decisions.append(d)
        ubigeo = catalogs.districts.get(key(row.get("Distrito")))
        if not ubigeo or not ubigeo.startswith("0401"):
            d.state = "FUERA_DE_AMBITO"
            d.issues.append("distrito_fuera_de_arequipa_o_no_resuelto")
            continue
        doc = source_text(row.get("N°_DNI"))
        code = positive_id(row.get("Codclie"))
        birth = source_date(row.get("Fecha_nacimiento"), as_of)
        blocked = False

        def reject(reason: str, decision: Decision = d) -> None:
            nonlocal blocked
            blocked = True
            decision.issues.append(reason)

        if doc is None or document_problem("DNI", doc) or len(set(doc)) == 1:
            reject("dni_ausente_o_invalido")
        if doc and documents[doc] > 1:
            reject("dni_duplicado_en_origen")
        if not code or codes[code] > 1:
            reject("codclie_invalido_o_duplicado")
        if not birth:
            reject("nacimiento_ausente_o_invalido")
        identity = tuple(key(row.get(f)) for f in (*NAME_FIELDS, "Fecha_nacimiento"))
        if identities[identity] > 1:
            reject("nombre_y_nacimiento_repetidos")
        if not any(source_text(row.get(f)) for f in NAME_FIELDS):
            reject("sin_nombres")
        values: dict[str, Any] = dict(
            codclie_legacy=code,
            tipo_documento_codigo="DNI",
            numero_documento=doc,
            fecha_nacimiento=birth,
            ubigeo_residencia_codigo=ubigeo,
        )
        for source, (target, limit) in TEXT_FIELDS.items():
            raw = row.get(source)
            value = source_text(raw)
            if raw is not None and not isinstance(raw, str):
                reject("tipo_de_texto_invalido:" + target)
            if value and (damaged(value) or len(value) > limit):
                reject("texto_danado_o_largo:" + target)
                value = None
            values[target] = value
        registered = source_date(row.get("Fecha_inscripcion"), as_of)
        if row.get("Fecha_inscripcion") and registered is None:
            d.issues.append("inscripcion_invalida_archivada")
        if registered and birth and registered < birth:
            d.issues.append("inscripcion_anterior_a_nacimiento_archivada")
            registered = None
        if registered == date(2016, 1, 1):
            d.issues.append("inscripcion_posiblemente_predeterminada")
        values["fecha_inscripcion"] = registered
        if birth and PatientResponsibleRules.is_minor(birth, registered or as_of):
            reject("menor_sin_responsable_acreditado")
        sex = {"FEMENINO": "F", "MASCULINO": "M"}.get(key(row.get("Sexo")))
        values["sexo_codigo"] = sex if sex in catalogs.sexes else None
        if row.get("Sexo") and values["sexo_codigo"] is None:
            d.issues.append("sexo_no_resuelto")
        values["establecimiento_registro_id"] = catalogs.establishments.get(
            key(row.get("Establecimiento"))
        )
        if values["establecimiento_registro_id"] is None:
            # Only patients whose registration site is known enter this experiment.
            reject("establecimiento_no_resuelto")
        insurance = catalogs.insurances.get(key(row.get("Seguro")))
        values["seguro_id"] = insurance[0] if insurance else None
        if row.get("Seguro") and not insurance:
            d.issues.append("seguro_no_resuelto")
        locality = values["localidad"]
        if locality == ubigeo:
            values["localidad"] = None
            d.issues.append("localidad_era_ubigeo_archivada")
        elif locality:
            match = catalogs.localities.get((ubigeo, key(locality)))
            if match:
                values["localidad_id"], values["localidad"] = match
            else:
                d.issues.append("localidad_textual_sin_coincidencia_catalogo")
        hf = normalize_family_history(source_text(row.get("Historia_Familiar")))
        if hf and (
            damaged(hf)
            or family_history_problem(hf)
            or hf.split("-", 1)[0] not in catalogs.family_prefixes
        ):
            d.issues.append("historia_familiar_incompatible_archivada")
            hf = None
        values["historia_familiar"] = hf
        # Condition is dated clinical context, not a current diagnosis. Preserve in
        # the archive; derive current life stage when a real encounter is registered.
        if source_text(row.get("Condicion")):
            d.issues.append("condicion_historica_solo_archivo")
        values["condicion"] = None
        sis = dict(
            zip(
                ("sis_diresa", "sis_tipo", "sis_numero"),
                (source_text(row.get(f)) for f in ("Arequipa_040", "Arequipa_2", "Arequipa_SIS")),
                strict=True,
            )
        )
        if any(sis.values()):
            try:
                normalized_sis = PatientCreate.model_validate({**values, **sis})
                valid_sis = insurance and insurance[1] and sis["sis_tipo"] and sis["sis_numero"]
                if valid_sis:
                    values.update({f: getattr(normalized_sis, f) for f in sis})
                else:
                    d.issues.append("sis_incompleto_o_inconsistente_archivado")
            except ValidationError:
                d.issues.append("sis_incompleto_o_inconsistente_archivado")
        if "DNI" not in catalogs.document_types:
            reject("catalogo_dni_no_disponible")
        prior = archived.get(number)
        owner = existing_docs.get(("DNI", key(doc)))
        legacy_owner = existing_codes.get(code)
        if prior:
            if (
                prior["huella_fila"] == digest(row)
                and owner
                and prior["destino_tabla"] == "pacientes"
                and str(owner["id"]) == prior["destino_id"]
                and owner["codclie_legacy"] == code
            ):
                d.patient_id = owner["id"]
                d.state = "YA_IMPORTADO"
                # Re-running never overwrites subsequent patient edits.
                continue
            reject("trazabilidad_previa_incompatible")
        elif owner or legacy_owner:
            reject("identidad_ya_existe_en_destino")
        if not blocked:
            try:
                d.payload = PatientCreate.model_validate(values)
                d.state = "ACEPTADO"
            except ValidationError:
                reject("contrato_actual_incompatible")
    return decisions


def summarize(decisions: list[Decision]) -> dict:
    return {
        "version_etl": VERSION,
        "filas_origen": len(decisions),
        "estados": dict(sorted(Counter(d.state for d in decisions).items())),
        "incidencias": dict(sorted(Counter(i for d in decisions for i in set(d.issues)).items())),
    }
