"""Patient-only ETLSIS import. Dry-run by default; local development only."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from functools import cache
from pathlib import Path

from sqlalchemy import func, insert, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.exceptions import DomainError
from app.models.audit import AuditLog
from app.models.catalog import DocumentType, FamilyHistoryPrefix, Insurance, Sex
from app.models.legacy import LegacyImport, LegacyRecord
from app.models.organization import Establishment, Localidad, Ubigeo
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.audit import AuditService
from app.services.legacy_patients import (
    VERSION,
    Catalogs,
    build_plan,
    canonical,
    digest,
    key,
    read_source,
    summarize,
    unique_index,
)
from app.services.patient_data import PatientDataRules
from app.services.patient_responsible import PatientResponsibleRules


class CachedCatalogRepository:
    """Cache catalog reads within the import's single transaction/snapshot."""

    def __init__(self, session: Session):
        self.repository = PatientRepository(session)
        self.methods = {}

    def __getattr__(self, name):
        if not name.startswith("get_"):
            raise AttributeError(name)
        if name not in self.methods:
            self.methods[name] = cache(getattr(self.repository, name))
        return self.methods[name]


def load_catalogs(session: Session, tables: dict) -> Catalogs:
    def rows(model, *columns, active=True):
        query = select(*(getattr(model, c) for c in columns))
        if active:
            query = query.where(model.activo.is_(True))
        return [dict(r) for r in session.execute(query).mappings()]

    ubigeos = {r["codigo"]: r for r in rows(Ubigeo, "codigo", "distrito", active=False)}
    district_rows = []
    for row in tables["Provincia"]:
        parts = [row.get(f) for f in ("IdDpto", "IdProvincia", "IdDistrito")]
        if not all(
            isinstance(v, str) and len(v) == 2 and v.isascii() and v.isdigit() for v in parts
        ):
            continue
        code = "".join(parts)
        destination = ubigeos.get(code)
        if (
            not destination
            or str(row.get("Ubigeo", "")).zfill(6) != code
            or not code.startswith("0401")
        ):
            continue
        if key(row.get("Distrito")) not in {
            key(destination["distrito"]),
            "CERCADO" if code == "040101" else "",
        }:
            continue
        district_rows.append({"nombre": row["Distrito"], "codigo": code})
    districts = {k[0]: v for k, v in unique_index(district_rows, ("nombre",), "codigo").items()}

    sites = rows(Establishment, "id", "codigo_renaes")
    renaes = unique_index(sites, ("codigo_renaes",), "id")
    source_sites = unique_index(tables["EESS"], ("EESS",), "Renaes")
    establishments = {
        name[0]: renaes[(key(code),)]
        for name, code in source_sites.items()
        if (key(code),) in renaes and key(code).isascii() and key(code).isdigit()
    }
    insurances = {
        key(r["nombre"]): (r["id"], r["regimen"] == "SIS" or r["codigo"] == "SIS")
        for r in rows(Insurance, "id", "codigo", "nombre", "regimen")
    }
    locality_rows = rows(Localidad, "id", "ubigeo_codigo", "nombre")
    locality_index = unique_index(locality_rows, ("ubigeo_codigo", "nombre"), "id")
    locality_by_id = {r["id"]: r for r in locality_rows}
    localities = {k: (v, locality_by_id[v]["nombre"]) for k, v in locality_index.items()}
    return Catalogs(
        districts,
        establishments,
        insurances,
        localities,
        {r["codigo"] for r in rows(FamilyHistoryPrefix, "codigo")},
        {r["codigo"] for r in rows(Sex, "codigo")},
        {r["codigo"] for r in rows(DocumentType, "codigo")},
    )


