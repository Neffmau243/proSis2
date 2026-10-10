"""Reference catalog endpoints read directly from MySQL.

The SPA depends on these payload shapes to render every selector, so the tests
also pin the contract that must never change silently.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.catalog import Cie10, Profession, ServiceOffering, Specialty
from app.models.organization import Ubigeo
from app.models.patient import RiskGroup

pytestmark = pytest.mark.integration


@pytest.fixture
def catalog_rows(db_session: Session) -> dict[str, str]:
    """One extra row per catalog, distinguishable through a unique token."""

    token = uuid4().hex[:8].upper()
    db_session.add(Specialty(codigo=f"E{token[:6]}", nombre=f"Especialidad {token}", grupo="CLINICA"))
    db_session.add(
        ServiceOffering(codigo=f"P{token[:6]}", descripcion=f"Prestación {token}", grupo="CONSULTA")
    )
    db_session.add(Cie10(codigo=f"Z{token[:4]}", descripcion=f"Diagnóstico {token}", categoria="GENERAL"))
    db_session.add(Cie10(codigo=f"Y{token[:4]}", descripcion=f"Otro diagnóstico {token}", categoria="GENERAL"))
    db_session.add(Profession(nombre=f"Profesión {token}"))
    db_session.add(RiskGroup(codigo=f"R{token[:6]}", nombre=f"Riesgo {token}"))
    db_session.add(
        Ubigeo(
            codigo=f"05{token[:4]}",
            departamento="MOQUEGUA",
            provincia="ILO",
            distrito=f"Distrito {token}",
            localidad="PUERTO",
        )
    )
    db_session.commit()
    return {"token": token}


def test_simple_catalogs_return_seeded_reference_values(
    clinic_scene, catalog_rows: dict[str, str], api_prefix
) -> None:
    expected = {
        "/catalogos/tipos-documento": {"DNI", "CE", "PAS"},
        "/catalogos/sexos": {"F", "M", "I"},
        "/catalogos/modalidades-atencion": {"AMBULATORIA", "EMERGENCIA"},
    }
    for path, codes in expected.items():
        response = clinic_scene.admin_client.get(f"{api_prefix}{path}")
        assert response.status_code == 200, path
        body = response.json()
        assert codes <= {item["codigo"] for item in body}, path
        assert all(set(item) == {"codigo", "nombre", "activo"} for item in body), path
        assert all(item["activo"] is True for item in body), path

    specialties = clinic_scene.admin_client.get(f"{api_prefix}/catalogos/especialidades")
    assert specialties.status_code == 200
    assert {"codigo", "nombre", "activo", "grupo"} == set(specialties.json()[0])

    risk_groups = clinic_scene.admin_client.get(f"{api_prefix}/catalogos/grupos-riesgo")
    assert risk_groups.status_code == 200
    assert {"id", "codigo", "nombre", "activo", "descripcion"} == set(risk_groups.json()[0])

    insurances = clinic_scene.admin_client.get(f"{api_prefix}/catalogos/seguros")
    assert insurances.status_code == 200
    assert {"id", "codigo", "nombre", "activo", "codigo_sis", "regimen"} == set(
        insurances.json()[0]
    )

    professions = clinic_scene.admin_client.get(f"{api_prefix}/catalogos/profesiones")
    assert professions.status_code == 200
    assert {"id", "codigo", "nombre", "activo"} == set(professions.json()[0])


def test_age_group_catalog_exposes_month_boundaries(clinic_scene, api_prefix) -> None:
    response = clinic_scene.admin_client.get(f"{api_prefix}/catalogos/grupos-etarios")

    assert response.status_code == 200
    body = response.json()
    ranges = {
        item["codigo"]: (item["edad_minima_meses"], item["edad_maxima_meses"])
        for item in body
    }
    assert ranges == {
        "NINO": (0, 143),
        "ADOLESCENTE": (144, 215),
        "JOVEN": (216, 359),
        "ADULTO": (360, 719),
        "ADULTO_MAYOR": (720, None),
    }
    assert all(
        set(item) == {"codigo", "nombre", "activo", "edad_minima_meses", "edad_maxima_meses"}
        for item in body
    )


def test_paginated_catalogs_accept_a_search_term(
    clinic_scene, catalog_rows: dict[str, str], api_prefix
) -> None:
    token = catalog_rows["token"]
    # ``especialidades`` and ``grupos-riesgo`` are complete lists: they are
    # short enough to render every option at once.
    list_cases = {
        "/catalogos/especialidades": (f"Especialidad {token}", {"codigo", "nombre", "activo", "grupo"}),
        "/catalogos/grupos-riesgo": (
            f"Riesgo {token}",
            {"id", "codigo", "nombre", "activo", "descripcion"},
        ),
    }
    for path, (term, shape) in list_cases.items():
        listed = clinic_scene.admin_client.get(f"{api_prefix}{path}")
        assert listed.status_code == 200, listed.text
        matches = [item for item in listed.json() if term.split()[-1] in str(item)]
        assert matches, f"{path} no expone '{term}'"
        assert set(matches[0]) == shape

    page_cases = {
        "/catalogos/prestaciones": f"Prestación {token}",
        "/catalogos/cie10": f"Diagnóstico {token}",
        "/catalogos/ubigeos": f"Distrito {token}",
        "/catalogos/localidades": "CERCADO",
        "/catalogos/profesionales": clinic_scene.suffix,
        "/catalogos/establecimientos": clinic_scene.suffix,
        "/catalogos/consultorios": clinic_scene.suffix,
    }
    for path, term in page_cases.items():
        response = clinic_scene.admin_client.get(
            f"{api_prefix}{path}", params={"q": term, "limit": 10, "offset": 0}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items", "total", "limit", "offset", "has_more"}, path
        assert body["total"] >= 1, f"{path} no encontró '{term}'"
        assert body["limit"] == 10
        assert body["has_more"] is False

    # A filter that matches nothing is still a valid, empty page.
    empty = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/cie10", params={"q": "ZZZZNADA"}
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["total"] == 0
    assert empty.json()["has_more"] is False


def test_catalog_pagination_walks_pages_without_repeating(
    clinic_scene, catalog_rows: dict[str, str], api_prefix
) -> None:
    token = catalog_rows["token"]
    first = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/cie10", params={"q": token[:6], "limit": 1, "offset": 0}
    )
    assert first.status_code == 200
    body = first.json()
    assert len(body["items"]) == 1
    assert body["has_more"] is True
    assert body["total"] >= 2

    second = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/cie10", params={"q": token[:6], "limit": 1, "offset": 1}
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1
    assert second.json()["items"][0]["codigo"] != body["items"][0]["codigo"]


def test_family_history_catalog_exposes_seeded_prefix_metadata(
    clinic_scene, api_prefix
) -> None:
    """The selector catalog is stable even before any patient uses a prefix."""

    response = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/historias-familiares",
        params={"q": "amarillo", "limit": 10, "offset": 0},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [
            {
                "codigo": "AM",
                "nombre": "AMARILLO",
                "tipo": "COLOR",
                "color_hex": "#F2C94C",
                "activo": True,
            }
        ],
        "total": 1,
        "limit": 10,
        "offset": 0,
        "has_more": False,
    }


def test_catalog_filters_validate_their_ranges(clinic_scene, api_prefix) -> None:
    client = clinic_scene.admin_client
    invalid = [
        {"q": "A"},  # min_length=2
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ]
    for params in invalid:
        response = client.get(f"{api_prefix}/catalogos/cie10", params=params)
        assert response.status_code == 422, params
        assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    invalid_office = client.get(f"{api_prefix}/catalogos/consultorios", params={"establecimiento_id": 0})
    assert invalid_office.status_code == 422

    # An unknown establishment simply yields an empty page.
    empty = client.get(
        f"{api_prefix}/catalogos/consultorios", params={"establecimiento_id": 999999999}
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []


def test_catalogs_require_authentication(clinic_scene, api_prefix) -> None:
    response = clinic_scene.anonymous_client.get(f"{api_prefix}/catalogos/sexos")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"


def test_professional_and_office_catalog_are_limited_to_active_records(
    clinic_scene, create_professional, db_session: Session, api_prefix
) -> None:
    active = create_professional()
    inactive = create_professional(activo=False)

    professionals = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/profesionales", params={"q": active.colegiatura}
    )
    assert professionals.status_code == 200
    assert [item["id"] for item in professionals.json()["items"]] == [active.id]

    inactive_lookup = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/profesionales", params={"q": inactive.colegiatura}
    )
    assert inactive_lookup.status_code == 200
    assert inactive_lookup.json()["items"] == []

    offices = clinic_scene.admin_client.get(
        f"{api_prefix}/catalogos/consultorios",
        params={"establecimiento_id": clinic_scene.establecimiento_id, "limit": 100},
    )
    assert offices.status_code == 200
    assert clinic_scene.consultorio_id in [item["id"] for item in offices.json()["items"]]
