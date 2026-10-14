/** Values frozen by the server; never reconstructed from current catalogs. */
export interface EncounterLocationSnapshot {
  ubigeo_residencia_codigo?: string | null
  departamento?: string | null
  provincia?: string | null
  distrito?: string | null
  localidad_id?: number | null
  localidad_codigo_catalogo?: string | null
  localidad_codigo_sis?: string | null
  localidad?: string | null
  direccion?: string | null
  establecimiento_registro_id?: number | null
  establecimiento_registro_nombre?: string | null
  establecimiento_id?: number | null
  establecimiento_nombre?: string | null
  establecimiento_ubigeo_codigo?: string | null
  establecimiento_departamento?: string | null
  establecimiento_provincia?: string | null
  establecimiento_distrito?: string | null
  consultorio_id?: number | null
  consultorio_codigo?: string | null
  consultorio_nombre?: string | null
  consultorio_ruta?: string | null
  consultorio_padre_id?: number | null
  consultorio_ancestros_ids?: number[]
  area_codigo?: string | null
  especialidad_codigo?: string | null
  especialidad_nombre?: string | null
  profesional_id?: number | null
  profesional_nombre?: string | null
}
