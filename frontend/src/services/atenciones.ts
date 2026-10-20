import http from './http'
import type { ClinicalContext, NutritionCapture, NutritionRecord } from '@/types/nutritionRecord'
import type { PageResponse } from '@/types/api'
import type { FuaPrintInput, FuaPrintSnapshot } from '@/types/fua'

/** Población clínica declarada durante la admisión. */
export type CareGroupCode = 'NINOS_ADOLESCENTES_ADULTOS_MAYORES' | 'GESTANTES' | 'PUERPERAS'

/** Pluralidad de la gestación, registrada para Gestantes y Puérperas. */
export type PregnancyTypeCode = 'UNICO' | 'MULTIPLE'

export interface AttentionServiceItem {
  numero_orden: number
  prestacion_codigo: string
  cantidad: string
}

export interface AttentionDiagnosisItem {
  numero_orden: number
  cie10_codigo: string
  tipo_diagnostico: string | null
  observacion: string | null
}

export interface Attention {
  numero_referencia_ingreso?: string | null
  numero_contrarreferencia_ingreso?: string | null
  contexto_clinico?: ClinicalContext | null
  evaluaciones_nutricionales?: NutritionRecord[]
  valoracion_calculada?: NutritionalIndicatorsPreview | null
  fua_impresion: FuaPrintSnapshot | null
  id: number
  paciente_id: number
  establecimiento_id: number
  establecimiento_nombre?: string | null
  profesional_id: number | null
  profesional_nombre?: string | null
  especialidad_codigo: string | null
  especialidad_nombre?: string | null
  consultorio_id: number | null
  consultorio_nombre: string | null
  consultorio_ruta?: string | null
  modalidad_atencion_codigo: string
  grupo_etario_codigo: string
  grupo_atencion_codigo: CareGroupCode
  fecha_atencion: string
  fecha_atendido: string | null
  historia_clinica_snapshot: string | null
  edad_anios: number | null
  edad_detallada: string | null
  peso_kg: string | null
  talla_cm: string | null
  perimetro_abdominal_cm: string | null
  tipo_embarazo_codigo: string | null
  peso_antes_embarazo_kg: string | null
  fecha_probable_parto: string | null
  fecha_parto: string | null
  presion_sistolica: number | null
  presion_diastolica: number | null
  temperatura_c: string | null
  imc: string | null
  pe: string | null
  te: string | null
  pt: string | null
  referencia_nutricional: string | null
  hora_inicio: string | null
  hora_fin: string | null
  admision: string | null
  observaciones: string | null
  estado: string
  created_by_usuario_id: number | null
  created_at: string
  updated_at: string
  prestaciones: AttentionServiceItem[]
  diagnosticos: AttentionDiagnosisItem[]
}

export interface AttentionSearchParams {
  fecha_hora_desde?: string
  fecha_hora_hasta?: string
  paciente_id?: number
  consultorio_id?: number
  establecimiento_id?: number
  profesional_id?: number
  desde?: string
  hasta?: string
  estado?: 'ATENDIDO' | 'ANULADO'
  limit: number
  offset: number
}

export interface NutritionalSnapshotPayload extends NutritionCapture {
  diagnostico_peso_edad?: string | null
  diagnostico_talla_edad?: string | null
  diagnostico_peso_talla?: string | null
}

export interface AttentionCreatePayload {
  numero_referencia_ingreso?: string | null
  numero_contrarreferencia_ingreso?: string | null
  fua_datos?: FuaPrintInput | null
  paciente_id: number
  establecimiento_id: number
  profesional_id: number | null
  especialidad_codigo?: string | null
  consultorio_id: number | null
  modalidad_atencion_codigo: 'AMBULATORIA' | 'REFERENCIA' | 'EMERGENCIA'
  grupo_atencion_codigo?: CareGroupCode
  fecha_atencion: string
  fecha_atendido?: string | null
  peso_kg?: number | null
  talla_cm?: number | null
  perimetro_abdominal_cm?: number | null
  tipo_embarazo_codigo?: PregnancyTypeCode | null
  peso_antes_embarazo_kg?: number | null
  fecha_probable_parto?: string | null
  fecha_parto?: string | null
  presion_sistolica?: number | null
  presion_diastolica?: number | null
  temperatura_c?: number | null
  hora_inicio?: string | null
  hora_fin?: string | null
  admision?: string | null
  observaciones?: string | null
  prestaciones?: { prestacion_codigo: string; cantidad: string }[]
  diagnosticos?: {
    cie10_codigo: string
    tipo_diagnostico?: string | null
    observacion?: string | null
  }[]
  valoracion_nutricional?: NutritionalSnapshotPayload | null
}

export interface NutritionalIndicatorsPreviewPayload {
  grupo_atencion_codigo?: CareGroupCode
  peso_antes_embarazo_kg?: number | null
  paciente_id: number
  fecha_atencion: string
  peso_kg?: number | null
  talla_cm?: number | null
}

