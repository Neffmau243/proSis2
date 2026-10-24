"""Export and restore a private, portable installation snapshot for Docker.

Only master data is transferred: no encounters, clinical documents, audit log,
login locks or sessions. Foreign keys are remapped through natural identities;
source numeric ids are never assumed to match the destination installation.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

FORMAT_VERSION = 1
REVISION = "20261023_0042_docker_bootstrap"
SOURCE_REVISIONS = {"20261022_0041_assign_services", REVISION}

# Order also documents the dependency graph; offices are sorted by parent below.
# Alternative keys must resolve to the same destination record, or we abort.
IDENTITIES: dict[str, tuple[tuple[str, ...], ...]] = {
    "roles": (("codigo",),),
    "sexos": (("codigo",),),
    "tipos_documento": (("codigo",),),
    "etnias": (("codigo",),),
    "seguros": (("codigo",), ("nombre",)),
    "profesiones": (("nombre",),),
    "especialidades": (("codigo",),),
    "prestaciones": (("codigo",),),
    "modalidades_atencion": (("codigo",),),
    "grupos_etarios": (("codigo",),),
    "grupos_riesgo": (("codigo",),),
    "historias_familiares_catalogo": (("codigo",),),
    "ubigeos": (("codigo",),),
    "disa": (("codigo",),),
    "redes": (("id_disa", "codigo"),),
    "microredes": (("id_red", "codigo"),),
    "localidades": (("ubigeo_codigo", "codigo_catalogo"), ("ubigeo_codigo", "nombre_norm")),
    "establecimientos": (("codigo_renaes",), ("codigo_ideess",), ("codigo_legacy",)),
    "profesionales": (("numero_documento",), ("codigo_legacy",)),
    "profesional_especialidades": (("profesional_id", "especialidad_codigo"),),
    "usuarios": (("nombre_usuario",),),
    "usuario_roles": (("usuario_id", "rol_id"),),
    "consultorios": (("establecimiento_id", "codigo"),),
    "consultorio_profesionales": (("consultorio_id", "profesional_id", "fecha_inicio"),),
    "pacientes": (("tipo_documento_codigo", "numero_documento"), ("codclie_legacy",)),
    "paciente_responsables": (("paciente_id", "parentesco", "nombre_completo"),),
    "paciente_codigos_externos": (("paciente_id", "sistema"),),
    "paciente_anexos_legacy": (("paciente_id", "numero_anexo"),),
}
PATIENT_CHILDREN = {
    "paciente_responsables",
    "paciente_codigos_externos",
    "paciente_anexos_legacy",
}
JSON_SERVICE_TABLES = {"consultorios", "consultorio_profesionales"}
USER_TRANSIENT_FIELDS = {
    "ultimo_acceso_at",
    "intentos_fallidos_inicio_sesion",
    "bloqueado_inicio_sesion_hasta",
    "ultimo_intento_fallido_inicio_sesion_at",
}
_TEST_LABEL = re.compile(r"(?:^|[\s._-])(?:e2e|test|demo|prueba)(?:[\s._-]|\d|$)", re.I)
_TEST_HISTORY = re.compile(r"^(?:HC[-_]DEMO|PRUEBA|PRB\d|UI\d|E2E[-_])", re.I)


def _operational_data(tables: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Exclude inactive rows and explicitly labelled development fixtures."""
    labels = {
        "usuarios": ("nombre_usuario",),
        "profesionales": ("nombre_completo",),
        "consultorios": ("codigo", "nombre"),
        "especialidades": ("codigo", "nombre"),
        "pacientes": ("apellido_paterno", "apellido_materno", "primer_nombre", "otros_nombres"),
    }
    filtered = {}
    for name, rows in tables.items():
        filtered[name] = [
            row
            for row in rows
            if row.get("activo", row.get("estado", True))
            and not any(
                _TEST_LABEL.search(str(row.get(field) or "")) for field in labels.get(name, ())
            )
            and not (
                name == "pacientes"
                and row.get("codclie_legacy") is None
                and _TEST_HISTORY.search(row.get("historia_clinica") or "")
            )
        ]
    parents = {
        "profesional_especialidades": (
            ("profesional_id", "profesionales", "id"),
            ("especialidad_codigo", "especialidades", "codigo"),
        ),
        "usuario_roles": (("usuario_id", "usuarios", "id"),),
        "consultorio_profesionales": (
            ("consultorio_id", "consultorios", "id"),
            ("profesional_id", "profesionales", "id"),
        ),
        **{name: (("paciente_id", "pacientes", "id"),) for name in PATIENT_CHILDREN},
    }
    for name, references in parents.items():
        for field, parent, key in references:
            allowed = {row[key] for row in filtered[parent]}
            filtered[name] = [row for row in filtered[name] if row[field] in allowed]
    return filtered


