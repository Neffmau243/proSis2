import http from './http'
import type { CodeCatalogItem } from './catalogos'

export interface CareService extends CodeCatalogItem {
  area_codigos: string[]
  consultorios: CareServiceOffice[]
}

export interface CareServiceOffice {
  id: number
  nombre: string
  codigo?: string
  consultorio_padre_id?: number | null
  consultorio_padre_nombre?: string | null
  establecimiento_id: number
  establecimiento_nombre?: string | null
  activo: boolean
}

export const serviciosAsistenciales = {
  async get(code: string): Promise<CareService> {
    const { data } = await http.get<CareService>(
      `/configuracion/servicios/${encodeURIComponent(code)}`,
    )
    return data
  },
  async list(includeInactive = false): Promise<CareService[]> {
    const { data } = await http.get<CareService[]>('/configuracion/servicios', {
      params: { incluir_inactivos: includeInactive },
    })
    return data
  },
  async create(payload: { nombre: string; area_codigo: string }): Promise<CareService> {
    const { data } = await http.post<CareService>('/configuracion/servicios', payload)
    return data
  },
  async update(code: string, nombre: string): Promise<CareService> {
    const { data } = await http.patch<CareService>(
      `/configuracion/servicios/${encodeURIComponent(code)}`,
      { nombre },
    )
    return data
  },
  async setActive(service: CareService): Promise<CareService> {
    const url = `/configuracion/servicios/${encodeURIComponent(service.codigo)}`
    const { data } = service.activo
      ? await http.delete<CareService>(url)
      : await http.post<CareService>(`${url}/reactivar`)
    return data
  },
}
