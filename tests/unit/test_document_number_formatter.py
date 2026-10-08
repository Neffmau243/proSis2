import pytest
from pydantic import ValidationError

from app.exceptions import BusinessRuleError
from app.schemas.document import FuaIssueInput
from app.services.document import DocumentNumberFormatter, DocumentService, FuaNumberFormatter


def test_document_number_formatter_includes_site_period_and_padded_sequence() -> None:
    assert DocumentNumberFormatter().format("FUA", 14, "2026", 7) == "FUA-14-2026-00000007"


def test_fua_number_formatter_uses_renipress_lot_and_eight_digit_sequence() -> None:
    assert FuaNumberFormatter().format("00001291", "26", 1) == "00001291-26-00000001"


@pytest.mark.parametrize(
    ("renipress", "lote", "sequence"),
    (("1291", "26", 1), ("00001291", "2026", 1), ("00001291", "26", 0)),
)
def test_fua_number_formatter_rejects_non_standard_components(
    renipress: str, lote: str, sequence: int
) -> None:
    with pytest.raises(ValueError):
        FuaNumberFormatter().format(renipress, lote, sequence)


def test_renipress_is_padded_from_the_numeric_catalog_value() -> None:
    assert DocumentService._renipress_for("0001291") == "00001291"
    assert DocumentService._renipress_for("1291") == "00001291"


@pytest.mark.parametrize("value", (None, "", "IPRESS-1291", "123456789"))
def test_renipress_rejects_missing_or_non_numeric_catalog_values(value: str | None) -> None:
    with pytest.raises(BusinessRuleError, match="código RENAES"):
        DocumentService._renipress_for(value)


def test_fua_issue_contract_does_not_accept_legacy_city_or_eess_overrides() -> None:
    with pytest.raises(ValidationError):
        FuaIssueInput.model_validate({"atencion_id": 1, "codigo_ciudad": "040"})
    with pytest.raises(ValidationError):
        FuaIssueInput.model_validate({"atencion_id": 1, "codigo_eess": "2"})
