import http from './http'
import type { IdCatalogItem, SpecialtyCatalogItem } from './catalogos'

export interface StaffCatalogPayload {
  nombre: string
  grupo?: string | null
  es_area?: boolean
}

export const catalogosPersonal = {
  async deleteProfession(id: number): Promise<void> {
    await http.delete(`/configuracion/catalogos-personal/profesiones/${id}`)
  },
  async deleteSpecialty(codigo: string): Promise<void> {
    await http.delete(
      `/configuracion/catalogos-personal/especialidades/${encodeURIComponent(codigo)}`,
    )
  },
  async createProfession(nombre: string): Promise<IdCatalogItem> {
    const { data } = await http.post<IdCatalogItem>(
      '/configuracion/catalogos-personal/profesiones',
      { nombre },
    )
    return data
  },
  async createSpecialty(payload: StaffCatalogPayload): Promise<SpecialtyCatalogItem> {
    const { data } = await http.post<SpecialtyCatalogItem>(
      '/configuracion/catalogos-personal/especialidades',
      payload,
    )
    return data
  },
  async updateProfession(id: number, nombre: string): Promise<IdCatalogItem> {
    const { data } = await http.patch<IdCatalogItem>(
      `/configuracion/catalogos-personal/profesiones/${id}`,
      { nombre },
    )
    return data
  },
  async updateSpecialty(
    codigo: string,
    nombre: string,
    es_area?: boolean,
  ): Promise<SpecialtyCatalogItem> {
    const { data } = await http.patch<SpecialtyCatalogItem>(
      `/configuracion/catalogos-personal/especialidades/${encodeURIComponent(codigo)}`,
      { nombre, ...(es_area === undefined ? {} : { es_area }) },
    )
    return data
  },
}
