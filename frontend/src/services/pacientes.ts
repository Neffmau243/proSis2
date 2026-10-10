import http from './http'
import type { PageResponse } from '@/types/api'
import type { PatientSisData } from '@/utils/patientSis'

export interface PatientResponsible {
  id: number
  parentesco: string
  nombre_completo: string
  tipo_documento_codigo: string | null
  numero_documento: string | null
  telefono: string | null
  es_principal: boolean
  activo: boolean
}

export interface PatientRisk {
  grupo_riesgo_id: number
  fecha_inicio: string
  fecha_fin: string | null
  observacion: string | null
  grupo_riesgo_codigo: string | null
  grupo_riesgo_nombre: string | null
}

export interface Patient extends Partial<PatientSisData> {
  sufijo_documento?: string | null
  id: number
  codclie_legacy: number | null
  historia_clinica: string | null
  historia_familiar: string | null
  tipo_documento_codigo: string
  numero_documento: string
  fecha_inscripcion: string | null
  fecha_nacimiento: string
  apellido_paterno: string | null
  apellido_materno: string | null
  primer_nombre: string | null
  otros_nombres: string | null
  sexo_codigo: string | null
  ubigeo_residencia_codigo: string | null
  distrito_residencia: string | null
  localidad: string | null
  localidad_id: number | null
  direccion: string | null
  establecimiento_registro_id: number | null
  seguro_id: number | null
  telefono_principal: string | null
  condicion: string | null
  estado: boolean
  created_at: string
  updated_at: string
  responsables: PatientResponsible[]
  riesgos: PatientRisk[]
}

export interface PatientSearchParams {
  tipo_documento_codigo?: string
  numero_documento?: string
  historia_clinica?: string
  q?: string
  establecimiento_id?: number
  incluir_inactivos?: boolean
  limit: number
  offset: number
}

export interface ResponsibleCreatePayload {
  parentesco: 'MADRE' | 'PADRE' | 'TUTOR'
  nombre_completo: string
  tipo_documento_codigo?: string | null
  numero_documento?: string | null
  telefono?: string | null
  es_principal: boolean
  activo: boolean
}

export interface ResponsibleUpdatePayload {
  parentesco?: 'MADRE' | 'PADRE' | 'TUTOR'
  nombre_completo?: string
  tipo_documento_codigo?: string | null
  numero_documento?: string | null
  telefono?: string | null
  es_principal?: boolean
  activo?: boolean
}

export interface RiskCreatePayload {
  grupo_riesgo_id: number
  fecha_inicio: string
  fecha_fin?: string | null
  observacion?: string | null
}

export interface RiskUpdatePayload {
  fecha_fin?: string | null
  observacion?: string | null
}

export interface PatientCreatePayload extends Partial<PatientSisData> {
  sufijo_documento?: string | null
  historia_clinica?: string | null
  historia_familiar?: string | null
  tipo_documento_codigo: string
  numero_documento: string
  fecha_inscripcion?: string | null
  fecha_nacimiento: string
  apellido_paterno?: string | null
  apellido_materno?: string | null
  primer_nombre?: string | null
  otros_nombres?: string | null
  sexo_codigo?: string | null
  ubigeo_residencia_codigo?: string | null
  localidad?: string | null
  localidad_id?: number | null
  direccion?: string | null
  establecimiento_registro_id?: number | null
  seguro_id?: number | null
  telefono_principal?: string | null
  condicion?: string | null
  responsables?: ResponsibleCreatePayload[]
  riesgos?: RiskCreatePayload[]
}

/** Payload parcial del PATCH; el backend conserva los campos no enviados. */
export type PatientUpdatePayload = Partial<Omit<PatientCreatePayload, 'responsables' | 'riesgos'>>

export interface PatientDeactivationResponse {
  id: number
  estado: boolean
  mensaje: string
}

export const pacientes = {
  async search(params: PatientSearchParams): Promise<PageResponse<Patient>> {
    const { data } = await http.get<PageResponse<Patient>>('/patients', { params })
    return data
  },
  async get(id: number): Promise<Patient> {
    const { data } = await http.get<Patient>(`/patients/${id}`)
    return data
  },
  async create(payload: PatientCreatePayload): Promise<Patient> {
    const { data } = await http.post<Patient>('/patients', payload)
    return data
  },
  async update(id: number, payload: PatientUpdatePayload): Promise<Patient> {
    const { data } = await http.patch<Patient>(`/patients/${id}`, payload)
    return data
  },
  async deactivate(id: number): Promise<PatientDeactivationResponse> {
    const { data } = await http.delete<PatientDeactivationResponse>(`/patients/${id}`)
    return data
  },
  async addResponsible(
    patientId: number,
    payload: ResponsibleCreatePayload,
  ): Promise<PatientResponsible> {
    const { data } = await http.post<PatientResponsible>(
      `/patients/${patientId}/responsibles`,
      payload,
    )
    return data
  },
  async updateResponsible(
    patientId: number,
    responsibleId: number,
    payload: ResponsibleUpdatePayload,
  ): Promise<PatientResponsible> {
    const { data } = await http.patch<PatientResponsible>(
      `/patients/${patientId}/responsibles/${responsibleId}`,
      payload,
    )
    return data
  },
  async addRisk(patientId: number, payload: RiskCreatePayload): Promise<PatientRisk> {
    const { data } = await http.post<PatientRisk>(`/patients/${patientId}/risk-groups`, payload)
    return data
  },
  async updateRisk(
    patientId: number,
    riskGroupId: number,
    startDate: string,
    payload: RiskUpdatePayload,
  ): Promise<PatientRisk> {
    const { data } = await http.patch<PatientRisk>(
      `/patients/${patientId}/risk-groups/${riskGroupId}/${startDate}`,
      payload,
    )
    return data
  },
}
