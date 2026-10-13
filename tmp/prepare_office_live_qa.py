"""Prepare synthetic QA data exclusively in the isolated disposable app on 8001."""
import json
import re
from pathlib import Path
from uuid import uuid4

import httpx

environment = json.loads(Path("tmp/office-ui-environment.json").read_text(encoding="utf-8"))
assert environment["database"].startswith("proysis_test_office_ui_")
assert environment["url"] == "http://127.0.0.1:8001"
root = environment["url"] + "/api/v1"
readme = Path("README.md").read_text(encoding="utf-8")


def client(username):
    password = re.search(r"\| `" + re.escape(username) + r"` \| `([^`]+)`", readme).group(1)
    api = httpx.Client(base_url=root, timeout=30)
    response = api.post("/auth/login", json={"nombre_usuario": username, "password": password})
    response.raise_for_status()
    account = response.json()
    api.headers["Authorization"] = "Bearer " + account["access_token"]
    return api, account["usuario_id"]


admin, _ = client("admin")
doctor, _ = client("medico.demo")
catalog = doctor.get("/catalogos/consultorios", params={"limit": 100}).json()
medicine = next(item for item in catalog["items"] if item.get("area_codigo") == "ESPECIALIDADES:003")
assert "ESP_MEDICINA:003" in [item["codigo"] for item in medicine["servicios_habilitados"]]
staff = doctor.get("/catalogos/profesionales", params={"consultorio_id": medicine["id"], "limit": 100}).json()
assert staff["items"]
created = admin.post("/configuracion/consultorios", json={
    "establecimiento_id": medicine["establecimiento_id"], "codigo": "QA-" + uuid4().hex[:7].upper(),
    "nombre": "Sala QA jerarquía (prueba temporal)", "consultorio_padre_id": medicine["id"],
    "servicios_codigos": ["ESP_MEDICINA:001"],
})
created.raise_for_status()
room = created.json()
state = {"office_id": room["id"], "parent_id": medicine["id"],
         "establishment_id": medicine["establecimiento_id"], "professional_id": staff["items"][0]["id"]}
Path("tmp/office-live-qa.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
for attempt in range(10):
    patient = doctor.post("/patients", json={
        "tipo_documento_codigo": "DNI", "numero_documento": str(90000000 + int(uuid4().hex[:6], 16) % 9999999),
        "fecha_nacimiento": "1990-05-10", "apellido_paterno": "QA", "apellido_materno": "JERARQUIA",
        "primer_nombre": "PRUEBA", "sexo_codigo": "F",
        "establecimiento_registro_id": medicine["establecimiento_id"],
    })
    if patient.status_code == 201:
        break
    if patient.status_code != 409:
        patient.raise_for_status()
patient.raise_for_status()
state["patient_id"] = patient.json()["id"]
Path("tmp/office-live-qa.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
print(json.dumps({"prepared": True, **state}))
