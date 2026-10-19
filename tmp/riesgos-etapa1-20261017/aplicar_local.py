"""Apply only stage 1 to local development and check historical data hashes."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

settings = get_settings()
url = make_url(settings.sqlalchemy_database_url)
assert settings.environment == "development" and url.host in {"localhost", "127.0.0.1"}
engine = create_engine(url)

def frozen():
    result = {}
    with engine.connect() as connection:
        for label, query in {
            "atenciones": "SELECT id, valoracion_calculada, fua_impresion FROM atenciones ORDER BY id",
            "riesgos": "SELECT paciente_id, grupo_riesgo_id, fecha_inicio, fecha_fin, observacion FROM paciente_grupos_riesgo ORDER BY paciente_id, grupo_riesgo_id, fecha_inicio",
        }.items():
            rows = [list(row) for row in connection.execute(text(query))]
            result[label] = {"cantidad": len(rows), "sha256": hashlib.sha256(json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest()}
    return result

with engine.connect() as connection:
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
assert revision == "20261014_0036_locality_keys", revision
before = frozen()
command.upgrade(Config(str(ROOT / "alembic.ini")), "20261017_0037_nutrition_followup")
after = frozen()
assert before == after, "Historical data changed unexpectedly"
report = {"revision_anterior": revision, "revision_actual": "20261017_0037_nutrition_followup", "historico_conservado": True, "comprobacion": after}
(Path(__file__).parent / "migracion-local.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
engine.dispose()
