"""Separate ETLSIS care areas/services from the physical office tree.

Legacy area codes remain accepted so saved encounters and old clients keep
working. Esp_* identifies services, never a physical room or a qualification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

AREA_SERVICES: dict[str, tuple[str, ...]] = {
    "ESPECIALIDADES:003": (
        "ESP_MEDICINA:001",
        "ESP_MEDICINA:002",
        "ESP_MEDICINA:003",
        "ESP_MEDICINA:004",
    ),
    "ESPECIALIDADES2:001": (
        "ESPECIALIDADES:004",
        "ESPECIALIDADES:009",
        "ESP_ENFERMERIA:003",
        "ESP_ENFERMERIA:004",
    ),
    "ESPECIALIDADES2:006": ("ESP_ODONTOLOGIA:001",),
    "ESPECIALIDADES:006": ("ESP_PSICOLOGIA:001",),
    "ESPECIALIDADES:008": (
        "ESPECIALIDADES:007",
        "ESP_OBSTETRICIA:002",
        "ESP_OBSTETRICIA:003",
        "ESP_OBSTETRICIA:004",
        "ESP_OBSTETRICIA:005",
        "ESP_ENFERMERIA:004",
    ),
    "ESPECIALIDADES:005": (
        "ESP_NUTRICION:001",
        "ESP_NUTRICION:002",
        "ESP_NUTRICION:003",
        "ESP_ENFERMERIA:004",
    ),
    "ESPECIALIDADES:002": (),
    "ESPECIALIDADES:009": ("ESP_TOPICO:001", "ESP_TOPICO:002"),
}

AREA_NAMES = {
    "ESPECIALIDADES:003": "Medicina",
    "ESPECIALIDADES2:001": "Enfermería",
    "ESPECIALIDADES2:006": "Odontología",
    "ESPECIALIDADES:006": "Psicología",
    "ESPECIALIDADES:008": "Obstetricia",
    "ESPECIALIDADES:005": "Nutrición",
    "ESPECIALIDADES:002": "Laboratorio",
    "ESPECIALIDADES:009": "Tópico",
}


def areas_for_service(code: str) -> list[str]:
    return [area for area, services in AREA_SERVICES.items() if code == area or code in services]


def default_services(area: str | None) -> tuple[str, ...]:
    if area is None:
        return ()
    return (*AREA_SERVICES.get(area, ()), area)


CUSTOM_SERVICE_GROUP = "SERVICIO_AREA:"


def is_custom_service(code: str) -> bool:
    return bool(re.fullmatch(r"SRV-[0-9A-F]{16}", code))


def custom_service_area(entity: Any) -> str | None:
    group = getattr(entity, "grupo", None)
    code = getattr(entity, "codigo", "")
    if isinstance(code, str) and is_custom_service(code) and isinstance(group, str):
        return (
            group.removeprefix(CUSTOM_SERVICE_GROUP)
            if group.startswith(CUSTOM_SERVICE_GROUP)
            else None
        )
    return None


@dataclass(frozen=True)
class OfficeContext:
    area_code: str | None
    required_specialty: str | None
    service_codes: tuple[str, ...]
    active: bool
    path: str
    ancestor_ids: tuple[int, ...]


def office_context(office: Any) -> OfficeContext:
    """Resolve inherited services, area and status; fail closed on broken trees."""
    chain = []
    seen = set()
    current = office
    active = True
    while current is not None:
        if current.id in seen:
            active = False
            break
        seen.add(current.id)
        chain.append(current)
        active = active and bool(current.activo)
        parent_id = current.consultorio_padre_id
        parent = getattr(current, "padre", None)
        if parent_id is not None and (
            parent is None or parent.establecimiento_id != office.establecimiento_id
        ):
            active = False
            break
        current = parent
    area = next((item.area_codigo for item in chain if getattr(item, "area_codigo", None)), None)
    required = next((item.especialidad_codigo for item in chain if item.especialidad_codigo), None)
    if area is None:
        candidates = areas_for_service(required) if required else []
        area = (
            required if required in AREA_SERVICES else (candidates[0] if candidates else required)
        )
    if any(getattr(item, "area_codigo", None) not in (None, area) for item in chain):
        active = False
    services = default_services(area)
    # Parent constraints apply even if a child explicitly narrows its services.
    for index, item in enumerate(reversed(chain)):
        configured = getattr(item, "servicios_codigos", None)
        if configured is not None:
            # Only a root may enable registered custom services. Descendants
            # still intersect their parent's whitelist; configuration writes
            # validate the catalog identity and area before persisting it.
            if index == 0:
                services = tuple(
                    dict.fromkeys(
                        (*services, *(code for code in configured if is_custom_service(code)))
                    )
                )
            services = tuple(code for code in services if code in configured)
    return OfficeContext(
        area,
        required or area,
        services,
        active,
        " / ".join(item.nombre for item in reversed(chain)),
        tuple(item.id for item in chain[1:]),
    )
