import http from './http'
import type { CodeCatalogItem } from './catalogos'

export type OfficeServiceAdd =
  { codigo: string; nombre?: never } | { nombre: string; codigo?: never }
export interface OfficeServiceAdded {
  consultorio: OfficeResponse
  servicio: CodeCatalogItem
}

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
  servicios_codigos?: string[] | null
  profesional_nombre?: string | null
  profesional_activo?: boolean
  consultorio_nombre?: string | null
  heredada?: boolean
}

export interface OfficeAssignmentCreatePayload {
  profesional_id: number
  fecha_inicio: string
  fecha_fin?: string | null
  es_responsable: boolean
  vincular_area?: boolean
  servicios_codigos?: string[] | null
}

export interface OfficeListParams {
  establecimientoId?: number
  incluirInactivos?: boolean
}

export interface OfficeAssignmentUpdatePayload {
  fecha_inicio: string
  fecha_fin: string | null
  es_responsable: boolean
  servicios_codigos: string[] | null
}

export const consultorios = {
  async listServices(officeId: number): Promise<CodeCatalogItem[]> {
    const { data } = await http.get<CodeCatalogItem[]>(
      `/configuracion/consultorios/${officeId}/servicios`,
    )
    return data
  },
  async addService(officeId: number, payload: OfficeServiceAdd): Promise<OfficeServiceAdded> {
    const { data } = await http.post<OfficeServiceAdded>(
      `/configuracion/consultorios/${officeId}/servicios`,
      payload,
    )
    return data
  },
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
  async reactivate(id: number): Promise<OfficeResponse> {
    const { data } = await http.post<OfficeResponse>(`/configuracion/consultorios/${id}/reactivar`)
    return data
  },
  /** Puede devolver `[]`: sin asignaciones históricas no es un error. */
  async listAssignments(
    officeId: number,
    options?: { includeInherited?: boolean; serviceCode?: string },
  ): Promise<OfficeAssignmentResponse[]> {
    const { data } = await http.get<OfficeAssignmentResponse[]>(
      `/configuracion/consultorios/${officeId}/profesionales`,
      {
        params: options
          ? {
              incluir_heredados: options.includeInherited,
              servicio_codigo: options.serviceCode,
            }
          : undefined,
      },
    )
    return data
  },
  async updateAssignmentServices(
    assignment: OfficeAssignmentResponse,
    services: string[] | null,
  ): Promise<OfficeAssignmentResponse> {
    const { data } = await http.patch<OfficeAssignmentResponse>(
      `/configuracion/consultorios/${assignment.consultorio_id}/profesionales/${assignment.profesional_id}/${assignment.fecha_inicio}/servicios`,
      { servicios_codigos: services },
    )
    return data
  },
  async updateAssignment(
    assignment: OfficeAssignmentResponse,
    payload: OfficeAssignmentUpdatePayload,
  ): Promise<OfficeAssignmentResponse> {
    const { data } = await http.patch<OfficeAssignmentResponse>(
      `/configuracion/consultorios/${assignment.consultorio_id}/profesionales/${assignment.profesional_id}/${assignment.fecha_inicio}`,
      payload,
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