def _metadata(connection: Connection) -> sa.MetaData:
    metadata = sa.MetaData()
    metadata.reflect(connection, only=list(IDENTITIES))
    for table in metadata.tables.values():
        for column in table.c:
            # MariaDB reflects its JSON alias as LONGTEXT. Retain the JSON
            # encoder/decoder and distinguish SQL NULL from the empty list.
            if isinstance(column.type, sa.JSON) or (
                table.name in JSON_SERVICE_TABLES and column.name == "servicios_codigos"
            ):
                column.type = sa.JSON(none_as_null=True)
    return metadata


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


def export_snapshot(
    connection: Connection, destination: Path, *, selection: str = "active-operational"
) -> dict[str, int]:
    """Read one consistent source transaction; never alter the local database."""
    if selection not in {"active-operational", "all-master-data"}:
        raise ValueError("Selección de datos del snapshot desconocida.")
    revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    if revision not in SOURCE_REVISIONS:
        raise ValueError("Actualice la base a la revisión compatible antes de exportar.")
    metadata = _metadata(connection)
    patients = metadata.tables["pacientes"]
    selected_patients = sa.select(patients.c.id).where(
        patients.c.ubigeo_residencia_codigo.like("04%")
    )
    tables = {}
    for name in IDENTITIES:
        table = metadata.tables[name]
        statement = sa.select(table).order_by(*table.primary_key.columns)
        if name == "pacientes":
            statement = statement.where(table.c.ubigeo_residencia_codigo.like("04%"))
        elif name in PATIENT_CHILDREN:
            statement = statement.where(table.c.paciente_id.in_(selected_patients))
        rows = [dict(row) for row in connection.execute(statement).mappings()]
        if name == "usuarios":
            for row in rows:
                for field in USER_TRANSIENT_FIELDS:
                    row.pop(field, None)
        tables[name] = rows
    if selection == "active-operational":
        tables = _operational_data(tables)
    snapshot = {
        "format": FORMAT_VERSION,
        "source_revision": revision,
        "created_at": datetime.now(UTC).isoformat(),
        "patient_department": "04",
        "selection": selection,
        "tables": tables,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects the previous, potentially irreplaceable export.
    with destination.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed:
            compressed.write(json.dumps(snapshot, ensure_ascii=False, default=_json_value).encode())
    return {name: len(rows) for name, rows in tables.items()}


def _typed(table: sa.Table, row: dict) -> dict:
    if set(row) - set(table.c.keys()):
        raise ValueError(f"Columnas incompatibles en el snapshot de {table.name}.")
    values = dict(row)
    for column in table.c:
        value = values.get(column.name)
        if value is None:
            continue
        if isinstance(column.type, sa.DateTime) and isinstance(value, str):
            values[column.name] = datetime.fromisoformat(value)
        elif isinstance(column.type, sa.Date) and isinstance(value, str):
            values[column.name] = date.fromisoformat(value)
        elif isinstance(column.type, sa.Numeric):
            values[column.name] = Decimal(str(value))
    return values


def _key(value: Any) -> Any:
    # Match the application's MySQL case/accent-insensitive natural keys.
    if isinstance(value, str):
        return "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold().rstrip())
            if not unicodedata.combining(c)
        )
    return value


def _identity(row: dict, fields: tuple[str, ...]) -> tuple | None:
    values = tuple(row.get(field) for field in fields)
    return None if any(value is None for value in values) else tuple(map(_key, values))


def _primary(table: sa.Table, row: dict) -> tuple:
    return tuple(row[column.name] for column in table.primary_key)


