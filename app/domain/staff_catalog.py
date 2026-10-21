"""Identity comparison for the small staff reference catalogs."""

import unicodedata

from app.domain.office import AREA_NAMES


def is_care_area(entity: object) -> bool:
    return bool(getattr(entity, "es_area", False)) or getattr(entity, "codigo", None) in AREA_NAMES


def is_staff_specialty_code(code: str) -> bool:
    """Legacy Esp_* rows describe care services, not staff qualifications."""
    normalized = code.upper()
    if normalized in AREA_NAMES:
        return True
    return not normalized.startswith(
        ("ESP_", "CERTIFICADO:", "ESPECIALIDADES:", "ESPECIALIDADES2:", "ESPECIALIDADES3:")
    )


def catalog_name_key(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char)).casefold().split()
    )