def validate_with_current_rules(session: Session, decisions: list, as_of: date) -> None:
    rules = PatientDataRules(CachedCatalogRepository(session), lambda: as_of)
    responsible = PatientResponsibleRules(rules, lambda: as_of)
    for decision in decisions:
        command = decision.payload
        if command is None:
            continue
        values = command.model_dump(exclude={"responsables", "riesgos"})
        try:
            rules.validate_birth_and_registration_dates(
                command.fecha_nacimiento, command.fecha_inscripcion
            )
            rules.validate_document_number(command.tipo_documento_codigo, command.numero_documento)
            rules.validate_patient_catalogs(
                document_type_code=command.tipo_documento_codigo,
                sex_code=command.sexo_codigo,
                insurance_id=command.seguro_id,
                ubigeo_code=command.ubigeo_residencia_codigo,
                establishment_id=command.establecimiento_registro_id,
            )
            rules.validate_family_history(command.historia_familiar)
            rules.validate_insurance_affiliation(values)
            rules.validate_sis_and_ethnicity(values)
            rules.normalize_patient_locality(values)
            rules.validate_patient_residence(
                ubigeo_code=command.ubigeo_residencia_codigo, locality=values["localidad"]
            )
            responsible.validate_new_responsibles(
                command.responsables,
                birth_date=command.fecha_nacimiento,
                registration_date=command.fecha_inscripcion,
            )
        except DomainError as exc:
            decision.state = "PENDIENTE"
            decision.payload = None
            decision.issues.append("regla_actual:" + exc.code)


def persist(session: Session, batch: LegacyImport, selected: list) -> int:
    """No commits: the caller atomically owns patients, source archive and audit."""
    pending = [d for d in selected if d.state == "ACEPTADO"]
    for start in range(0, len(pending), 500):
        chunk = pending[start : start + 500]
        payloads = [d.payload.model_dump(exclude={"responsables", "riesgos"}) for d in chunk]
        session.execute(insert(Patient.__table__), payloads)
        ids = dict(
            session.execute(
                select(Patient.codclie_legacy, Patient.id).where(
                    Patient.codclie_legacy.in_([v["codclie_legacy"] for v in payloads])
                )
            ).all()
        )
        records = []
        audits = []
        for decision in chunk:
            patient_id = ids[decision.payload.codclie_legacy]
            decision.patient_id = patient_id
            records.append(
                dict(
                    importacion_id=batch.id,
                    tabla_origen="Pacientes",
                    fila_origen=decision.row_number,
                    huella_fila=digest(decision.source),
                    payload_json=canonical(decision.source),
                    incidencias=[{"codigo": i} for i in decision.issues],
                    estado="IMPORTADO",
                    destino_tabla="pacientes",
                    destino_id=str(patient_id),
                )
            )
            audits.append(
                dict(
                    usuario_id=None,
                    tabla_nombre="pacientes",
                    registro_id=patient_id,
                    accion="IMPORTAR_ETLSIS",
                    datos_anteriores=None,
                    datos_nuevos={"importacion_id": batch.id, "fila_origen": decision.row_number},
                )
            )
        session.execute(insert(LegacyRecord.__table__), records)
        session.execute(insert(AuditLog.__table__), audits)
    return len(pending)


