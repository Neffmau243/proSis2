"""Additional admission probes, only in the isolated database made for this run."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "e2e"))
from audit_admission import configure, TEST_USER, TEST_PASSWORD

_, target = configure("ipress_test_admission_20261017_combinaciones")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.main import app
from app.models.organization import Establishment, Office
from app.models.security import Professional
from app.models.clinical import Attention

engine = create_engine(target)
with Session(engine) as db:
    site = db.scalar(select(Establishment.id).where(Establishment.nombre == "PRUEBA E2E NO REAL"))
    office = db.scalar(select(Office.id).where(Office.codigo == "TEST-E2E"))
    professional = db.scalar(select(Professional.id).where(Professional.colegiatura == "TEST-E2E"))
    other_professional = db.scalar(select(Professional.id).where(Professional.id != professional, Professional.activo.is_(True)).order_by(Professional.id))
assert site and office and professional

results = []
observations = []
def count_attentions():
    with Session(engine) as db:
        return db.scalar(select(func.count(Attention.id)))

with TestClient(app, base_url="http://localhost") as client:
    auth = client.post("/api/v1/auth/login", json={"nombre_usuario":TEST_USER,"password":TEST_PASSWORD})
    assert auth.status_code == 200, auth.text
    client.headers["Authorization"] = "Bearer " + auth.json()["access_token"]
    patients = {}
    for index, (name, birth, sex) in enumerate([
        ("ADULTO", "1990-01-01", "M"), ("ADULTA", "1990-01-01", "F"),
        ("NINO", "2023-04-17", "M"), ("NINA", "2023-04-17", "F"),
    ], start=1):
        data = dict(tipo_documento_codigo="OTRO", numero_documento=f"EXTRA171026{index}",
            fecha_nacimiento=birth, sexo_codigo=sex, primer_nombre=name, apellido_paterno="PRUEBA",
            apellido_materno="FICTICIA", historia_clinica=f"EXTRA-171026-{index}", establecimiento_registro_id=site)
        if name in ("NINO", "NINA"):
            data["responsables"] = [dict(parentesco="MADRE",nombre_completo="MADRE FICTICIA PRUEBA",es_principal=True)]
        response = client.post("/api/v1/patients",json=data)
        assert response.status_code == 201, response.text
        patients[name] = response.json()["id"]

    base = dict(paciente_id=patients["ADULTA"],establecimiento_id=site,consultorio_id=office,
        profesional_id=professional,fecha_atencion="2026-10-17T09:00:00",modalidad_atencion_codigo="AMBULATORIA",
        grupo_atencion_codigo="NINOS_ADOLESCENTES_ADULTOS_MAYORES",peso_kg=60,talla_cm=160,
        observaciones="PRUEBA AISLADA DE COMBINACIONES 17/10/2026")
    negatives = [
        ("Fecha futura", {"fecha_atencion":"2026-10-18T09:00:00"}),
        ("Fecha anterior al nacimiento", {"paciente_id":patients["NINO"],"fecha_atencion":"2023-04-16T09:00:00"}),
        ("Fecha efectiva anterior a atención", {"fecha_atendido":"2026-10-16T09:00:00"}),
        ("Hora fin anterior a inicio", {"hora_inicio":"10:00:00","hora_fin":"09:00:00"}),
        ("Sistólica menor a diastólica", {"presion_sistolica":60,"presion_diastolica":90}),
        ("Presiones iguales", {"presion_sistolica":90,"presion_diastolica":90}),
        ("Temperatura fuera de protocolo", {"temperatura_c":50}),
        ("Presión fuera de protocolo", {"presion_sistolica":999}),
        ("Consultorio de otra sede", {"establecimiento_id":1}),
        ("Profesional no asignado al consultorio", {"profesional_id":other_professional}),
        ("Grupo general con fecha de parto", {"fecha_parto":"2026-10-10"}),
        ("Gestante con fecha de parto", {"grupo_atencion_codigo":"GESTANTES","fecha_parto":"2026-10-10"}),
        ("Puérpera con fecha probable de parto", {"grupo_atencion_codigo":"PUERPERAS","fecha_probable_parto":"2026-11-10"}),
        ("Código CIE-10 inexistente", {"diagnosticos":[{"cie10_codigo":"NO_EXISTE"}]}),
        ("Prestación inexistente", {"prestaciones":[{"prestacion_codigo":"NO_EXISTE","cantidad":1}]}),
    ]
    for label, changes in negatives:
        before = count_attentions()
        response = client.post("/api/v1/atenciones",json={**base,**changes})
        after = count_attentions()
        results.append(dict(case=label,status=response.status_code,passed=response.status_code in (403,404,422) and before==after,
            no_partial_save=before==after,response=response.json()))

    # Characterize surprising acceptance separately from passing expected rules.
    probes = [
        ("Adulto masculino / gestantes", {"paciente_id":patients["ADULTO"],"grupo_atencion_codigo":"GESTANTES"}),
        ("Adulto masculino / puérperas", {"paciente_id":patients["ADULTO"],"grupo_atencion_codigo":"PUERPERAS"}),
        ("Niño de 3 años / gestantes", {"paciente_id":patients["NINO"],"grupo_atencion_codigo":"GESTANTES"}),
        ("Niña de 3 años / puérperas", {"paciente_id":patients["NINA"],"grupo_atencion_codigo":"PUERPERAS"}),
        ("Gestante / fecha probable de parto anterior a atención", {"grupo_atencion_codigo":"GESTANTES","fecha_probable_parto":"2026-10-01"}),
        ("Puérpera / fecha de parto futura", {"grupo_atencion_codigo":"PUERPERAS","fecha_parto":"2027-01-01"}),
        ("Atención sin mediciones, diagnósticos ni prestaciones", {"peso_kg":None,"talla_cm":None}),
    ]
    for label,changes in probes:
        response = client.post("/api/v1/atenciones",json={**base,**changes})
        body = response.json()
        observations.append(dict(case=label,status=response.status_code,stored={key:body.get(key) for key in
            ("id","estado","grupo_atencion_codigo","grupo_etario_codigo","fecha_parto","fecha_probable_parto","prestaciones","diagnosticos")}
            if response.status_code==201 else body))

report = dict(database=target.database,negative_cases=results,passed=sum(r["passed"] for r in results),
    total=len(results),observations=observations,patients=patients)
path = Path(__file__).with_name("combinaciones-extra.json")
path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
print(json.dumps(report,ensure_ascii=True,default=str))
engine.dispose()
sys.exit(0 if report["passed"]==report["total"] else 1)
