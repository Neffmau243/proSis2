"""Staff catalog names can change; IDs, codes and status remain immutable."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=2, max_length=100)]

    @field_validator("nombre", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> Any:
        return " ".join(value.split()).upper() if isinstance(value, str) else value


class SpecialtyCreate(ProfessionCreate):
    nombre: Annotated[str, Field(min_length=2, max_length=150)]
    es_area: bool = False
    grupo: Annotated[str, Field(min_length=1, max_length=100)] | None = None

    @field_validator("grupo", mode="before")
    @classmethod
    def normalize_group(cls, value: Any) -> Any:
        if isinstance(value, str):
            return " ".join(value.split()).upper() or None
        return value


class ProfessionUpdate(ProfessionCreate):
    """Rename a profession without replacing its identity."""


class SpecialtyUpdate(ProfessionCreate):
    nombre: Annotated[str, Field(min_length=2, max_length=150)]
    es_area: bool | None = None
