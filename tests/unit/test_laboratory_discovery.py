"""Laboratory filtering preserves ownership scoping in both rows and totals."""
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import mysql

from app.repositories.discovery import AttentionDiscoveryRepository
from app.schemas.attention import AttentionCreate
from app.schemas.discovery import AttentionSearchCriteria


def test_laboratory_filter_applies_to_rows_and_total_without_removing_scope():
    session = MagicMock()
    session.execute.return_value.unique.return_value.scalars.return_value = []
    session.scalar.return_value = 0
    result = AttentionDiscoveryRepository(session).search(
        AttentionSearchCriteria(consultorio_id=8, profesional_id=4),
        professional_id=4, establishment_ids=[2],
    )
    assert result.total == 0
    for statement in [session.execute.call_args.args[0], session.scalar.call_args.args[0]]:
        sql = str(statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "atenciones.consultorio_id = 8" in sql
        assert "atenciones.profesional_id = 4" in sql
        assert "atenciones.establecimiento_id IN (2)" in sql


def test_laboratory_filter_requires_positive_office_id():
    with pytest.raises(ValidationError):
        AttentionSearchCriteria(consultorio_id=0)


def test_shift_bounds_apply_to_rows_and_count_with_an_exclusive_end():
    session = MagicMock()
    session.execute.return_value.unique.return_value.scalars.return_value = []
    session.scalar.return_value = 0
    AttentionDiscoveryRepository(session).search(
        AttentionSearchCriteria(
            consultorio_id=8, profesional_id=4,
            fecha_hora_desde="2026-10-12T07:00:00",
            fecha_hora_hasta="2026-10-12T13:00:00",
        ), professional_id=4, establishment_ids=[2],
    )
    for statement in [session.execute.call_args.args[0], session.scalar.call_args.args[0]]:
        sql = str(statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "atenciones.fecha_atencion >= '2026-10-12 07:00:00'" in sql
        assert "atenciones.fecha_atencion < '2026-10-12 13:00:00'" in sql
        assert "atenciones.consultorio_id = 8" in sql
        assert "atenciones.establecimiento_id IN (2)" in sql


@pytest.mark.parametrize("end", [None, "2026-10-12T06:00:00", "2026-10-12T07:00:00"])
def test_shift_rejects_incomplete_and_inverted_intervals(end):
    with pytest.raises(ValidationError):
        AttentionSearchCriteria(fecha_hora_desde="2026-10-12T07:00:00", fecha_hora_hasta=end)


def test_intake_reference_preserves_leading_zeroes_and_is_not_an_issued_document():
    command = AttentionCreate(
        paciente_id=1, establecimiento_id=2, profesional_id=4, consultorio_id=8,
        modalidad_atencion_codigo="AMBULATORIA", fecha_atencion="2026-10-12T09:00:00",
        numero_referencia_ingreso=" 001565 ", numero_contrarreferencia_ingreso="00007",
    )
    assert command.numero_referencia_ingreso == "001565"
    assert command.numero_contrarreferencia_ingreso == "00007"


def test_invalid_shift_is_a_request_validation_error_before_querying():
    from types import SimpleNamespace

    from fastapi.exceptions import RequestValidationError

    from app.controllers.attention_discovery import search_attentions

    with pytest.raises(RequestValidationError):
        search_attentions(
            principal=SimpleNamespace(user_id=1, roles=["PROFESIONAL"]),
            db=MagicMock(),
            fecha_hora_desde="2026-10-12T13:00:00",
            fecha_hora_hasta="2026-10-12T07:00:00",
        )
