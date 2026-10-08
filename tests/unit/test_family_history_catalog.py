from app.repositories.catalog import CatalogPage
from app.services.catalog import CatalogService


class FamilyHistoryRepository:
    def __init__(self) -> None:
        self.args: tuple[str | None, int, int] | None = None

    def page_family_histories(
        self, *, query: str | None, limit: int, offset: int
    ) -> CatalogPage[str]:
        self.args = (query, limit, offset)
        return CatalogPage(items=["HF-VERDE-01"], total=1)


def test_family_history_catalog_normalizes_the_search_and_returns_reusable_codes():
    repository = FamilyHistoryRepository()

    page = CatalogService(None, repository=repository).family_histories(
        query="  verde  ", limit=25, offset=0
    )

    assert repository.args == ("verde", 25, 0)
    assert [item.codigo for item in page.items] == ["HF-VERDE-01"]
    assert page.total == 1
