import http from './http'
import type { PageResponse } from '@/types/api'

export interface CodeCatalogItem {
  codigo: string
  nombre: string
  activo: boolean
}

export interface IdCatalogItem {
  regimen?: string | null
  id: number
  codigo: string
  nombre: string
  activo: boolean
}

/** Insurance plan as sourced from ETLSIS/EESS_SIS. */
export interface InsuranceCatalogItem extends IdCatalogItem {
  codigo_sis: string | null
  regimen: string | null
}

export interface FamilyHistoryCatalogItem {
  codigo: string
  nombre: string
  tipo: 'COLOR' | 'SECTOR'
  color_hex: string | null
  activo: boolean
}

export interface SpecialtyCatalogItem extends CodeCatalogItem {
  grupo: string | null
  area_codigos?: string[]
  es_area?: boolean
}

export interface ServiceCatalogItem {
  codigo: string
  descripcion: string
  grupo: string | null
  activo: boolean
}

export interface Cie10CatalogItem {
  codigo: string
  descripcion: string
  categoria: string | null
  activo: boolean
}

export interface AgeGroupCatalogItem extends CodeCatalogItem {
  edad_minima_meses: number | null
  edad_maxima_meses: number | null
}

export interface RiskGroupCatalogItem extends IdCatalogItem {
  descripcion: string | null
}

export interface EstablishmentCatalogItem {
  id: number
  codigo_renaes: string | null
  codigo_ideess: string | null
  disa_codigo: string | null
  nombre: string
  abreviatura: string | null
  activo: boolean
}

export interface OfficeCatalogItem {
  id: number
  establecimiento_id: number
  codigo: string
  nombre: string
  especialidad_codigo: string | null
  activo: boolean
  consultorio_padre_id?: number | null
  area_codigo?: string | null
  area_nombre?: string | null
  ruta?: string
  activo_efectivo?: boolean
  servicios_habilitados?: CodeCatalogItem[]
}

export interface ProfessionalCatalogItem {
  id: number
  nombre_completo: string
  colegiatura: string | null
  activo: boolean
}

export interface UbigeoCatalogItem {
  codigo: string
  departamento: string
  provincia: string
  distrito: string
  localidad: string | null
}

export interface LocalidadCatalogItem {
  id: number
  ubigeo_codigo: string
  codigo_sis: string
  nombre: string
  activo: boolean
}

async function getList<T>(path: string): Promise<T[]> {
  const { data } = await http.get<T[]>(path)
  return data
}

/** Arma los params omitiendo valores vacíos (el backend exige q >= 2 caracteres). */
function searchParams(params: Record<string, unknown>): Record<string, unknown> {
  const clean: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (key === 'q' && typeof value === 'string') {
      const query = value.trim()
      if (query.length >= 2) clean[key] = query
      continue
    }
    clean[key] = value
  }
  return clean
}

async function searchPage<T>(
  path: string,
  params: Record<string, unknown>,
): Promise<PageResponse<T>> {
  const { data } = await http.get<PageResponse<T>>(path, { params: searchParams(params) })
  return data
}

export const catalogos = {
  etnias: () => getList<CodeCatalogItem>('/catalogos/etnias'),
  tiposDocumento: () => getList<CodeCatalogItem>('/catalogos/tipos-documento'),
  sexos: () => getList<CodeCatalogItem>('/catalogos/sexos'),
  seguros: () => getList<InsuranceCatalogItem>('/catalogos/seguros'),
  profesiones: () => getList<IdCatalogItem>('/catalogos/profesiones'),
  especialidades: () => getList<SpecialtyCatalogItem>('/catalogos/especialidades'),
  modalidades: () => getList<CodeCatalogItem>('/catalogos/modalidades-atencion'),
  gruposEtarios: () => getList<AgeGroupCatalogItem>('/catalogos/grupos-etarios'),
  gruposRiesgo: () => getList<RiskGroupCatalogItem>('/catalogos/grupos-riesgo'),
  historiasFamiliares: (q: string | undefined, limit = 25, offset = 0) =>
    searchPage<FamilyHistoryCatalogItem>('/catalogos/historias-familiares', { q, limit, offset }),
  prestaciones: (q: string | undefined, limit = 25, offset = 0) =>
    searchPage<ServiceCatalogItem>('/catalogos/prestaciones', { q, limit, offset }),
  cie10: (q: string | undefined, limit = 25, offset = 0) =>
    searchPage<Cie10CatalogItem>('/catalogos/cie10', { q, limit, offset }),
  establecimientos: (q: string | undefined, limit = 25, offset = 0) =>
    searchPage<EstablishmentCatalogItem>('/catalogos/establecimientos', { q, limit, offset }),
  consultorios: (
    establecimientoId: number | undefined,
    q: string | undefined,
    limit = 25,
    offset = 0,
  ) =>
    searchPage<OfficeCatalogItem>('/catalogos/consultorios', {
      establecimiento_id: establecimientoId,
      q,
      limit,
      offset,
    }),
  profesionales: (
    q: string | undefined,
    limit = 25,
    offset = 0,
    consultorioId?: number,
    fecha?: string,
  ) =>
    searchPage<ProfessionalCatalogItem>('/catalogos/profesionales', {
      q,
      limit,
      offset,
      consultorio_id: consultorioId,
      fecha,
    }),
  ubigeos: (q: string | undefined, limit = 25, offset = 0) =>
    searchPage<UbigeoCatalogItem>('/catalogos/ubigeos', { q, limit, offset }),
  localidades: (ubigeoCodigo: string | undefined, q: string | undefined, limit = 50, offset = 0) =>
    searchPage<LocalidadCatalogItem>('/catalogos/localidades', {
      ubigeo_codigo: ubigeoCodigo,
      q,
      limit,
      offset,
    }),
}