def _baseline_only(connection: Connection) -> bool:
    """Recognize only an unused Alembic installation, before its first import.

    Revision 0025 already created legacy users. On a brand-new database their
    hashes must be replaced with the exported current hashes, not the old DNI
    defaults. Any subsequent import preserves destination passwords and data.
    """
    for table in ("pacientes", "atenciones"):
        if connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}")):
            return False
    users = set(connection.execute(sa.text("SELECT id FROM usuarios")).scalars())
    imported = set()
    for record_id, payload in connection.execute(
        sa.text(
            "SELECT registro_id, datos_nuevos FROM auditoria "
            "WHERE tabla_nombre='usuarios' AND accion='BOOTSTRAP'"
        )
    ):
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict) and payload.get("origen") == "operarios_sis":
            imported.add(record_id)
    if users != imported:
        return False
    return not connection.scalar(
        sa.text("SELECT COUNT(*) FROM auditoria WHERE accion <> 'BOOTSTRAP'")
    )


def _snapshot_audit(connection: Connection) -> sa.Table:
    return sa.Table(
        "auditoria", sa.MetaData(),
        sa.Column("datos_nuevos", sa.JSON(none_as_null=True)),
        autoload_with=connection,
    )


def _record_import(connection: Connection, source: Path, revision: str, inserted: dict,
                   *, baseline: bool) -> None:
    connection.execute(_snapshot_audit(connection).insert().values(
        tabla_nombre="instalacion_docker",
        registro_id=None,
        accion="IMPORTAR_DOCKER",
        datos_nuevos={
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_revision": revision,
            "inserted": inserted,
            "baseline_synchronized": baseline,
        },
    ))


def _already_imported(connection: Connection, digest: str) -> bool:
    audit = _snapshot_audit(connection)
    query = sa.select(audit.c.datos_nuevos).where(
        audit.c.tabla_nombre == "instalacion_docker", audit.c.accion == "IMPORTAR_DOCKER"
    )
    return any(isinstance(payload, dict) and payload.get("sha256") == digest
               for payload in connection.execute(query).scalars())


def restore_snapshot(connection: Connection, source: Path) -> dict[str, int]:
    """Merge master data in the caller's transaction, with remapped identities."""
    with gzip.open(source, "rt", encoding="utf-8") as stream:
        snapshot = json.load(stream)
    if (
        snapshot.get("format") != FORMAT_VERSION
        or snapshot.get("source_revision") not in SOURCE_REVISIONS
        or snapshot.get("patient_department") != "04"
        or set(snapshot.get("tables", {})) != set(IDENTITIES)
    ):
        raise ValueError("Formato o revisión del snapshot Docker incompatible.")
    metadata = _metadata(connection)
    tables = snapshot["tables"]
    # Decode and check all input columns before any write.
    data = {
        name: [_typed(metadata.tables[name], row) for row in tables[name]] for name in IDENTITIES
    }
    if any(
        not str(row.get("ubigeo_residencia_codigo", "")).startswith("04")
        for row in data["pacientes"]
    ):
        raise ValueError("El snapshot contiene pacientes fuera de Arequipa.")
    refresh_baseline = _baseline_only(connection)
    mappings: dict[str, dict[tuple, tuple]] = {name: {} for name in IDENTITIES}
    inserted = dict.fromkeys(IDENTITIES, 0)

    def import_batch(name: str, rows: list[dict]) -> None:
        table = metadata.tables[name]
        fields = IDENTITIES[name]

        def index_destination() -> list[dict]:
            indices: list[dict] = [{} for _ in fields]
            for row in connection.execute(sa.select(table)).mappings():
                for index, columns in zip(indices, fields, strict=True):
                    key = _identity(row, columns)
                    if key is not None:
                        primary = _primary(table, row)
                        if key in index and index[key] != primary:
                            raise ValueError(
                                f"Identidad ambigua en {name}; no se mezclaron registros."
                            )
                        index[key] = primary
            return indices

        indices = index_destination()

        def locate(row: dict) -> tuple | None:
            matches = {
                index[key]
                for index, columns in zip(indices, fields, strict=True)
                if (key := _identity(row, columns)) is not None and key in index
            }
            if len(matches) > 1:
                raise ValueError(f"Identidades incompatibles en {name}; no se mezclaron registros.")
            return next(iter(matches), None)

        prepared = []
        pending = []
        seen: list[set] = [set() for _ in fields]
        for row in rows:
            values = dict(row)
            for fk in table.foreign_keys:
                value = values.get(fk.parent.name)
                if value is not None:
                    parent = mappings[fk.column.table.name]
                    if (value,) not in parent:
                        raise ValueError(f"Falta una referencia de {name}.{fk.parent.name}.")
                    values[fk.parent.name] = parent[(value,)][0]
            if not any(_identity(values, columns) is not None for columns in fields):
                raise ValueError(f"Registro sin identidad portable en {name}.")
            existing = locate(values)
            prepared.append((row, values))
            if existing is None:
                for keys, columns in zip(seen, fields, strict=True):
                    key = _identity(values, columns)
                    if key is not None:
                        if key in keys:
                            raise ValueError(f"Identidad repetida en el snapshot de {name}.")
                        keys.add(key)
                pending.append(
                    {
                        key: value
                        for key, value in values.items()
                        if table.c[key] is not table.autoincrement_column
                    }
                )
            elif refresh_baseline:
                changed = {
                    key: value for key, value in values.items() if not table.c[key].primary_key
                }
                if changed:
                    connection.execute(
                        sa.update(table)
                        .where(
                            sa.and_(
                                *(
                                    column == value
                                    for column, value in zip(
                                        table.primary_key, existing, strict=True
                                    )
                                )
                            )
                        )
                        .values(**changed)
                    )
        for start in range(0, len(pending), 500):
            connection.execute(sa.insert(table), pending[start : start + 500])
        inserted[name] += len(pending)
        indices = index_destination()
        for original, values in prepared:
            destination = locate(values)
            if destination is None:
                raise ValueError(f"No se pudo resolver la identidad importada en {name}.")
            mappings[name][_primary(table, original)] = destination

    for name in IDENTITIES:
        remaining = list(data[name])
        if name != "consultorios":
            import_batch(name, remaining)
            continue
        # Resolve physical office trees independently of source numeric id order.
        while remaining:
            ready = [
                row
                for row in remaining
                if row.get("consultorio_padre_id") is None
                or (row["consultorio_padre_id"],) in mappings[name]
            ]
            if not ready:
                raise ValueError("Jerarquía de consultorios incompleta o circular.")
            import_batch(name, ready)
            done = {row["id"] for row in ready}
            remaining = [row for row in remaining if row["id"] not in done]
    if any(inserted.values()) or refresh_baseline:
        _record_import(
            connection, source, snapshot["source_revision"], inserted, baseline=refresh_baseline
        )
    return inserted


