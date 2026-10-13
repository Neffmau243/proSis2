"""Audit office metadata with a MySQL read-only transaction; no patient data."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import Mock

from sqlalchemy import text

from app.core.database import engine
from app.exceptions import BusinessRuleError
from app.mappers.catalog import office_to_catalog_item
from app.models.organization import Office
from app.schemas.attention import AttentionCreate
from app.schemas.office import OfficeUpdate
from app.services.attention import AttentionService
from app.services.office import OfficeService


QUERIES = {
    "offices": """
        SELECT COUNT(*) total, SUM(activo = 1) active,
               SUM(consultorio_padre_id IS NOT NULL) with_parent,
               COUNT(DISTINCT establecimiento_id) establishments
        FROM consultorios
    """,
    "hierarchy_integrity": """
        SELECT SUM(c.activo = 1 AND p.activo = 0) active_child_inactive_parent,
               SUM(c.establecimiento_id <> p.establecimiento_id) cross_site_parent
        FROM consultorios c JOIN consultorios p ON p.id = c.consultorio_padre_id
    """,
    "specialty_groups": """
        SELECT grupo, COUNT(*) total FROM especialidades
        GROUP BY grupo ORDER BY grupo
    """,
    "assignment_scope_distribution": """
        SELECT sites, COUNT(*) professionals FROM (
            SELECT a.profesional_id, COUNT(DISTINCT c.establecimiento_id) sites
            FROM consultorio_profesionales a
            JOIN consultorios c ON c.id = a.consultorio_id
            WHERE c.activo = 1 AND a.fecha_inicio <= CURRENT_DATE
              AND (a.fecha_fin IS NULL OR a.fecha_fin >= CURRENT_DATE)
            GROUP BY a.profesional_id
        ) scope GROUP BY sites ORDER BY sites
    """,
    "assignment_specialty_integrity": """
        SELECT COUNT(*) incompatible_current_or_future FROM consultorio_profesionales a
        JOIN consultorios c ON c.id = a.consultorio_id
        LEFT JOIN profesional_especialidades s
          ON s.profesional_id = a.profesional_id
         AND s.especialidad_codigo = c.especialidad_codigo
        WHERE c.activo = 1 AND c.especialidad_codigo IS NOT NULL
          AND (a.fecha_fin IS NULL OR a.fecha_fin >= CURRENT_DATE)
          AND s.profesional_id IS NULL
    """,
    "organization_links": """
        SELECT COUNT(*) active_sites, SUM(id_microred IS NULL) without_microred
        FROM establecimientos WHERE activo = 1
    """,
    "assignment_count": "SELECT COUNT(*) total FROM consultorio_profesionales",
}


def detached_probes() -> dict[str, object]:
    """Run use cases on detached entities and mocks, never on the live session."""
    parent = Office(id=1, establecimiento_id=1, codigo="P", nombre="Padre",
                    consultorio_padre_id=None, especialidad_codigo="MED", activo=True)
    child = Office(id=2, establecimiento_id=1, codigo="H", nombre="Hijo",
                   consultorio_padre_id=1, especialidad_codigo=None, activo=True)
    session = Mock()
    service = OfficeService(session)
    repository = Mock()
    repository.get_by_id.return_value = parent
    service._repository = repository
    service.deactivate(1, actor_id=1)
    deactivation_calls = [call[0] for call in repository.method_calls]

    clinical = AttentionService(Mock())
    clinical_repository = Mock()
    clinical_repository.get_active_office.return_value = child
    clinical_repository.get_active_establishment.return_value = object()
    clinical_repository.get_active_professional.return_value = object()
    clinical_repository.get_active_mode.return_value = object()
    clinical_repository.get_active_specialty.return_value = object()
    clinical._attentions = clinical_repository
    clinical._validate_clinical_context(AttentionCreate(
        paciente_id=1, establecimiento_id=1, consultorio_id=2, profesional_id=99,
        modalidad_atencion_codigo="AMBULATORIA", fecha_atencion=datetime(2026, 10, 13, 9),
        especialidad_codigo=None,
    ))
    clinical_calls = [call[0] for call in clinical_repository.method_calls]
    catalog = office_to_catalog_item(child).model_dump()
    clinical_repository.get_active_office.return_value = Office(
        id=3, establecimiento_id=1, codigo="MED", nombre="Medicina",
        consultorio_padre_id=None, especialidad_codigo="ESPECIALIDADES:003", activo=True,
    )
    pediatric_error = None
    try:
        clinical._validate_clinical_context(AttentionCreate(
            paciente_id=1, establecimiento_id=1, consultorio_id=3, profesional_id=99,
            modalidad_atencion_codigo="AMBULATORIA", fecha_atencion=datetime(2026, 10, 13, 9),
            especialidad_codigo="ESP_MEDICINA:003",
        ))
    except BusinessRuleError as error:
        pediatric_error = error.code

    repository.reset_mock()
    repository.get_active_establishment.return_value = object()
    repository.get_active_specialty.return_value = object()
    service.update(1, OfficeUpdate(especialidad_codigo="OTHER"), actor_id=1)
    return {
        "deactivation": {
            "parent_active": parent.activo,
            "child_active": child.activo,
            "repository_calls": deactivation_calls,
        },
        "clinical_context": {
            "child_without_specialty_accepted": True,
            "repository_calls": clinical_calls,
            "caveat": "Context validator only; patient/actor/date checks run elsewhere.",
        },
        "catalog_fields": sorted(catalog),
        "catalog_exposes_parent": "consultorio_padre_id" in catalog,
        "pediatrics_in_medicine_error": pediatric_error,
        "office_specialty_change_repository_calls": [call[0] for call in repository.method_calls],
    }


def main() -> None:
    results: dict[str, object] = {}
    with engine.connect() as connection:
        connection.exec_driver_sql("START TRANSACTION READ ONLY")
        try:
            for label, query in QUERIES.items():
                results[label] = [dict(row) for row in connection.execute(text(query)).mappings()]
        finally:
            connection.rollback()
    results["detached_probes"] = detached_probes()
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
