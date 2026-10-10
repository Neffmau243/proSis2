import type { PatientSisData } from '@/utils/patientSis'

export type ResponsibleRelationship = 'MADRE' | 'PADRE' | 'TUTOR'

export interface ResponsibleRow {
  parentesco: ResponsibleRelationship
  nombre_completo: string
  tipo_documento_codigo: string | null
  numero_documento: string | null
  telefono: string | null
  es_principal: boolean
}

export interface RiskRow {
  grupo_riesgo_id: number | null
  fecha_inicio: string
  fecha_fin: string | null
  observacion: string
}

export interface PatientRegistrationDraft extends PatientSisData {
  sufijo_documento?: string
  tipo_documento_codigo: string
  numero_documento: string
  historia_clinica: string
  historia_familiar: string
  apellido_paterno: string
  apellido_materno: string
  primer_nombre: string
  otros_nombres: string
  fecha_nacimiento: string
  sexo_codigo: string | null
  fecha_inscripcion: string
  seguro_id: number | null
  establecimiento_registro_id: number | null
  ubigeo_residencia_codigo: string | null
  localidad: string
  localidad_id: number | null
  direccion: string
  telefono_principal: string
  condicion: string
  responsables: ResponsibleRow[]
  riesgos: RiskRow[]
}

export type PatientRegistrationPatch = Partial<PatientRegistrationDraft>