export interface NutritionalIndicatorsPreview {
  version_calculo?: string | null
  seguimiento?: {
    version: string
    mensaje: string
    tamizaje: 'NO_EVALUADO'
    tendencia: {
      estado: 'NO_APLICA' | 'DATOS_INSUFICIENTES' | 'COMPARADO'
      mensaje: string
      fecha_anterior?: string
      dias?: number
      cambio_peso_kg?: string
      cambio_talla_cm?: string
    }
    sugerencias: readonly {
      codigo: string
      motivo: string
      metodo: string
      requiere_confirmacion: boolean
    }[]
  } | null
  grupo_referencia?: 'INFANTIL' | 'ESCOLAR' | 'ADULTO' | 'ADULTO_MAYOR' | 'GESTANTE' | 'PUERPERA'
  imc_edad?: string | null
  diagnostico_imc?: string | null
  imc_pregestacional?: string | null
  ganancia_peso_kg?: string | null
  diagnostico_peso_edad?: string | null
  diagnostico_talla_edad?: string | null
  diagnostico_peso_talla?: string | null
  imc: string | null
  pe: string | null
  te: string | null
  pt: string | null
  estado: string
  mensaje: string
  referencia: string | null
}

export interface FuaIssuePayload {
  atencion_id: number
  observaciones?: string | null
}

export interface FuaResponse {
  id: number
  atencion_id: number
  numero_fua: string | null
  codigo_renipress: string | null
  lote_fua: string | null
  correlativo_fua: string | null
  codigo_ciudad: string | null
  codigo_anio: string | null
  codigo_eess: string | null
  edad_declarada: string | null
  fecha_emision: string
  estado: string
  observaciones: string | null
}

export interface CertificateIssuePayload {
  atencion_id: number
  tipo: string
  profesional_id?: number | null
  prestaciones?: string[]
}

export interface CertificateResponse {
  id: number
  atencion_id: number
  establecimiento_id: number
  profesional_id: number
  numero_certificado: string
  tipo: string
  fecha_emision: string
  consultorio: string | null
  admision: string | null
  estado: string
  prestaciones: string[]
}

export interface ReferralCreatePayload {
  atencion_id: number
  tipo: string
  establecimiento_destino_id: number
  motivo: string
  observaciones?: string | null
  estado: 'PENDIENTE'
}

export interface ReferralResponse {
  id: number
  atencion_id: number
  numero_referencia: string | null
  tipo: string
  establecimiento_origen_id: number
  establecimiento_destino_id: number
  fecha_emision: string
  motivo: string | null
  observaciones: string | null
  estado: string
}

export const atenciones = {
  async exportNutrition(id: number): Promise<Record<string, unknown>> {
    const { data } = await http.post<Record<string, unknown>>(
      `/atenciones/${id}/nutricion/exportacion`,
    )
    return data
  },
  async confirmNutritionSent(id: number, constancia: string): Promise<Attention> {
    const { data } = await http.post<Attention>(`/atenciones/${id}/nutricion/envio`, { constancia })
    return data
  },
  async search(params: AttentionSearchParams): Promise<PageResponse<Attention>> {
    const { data } = await http.get<PageResponse<Attention>>('/atenciones/busqueda', {
      params,
    })
    return data
  },
  /** Últimas cinco atenciones visibles; el historial completo usa search con paginación. */
  async listByPatient(patientId: number): Promise<Attention[]> {
    const { data } = await http.get<Attention[]>('/atenciones', {
      params: { paciente_id: patientId },
    })
    return data
  },
  async get(id: number): Promise<Attention> {
    const { data } = await http.get<Attention>(`/atenciones/${id}`)
    return data
  },
  async create(payload: AttentionCreatePayload): Promise<Attention> {
    const { data } = await http.post<Attention>('/atenciones', payload)
    return data
  },
  async previewNutritionalIndicators(
    payload: NutritionalIndicatorsPreviewPayload,
  ): Promise<NutritionalIndicatorsPreview> {
    const { data } = await http.post<NutritionalIndicatorsPreview>(
      '/atenciones/indicadores-nutricionales/vista-previa',
      payload,
    )
    return data
  },
  async cancel(id: number, payload: { observaciones: string }): Promise<Attention> {
    const { data } = await http.post<Attention>(`/atenciones/${id}/anulacion`, payload)
    return data
  },
  async emitirFua(payload: FuaIssuePayload): Promise<FuaResponse> {
    const { data } = await http.post<FuaResponse>('/documentos/fua', payload)
    return data
  },
  async emitirCertificado(payload: CertificateIssuePayload): Promise<CertificateResponse> {
    const { data } = await http.post<CertificateResponse>('/documentos/certificados', payload)
    return data
  },
  async crearReferencia(payload: ReferralCreatePayload): Promise<ReferralResponse> {
    const { data } = await http.post<ReferralResponse>('/documentos/referencias', payload)
    return data
  },
}
