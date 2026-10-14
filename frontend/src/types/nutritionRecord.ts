import type { EncounterLocationSnapshot } from './encounterLocation'

export type NutritionScope = 'NINO' | 'ADULTO' | 'GESTANTE' | 'PUERPERA' | 'DESCONOCIDO'

export interface NutritionCapture {
  hemoglobina?: number | null
  fecha_hemoglobina?: string | null
  hemoglobina_corregida?: number | null
  metodo_correccion_hb?: string | null
  hematocrito?: number | null
  altitud_msnm?: number | null
  edad_gestacional_semanas?: number | null
  estado_ganancia_peso?: string | null
  diagnostico?: string | null
  juntos?: boolean | null
  pin?: boolean | null
  crecer?: boolean | null
  nro_controles_cred?: number | null
  nro_sachets?: number | null
  nro_consejerias?: number | null
  nro_sesiones?: number | null
  nro_visitas?: number | null
  institucion_educativa?: string | null
  nivel_educativo?: string | null
  grado?: string | null
  turno?: string | null
  codigo_matricula?: string | null
  seccion?: string | null
  aula?: string | null
  p65?: number | null
  vl?: number | null
  cp?: number | null
  flag_legacy?: number | null
  pending_legacy?: boolean | null
}

type DecimalField = 'hemoglobina' | 'hemoglobina_corregida' | 'hematocrito' | 'altitud_msnm'
export interface NutritionRecord extends Omit<NutritionCapture, DecimalField> {
  id: number
  tipo: string | null
  hemoglobina: string | null
  hemoglobina_corregida: string | null
  hematocrito: string | null
  altitud_msnm: string | null
  imc: string | null
  whz: string | null
  haz: string | null
  waz: string | null
  estado_exportacion: 'PENDIENTE' | 'EXPORTADO' | 'ENVIADO' | null
  exportado_at: string | null
  enviado: boolean
  enviado_at: string | null
  constancia_envio: string | null
}

export interface ClinicalContext extends EncounterLocationSnapshot {
  version: number
  historia_clinica: string | null
  historia_familiar: string | null
  tipo_documento_codigo: string | null
  numero_documento: string | null
  sufijo_documento: string | null
  fecha_nacimiento: string
  sexo_codigo: string | null
  apellido_paterno: string | null
  apellido_materno: string | null
  primer_nombre: string | null
  otros_nombres: string | null
  condicion: string | null
  edad_detallada: string
  provincia: string | null
  distrito: string | null
  localidad: string | null
  sis: boolean | null
  establecimiento_nombre: string | null
  codigo_ideess: string | null
  codigo_renaes: string | null
  disa_codigo: string | null
  red_codigo: string | null
  microred_codigo: string | null
}
