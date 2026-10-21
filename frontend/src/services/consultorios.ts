import http from './http'

export interface OfficeResponse {
  id: number
  establecimiento_id: number
  consultorio_padre_id: number | null
  codigo: string
  nombre: string
  especialidad_codigo: string | null
  especialidad_requerida_codigo?: string | null
  activo: boolean
  area_codigo?: string | null
  area_nombre?: string | null
  servicios_codigos?: string[] | null
  servicios_habilitados?: { codigo: string; nombre: string; activo: boolean }[]
  ruta?: string
  activo_efectivo?: boolean
  establecimiento_nombre?: string | null
  consultorio_padre_nombre?: string | null
}

export interface OfficeCreatePayload {
  establecimiento_id: number
  codigo: string
  nombre: string
  consultorio_padre_id?: number | null
  especialidad_codigo?: string | null
  area_codigo?: string | null
  servicios_codigos?: string[] | null
}

/**
 * El PATCH no puede mover un consultorio de establecimiento: por eso el tipo
 * omite `establecimiento_id`.
 */
export type OfficeUpdatePayload = Omit<Partial<OfficeCreatePayload>, 'establecimiento_id'>

export interface OfficeAssignmentResponse {
  consultorio_id: number
  profesional_id: number
  fecha_inicio: string
  fecha_fin: string | null
  es_responsable: boolean
}

export interface OfficeAssignmentCreatePayload {
  profesional_id: number
  fecha_inicio: string
  fecha_fin?: string | null
  es_responsable: boolean
  vincular_area?: boolean
}

export interface OfficeListParams {
  establecimientoId?: number
  incluirInactivos?: boolean
}

export const consultorios = {
  /** `incluir_inactivos` y `establecimiento_id` son los únicos filtros del backend. */
  async list(params: OfficeListParams = {}): Promise<OfficeResponse[]> {
    const query: Record<string, unknown> = {}
    if (params.establecimientoId) query.establecimiento_id = params.establecimientoId
    if (params.incluirInactivos) query.incluir_inactivos = true
    const { data } = await http.get<OfficeResponse[]>('/configuracion/consultorios', {
      params: Object.keys(query).length ? query : undefined,
    })
    return data
  },
  async get(id: number): Promise<OfficeResponse> {
    const { data } = await http.get<OfficeResponse>(`/configuracion/consultorios/${id}`)
    return data
  },
  async create(payload: OfficeCreatePayload): Promise<OfficeResponse> {
    const { data } = await http.post<OfficeResponse>('/configuracion/consultorios', payload)
    return data
  },
  async update(id: number, payload: OfficeUpdatePayload): Promise<OfficeResponse> {
    const { data } = await http.patch<OfficeResponse>(`/configuracion/consultorios/${id}`, payload)
    return data
  },
  async deactivate(id: number): Promise<OfficeResponse> {
    const { data } = await http.delete<OfficeResponse>(`/configuracion/consultorios/${id}`)
    return data
  },
  /** Puede devolver `[]`: sin asignaciones históricas no es un error. */
  async listAssignments(officeId: number): Promise<OfficeAssignmentResponse[]> {
    const { data } = await http.get<OfficeAssignmentResponse[]>(
      `/configuracion/consultorios/${officeId}/profesionales`,
    )
    return data
  },
  async assign(
    officeId: number,
    payload: OfficeAssignmentCreatePayload,
  ): Promise<OfficeAssignmentResponse> {
    const { data } = await http.post<OfficeAssignmentResponse>(
      `/configuracion/consultorios/${officeId}/profesionales`,
      payload,
    )
    return data
  },
  /** `startDate` identifica la asignación: es su fecha de inicio (`YYYY-MM-DD`). */
  async closeAssignment(
    officeId: number,
    professionalId: number,
    startDate: string,
    fechaFin: string,
  ): Promise<OfficeAssignmentResponse> {
    const { data } = await http.patch<OfficeAssignmentResponse>(
      `/configuracion/consultorios/${officeId}/profesionales/${professionalId}/${startDate}/cierre`,
      { fecha_fin: fechaFin },
    )
    return data
  },
}
