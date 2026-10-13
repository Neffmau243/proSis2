"""Back up office metadata before applying the additive local migration."""
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.database import engine

backup = Path("tmp/consultorios_before_0033.json")
with engine.connect() as connection:
    connection.exec_driver_sql("START TRANSACTION READ ONLY")
    rows = [dict(row) for row in connection.execute(text("SELECT * FROM consultorios")).mappings()]
    connection.rollback()
if not backup.exists():
    backup.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
command.upgrade(Config("alembic.ini"), "head")
with engine.connect() as connection:
    print("Migration:", connection.scalar(text("SELECT version_num FROM alembic_version")))
    print("Offices:", connection.scalar(text("SELECT COUNT(*) FROM consultorios")))
    print("Assignments:", connection.scalar(text("SELECT COUNT(*) FROM consultorio_profesionales")))
