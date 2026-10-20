"""Local capture rules, not online identity verification or SIS TDI codes."""

import re


def document_problem(document_type: str, number: str) -> str | None:
    if document_type == "DNI":
        if not re.fullmatch(r"[0-9]{8}", number):
            return "El DNI debe contener exactamente 8 dígitos, sin letras ni separadores."
    elif document_type in {"CE", "PAS"}:
        # Preserve the existing 30-character contract for foreign documents.
        if not re.fullmatch(r"[A-Za-z0-9]{1,30}", number):
            return "El CE o pasaporte debe contener de 1 a 30 letras o dígitos, sin espacios."
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9./-]{0,29}", number):
        return "Use hasta 30 letras, dígitos o separadores . / -, empezando por letra o dígito."
    return None
