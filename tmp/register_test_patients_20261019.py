"""Create three explicitly fictional records through the running local API."""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.database import SessionLocal

OUTPUT = Path(r"C:\Users\forth\.codex\visualizations\2026\10\19\01a154c6-03eb-7e82-8333-9b35326c4db7\pacientes-prueba-20261019")
OUTPUT.mkdir(parents=True, exist_ok=True)
JOURNAL = OUTPUT / "registro.json"
report = json.loads(JOURNAL.read_text(encoding="utf-8")) if JOURNAL.exists() else {
    "descripcion": "Registros ficticios de prueba, creados en la aplicación local mediante API.",
    "base_url": "http://localhost:8000", "casos": {},
}


def save():
    JOURNAL.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def api(client, method, path, payload=None, expected=200):
    response = client.request(method, path, json=payload)
    if response.status_code != expected:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text[:2000]}")
    return response.json()


with httpx.Client(base_url="http://localhost:8000/api/v1", timeout=40, trust_env=False) as client:
    login = api(client, "POST", "/auth/login", {"nombre_usuario": "medico.demo", "password": "18594027"})
    client.headers["Authorization"] = "Bearer " + login["access_token"]
    report["usuario_creador_id"] = login["usuario_id"]
    for mode, suffix, birth, sex, weight, height in [
        ("AMBULATORIA", "AMB", "1990-04-12", "F", 65, 168),
        ("REFERENCIA", "REF", "1992-06-15", "M", 62, 160),
        ("EMERGENCIA", "EME", "1988-08-20", "M", 70, 172),
    ]:
        case = report["casos"].setdefault(mode, {})
        document = f"PRB191026-{suffix}"
        history = f"PRB191026{suffix[0]}"
        marker = f"PRUEBA FICTICIA 20261019 {mode} - REGISTRO NO REAL"
        patient_payload = {
            "tipo_documento_codigo": "OTRO", "numero_documento": document,
            "fecha_nacimiento": birth, "apellido_paterno": "PRUEBA",
            "apellido_materno": "FICTICIA", "primer_nombre": mode,
            "otros_nombres": "NO REAL", "sexo_codigo": sex,
            "historia_clinica": history, "establecimiento_registro_id": 1,
            "seguro_id": 1, "direccion": marker,
        }
        # Recover only this exact fictional identity after an interrupted run.
        with SessionLocal() as session:
            found = session.execute(text(
                "SELECT id, apellido_paterno, apellido_materno, primer_nombre, historia_clinica "
                "FROM pacientes WHERE tipo_documento_codigo=:kind AND numero_documento=:doc"
            ), {"kind": "OTRO", "doc": document}).mappings().all()
        if found:
            assert len(found) == 1
            existing = found[0]
            for field in ("apellido_paterno", "apellido_materno", "primer_nombre", "historia_clinica"):
                assert existing[field] == patient_payload[field], "Identity collision; no existing row modified"
            patient_id = existing["id"]
        else:
            created = api(client, "POST", "/patients", patient_payload, expected=201)
            patient_id = created["id"]
        case.update(paciente_id=patient_id, documento=document, historia_clinica=history)
        save()
        with SessionLocal() as session:
            matches = session.execute(text(
                "SELECT id FROM atenciones WHERE paciente_id=:patient AND observaciones=:marker"
            ), {"patient": patient_id, "marker": marker}).scalars().all()
        assert len(matches) <= 1
        if matches:
            attention_id = matches[0]
        else:
            referral = mode == "REFERENCIA"
            fua = {"tipo_atencion": mode}
            if referral:
                fua.update(referencia_renipress="00001234", referencia_nombre="IPRESS FICTICIA PRUEBA",
                           referencia_hoja="TEST-191026-REF-01")
            payload = {
                "paciente_id": patient_id, "establecimiento_id": 1,
                "modalidad_atencion_codigo": mode,
                "fecha_atencion": datetime.now(ZoneInfo("America/Lima")).replace(tzinfo=None).isoformat(timespec="seconds"),
                "consultorio_id": None if referral else 1,
                "profesional_id": None if referral else 10,
                "especialidad_codigo": None if referral else "ESP_MEDICINA:001",
                "grupo_atencion_codigo": "NINOS_ADOLESCENTES_ADULTOS_MAYORES",
                "admision": marker, "observaciones": marker,
                "peso_kg": weight, "talla_cm": height,
                "presion_sistolica": 120, "presion_diastolica": 80,
                "temperatura_c": 36.5, "perimetro_abdominal_cm": 80,
                "fua_datos": fua,
            }
            attention_id = api(client, "POST", "/atenciones", payload, expected=201)["id"]
        case["atencion_id"] = attention_id
        save()
        patient = api(client, "GET", f"/patients/{patient_id}")
        attention = api(client, "GET", f"/atenciones/{attention_id}")
        assert patient["numero_documento"] == document and patient["historia_clinica"] == history
        assert attention["paciente_id"] == patient_id and attention["modalidad_atencion_codigo"] == mode
        snapshot = attention["fua_impresion"]
        assert snapshot["tipo_atencion"] == mode and snapshot["historia_clinica"] == history
        if mode == "REFERENCIA":
            assert all(attention[k] is None for k in ("consultorio_id", "profesional_id", "especialidad_codigo"))
            assert snapshot["referencia_renipress"] == "00001234"
            assert snapshot["referencia_nombre"] == "IPRESS FICTICIA PRUEBA"
            assert snapshot["referencia_hoja"] == "TEST-191026-REF-01"
            assert snapshot["profesional_nombre"] is None
        else:
            assert attention["consultorio_id"] == 1 and attention["profesional_id"] == 10
            assert attention["especialidad_codigo"] == "ESP_MEDICINA:001"
            assert all(snapshot[k] is None for k in ("referencia_renipress", "referencia_nombre", "referencia_hoja"))
        with SessionLocal() as session:
            stored_patient = dict(session.execute(text(
                "SELECT id, codclie_legacy, historia_clinica, tipo_documento_codigo, numero_documento, "
                "establecimiento_registro_id, profesional_registro_id, seguro_id, condicion "
                "FROM pacientes WHERE id=:id"
            ), {"id": patient_id}).mappings().one())
            stored_attention = dict(session.execute(text(
                "SELECT id, codigo_legacy, paciente_id, establecimiento_id, consultorio_id, profesional_id, "
                "especialidad_codigo, modalidad_atencion_codigo, grupo_atencion_codigo, grupo_etario_codigo, "
                "created_by_usuario_id, estado, fua_impresion FROM atenciones WHERE id=:id"
            ), {"id": attention_id}).mappings().one())
            raw_fua = stored_attention.pop("fua_impresion")
            stored_fua = json.loads(raw_fua) if isinstance(raw_fua, str) else raw_fua
            # Decimal representation can differ between the JSON and API; compare stable identity/reference fields.
            for key in ("tipo_atencion", "historia_clinica", "referencia_renipress", "referencia_nombre", "referencia_hoja"):
                assert stored_fua[key] == snapshot[key]
            for key in ("consultorio_id", "profesional_id", "especialidad_codigo", "modalidad_atencion_codigo"):
                assert stored_attention[key] == attention[key]
            audits = [dict(row) for row in session.execute(text(
                "SELECT id, usuario_id, tabla_nombre, registro_id, accion, fecha FROM auditoria "
                "WHERE (tabla_nombre='pacientes' AND registro_id=:patient) "
                "OR (tabla_nombre='atenciones' AND registro_id=:attention) ORDER BY id"
            ), {"patient": patient_id, "attention": attention_id}).mappings()]
            assert any(a["tabla_nombre"] == "pacientes" for a in audits)
            assert any(a["tabla_nombre"] == "atenciones" for a in audits)
        case.update(paciente=patient, atencion=attention, mysql_paciente=stored_patient,
                    mysql_atencion=stored_attention, auditoria=audits, verificado_api_y_mysql=True)
        save()
        print(json.dumps({"modalidad": mode, "paciente_id": patient_id, "atencion_id": attention_id,
                          "historia_clinica": history, "documento": document, "verificado": True}, ensure_ascii=False), flush=True)
report["verificado_en"] = datetime.now(ZoneInfo("America/Lima")).isoformat(timespec="seconds")
save()
print("Evidencia:", JOURNAL)
