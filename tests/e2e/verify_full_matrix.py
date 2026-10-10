"""Exhaustive catalog combinations against isolated MySQL via real API routes.

Usage: python tests/e2e/verify_full_matrix.py ipress_test_admission_20261001_fixes
Not a browser test. Creates synthetic data only; never removes existing records.
"""
import json
import sys
from pathlib import Path
from uuid import uuid4

from audit_admission import TEST_PASSWORD, TEST_USER, configure

_, target = configure(sys.argv[1])

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.main import app
from app.models.clinical import Attention
from app.models.organization import Establishment, Office
from app.models.patient import Patient
from app.models.security import Professional
from app.models.surveillance import NutritionalEvaluation

engine = create_engine(target)
run = uuid4().hex[:10]
report = {"database": target.database, "run": run, "cases": [], "patients": [],
          "scope": "API TestClient + real MySQL, not browser or physical printing"}
ethnicity_matrix = "--ethnicity-matrix" in sys.argv[2:]
output = Path(__file__).with_name("ethnicity_matrix_results.json" if ethnicity_matrix else "full_matrix_results.json")
report["snapshots"] = []
GENERAL = "NINOS_ADOLESCENTES_ADULTOS_MAYORES"
affiliation = dict(sis_diresa="040", sis_tipo="2", sis_numero="00112233", sis_secuencia="01")
documents = ("DNI", "CE", "PAS", "DE", "OTRO")


def expect(ok, message):
    if not ok:
        raise AssertionError(message)


with Session(engine) as session:
    site = session.scalar(select(Establishment.id).where(Establishment.nombre == "PRUEBA E2E NO REAL"))
    office = session.scalar(select(Office.id).where(Office.codigo == "TEST-E2E"))
    professional = session.scalar(select(Professional.id).where(Professional.colegiatura == "TEST-E2E"))
expect(site and office and professional, "Missing isolated fixtures")

