export interface FuaPrintInput {
  personal_atiende: 'IPRESS' | 'ITINERANTE' | 'AISPED' | null
  lugar_atencion: 'INTRAMURAL' | 'EXTRAMURAL' | null
  tipo_atencion: 'AMBULATORIA' | 'REFERENCIA' | 'EMERGENCIA' | null
  codigo_aisped: string | null
  codigo_renipress: string | null
  sis_diresa: string | null
  sis_tipo: string | null
  sis_numero: string | null
  sis_componente: string | null
  etnia_codigo: string | null
  referencia_renipress: string | null
  referencia_nombre: string | null
  referencia_hoja: string | null
}

export interface FuaPrintSnapshot extends FuaPrintInput {
  version: 1 | 2
  sis_secuencia?: string | null
  renipress_preimpreso?: boolean
  ipress_nombre: string
  profesional_nombre: string
  profesional_documento: string | null
  profesional_colegiatura: string | null
  tipo_documento: string
  tdi: '2' | '3' | null
  numero_documento: string
  apellido_paterno: string | null
  apellido_materno: string | null
  primer_nombre: string | null
  otros_nombres: string | null
  sexo_codigo: string | null
  fecha_nacimiento: string
  historia_clinica: string | null
  fecha_atencion: string
  hora_atencion: string
  peso_kg: string | number | null
  talla_cm: string | number | null
  presion_sistolica: number | null
  presion_diastolica: number | null
  imc: string | number | null
  perimetro_abdominal_cm: string | number | null
  grupo_atencion_codigo: string
  fecha_probable_parto: string | null
  fecha_parto: string | null
}
