"""The quick patient history is bounded in SQL and keeps clinical visibility."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.repositories.attention import AttentionRepository


@pytest.mark.parametrize(
    ("professional_id", "establishment_ids"),
    [(None, None), (7, set()), (7, {2})],
)
def test_patient_history_limits_to_five_with_stable_order_and_scope(
    professional_id, establishment_ids
):
    session = MagicMock(spec=Session)
    session.execute.return_value.unique.return_value.scalars.return_value = []

    AttentionRepository(session).list_by_patient(
        42, professional_id=professional_id, establishment_ids=establishment_ids
    )

    statement = session.execute.call_args.args[0]
    sql = " ".join(
        str(
            statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True})
        ).split()
    )
    assert "atenciones.paciente_id = 42" in sql
    assert "ORDER BY atenciones.fecha_atencion DESC, atenciones.id DESC LIMIT 5" in sql
    if professional_id is not None:
        assert "atenciones.profesional_id = 7" in sql
        assert "atenciones.modalidad_atencion_codigo = 'REFERENCIA'" in sql
        assert "usuarios.profesional_id = 7" in sql
    if establishment_ids:
        assert "atenciones.establecimiento_id IN (2)" in sql
