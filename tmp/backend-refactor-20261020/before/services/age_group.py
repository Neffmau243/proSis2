"""Caso de uso para configurar y resolver grupos etarios."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.mappers.age_group import age_group_to_response
from app.models.catalog import AgeGroup
from app.repositories.age_group import AgeGroupRepository
from app.schemas.age_group import (
    AgeGroupConfigurationInput,
    AgeGroupRangeInput,
    AgeGroupResponse,
)


class AgeGroupService:
    """Mantiene rangos mutuamente excluyentes y los resuelve en servidor."""

    def __init__(
        self,
        session: Session,
        audit: Callable[..., None] | None = None,
    ) -> None:
        self._session = session
        self._repository = AgeGroupRepository(session)
        self._audit = audit

    def list(self) -> list[AgeGroupResponse]:
        return [age_group_to_response(group) for group in self._repository.list_all()]

    def configure(
        self,
        command: AgeGroupConfigurationInput,
        *,
        actor_id: int | None,
    ) -> list[AgeGroupResponse]:
        """Actualiza toda la configuración en una transacción con bloqueo de filas."""
        try:
            groups = self._repository.list_all(lock=True)
            existing_by_code = {group.codigo: group for group in groups}
            requested_by_code = {item.codigo: item for item in command.grupos}
            unknown = requested_by_code.keys() - existing_by_code.keys()
            if unknown:
                raise NotFoundError(
                    code="GRUPO_ETARIO_NO_ENCONTRADO",
                    message=f"No existen los grupos etarios: {', '.join(sorted(unknown))}",
                )
            missing = existing_by_code.keys() - requested_by_code.keys()
            if missing:
                raise BusinessRuleError(
                    code="CONFIGURACION_GRUPOS_INCOMPLETA",
                    message=(
                        "La configuración debe incluir todos los grupos etarios existentes: "
                        f"{', '.join(sorted(missing))}"
                    ),
                )

            self._validate_ranges(list(requested_by_code.values()), command.exigir_cobertura_continua)
            before = {group.codigo: self._snapshot(group) for group in groups}
            for code, item in requested_by_code.items():
                entity = existing_by_code[code]
                entity.edad_minima_meses = item.edad_minima_meses
                entity.edad_maxima_meses = item.edad_maxima_meses
                entity.activo = item.activo

            self._session.flush()
            if self._audit is not None:
                self._audit(
                    actor_id=actor_id,
                    action="UPDATE",
                    table_name="grupos_etarios",
                    record_id=None,
                    before=before,
                    after={group.codigo: self._snapshot(group) for group in groups},
                )
            self._session.commit()
            return [age_group_to_response(group) for group in groups]
        except Exception:
            self._session.rollback()
            raise

    def resolve(self, age_in_months: int) -> AgeGroup:
        group = self._repository.find_matching_active(age_in_months)
        if group is None:
            raise BusinessRuleError(
                code="GRUPO_ETARIO_NO_CONFIGURADO",
                message="No existe un grupo etario activo para la edad calculada",
            )
        return group

    @staticmethod
    def _validate_ranges(
        groups: list[AgeGroupRangeInput], require_continuity: bool
    ) -> None:
        active = sorted(
            (group for group in groups if group.activo),
            key=lambda group: group.edad_minima_meses if group.edad_minima_meses is not None else -1,
        )
        open_ended = [group for group in active if group.edad_maxima_meses is None]
        if len(open_ended) > 1:
            raise BusinessRuleError(
                code="MULTIPLES_GRUPOS_SIN_MAXIMO",
                message="Solo puede haber un grupo etario activo sin edad máxima",
            )

        previous: AgeGroupRangeInput | None = None
        for group in active:
            if group.edad_minima_meses is None:
                raise BusinessRuleError(
                    code="GRUPO_ETARIO_SIN_MINIMO",
                    message=f"El grupo {group.codigo} no tiene edad mínima",
                )
            if previous is not None:
                if previous.edad_maxima_meses is None:
                    raise BusinessRuleError(
                        code="RANGOS_ETARIOS_SUPERPUESTOS",
                        message="Un grupo sin edad máxima debe ser el último rango activo",
                    )
                if group.edad_minima_meses <= previous.edad_maxima_meses:
                    raise BusinessRuleError(
                        code="RANGOS_ETARIOS_SUPERPUESTOS",
                        message=f"Los grupos {previous.codigo} y {group.codigo} se superponen",
                    )
                if (
                    require_continuity
                    and group.edad_minima_meses != previous.edad_maxima_meses + 1
                ):
                    raise BusinessRuleError(
                        code="HUECO_RANGOS_ETARIOS",
                        message=f"Existe un hueco entre {previous.codigo} y {group.codigo}",
                    )
            previous = group

    @staticmethod
    def _snapshot(group: AgeGroup) -> dict[str, object]:
        return {
            "codigo": group.codigo,
            "edad_minima_meses": group.edad_minima_meses,
            "edad_maxima_meses": group.edad_maxima_meses,
            "activo": group.activo,
        }
