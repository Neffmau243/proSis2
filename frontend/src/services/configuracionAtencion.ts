import http from './http'
import type { PageResponse } from '@/types/api'

export interface EstablishmentDraft {
  nombre: string
  abreviatura: string | null
  codigo_renaes: string | null
  codigo_ideess: string | null
  ubigeo_codigo: string | null
}
export interface EstablishmentAdmin extends EstablishmentDraft {
  id: number
  activo: boolean
  ubicacion: string | null
  consultorios_total: number
  fua_personal_atiende: string
  fua_lugar_atencion: string
  fua_codigo_aisped: string | null
  fua_renipress_preimpreso: boolean
}
export interface CareArea {
  codigo: string
  nombre: string
  activo: boolean
  es_area_base: boolean
  consultorios: {
    id: number
    nombre: string
    establecimiento_id: number
    establecimiento_nombre: string
    activo: boolean
  }[]
}
export const establecimientosAdmin = {
  async list(q: string, includeInactive: boolean, offset: number) {
    return (
      await http.get<PageResponse<EstablishmentAdmin>>('/configuracion/establecimientos', {
        params: { q: q.trim() || undefined, incluir_inactivos: includeInactive, limit: 25, offset },
      })
    ).data
  },
  async get(id: number) {
    return (await http.get<EstablishmentAdmin>(`/configuracion/establecimientos/${id}`)).data
  },
  async save(draft: EstablishmentDraft, id?: number) {
    return (
      id
        ? await http.patch<EstablishmentAdmin>(`/configuracion/establecimientos/${id}`, draft)
        : await http.post<EstablishmentAdmin>('/configuracion/establecimientos', draft)
    ).data
  },
  async setActive(id: number, active: boolean) {
    return (
      active
        ? await http.post<EstablishmentAdmin>(`/configuracion/establecimientos/${id}/reactivar`)
        : await http.delete<EstablishmentAdmin>(`/configuracion/establecimientos/${id}`)
    ).data
  },
}
export const areasAtencion = {
  async list(includeInactive = false) {
    return (
      await http.get<CareArea[]>('/configuracion/areas', {
        params: { incluir_inactivos: includeInactive },
      })
    ).data
  },
  async save(nombre: string, code?: string) {
    return (
      code
        ? await http.patch<CareArea>(`/configuracion/areas/${encodeURIComponent(code)}`, { nombre })
        : await http.post<CareArea>('/configuracion/areas', { nombre })
    ).data
  },
  async setActive(code: string, active: boolean) {
    const path = `/configuracion/areas/${encodeURIComponent(code)}`
    return (
      active ? await http.post<CareArea>(`${path}/reactivar`) : await http.delete<CareArea>(path)
    ).data
  },
}
