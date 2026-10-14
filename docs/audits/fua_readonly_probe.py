"""Inspect aggregate completeness in the configured DB; never print patient data."""
import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings
from app.models.base import Base
import app.models  # Register ORM metadata; no DDL.


report = {"scope": "configured local DB; read-only aggregate queries", "queries": {}}
engine = create_engine(get_settings().sqlalchemy_database_url, echo=False)
queries = {
    "patients": """SELECT COUNT(*) AS total,
        COALESCE(SUM(p.primer_nombre IS NULL OR TRIM(p.primer_nombre)=''),0) AS missing_first_name,
        COALESCE(SUM(p.apellido_paterno IS NULL AND p.apellido_materno IS NULL),0) AS missing_both_surnames,
        COALESCE(SUM(p.sexo_codigo IS NULL),0) AS missing_sex,
        COALESCE(SUM(p.historia_clinica IS NULL OR TRIM(p.historia_clinica)=''),0) AS missing_history,
        COALESCE(SUM((s.regimen='SIS' OR s.codigo='SIS') AND
          (p.sis_tipo IS NULL OR p.sis_numero IS NULL)),0) AS sis_missing_type_or_number,
        COALESCE(SUM((s.regimen='SIS' OR s.codigo='SIS') AND p.sis_diresa IS NULL),0) AS sis_missing_diresa,
        COALESCE(SUM((s.regimen='SIS' OR s.codigo='SIS')),0) AS sis_patients,
        COALESCE(SUM(p.tipo_documento_codigo='DNI' AND p.numero_documento NOT REGEXP '^[0-9]{8}$'),0) AS malformed_dni
        FROM pacientes p LEFT JOIN seguros s ON s.id=p.seguro_id""",
    "attentions": """SELECT COUNT(*) AS total,
        COALESCE(SUM(a.fua_impresion IS NULL),0) AS missing_fua_snapshot,
        COALESCE(SUM(NOT EXISTS(SELECT 1 FROM atencion_prestaciones p WHERE p.atencion_id=a.id)),0) AS without_services,
        COALESCE(SUM(NOT EXISTS(SELECT 1 FROM atencion_diagnosticos d WHERE d.atencion_id=a.id)),0) AS without_diagnoses,
        COALESCE(SUM(a.peso_kg IS NULL OR a.talla_cm IS NULL),0) AS missing_weight_or_height,
        COALESCE(SUM(a.presion_sistolica IS NULL OR a.presion_diastolica IS NULL),0) AS missing_complete_bp,
        COALESCE(SUM(a.grupo_atencion_codigo IN ('GESTANTES','PUERPERAS') AND a.perimetro_abdominal_cm IS NULL),0) AS maternal_missing_waist,
        COALESCE(SUM(a.numero_referencia_ingreso IS NOT NULL AND
           COALESCE(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.tipo_atencion')),'') <> 'REFERENCIA'),0) AS incoming_reference_not_marked_in_fua
        FROM atenciones a WHERE a.estado='ATENDIDO'""",
    "snapshot_records": """SELECT
        COALESCE(JSON_UNQUOTE(JSON_EXTRACT(fua_impresion,'$.version')),'none') AS snapshot_version,
        COUNT(*) AS total
        FROM atenciones GROUP BY snapshot_version""",
    "saved_clinical_fields_match_snapshot": """SELECT COUNT(*) AS total,
        COALESCE(SUM(NOT (a.peso_kg <=> CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.peso_kg')),'null') AS DECIMAL(10,3)))),0) AS weight_mismatch,
        COALESCE(SUM(NOT (a.talla_cm <=> CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.talla_cm')),'null') AS DECIMAL(10,3)))),0) AS height_mismatch,
        COALESCE(SUM(NOT (a.presion_sistolica <=> CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.presion_sistolica')),'null') AS UNSIGNED))),0) AS systolic_mismatch,
        COALESCE(SUM(NOT (a.presion_diastolica <=> CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.presion_diastolica')),'null') AS UNSIGNED))),0) AS diastolic_mismatch,
        COALESCE(SUM(NOT (a.imc <=> CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.imc')),'null') AS DECIMAL(10,3)))),0) AS bmi_mismatch,
        COALESCE(SUM(NOT (a.perimetro_abdominal_cm <=> CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.perimetro_abdominal_cm')),'null') AS DECIMAL(10,3)))),0) AS waist_mismatch,
        COALESCE(SUM(NOT (a.historia_clinica_snapshot <=> NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.historia_clinica')),'null'))),0) AS history_mismatch,
        COALESCE(SUM(NOT (a.modalidad_atencion_codigo <=> NULLIF(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.tipo_atencion')),'null'))),0) AS mode_mismatch,
        COALESCE(SUM(a.temperatura_c IS NOT NULL),0) AS saved_temperature,
        COALESCE(SUM(JSON_EXTRACT(a.fua_impresion,'$.temperatura_c') IS NOT NULL),0) AS temperature_in_fua
        FROM atenciones a WHERE a.fua_impresion IS NOT NULL""",
    "fua_documents": """SELECT COUNT(*) AS total,
        COALESCE(SUM(numero_fua IS NOT NULL AND numero_fua NOT REGEXP '^[0-9]{8}-[0-9]{2}-[0-9]{8}$'),0) AS non_current_number_structure,
        COALESCE(SUM(codigo_renipress IS NULL OR lote_fua IS NULL OR correlativo_fua IS NULL),0) AS missing_current_components
        FROM fua""",
    "rmcv_catalog": """SELECT codigo, activo FROM prestaciones
        WHERE codigo IN ('301','302','303','304','305','306') ORDER BY codigo""",
    "diagnosis_types": """SELECT tipo_diagnostico, COUNT(*) AS total
        FROM atencion_diagnosticos GROUP BY tipo_diagnostico""",
    "establishments": """SELECT COUNT(*) AS total,
        COALESCE(SUM(codigo_renaes IS NULL OR codigo_renaes NOT REGEXP '^[0-9]{1,8}$'),0) AS unusable_renipress,
        COALESCE(SUM(fua_renipress_preimpreso=1),0) AS uses_preprinted_code,
        COALESCE(SUM(fua_personal_atiende='IPRESS' AND fua_lugar_atencion='INTRAMURAL'),0) AS defaults_ipress_intramural
        FROM establecimientos WHERE activo=1""",
    "professional_identity": """SELECT COUNT(*) AS total,
        COALESCE(SUM(numero_documento IS NULL OR TRIM(numero_documento)=''),0) AS missing_document,
        COALESCE(SUM(colegiatura IS NULL OR TRIM(colegiatura)=''),0) AS missing_registration
        FROM profesionales WHERE activo=1""",
    "responsible_in_saved_snapshot": """SELECT COUNT(*) AS total,
        COALESCE(SUM(JSON_UNQUOTE(JSON_EXTRACT(fua_impresion,'$.profesional_documento')) IN ('null','')
          OR JSON_EXTRACT(fua_impresion,'$.profesional_documento') IS NULL),0) AS missing_document,
        COALESCE(SUM(JSON_UNQUOTE(JSON_EXTRACT(fua_impresion,'$.profesional_colegiatura')) IN ('null','')
          OR JSON_EXTRACT(fua_impresion,'$.profesional_colegiatura') IS NULL),0) AS missing_registration
        FROM atenciones WHERE fua_impresion IS NOT NULL""",
    "maternal_dates": """SELECT COUNT(*) AS total,
        COALESCE(SUM(grupo_atencion_codigo='GESTANTES'),0) AS pregnant,
        COALESCE(SUM(grupo_atencion_codigo='PUERPERAS'),0) AS puerperal,
        COALESCE(SUM(fecha_parto > DATE(fecha_atencion)),0) AS delivery_after_attention,
        COALESCE(SUM(grupo_atencion_codigo='GESTANTES' AND fecha_probable_parto IS NULL),0) AS pregnant_missing_due_date,
        COALESCE(SUM(grupo_atencion_codigo='PUERPERAS' AND fecha_parto IS NULL),0) AS puerperal_missing_delivery_date
        FROM atenciones WHERE estado='ATENDIDO'""",
    "used_professional_profiles": """SELECT COALESCE(pf.nombre,'SIN_CATEGORIA') AS profession,
        COUNT(*) AS attention_count,
        COALESCE(SUM(JSON_UNQUOTE(JSON_EXTRACT(a.fua_impresion,'$.profesional_colegiatura')) IN ('null','')
          OR JSON_EXTRACT(a.fua_impresion,'$.profesional_colegiatura') IS NULL),0) AS missing_registration_in_snapshot
        FROM atenciones a JOIN profesionales p ON p.id=a.profesional_id
        LEFT JOIN profesiones pf ON pf.id=p.profesion_id
        WHERE a.estado='ATENDIDO' GROUP BY pf.nombre""",
}

with engine.connect() as conn:
    conn.execute(text("SET TRANSACTION READ ONLY"))
    conn.execute(text("START TRANSACTION READ ONLY"))
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    report["schema"] = {
        "table_count": len(tables),
        "missing_orm_tables": sorted(set(Base.metadata.tables) - set(tables)),
        "missing_orm_columns": {},
    }
    for name, table in Base.metadata.tables.items():
        if name not in tables:
            continue
        missing = sorted(set(table.columns.keys()) - {c["name"] for c in inspector.get_columns(name)})
        if missing:
            report["schema"]["missing_orm_columns"][name] = missing
    report["schema"]["alembic_revisions"] = list(conn.execute(text("SELECT version_num FROM alembic_version")).scalars())
    for key, query in queries.items():
        report["queries"][key] = [dict(row) for row in conn.execute(text(query)).mappings()]
    conn.rollback()
engine.dispose()
path = Path("tmp/pdfs/fua_readonly_audit.json")
path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
