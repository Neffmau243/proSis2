from types import SimpleNamespace

from app.repositories.catalog import CatalogPage
from app.services.catalog import CatalogService


class FamilyHistoryRepository:
    def __init__(self) -> None:
        self.args: tuple[str | None, int, int] | None = None

    def page_family_histories(
        self, *, query: str | None, limit: int, offset: int
    ) -> CatalogPage[SimpleNamespace]:
        self.args = (query, limit, offset)
        return CatalogPage(
            items=[
                SimpleNamespace(
                    codigo="VC",
                    nombre="VERDE CLARO",
                    tipo="COLOR",
                    color_hex="#86C766",
                    activo=True,
                )
            ],
            total=1,
        )


def test_family_history_catalog_normalizes_search_and_returns_prefix_metadata():
    repository = FamilyHistoryRepository()

    page = CatalogService(None, repository=repository).family_histories(
        query="  verde  ", limit=25, offset=0
    )

    assert repository.args == ("verde", 25, 0)
    assert page.items[0].model_dump() == {
        "codigo": "VC",
        "nombre": "VERDE CLARO",
        "tipo": "COLOR",
        "color_hex": "#86C766",
        "activo": True,
    }
    assert page.total == 1
