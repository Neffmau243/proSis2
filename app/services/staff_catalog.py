"""Add catalog entries without changing qualifications, assignments or care areas."""

from collections.abc import Callable
from hashlib import sha256

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.office import AREA_NAMES
from app.domain.staff_catalog import catalog_name_key, is_care_area, is_staff_specialty_code
from app.exceptions import ConflictError, NotFoundError
from app.mappers.catalog import profession_to_catalog_item, specialty_to_catalog_item
from app.models.catalog import Profession, Specialty
from app.repositories.staff_catalog import StaffCatalogRepository
from app.schemas.catalog import IdCatalogItem, SpecialtyCatalogItem
from app.schemas.staff_catalog import (
    ProfessionCreate,
    ProfessionUpdate,
    SpecialtyCreate,
    SpecialtyUpdate,
)


class StaffCatalogService:
    def __init__(self, session: Session, audit: Callable[..., None] | None = None) -> None:
        self._session = session
        self._repository = StaffCatalogRepository(session)
        self._audit = audit

    def create_profession(self, command: ProfessionCreate, *, actor_id: int) -> IdCatalogItem:
        try:
            if self._repository.profession_name_exists(command.nombre):
                raise ConflictError(
                    code="PROFESION_DUPLICADA",
                    message="Ya existe una profesión con ese nombre, incluso entre las inactivas.",
                )
            entity = Profession(nombre=command.nombre, activo=True)
            self._repository.add(entity)
            self._session.flush()
            response = profession_to_catalog_item(entity)
            self._record(actor_id, "profesiones", entity.id, response.model_dump())
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="PROFESION_DUPLICADA", message="Ya existe una profesión con ese nombre."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def create_specialty(self, command: SpecialtyCreate, *, actor_id: int) -> SpecialtyCatalogItem:
        try:
            if self._repository.specialty_name_exists(command.nombre):
                raise ConflictError(
                    code="ESPECIALIDAD_DUPLICADA",
                    message=(
                        "Ya existe una especialidad con ese nombre, incluso entre las inactivas."
                    ),
                )
            # A stable internal key also prevents concurrent duplicate creates
            # for the same normalized name, without changing legacy codes.
            suffix = sha256(catalog_name_key(command.nombre).encode("utf-8")).hexdigest()[:16]
            attempt = 0
            # Renaming never changes a code. If that code was originally
            # derived from this name, allocate the next stable free key.
            while (occupied := self._repository.get_specialty(f"ESP-{suffix.upper()}")) is not None:
                if catalog_name_key(occupied.nombre) == catalog_name_key(command.nombre):
                    raise ConflictError(
                        code="ESPECIALIDAD_DUPLICADA",
                        message="Ya existe una especialidad con ese nombre.",
                    )
                attempt += 1
                key = f"{catalog_name_key(command.nombre)}:{attempt}"
                suffix = sha256(key.encode("utf-8")).hexdigest()[:16]
            entity = Specialty(
                codigo=f"ESP-{suffix.upper()}",
                nombre=command.nombre,
                grupo=command.grupo,
                es_area=command.es_area,
                activo=True,
            )
            self._repository.add(entity)
            self._session.flush()
            response = specialty_to_catalog_item(entity)
            # Audit IDs are numeric; the specialty key is retained in `after`.
            self._record(actor_id, "especialidades", None, response.model_dump())
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="ESPECIALIDAD_DUPLICADA", message="Ya existe una especialidad con ese nombre."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update_profession(
        self, identifier: int, command: ProfessionUpdate, *, actor_id: int
    ) -> IdCatalogItem:
        try:
            entity = self._repository.get_profession(identifier, lock=True)
            if entity is None:
                raise NotFoundError(
                    code="PROFESION_NO_ENCONTRADA", message="No existe la profesión."
                )
            if self._repository.profession_name_exists(command.nombre, exclude_id=identifier):
                raise ConflictError(
                    code="PROFESION_DUPLICADA", message="Ya existe una profesión con ese nombre."
                )
            before = profession_to_catalog_item(entity).model_dump()
            entity.nombre = command.nombre
            self._session.flush()
            response = profession_to_catalog_item(entity)
            self._record(actor_id, "profesiones", entity.id, response.model_dump(), before=before)
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="PROFESION_DUPLICADA", message="Ya existe una profesión con ese nombre."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def update_specialty(
        self, code: str, command: SpecialtyUpdate, *, actor_id: int
    ) -> SpecialtyCatalogItem:
        try:
            entity = self._repository.get_specialty(code, lock=True)
            if entity is None or not is_staff_specialty_code(entity.codigo):
                raise NotFoundError(
                    code="ESPECIALIDAD_NO_ENCONTRADA", message="No existe el área o especialidad."
                )
            if self._repository.specialty_name_exists(command.nombre, exclude_code=entity.codigo):
                raise ConflictError(
                    code="ESPECIALIDAD_DUPLICADA",
                    message="Ya existe una especialidad con ese nombre.",
                )
            before = specialty_to_catalog_item(entity).model_dump()
            if command.es_area is not None and command.es_area != is_care_area(entity):
                if entity.codigo in AREA_NAMES:
                    raise ConflictError(
                        code="AREA_BASE_PROTEGIDA",
                        message=(
                            "El tipo de esta área base se conserva porque organiza "
                            "servicios existentes."
                        ),
                    )
                if self._repository.specialty_operationally_used(entity.codigo):
                    raise ConflictError(
                        code="TIPO_CATALOGO_EN_USO",
                        message=(
                            "No se puede cambiar el tipo: este registro está vinculado a "
                            "consultorios o atenciones. Revise esos vínculos primero."
                        ),
                    )
                entity.es_area = command.es_area
            entity.nombre = command.nombre
            self._session.flush()
            response = specialty_to_catalog_item(entity)
            self._record(actor_id, "especialidades", None, response.model_dump(), before=before)
            self._session.commit()
            return response
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="ESPECIALIDAD_DUPLICADA", message="Ya existe una especialidad con ese nombre."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def delete_profession(self, identifier: int, *, actor_id: int) -> None:
        self._delete_entry(identifier, specialty=False, actor_id=actor_id)

    def delete_specialty(self, code: str, *, actor_id: int) -> None:
        self._delete_entry(code, specialty=True, actor_id=actor_id)

    def _delete_entry(self, identifier: int | str, *, specialty: bool, actor_id: int) -> None:
        try:
            entity = (
                self._repository.get_specialty(str(identifier), lock=True)
                if specialty
                else self._repository.get_profession(int(identifier), lock=True)
            )
            label = "especialidad" if specialty else "profesión"
            if entity is None or (specialty and not is_staff_specialty_code(entity.codigo)):
                raise NotFoundError(code="CATALOGO_NO_ENCONTRADO", message=f"No existe la {label}.")
            if specialty and entity.codigo in AREA_NAMES:
                raise ConflictError(
                    code="AREA_BASE_PROTEGIDA",
                    message=(
                        "Esta área base organiza los servicios de atención y no se puede eliminar."
                    ),
                )
            in_use = (
                self._repository.specialty_in_use(entity.codigo)
                if specialty
                else self._repository.profession_in_use(entity.id)
            )
            if in_use:
                raise ConflictError(
                    code="CATALOGO_EN_USO",
                    message=(
                        f"No se puede eliminar la {label}: está vinculada a profesionales, "
                        "consultorios o atenciones. Revise sus vínculos antes de eliminarla."
                    ),
                )
            before = (
                specialty_to_catalog_item(entity)
                if specialty
                else profession_to_catalog_item(entity)
            ).model_dump()
            self._repository.delete(entity)
            self._record(
                actor_id,
                "especialidades" if specialty else "profesiones",
                None if specialty else entity.id,
                None,
                before=before,
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                code="CATALOGO_EN_USO", message="El registro está en uso y no se puede eliminar."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def _record(
        self,
        actor_id: int,
        table: str,
        record_id: int | None,
        after: dict | None,
        *,
        before: dict | None = None,
    ) -> None:
        if self._audit is not None:
            self._audit(
                actor_id=actor_id,
                action="DELETE"
                if after is None
                else ("UPDATE" if before is not None else "INSERT"),
                table_name=table,
                record_id=record_id,
                before=before,
                after=after,
            )
