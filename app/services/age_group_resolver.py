"""Read-only age-group resolution, separate from administrative configuration."""

from app.exceptions import BusinessRuleError
from app.models.catalog import AgeGroup
from app.repositories.age_group import AgeGroupRepository


class AgeGroupResolver:
    def __init__(self, repository: AgeGroupRepository) -> None:
        self._repository = repository

    def resolve(self, age_in_months: int) -> AgeGroup:
        group = self._repository.find_matching_active(age_in_months)
        if group is None:
            raise BusinessRuleError(
                code="GRUPO_ETARIO_NO_CONFIGURADO",
                message="No existe un grupo etario activo para la edad calculada",
            )
        return group