def run(*, source: Path, snapshot: Path, as_of: date, apply=False, limit=None) -> dict:
    settings = get_settings()
    if settings.environment != "development" or engine.url.host not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("Este experimento solo admite MySQL local en development.")
    today = datetime.now(timezone(timedelta(hours=-5))).date()
    if as_of > today or (limit is not None and limit <= 0):
        raise ValueError("Fecha futura o límite inválido.")
    manifest, tables = read_source(snapshot, source)
    source_hash = manifest["source_sha256"]
    lock_name = "etl_patients_" + digest(str(engine.url.database))[:40]
    with engine.connect() as connection:
        locked = False
        try:
            if apply:
                locked = (
                    connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": lock_name}) == 1
                )
                connection.commit()
                if not locked:
                    raise ValueError("Otra importación de pacientes está en curso.")
            with connection.begin(), Session(bind=connection) as session:
                if not apply:
                    session.execute(text("SET TRANSACTION READ ONLY"))
                batch = session.scalar(
                    select(LegacyImport).where(LegacyImport.huella_fuente == source_hash)
                )
                if batch and batch.version_etl != VERSION:
                    raise ValueError("La fuente ya tiene otro importador; requiere conciliación.")
                archived = (
                    {}
                    if batch is None
                    else {
                        r["fila_origen"]: dict(r)
                        for r in session.execute(
                            select(
                                LegacyRecord.fila_origen,
                                LegacyRecord.huella_fila,
                                LegacyRecord.destino_tabla,
                                LegacyRecord.destino_id,
                            ).where(
                                LegacyRecord.importacion_id == batch.id,
                                LegacyRecord.tabla_origen == "Pacientes",
                            )
                        ).mappings()
                    }
                )
                existing = [
                    dict(r)
                    for r in session.execute(
                        select(
                            Patient.id,
                            Patient.codclie_legacy,
                            Patient.tipo_documento_codigo,
                            Patient.numero_documento,
                        )
                    ).mappings()
                ]
                catalogs = load_catalogs(session, tables)
                decisions = build_plan(tables, catalogs, existing, archived, as_of=as_of)
                validate_with_current_rules(session, decisions, as_of)
                selected = [d for d in decisions if d.state in {"ACEPTADO", "YA_IMPORTADO"}]
                if limit:
                    selected = selected[:limit]
                summary = {
                    **summarize(decisions),
                    "fecha_referencia": as_of.isoformat(),
                    "provincia_ubigeo": "0401",
                    "distritos_resueltos": len(catalogs.districts),
                    "huella_fuente": source_hash,
                    "modo": "apply" if apply else "dry-run",
                    "seleccionados": len(selected),
                    "por_insertar": sum(d.state == "ACEPTADO" for d in selected),
                    "ya_importados_seleccionados": sum(d.state == "YA_IMPORTADO" for d in selected),
                    "pacientes_antes": len(existing),
                    "atenciones_antes": session.scalar(text("SELECT COUNT(*) FROM atenciones")),
                }
                if apply:
                    if batch is None:
                        batch = LegacyImport(
                            huella_fuente=source_hash,
                            version_etl=VERSION,
                            manifiesto={
                                "source_sha256": source_hash,
                                "scope": "Pacientes/0401",
                                "reader": manifest["reader"],
                                "tables": manifest["tables"],
                            },
                            estado="COMPLETADO",
                        )
                        session.add(batch)
                        session.flush()
                    created = persist(session, batch, selected)
                    summary.update(importacion_id=batch.id, insertados=created)
                    summary["pacientes_despues"] = session.scalar(
                        select(func.count()).select_from(Patient)
                    )
                    summary["atenciones_despues"] = session.scalar(
                        text("SELECT COUNT(*) FROM atenciones")
                    )
                    if (
                        summary["pacientes_despues"] != len(existing) + created
                        or summary["atenciones_despues"] != summary["atenciones_antes"]
                    ):
                        raise ValueError("La conciliación final no coincide; se revierte el lote.")
                    if created or batch.resumen is None:
                        batch.resumen = summary
                        AuditService(session).record(
                            actor_id=None,
                            action="IMPORTAR_ETLSIS",
                            table_name="importaciones_legado",
                            record_id=batch.id,
                            before=None,
                            after=summary,
                        )
                    session.flush()
                else:
                    # An explicit READ ONLY transaction makes dry-run writes fail at MySQL.
                    summary["insertados"] = 0
            return summary
        finally:
            if locked:
                connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("Data_base.mdb"))
    parser.add_argument("--snapshot", type=Path, default=Path("etlSis/private/ace-source"))
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=datetime.now(timezone(timedelta(hours=-5))).date(),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = run(
            source=args.source,
            snapshot=args.snapshot,
            as_of=args.as_of,
            apply=args.apply,
            limit=args.limit,
        )
    except Exception as exc:
        # SQL exceptions can include bound patient data or credentials. Do not log them.
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "mensaje": "Importación detenida; la transacción no se confirmó.",
                }
            )
        )
        return 1
    rendered = json.dumps(result, ensure_ascii=True, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
