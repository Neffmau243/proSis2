export interface OfficeForm {
  establecimiento_id: number | null
  codigo: string
  nombre: string
  especialidad_codigo: string | null
  area_codigo: string | null
  servicios_codigos: string[] | null
  consultorio_padre_id: number | null
}