def ensure_from_environment(connection: Connection) -> dict[str, int] | None:
    """Import each configured snapshot once, also after revision 0042 was applied.

    The historical migration remains compatible. Later restarts consult the
    successful import marker instead of resurrecting deliberately removed rows
    or resetting credentials. This is installation work, separate from DDL.
    """
    filename = os.environ.get("IPRESS_BOOTSTRAP_FILE", "").strip()
    if not filename:
        return None
    source = Path(filename)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if _already_imported(connection, digest):
        return None
    counts = restore_snapshot(connection, source)
    if not _already_imported(connection, digest):
        # A valid snapshot may already be present without an import marker.
        # Record that successful reconciliation to avoid rescanning every boot.
        with gzip.open(source, "rt", encoding="utf-8") as stream:
            revision = json.load(stream)["source_revision"]
        _record_import(connection, source, revision, counts, baseline=False)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument(
        "--selection", choices=["active-operational", "all-master-data"],
        default="active-operational",
        help="all-master-data conserva también cuentas inactivas y registros de pruebas.",
    )
    actions.add_parser("restore").add_argument("--input", type=Path, required=True)
    actions.add_parser("ensure", help="Carga la copia configurada una sola vez por contenido.")
    args = parser.parse_args()
    from app.core.config import get_settings

    engine = sa.create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            if args.action == "export":
                counts = export_snapshot(connection, args.output, selection=args.selection)
            elif args.action == "restore":
                counts = restore_snapshot(connection, args.input)
            else:
                counts = ensure_from_environment(connection)
        print(json.dumps({"action": args.action, "counts": counts}, ensure_ascii=False))
    finally:
        engine.dispose()


def migrate_from_environment(connection: Connection) -> None:
    filename = os.environ.get("IPRESS_BOOTSTRAP_FILE", "").strip()
    if filename:
        counts = restore_snapshot(connection, Path(filename))
        print("Docker bootstrap: " + json.dumps(counts))


if __name__ == "__main__":
    main()
