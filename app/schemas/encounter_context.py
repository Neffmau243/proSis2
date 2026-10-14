"""Server-owned territorial and care hierarchy frozen at encounter creation."""

from pydantic import BaseModel, Field


class EncounterLocationSnapshot(BaseModel):
    ubigeo_residencia_codigo: str | None = None
    departamento: str | None = None
    provincia: str | None = None
    distrito: str | None = None
    localidad_id: int | None = None
    localidad_codigo_catalogo: str | None = None
    localidad_codigo_sis: str | None = None
    localidad: str | None = None
    direccion: str | None = None
    establecimiento_registro_id: int | None = None
    establecimiento_registro_nombre: str | None = None
    establecimiento_id: int | None = None
    establecimiento_nombre: str | None = None
    establecimiento_ubigeo_codigo: str | None = None
    establecimiento_departamento: str | None = None
    establecimiento_provincia: str | None = None
    establecimiento_distrito: str | None = None
    consultorio_id: int | None = None
    consultorio_codigo: str | None = None
    consultorio_nombre: str | None = None
    consultorio_ruta: str | None = None
    consultorio_padre_id: int | None = None
    consultorio_ancestros_ids: list[int] = Field(default_factory=list)
    area_codigo: str | None = None
    especialidad_codigo: str | None = None
    especialidad_nombre: str | None = None
    profesional_id: int | None = None
    profesional_nombre: str | None = None
