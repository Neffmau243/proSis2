"""End-to-end: admisión con N.° de historia clínica, datos de impresión FUA y puérpera.

Ejercita las rutas reales de FastAPI con TestClient y una base MySQL aislada ya
creada con ``audit_admission.py setup``. No simula el repositorio ni modifica
código de aplicación. Cada caso escribe evidencia en
``hc_admission_results.json`` junto a este script.

Uso:
    .venv/Scripts/python.exe tests/e2e/audit_admission.py setup ipress_test_admission_<sufijo>
    .venv/Scripts/python.exe tests/e2e/verify_hc_admission.py ipress_test_admission_<sufijo>

Cubre tres áreas:
  1. Admisión de un paciente con N.° H. clínica (incluidos ceros iniciales).
  2. Datos que consumen la vista previa y la calibración de impresión FUA.
  3. Admisión puérpera con su propia historia clínica.

La calibración en milímetros y la impresión física son responsabilidad del
navegador; aquí solo se verifica el contrato de datos del servidor. Ver la
prueba de componente ``frontend/tests/components/FuaPrintDialog.test.ts`` para
el flujo de calibración en la interfaz.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Import local al e2e: ``configure`` debe fijar DATABASE_URL antes de tocar la app.
# ruff: noqa: E402, I001

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

engine = create_engine(target)
with Session(engine) as session:
    site = session.scalar(
        select(Establishment.id).where(Establishment.nombre == "PRUEBA E2E NO REAL")
    )
    office = session.scalar(select(Office.id).where(Office.codigo == "TEST-E2E"))
    professional = session.scalar(
        select(Professional.id).where(Professional.colegiatura == "TEST-E2E")
    )
assert site and office and professional

results = []
GENERAL = "NINOS_ADOLESCENTES_ADULTOS_MAYORES"


def check(name, success):
    results.append({"case": name, "pass": bool(success)})
    assert success, name


request_count = 0


def request(name, method, route, status, payload=None):
    global request_count
    response = client.request(method, "/api/v1" + route, json=payload)
    check(f"{name}: HTTP {status}", response.status_code == status)
    request_count += 1
    return response.json()


with TestClient(app, base_url="http://localhost") as client:
    login = client.post(
        "/api/v1/auth/login", json={"nombre_usuario": TEST_USER, "password": TEST_PASSWORD}
    )
    assert login.status_code == 200, login.text
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]

    stamp = datetime.now().strftime("%H%M%S")

    def new_patient(serial, **overrides):
        payload = {
            "tipo_documento_codigo": "DNI",
            "numero_documento": f"8{serial}{stamp}",
            "primer_nombre": "HISTORIA",
            "apellido_paterno": "PRUEBA",
            "apellido_materno": "FICTICIA",
            "fecha_nacimiento": "1994-02-10",
            "sexo_codigo": "F",
            "condicion": "NO GESTANTE",
            "establecimiento_registro_id": site,
            **overrides,
        }
        return payload

    def new_attention(pid, **overrides):
        return {
            "paciente_id": pid,
            "establecimiento_id": site,
            "consultorio_id": office,
            "profesional_id": professional,
            "fecha_atencion": "2026-10-08T09:00:00",
            "modalidad_atencion_codigo": "AMBULATORIA",
            "grupo_atencion_codigo": GENERAL,
            "peso_kg": 60,
            "talla_cm": 160,
            "presion_sistolica": 110,
            "presion_diastolica": 70,
            **overrides,
        }

    # ------------------------------------------------------------------ 1. HC
    hc = "0" + stamp  # ceros iniciales: la búsqueda y la persistencia son texto, no número
    patient = request(
        "Alta con historia clínica", "POST", "/patients", 201, new_patient(1, historia_clinica=hc)
    )
    pid = patient["id"]
    check("La respuesta conserva la HC exacta", patient["historia_clinica"] == hc)
    fetched = request("Recuperar paciente", "GET", f"/patients/{pid}", 200)
    check("GET devuelve la HC con ceros iniciales", fetched["historia_clinica"] == hc)
    with Session(engine) as session:
        check(
            "MySQL conserva la HC como texto",
            session.get(Patient, pid).historia_clinica == hc,
        )

    found = request("Buscar por HC exacta", "GET", f"/patients?historia_clinica={hc}", 200)
    check("Búsqueda exacta encuentra al paciente", any(p["id"] == pid for p in found["items"]))
    without_zeros = request(
        "Buscar por HC sin ceros", "GET", f"/patients?historia_clinica={stamp}", 200
    )
    check(
        "Buscar sin ceros iniciales no devuelve al paciente",
        all(p["id"] != pid for p in without_zeros["items"]),
    )

    updated_hc = hc + "-A"
    request(
        "Actualizar historia clínica",
        "PATCH",
        f"/patients/{pid}",
        200,
        {"historia_clinica": updated_hc},
    )
    reread = request("Releer tras PATCH", "GET", f"/patients/{pid}", 200)
    check("PATCH persiste la nueva HC", reread["historia_clinica"] == updated_hc)
    with Session(engine) as session:
        check(
            "MySQL refleja la nueva HC",
            session.get(Patient, pid).historia_clinica == updated_hc,
        )

    without_hc = request(
        "Alta sin historia clínica", "POST", "/patients", 201, new_patient(2)
    )
    check("La historia clínica es opcional", without_hc["historia_clinica"] is None)

    # ------------------------------------------------------- 2. Datos FUA
    attention = request("Atención del paciente", "POST", "/atenciones", 201, new_attention(pid))
    check(
        "La atención congela la HC vigente",
        attention["historia_clinica_snapshot"] == updated_hc,
    )
    fua = attention["fua_impresion"]
    check("La copia FUA lleva la historia clínica", fua["historia_clinica"] == updated_hc)
    check("La copia FUA es la versión 2", fua["version"] == 2)
    check(
        "La copia FUA trae la sede y el RENIPRESS preimpreso",
        fua["ipress_nombre"] == "PRUEBA E2E NO REAL"
        and isinstance(fua["renipress_preimpreso"], bool),
    )
    check(
        "La copia FUA identifica al paciente",
        fua["tipo_documento"] == "DNI" and fua["tdi"] == "2" and fua["numero_documento"],
    )
    # Campos que la vista previa de calibración posiciona en la hoja.
    check(
        "La copia FUA trae fecha, hora y medidas para la impresión",
        fua["fecha_atencion"] == "2026-10-08"
        and fua["hora_atencion"] == "09:00:00"
        and float(fua["peso_kg"]) == 60
        and float(fua["talla_cm"]) == 160
        and fua["presion_sistolica"] == 110
        and fua["presion_diastolica"] == 70
        and fua["imc"] is not None,
    )
    check(
        "El grupo general no arrastra fecha de parto",
        fua["fecha_probable_parto"] is None and fua["fecha_parto"] is None,
    )

    # La copia impresa no debe cambiar si la ficha se edita después.
    request(
        "Cambiar HC tras la atención",
        "PATCH",
        f"/patients/{pid}",
        200,
        {"historia_clinica": hc + "-B"},
    )
    historical = request("Releer atención histórica", "GET", f"/atenciones/{attention['id']}", 200)
    check(
        "La atención histórica conserva la HC impresa",
        historical["fua_impresion"] == fua
        and historical["historia_clinica_snapshot"] == updated_hc,
    )
    fresh = request(
        "Nueva atención con la HC nueva", "POST", "/atenciones", 201, new_attention(pid)
    )
    check(
        "La nueva atención usa la HC actual",
        fresh["fua_impresion"]["historia_clinica"] == hc + "-B",
    )

    # ---------------------------------------------------------- 3. Puérpera
    puerperal_hc = "PUE-" + stamp
    puerperal = request(
        "Alta de puérpera",
        "POST",
        "/patients",
        201,
        new_patient(3, historia_clinica=puerperal_hc),
    )
    ppid = puerperal["id"]
    check("La puérpera conserva su historia clínica", puerperal["historia_clinica"] == puerperal_hc)

    delivery = "2026-09-20"
    for mode in ("AMBULATORIA", "EMERGENCIA"):
        saved = request(
            "Atención puérpera " + mode,
            "POST",
            "/atenciones",
            201,
            new_attention(
                ppid,
                modalidad_atencion_codigo=mode,
                grupo_atencion_codigo="PUERPERAS",
                tipo_embarazo_codigo="UNICO",
                peso_antes_embarazo_kg=55,
                fecha_parto=delivery,
            ),
        )
        fetched = request("Recuperar puérpera " + mode, "GET", f"/atenciones/{saved['id']}", 200)
        check(
            "Grupo y modalidad puérpera " + mode,
            fetched["grupo_atencion_codigo"] == "PUERPERAS"
            and fetched["modalidad_atencion_codigo"] == mode,
        )
        check(
            "La copia FUA puérpera imprime la fecha del parto",
            fetched["fua_impresion"]["historia_clinica"] == puerperal_hc
            and fetched["fua_impresion"]["fecha_parto"] == delivery
            and fetched["fua_impresion"]["fecha_probable_parto"] is None,
        )
        with Session(engine) as session:
            row = session.get(Attention, saved["id"])
            check(
                "MySQL puérpera " + mode,
                row.historia_clinica_snapshot == puerperal_hc
                and row.fecha_parto.isoformat() == delivery
                and row.grupo_atencion_codigo == "PUERPERAS",
            )

    # La gestante no admite fecha real de parto: el recuadro se llena según el grupo.
    request(
        "Gestante rechaza fecha de parto",
        "POST",
        "/atenciones",
        422,
        new_attention(
            ppid,
            grupo_atencion_codigo="GESTANTES",
            tipo_embarazo_codigo="UNICO",
            peso_antes_embarazo_kg=55,
            fecha_probable_parto="2027-01-15",
            fecha_parto=delivery,
        ),
    )
    condition = request("Condición de la ficha", "GET", f"/patients/{ppid}", 200)
    check("La ficha queda como PUERPERA", condition["condicion"] == "PUERPERA")

    # ------------------------------- 4. Historial y correspondencia del FUA
    # Dos pacientes distintos: lo guardado en el historial de cada uno debe ser
    # su propia copia FUA, sin mezclarse ni reconstruirse con datos posteriores.
    a_hc = "HIST-A-" + stamp
    b_hc = "HIST-B-" + stamp
    patient_a = request(
        "Alta paciente historial A",
        "POST",
        "/patients",
        201,
        new_patient(4, historia_clinica=a_hc, primer_nombre="ALFA", apellido_paterno="HISTORIAL"),
    )
    patient_b = request(
        "Alta paciente historial B",
        "POST",
        "/patients",
        201,
        new_patient(5, historia_clinica=b_hc, primer_nombre="BETA", apellido_paterno="HISTORIAL"),
    )
    aid, bid = patient_a["id"], patient_b["id"]
    attention_a = request("Atención del paciente A", "POST", "/atenciones", 201, new_attention(aid))
    attention_b = request("Atención del paciente B", "POST", "/atenciones", 201, new_attention(bid))
    fua_a, fua_b = attention_a["fua_impresion"], attention_b["fua_impresion"]
    check(
        "El FUA del paciente A lleva sus propios datos",
        fua_a["historia_clinica"] == a_hc
        and fua_a["numero_documento"] == patient_a["numero_documento"]
        and fua_a["primer_nombre"] == "ALFA"
        and fua_a["apellido_paterno"] == "HISTORIAL",
    )
    check(
        "El FUA del paciente B lleva sus propios datos",
        fua_b["historia_clinica"] == b_hc
        and fua_b["numero_documento"] == patient_b["numero_documento"]
        and fua_b["primer_nombre"] == "BETA",
    )
    check(
        "Los FUA de dos pacientes no se mezclan",
        fua_a["numero_documento"] != fua_b["numero_documento"]
        and fua_a["historia_clinica"] != fua_b["historia_clinica"],
    )

    history_a = request("Historial del paciente A", "GET", f"/atenciones?paciente_id={aid}", 200)
    history_b = request("Historial del paciente B", "GET", f"/atenciones?paciente_id={bid}", 200)
    check(
        "El historial de A solo trae las atenciones y el FUA de A",
        all(item["paciente_id"] == aid for item in history_a)
        and all(item["fua_impresion"]["historia_clinica"] == a_hc for item in history_a)
        and all(item["id"] != attention_b["id"] for item in history_a),
    )
    check(
        "El historial de B solo trae las atenciones y el FUA de B",
        all(item["paciente_id"] == bid for item in history_b)
        and all(item["fua_impresion"]["historia_clinica"] == b_hc for item in history_b)
        and all(item["id"] != attention_a["id"] for item in history_b),
    )
    search_a = request(
        "Búsqueda de historial del paciente A",
        "GET",
        f"/atenciones/busqueda?paciente_id={aid}",
        200,
    )
    check(
        "La búsqueda de historial devuelve el FUA correcto de A",
        all(item["paciente_id"] == aid for item in search_a["items"])
        and any(
            item["id"] == attention_a["id"]
            and item["fua_impresion"]["historia_clinica"] == a_hc
            for item in search_a["items"]
        ),
    )

    # La copia impresa es inmutable: corregir la ficha después no reescribe el FUA.
    request(
        "Corregir datos de la ficha A",
        "PATCH",
        f"/patients/{aid}",
        200,
        {"primer_nombre": "GAMMA", "apellido_paterno": "CORREGIDO"},
    )
    history_a2 = request(
        "Historial de A tras corregir la ficha", "GET", f"/atenciones?paciente_id={aid}", 200
    )
    check(
        "El FUA guardado no cambia al corregir la ficha",
        any(
            item["id"] == attention_a["id"] and item["fua_impresion"] == fua_a
            for item in history_a2
        ),
    )

report = {
    "database": target.database,
    "patient_id": pid,
    "puerperal_patient_id": ppid,
    "historia_clinica": hc + "-B",
    "puerperal_historia_clinica": puerperal_hc,
    "cases": results,
}
Path(__file__).with_name("hc_admission_results.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {
            "database": target.database,
            "checks": len(results),
            "passed": sum(1 for r in results if r["pass"]),
            "failed": 0,
        }
    )
)
engine.dispose()