try:
    with TestClient(app, base_url="http://localhost") as client:
        def request(method, route, status=200, payload=None):
            response = client.request(method, "/api/v1" + route, json=payload)
            expect(response.status_code == status,
                   f"{method} {route}: expected {status}, got {response.status_code}: {response.text[:800]}")
            return response.json()

        token = request("POST", "/auth/login", payload={"nombre_usuario": TEST_USER, "password": TEST_PASSWORD})
        client.headers["Authorization"] = "Bearer " + token["access_token"]
        insurers = request("GET", "/catalogos/seguros")
        report["insurers"] = insurers
        expect(len(insurers) == 11, "Catalog changed; revise expected matrix size")
        ethnicities = request("GET", "/catalogos/etnias")
        report["ethnicities"] = ethnicities
        report["ethnicity_matrix"] = ethnicity_matrix
        ethnicity_codes = [None, *[entry["codigo"] for entry in ethnicities]]
        expect(len(set(ethnicity_codes)) == len(ethnicity_codes), "Duplicate ethnicity catalog codes")
        # Allocate unique synthetic DNI values even when this script is rerun.
        with Session(engine) as session:
            occupied = set(session.scalars(select(Patient.numero_documento).where(Patient.tipo_documento_codigo == "DNI")))
            occupied_ce = set(session.scalars(select(Patient.numero_documento).where(Patient.tipo_documento_codigo == "CE")))
        next_dni = 96000000
        profiles = [("ADULTA", "1994-02-10"), ("NINO", "2020-03-10"), ("MAYOR", "1950-06-15")]
        if ethnicity_matrix:
            profiles.insert(2, ("ADOLESCENTE", "2012-03-10"))
        for profile, birth in profiles:
            for doc in documents:
                selected_ethnicities = ethnicity_codes if profile == "ADULTA" else [None, "1", "40", "58"]
                selections = [(insurer, None) for insurer in insurers]
                if ethnicity_matrix:
                    selections = [(insurers[index % len(insurers)], code) for index, code in enumerate(selected_ethnicities)]
                for insurer, ethnicity in selections:
                    while str(next_dni) in occupied or str(100000000 + next_dni) in occupied_ce:
                        next_dni += 1
                    number = str(next_dni) if doc == "DNI" else (
                        str(100000000 + next_dni) if doc == "CE" else f"T{run}{len(report['patients']):03}")
                    occupied.add(str(next_dni))
                    if doc == "CE":
                        occupied_ce.add(number)
                    next_dni += 1
                    is_sis = insurer.get("regimen") == "SIS" or insurer["codigo"] == "SIS"
                    fields = affiliation if is_sis else dict.fromkeys(affiliation)
                    sent = dict(tipo_documento_codigo=doc, numero_documento=number,
                                primer_nombre=profile, apellido_paterno="PRUEBA", apellido_materno="MATRIZ",
                                sexo_codigo="F" if profile == "ADULTA" else "M", fecha_nacimiento=birth,
                                condicion="NO GESTANTE", establecimiento_registro_id=site,
                                historia_clinica=f"MX-{run}-{len(report['patients'])}", seguro_id=insurer["id"],
                                etnia_codigo=ethnicity, **fields)
                    if profile in {"NINO", "ADOLESCENTE"}:
                        sent["responsables"] = [{"parentesco": "MADRE", "nombre_completo": "MADRE FICTICIA", "es_principal": True}]
                    patient = request("POST", "/patients", 201, sent)
                    pid = patient["id"]
                    report["patients"].append(pid)
                    fetched = request("GET", f"/patients/{pid}")
                    patient_keys = ("tipo_documento_codigo", "numero_documento", "seguro_id", "fecha_nacimiento", "etnia_codigo", *fields)
                    expect(all(fetched[k] == sent[k] for k in patient_keys), f"Patient GET mismatch {pid}")
                    with Session(engine) as session:
                        row = session.get(Patient, pid)
                        expect(all(str(getattr(row, k)) == str(sent[k]) for k in patient_keys), f"Patient SQL mismatch {pid}")
                    history = []
                    age_condition = {
                        "ADULTA": "ADULTO",
                        "NINO": "NIÑO",
                        "ADOLESCENTE": "ADOLESCENTE",
                        "MAYOR": "ADULTO MAYOR",
                    }[profile]
                    condition = "NO GESTANTE"
                    groups = (GENERAL, "GESTANTES", "PUERPERAS") if profile == "ADULTA" else (GENERAL,)
                    for mode in ("AMBULATORIA", "EMERGENCIA"):
                        for group in groups:
                            case = dict(profile=profile, document=doc, insurance=insurer["codigo"], ethnicity=ethnicity,
                                        mode=mode, group=group, patient_id=pid, passed=False)
                            report["cases"].append(case)
                            payload = dict(paciente_id=pid, establecimiento_id=site, consultorio_id=office,
                                           profesional_id=professional, fecha_atencion="2026-10-01T09:00:00",
                                           modalidad_atencion_codigo=mode, grupo_atencion_codigo=group,
                                           peso_kg=20 if profile == "NINO" else 60,
                                           talla_cm=115 if profile == "NINO" else 160)
                            if group == "GESTANTES":
                                payload.update(tipo_embarazo_codigo="UNICO", peso_antes_embarazo_kg=55,
                                               fecha_probable_parto="2027-03-01",
                                               valoracion_nutricional={"edad_gestacional_semanas": 18})
                            saved = request("POST", "/atenciones", 201, payload)
                            aid = saved["id"]
                            case["attention_id"] = aid
                            attention = request("GET", f"/atenciones/{aid}")
                            for key in ("paciente_id", "modalidad_atencion_codigo", "grupo_atencion_codigo"):
                                expect(attention[key] == payload[key], f"Attention GET {key}: {aid}")
                            for key in ("tipo_embarazo_codigo", "peso_antes_embarazo_kg", "fecha_probable_parto"):
                                actual, expected = attention[key], payload.get(key)
                                expect(float(actual) == expected if key == "peso_antes_embarazo_kg" and expected is not None else actual == expected,
                                       f"Pregnancy field {key}: {aid}")
                            snapshot = attention["fua_impresion"]
                            # FUA normalizes all text to uppercase; patient master data keeps input case.
                            expect(snapshot["tipo_documento"] == doc and snapshot["numero_documento"] == number.upper(), f"FUA identity {aid}")
                            expect(snapshot["tdi"] == {"DNI": "2", "CE": "3"}.get(doc), f"Unexpected TDI {aid}")
                            expect(all(snapshot[k] == fields[k] for k in fields), f"FUA SIS fields {aid}")
                            expect(snapshot["grupo_atencion_codigo"] == group, f"FUA group {aid}")
                            expect(snapshot["tipo_atencion"] == mode, f"FUA mode {aid}")
                            expect(snapshot["etnia_codigo"] == ethnicity, f"FUA ethnicity {aid}")
                            condition = {
                                "GESTANTES": "GESTANTE",
                                "PUERPERAS": "PUERPERA",
                            }.get(group, age_condition)
                            current = request("GET", f"/patients/{pid}")
                            expect(current["condicion"] == condition, f"Patient condition {aid}")
                            with Session(engine) as session:
                                row = session.get(Attention, aid)
                                expect(row.grupo_atencion_codigo == group and row.modalidad_atencion_codigo == mode
                                       and row.fua_impresion == snapshot, f"Attention SQL {aid}")
                                expect(session.get(Patient, pid).condicion == condition, f"Patient SQL condition {aid}")
                                nutrition = session.scalars(select(NutritionalEvaluation).where(NutritionalEvaluation.atencion_id == aid)).all()
                                if group == "GESTANTES":
                                    expect(len(nutrition) == 1 and nutrition[0].edad_gestacional_semanas == 18, f"Gestational age SQL {aid}")
                                else:
                                    expect(not any(n.edad_gestacional_semanas is not None for n in nutrition), f"Gestational age leaked {aid}")
                            history.append((aid, snapshot))
                            report["snapshots"].append({"attention_id": aid, "profile": profile, "snapshot": snapshot})
                            case["passed"] = True
                    for aid, snapshot in history:
                        expect(request("GET", f"/atenciones/{aid}")["fua_impresion"] == snapshot, f"History mutated {aid}")
                print(json.dumps({"profile": profile, "document": doc, "completed": len(report["cases"])}), flush=True)
        expected_count = len(ethnicity_codes) * len(documents) * 6 + 3 * 4 * len(documents) * 2 if ethnicity_matrix else 550
        expect(len(report["cases"]) == expected_count, "Incomplete matrix")
        report["expected"] = expected_count
        report["complete"] = True
        if ethnicity_matrix:
            # Dev-only browser fixture from actual persisted synthetic responses.
            browser_cases = [entry for entry in report["snapshots"]
                             if entry["profile"] == "ADULTA" and entry["snapshot"]["etnia_codigo"] == "40"]
            expect(len(browser_cases) == len(documents) * 6, "Incomplete browser fixture")
            fixture = Path(__file__).resolve().parents[2] / "frontend/tests/fixtures/fua-ethnicity-audit.json"
            fixture.write_text(json.dumps(browser_cases, indent=2, ensure_ascii=False), encoding="utf-8")
except Exception as error:
    report["error"] = str(error)
    raise
finally:
    report["passed"] = sum(c["passed"] for c in report["cases"])
    report["failed"] = sum(not c["passed"] for c in report["cases"])
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    engine.dispose()
    print(json.dumps({k: report.get(k) for k in ("database", "complete", "passed", "failed")}), flush=True)
