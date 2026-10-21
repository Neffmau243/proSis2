import type { FuaPrintInput, FuaPrintSnapshot } from '../types/fua.ts'

export function emptyFuaInput(): FuaPrintInput {
  return {
    personal_atiende: null,
    lugar_atencion: null,
    tipo_atencion: null,
    codigo_aisped: null,
    codigo_renipress: null,
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
    sis_componente: null,
    etnia_codigo: null,
    referencia_renipress: null,
    referencia_nombre: null,
    referencia_hoja: null,
  }
}

export function normalizeFuaText(key: keyof FuaPrintInput, value: string | null): string | null {
  // Names keep their separators while typing. The API trims them on save.
  return (key === 'referencia_nombre' ? value?.toUpperCase() : value?.trim().toUpperCase()) || null
}

/** Same structural checks as the API; no invented SIS or ethnicity catalog. */
export function validateFuaInput(value: FuaPrintInput): string[] {
  const errors: string[] = []
  const patterns: [keyof FuaPrintInput, RegExp, string][] = [
    ['codigo_renipress', /^\d{8}$/, 'RENIPRESS debe tener 8 dígitos.'],
    ['sis_diresa', /^[A-Z0-9]{3}$/, 'DIRESA debe tener 3 caracteres alfanuméricos.'],
    ['sis_tipo', /^[A-Z0-9]{1,2}$/, 'El tipo de afiliación debe tener uno o dos caracteres.'],
    ['sis_numero', /^[A-Z0-9-]{1,30}$/, 'Revise el número de afiliación SIS.'],
    ['sis_componente', /^[A-Z0-9-]{1,20}$/, 'Revise el componente de afiliación del RN.'],
    ['etnia_codigo', /^\d{1,3}$/, 'El código de etnia debe tener entre 1 y 3 dígitos.'],
    ['referencia_renipress', /^\d{8}$/, 'RENIPRESS de origen debe tener 8 dígitos.'],
  ]
  for (const [key, pattern, message] of patterns) {
    if (value[key] && !pattern.test(value[key]!)) errors.push(message)
  }
  const affiliate = [value.sis_diresa, value.sis_tipo, value.sis_numero]
  if ((affiliate.some(Boolean) || value.sis_componente) && !affiliate.slice(1).every(Boolean)) {
    errors.push('Complete tipo y número de afiliación SIS juntos.')
  }
  if (value.personal_atiende === 'AISPED' && !value.codigo_aisped)
    errors.push('Indique el código AISPED.')
  if (value.personal_atiende !== 'AISPED' && value.codigo_aisped)
    errors.push('El código AISPED solo corresponde a personal AISPED.')
  if (
    value.tipo_atencion === 'REFERENCIA' &&
    ![value.referencia_renipress, value.referencia_nombre, value.referencia_hoja].every(Boolean)
  ) {
    errors.push('Complete RENIPRESS, nombre de origen y hoja de referencia.')
  }
  if (
    value.tipo_atencion !== 'REFERENCIA' &&
    [value.referencia_renipress, value.referencia_nombre, value.referencia_hoja].some(Boolean)
  )
    errors.push('Los datos de referencia requieren atención REFERENCIA.')
  return errors
}

const LOCAL_DOCUMENT_LABELS: Record<string, string> = {
  PAS: 'Pasaporte',
  DE: 'Documento extranjero',
  OTRO: 'Otro documento',
}

export function fuaIdentityProblem(s: FuaPrintSnapshot): string | null {
  if (!s.numero_documento?.trim())
    return 'Falta el número de documento. Revise la identificación guardada.'
  const expected = ({ DNI: '2', CE: '3' } as Record<string, string>)[s.tipo_documento]
  if (Object.hasOwn(LOCAL_DOCUMENT_LABELS, s.tipo_documento) && s.tdi == null) return null
  if (!expected || s.tdi !== expected) {
    return 'La identificación guardada tiene un tipo o TDI inconsistente. Revise el registro antes de imprimir.'
  }
  return null
}

/**
 * Recuadro único de parto del formato: FPP en la gestante y fecha real del
 * parto en la puérpera. En el grupo general no aplica.
 */
export function fuaDeliveryBox(
  s: FuaPrintSnapshot,
): { label: string; value: string | null } | null {
  if (s.grupo_atencion_codigo === 'PUERPERAS') {
    return { label: 'Fecha del parto', value: s.fecha_parto ?? null }
  }
  if (s.grupo_atencion_codigo === 'GESTANTES') {
    return { label: 'Fecha probable de parto', value: s.fecha_probable_parto ?? null }
  }
  return null
}

/** El perímetro abdominal solo se captura en el grupo general. */
export function fuaUsesAbdominalPerimeter(s: FuaPrintSnapshot): boolean {
  return s.grupo_atencion_codigo !== 'GESTANTES' && s.grupo_atencion_codigo !== 'PUERPERAS'
}

/** Validate only the frozen maternal value, including a recorded zero. */
function gestationalWeeksForPrint(s: FuaPrintSnapshot): string {
  const weeks = s.edad_gestacional_semanas
  return s.grupo_atencion_codigo === 'GESTANTES' &&
    typeof weeks === 'number' && Number.isInteger(weeks) && weeks >= 0 && weeks <= 45
    ? String(weeks) : ''
}

export function fuaWarnings(s: FuaPrintSnapshot): string[] {
  const result: string[] = []
  const delivery = fuaDeliveryBox(s)
  const required: [unknown, string][] = [
    [s.personal_atiende, 'Personal que atiende'],
    [s.lugar_atencion, 'Lugar de atención'],
    [s.renipress_preimpreso !== false || s.codigo_renipress, 'RENIPRESS'],
    [s.sis_diresa && s.sis_tipo && s.sis_numero, 'Afiliación SIS completa'],
    [s.historia_clinica, 'Historia clínica'],
    [s.profesional_documento, 'Documento del profesional responsable'],
    [s.profesional_colegiatura, 'Colegiatura del profesional (cuando corresponda)'],
    [s.peso_kg, 'Peso'],
    [s.talla_cm, 'Talla'],
    [s.presion_sistolica && s.presion_diastolica, 'Presión arterial completa'],
    [s.imc, 'IMC'],
    // En gestantes y puérperas el recuadro lo ocupa la fecha de parto, no el PAB.
    [!fuaUsesAbdominalPerimeter(s) || s.perimetro_abdominal_cm, 'Perímetro abdominal'],
    ...(delivery ? [[delivery.value, delivery.label] as [unknown, string]] : []),
    [s.grupo_atencion_codigo !== 'GESTANTES' || gestationalWeeksForPrint(s) !== '',
      'Edad gestacional'],
    [s.etnia_codigo, 'Etnia (cuando corresponda)'],
  ]
  for (const [value, label] of required) if (!value) result.push(label)
  const identityProblem = fuaIdentityProblem(s)
  if (identityProblem) result.push(identityProblem)
  return result
}

export interface FuaField {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
  font: number
  step: number
  skip: number
  enabled: boolean
}
export interface FuaLayout {
  version: 1
  template?: 'sis-v02'
  width: number
  height: number
  offsetX: number
  offsetY: number
  calibrated: boolean
  fields: FuaField[]
}

/** Baseline paper profile used by the FUA preview and the printed page. */
export const FUA_DEFAULT_PAPER_MM = Object.freeze({ width: 216, height: 356 })
const FUA_REFERENCE_GRID_PX = Object.freeze({ width: 598, height: 989 })
const FUA_REFERENCE_MARGIN_MM = 10

// Field labels and character pitch; all initial geometry uses the official annex.
const seeds: [string, string, number?][] = [
  ['codigo_renipress', 'RENIPRESS'],
  ['ipress_nombre', 'Nombre IPRESS'],
  ['personal_ipress', 'X · De la IPRESS'],
  ['personal_itinerante', 'X · Itinerante'],
  ['personal_aisped', 'X · AISPED'],
  ['codigo_aisped', 'Código AISPED'],
  ['lugar_intramural', 'X · Intramural'],
  ['lugar_extramural', 'X · Extramural'],
  ['atencion_ambulatoria', 'X · Ambulatoria'],
  ['atencion_referencia', 'X · Referencia'],
  ['atencion_emergencia', 'X · Emergencia'],
  ['referencia_renipress', 'Referencia · RENIPRESS'],
  ['referencia_nombre', 'Referencia · IPRESS origen'],
  ['referencia_hoja', 'Referencia · Hoja'],
  ['tdi', 'TDI'],
  ['numero_documento', 'Documento'],
  ['sis_diresa', 'SIS · DIRESA'],
  ['sis_tipo', 'SIS · Tipo'],
  ['sis_numero', 'SIS · Número / RN'],
  ['apellido_paterno', 'Apellido paterno'],
  ['apellido_materno', 'Apellido materno'],
  ['primer_nombre', 'Primer nombre'],
  ['otros_nombres', 'Otros nombres'],
  ['sexo_m', 'X · Masculino'],
  ['sexo_f', 'X · Femenino'],
  ['nacimiento_dia', 'Nacimiento · Día', 7],
  ['nacimiento_mes', 'Nacimiento · Mes', 7],
  ['nacimiento_anio', 'Nacimiento · Año', 8],
  ['historia_clinica', 'Historia clínica'],
  ['etnia_codigo', 'Código etnia'],
  ['gestante', 'X · Gestante'],
  ['puerpera', 'X · Puérpera'],
  ['edad_gestacional_semanas', 'Edad gestacional (semanas)'],
  ['parto_dia', 'Parto · Día', 7],
  ['parto_mes', 'Parto · Mes', 7],
  ['parto_anio', 'Parto · Año', 8],
  ['atencion_dia', 'Atención · Día', 5],
  ['atencion_mes', 'Atención · Mes', 5],
  ['atencion_anio', 'Atención · Año', 5.5],
  ['hora_hh', 'Hora', 3],
  ['hora_mm', 'Minutos', 3],
  ['peso_kg', 'Peso (kg)'],
  ['talla_cm', 'Talla (cm)'],
  ['pa', 'PA (mmHg)'],
  ['imc', 'IMC (kg/m²)'],
  ['perimetro_abdominal_cm', 'PAB (cm)'],
  ['profesional_documento', 'Responsable · DNI'],
  ['profesional_nombre', 'Responsable · Nombre'],
  ['profesional_colegiatura', 'Responsable · Colegiatura'],
  ['identity_note', 'Leyenda de documento · uso local'],
]

// Coordinates in the extracted annex 1 (page 11, 598 × 989 px).
// Kept separate so existing physical calibrations are never moved on upgrade.
const officialPositions: Record<string, [number, number, number]> = {
  codigo_renipress: [4, 104, 138],
  ipress_nombre: [151, 104, 441],
  personal_ipress: [58, 138, 10],
  personal_itinerante: [58, 153, 10],
  personal_aisped: [58, 168, 10],
  codigo_aisped: [72, 140, 70],
  lugar_intramural: [197, 138, 10],
  lugar_extramural: [197, 153, 10],
  atencion_ambulatoria: [269, 138, 10],
  atencion_referencia: [269, 153, 10],
  atencion_emergencia: [269, 168, 10],
  referencia_renipress: [283, 154, 78],
  referencia_nombre: [369, 154, 114],
  referencia_hoja: [491, 154, 101],
  tdi: [14, 210, 28],
  numero_documento: [50, 210, 70],
  sis_diresa: [128, 210, 29],
  sis_tipo: [164, 210, 25],
  sis_numero: [197, 210, 65],
  apellido_paterno: [4, 235, 259],
  apellido_materno: [274, 235, 318],
  primer_nombre: [4, 260, 259],
  otros_nombres: [274, 260, 318],
  sexo_m: [53, 291, 10],
  sexo_f: [53, 303, 10],
  nacimiento_dia: [139, 316, 37],
  nacimiento_mes: [184, 316, 35],
  nacimiento_anio: [228, 316, 82],
  historia_clinica: [321, 293, 97],
  etnia_codigo: [433, 293, 158],
  gestante: [53, 333, 10],
  puerpera: [53, 350, 10],
  edad_gestacional_semanas: [36, 651, 14],
  parto_dia: [139, 292, 37],
  parto_mes: [184, 292, 35],
  parto_anio: [228, 292, 82],
  atencion_dia: [7, 397, 25],
  atencion_mes: [39, 397, 23],
  atencion_anio: [73, 397, 62],
  hora_hh: [149, 397, 17],
  hora_mm: [175, 397, 17],
  peso_kg: [36, 577, 21],
  talla_cm: [104, 577, 25],
  pa: [178, 577, 38],
  imc: [256, 577, 21],
  perimetro_abdominal_cm: [307, 577, 24],
  profesional_documento: [4, 856, 103],
  profesional_nombre: [117, 856, 307],
  profesional_colegiatura: [435, 856, 157],
  identity_note: [4, 987, 590],
}

export function defaultFuaLayout(): FuaLayout {
  const printableWidth = FUA_DEFAULT_PAPER_MM.width - FUA_REFERENCE_MARGIN_MM * 2
  const printableHeight = FUA_DEFAULT_PAPER_MM.height - FUA_REFERENCE_MARGIN_MM * 2
  const grid = FUA_REFERENCE_GRID_PX
  return {
    version: 1,
    template: 'sis-v02',
    width: FUA_DEFAULT_PAPER_MM.width,
    height: FUA_DEFAULT_PAPER_MM.height,
    offsetX: 0,
    offsetY: 0,
    calibrated: false,
    fields: seeds.map(([id, label, step]) => {
      const [x, y, width] = officialPositions[id]!
      return {
        id,
        label,
        x: +(FUA_REFERENCE_MARGIN_MM + (x * printableWidth) / grid.width).toFixed(2),
        y: +(FUA_REFERENCE_MARGIN_MM + (y * printableHeight) / grid.height).toFixed(2),
        width: +((width * printableWidth) / grid.width).toFixed(2),
        height: ['peso_kg', 'talla_cm', 'pa', 'imc', 'perimetro_abdominal_cm'].includes(id)
          ? 2.8
          : 4,
        font: 8,
        step: step ?? 0,
        skip: 0,
        enabled: true,
      }
    }),
  }
}

export const FUA_LAYOUT_KEY = 'ipress.fua-layout.v1'
const bounded = (v: unknown, min: number, max: number): v is number =>
  typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max

/** Allowlist geometry only: local storage must never contain clinical values. */
export function parseFuaLayout(raw: string): FuaLayout {
  const v = JSON.parse(raw) as Omit<FuaLayout, 'template'> & { template?: 'historica' | 'sis-v02' }
  if (!v || (v.template != null && !['historica', 'sis-v02'].includes(v.template)))
    throw new Error('Plantilla de calibración inválida.')
  const template = defaultFuaLayout()
  if (
    v.version !== 1 ||
    !bounded(v.width, 100, 400) ||
    !bounded(v.height, 150, 600) ||
    !bounded(v.offsetX, -50, 50) ||
    !bounded(v.offsetY, -50, 50) ||
    !Array.isArray(v.fields)
  )
    throw new Error('Calibración inválida.')
  const legacySis = v.fields.find((f) => f.id === 'sis_numero_completo')
  const missingLegend = !v.fields.some((f) => f.id === 'identity_note')
  const missingGestationalAge = !v.fields.some((f) => f.id === 'edad_gestacional_semanas')
  const expectedIds = new Set(template.fields.map((f) => f.id))
  if (missingLegend) expectedIds.delete('identity_note')
  if (missingGestationalAge) expectedIds.delete('edad_gestacional_semanas')
  if (legacySis) {
    expectedIds.delete('sis_tipo')
    expectedIds.delete('sis_numero')
    expectedIds.add('sis_numero_completo')
  }
  if (
    v.fields.length !== expectedIds.size ||
    new Set(v.fields.map((f) => f.id)).size !== expectedIds.size ||
    v.fields.some((f) => !expectedIds.has(f.id))
  )
    throw new Error('Calibración inválida.')
  // Anchor the new boxes to DIRESA: an old combined field may have been
  // calibrated over the number box, leaving the type box empty.
  const sourceFields = v.fields.filter((f) => f.id !== 'sis_numero_completo')
  if (legacySis) {
    const diresa = v.fields.find((f) => f.id === 'sis_diresa')!
    const baseline = template.fields.find((f) => f.id === 'sis_diresa')!
    for (const original of template.fields.filter((f) =>
      ['sis_tipo', 'sis_numero'].includes(f.id),
    )) {
      sourceFields.push({
        ...legacySis,
        id: original.id,
        x: original.x + diresa.x - baseline.x,
        y: original.y + diresa.y - baseline.y,
        width: original.width,
        step: 0,
        skip: 0,
      })
    }
  }
  const fields = template.fields.map((original) => {
    const f = sourceFields.find((entry) => entry.id === original.id)
    if (!f && original.id === 'identity_note' && missingLegend) return original
    if (!f && original.id === 'edad_gestacional_semanas' && missingGestationalAge) {
      // Keep all existing positions; anchor the new maternal box to the weight
      // box's calibration, in the same section of the paper form.
      const weight = sourceFields.find((entry) => entry.id === 'peso_kg')!
      const baseline = template.fields.find((entry) => entry.id === 'peso_kg')!
      return { ...original, x: original.x + weight.x - baseline.x,
        y: original.y + weight.y - baseline.y }
    }
    if (
      !f ||
      !bounded(f.x, 0, 400) ||
      !bounded(f.y, 0, 600) ||
      !bounded(f.width, 1, 400) ||
      !bounded(f.height, 1, 30) ||
      !bounded(f.font, 5, 20) ||
      !bounded(f.step, 0, 15) ||
      !Number.isInteger(f.skip) ||
      !bounded(f.skip, 0, 2)
    )
      throw new Error('Posición inválida.')
    return {
      ...original,
      x: f.x,
      y: f.y,
      width: f.width,
      height: f.height,
      font: f.font,
      step: f.step,
      skip: f.skip,
      enabled: f.enabled !== false,
    }
  })
  return {
    version: 1,
    template: template.template,
    width: v.width,
    height: v.height,
    offsetX: v.offsetX,
    offsetY: v.offsetY,
    calibrated: v.calibrated === true && !missingLegend && !missingGestationalAge &&
      !legacySis && v.template === 'sis-v02',
    fields,
  }
}

export function fuaValues(s: FuaPrintSnapshot): Record<string, string> {
  const v: Record<string, string> = {}
  for (const [key, value] of Object.entries(s)) v[key] = value == null ? '' : String(value)
  const mark = (condition: boolean) => (condition ? 'X' : '')
  for (const code of ['IPRESS', 'ITINERANTE', 'AISPED'])
    v[`personal_${code.toLowerCase()}`] = mark(s.personal_atiende === code)
  for (const code of ['INTRAMURAL', 'EXTRAMURAL'])
    v[`lugar_${code.toLowerCase()}`] = mark(s.lugar_atencion === code)
  for (const code of ['AMBULATORIA', 'REFERENCIA', 'EMERGENCIA'])
    v[`atencion_${code.toLowerCase()}`] = mark(s.tipo_atencion === code)
  v.sexo_m = mark(s.sexo_codigo === 'M')
  v.sexo_f = mark(s.sexo_codigo === 'F')
  v.gestante = mark(s.grupo_atencion_codigo === 'GESTANTES')
  v.puerpera = mark(s.grupo_atencion_codigo === 'PUERPERAS')
  // Use only the frozen encounter value. A legacy FPP must never silently
  // produce a new age when an old FUA is opened or reprinted.
  v.edad_gestacional_semanas = gestationalWeeksForPrint(s)
  // DIRESA, type and affiliation number each have their own printed box.
  // Keep the optional RN suffix with the number, as in historical copies.
  v.sis_numero = [s.sis_numero, s.version === 2 ? s.sis_secuencia : s.sis_componente]
    .filter(Boolean)
    .join('-')
  // Even a previously saved calibration must not overprint a preprinted RENIPRESS.
  if (s.renipress_preimpreso !== false) v.codigo_renipress = ''
  // Local paper labels are not SIS codes; never mutate the saved snapshot/TDI.
  const localLabel = Object.hasOwn(LOCAL_DOCUMENT_LABELS, s.tipo_documento)
    ? LOCAL_DOCUMENT_LABELS[s.tipo_documento]
    : undefined
  if (localLabel && s.tdi == null) {
    v.tdi = s.tipo_documento
    v.identity_note = `${s.tipo_documento} = ${localLabel}. Uso local; no es un código TDI SIS.`
  }
  const partoDate = fuaDeliveryBox(s)?.value ?? null
  for (const [prefix, date] of [
    ['nacimiento', s.fecha_nacimiento],
    ['atencion', s.fecha_atencion],
    ['parto', partoDate],
  ]) {
    const [year = '', month = '', day = ''] = (date || '').slice(0, 10).split('-')
    v[`${prefix}_dia`] = day
    v[`${prefix}_mes`] = month
    v[`${prefix}_anio`] = year
  }
  v.hora_hh = s.hora_atencion.slice(0, 2)
  v.hora_mm = s.hora_atencion.slice(3, 5)
  v.pa =
    s.presion_sistolica && s.presion_diastolica
      ? `${s.presion_sistolica}/${s.presion_diastolica}`
      : ''
  for (const key of ['peso_kg', 'talla_cm', 'imc', 'perimetro_abdominal_cm']) {
    if (v[key]) v[key] = String(Number(Number(v[key]).toFixed(2)))
  }
  return v
}

/** Fit continuous text inside its calibrated box without changing positions or truncating it. */
export function fuaFieldFont(field: FuaField, value: string): number {
  // Stepped characters follow physical boxes: their pitch must remain calibrated.
  if (!value || field.step) return field.font
  const widthLimit = (field.width * 72) / (value.length * 25.4 * 0.61)
  const heightLimit = (field.height * 72) / (25.4 * 1.2)
  const fitted = Math.min(field.font, widthLimit, heightLimit)
  return Math.max(5, Math.floor(fitted * 100) / 100)
}

export function layoutProblems(layout: FuaLayout, values: Record<string, string>): string[] {
  const errors: string[] = []
  for (const id of ['tdi', 'numero_documento', 'identity_note']) {
    if (!values[id]) continue
    const field = layout.fields.find((f) => f.id === id)
    if (!field?.enabled || field.skip !== 0)
      errors.push(
        'La identificación y su leyenda deben imprimirse completas; active los campos y no omita caracteres.',
      )
  }
  for (const f of layout.fields.filter((field) => field.enabled)) {
    const value = (values[f.id] || '').slice(f.skip)
    if (!value) continue
    if (
      f.x + layout.offsetX < 0 ||
      f.y + layout.offsetY < 0 ||
      f.x + layout.offsetX + f.width > layout.width ||
      f.y + layout.offsetY + f.height > layout.height
    ) {
      errors.push(`${f.label}: fuera de la hoja`)
    }
    // Preview and print use the same fitted Courier font, with a 5 pt minimum.
    const font = fuaFieldFont(f, value)
    const charWidth = ((font * 25.4) / 72) * 0.61
    const needed = f.step
      ? Math.max(0, value.length - 1) * f.step + charWidth
      : value.length * charWidth
    if (needed > f.width || ((font * 25.4) / 72) * 1.2 > f.height)
      errors.push(`${f.label}: texto no cabe; ajuste ancho, paso o fuente`)
  }
  return errors
}

const escapeHtml = (s: string) =>
  s.replace(
    /[&<>"']/g,
    (c) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[c]!,
  )

export type FuaDocumentKind = 'atencion' | 'REF.Lab'

/** The browser uses the print document title as the suggested PDF filename. */
export function fuaDocumentTitle(
  values: Record<string, string>,
  test = false,
  documentKind: FuaDocumentKind = 'atencion',
): string {
  if (test) return 'Impresión FUA'
  const patientName = ['primer_nombre', 'otros_nombres', 'apellido_paterno', 'apellido_materno']
    .map((key) => values[key] || '')
    .join(' ')
    .normalize('NFC')
    .replace(/[<>:"/\\|?*]/g, ' ')
    .replace(/\p{Cc}/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[. ]+$/g, '')
  const attentionDate = values.fecha_atencion?.slice(0, 10) || ''
  const dateSuffix = /^\d{4}-\d{2}-\d{2}$/.test(attentionDate) ? attentionDate : ''
  return [documentKind, patientName, dateSuffix].filter(Boolean).join('-')
}

export function fuaPrintHtml(
  layout: FuaLayout,
  values: Record<string, string>,
  test = false,
  backgroundUrl?: string,
  backgroundInset = 0,
  documentKind: FuaDocumentKind = 'atencion',
): string {
  const safe = parseFuaLayout(JSON.stringify(layout))
  if (!bounded(backgroundInset, 0, 50)) throw new Error('Margen de referencia inválido.')
  const fields = safe.fields
    .filter((f) => f.enabled)
    .map((f) => {
      const value = test ? '+' : (values[f.id] || '').slice(f.skip)
      const font = test ? f.font : fuaFieldFont(f, value)
      const content =
        f.step && !test
          ? [...value]
              .map(
                (char, i) =>
                  `<span style="position:absolute;left:${i * f.step}mm">${escapeHtml(char)}</span>`,
              )
              .join('')
          : escapeHtml(value)
      return `<div style="position:absolute;left:${f.x + safe.offsetX}mm;top:${f.y + safe.offsetY}mm;width:${f.width}mm;height:${f.height}mm;font-size:${font}pt;${test ? 'outline:0.2mm solid #000;' : ''}">${content}</div>`
    })
    .join('')
  const background =
    backgroundUrl && !test
      ? `<img src="${escapeHtml(backgroundUrl)}" alt="FUA de referencia" style="position:absolute;left:${backgroundInset}mm;top:${backgroundInset}mm;width:${safe.width - 2 * backgroundInset}mm;height:${safe.height - 2 * backgroundInset}mm">`
      : ''
  const notice = background
    ? '<div style="position:absolute;left:10mm;top:2mm;font:8pt Arial,sans-serif">VISTA DE REVISIÓN · PRELLENADO PARCIAL · USO LOCAL</div>'
    : ''
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${escapeHtml(fuaDocumentTitle(values, test, documentKind))}</title><style>
    @page{size:${safe.width}mm ${safe.height}mm;margin:0}
    html,body{margin:0;padding:0;width:${safe.width}mm;height:${safe.height}mm}
    body{position:relative;color:#000;background:#fff;font-family:Courier New,monospace;line-height:1.2;white-space:nowrap}
    </style></head><body>${background}${notice}${fields}</body></html>`
}

export async function printFua(
  layout: FuaLayout,
  values: Record<string, string>,
  test = false,
  backgroundUrl?: string,
  backgroundInset = 0,
  documentKind: FuaDocumentKind = 'atencion',
): Promise<void> {
  if (!test && ((!backgroundUrl && !layout.calibrated) || layoutProblems(layout, values).length))
    throw new Error('Revise la calibración antes de imprimir.')
  const frame = document.createElement('iframe')
  frame.title = 'Salida de impresión FUA'
  frame.style.cssText = 'position:fixed;left:-10000px;width:1px;height:1px;border:0'
  frame.setAttribute('aria-hidden', 'true')
  const ready = new Promise<void>((resolve, reject) => {
    frame.onload = () => resolve()
    frame.onerror = () => reject(new Error('No se pudo preparar la impresión.'))
  })
  frame.srcdoc = fuaPrintHtml(layout, values, test, backgroundUrl, backgroundInset, documentKind)
  document.body.appendChild(frame)
  let restoreTitle: (() => void) | undefined
  let cleanupTimer: number | undefined
  const cleanup = () => {
    window.clearTimeout(cleanupTimer)
    restoreTitle?.()
    frame.remove()
  }
  try {
    await ready
    await frame.contentDocument?.fonts.ready
    if (backgroundUrl && !test) {
      const img = frame.contentDocument?.querySelector('img')
      if (!img || !img.complete || !img.naturalWidth)
        throw new Error(
          'No se pudo cargar la imagen de referencia. Vuelva a abrir la vista previa.',
        )
    }
    const target = frame.contentWindow
    if (!target) throw new Error('El navegador no permite abrir la impresión.')
    target.addEventListener('afterprint', cleanup, { once: true })
    target.focus()
    // Chromium may take the suggested filename from the parent tab when
    // printing an iframe. It can read that title after print() has returned.
    const previousTitle = document.title
    const printTitle = fuaDocumentTitle(values, test, documentKind)
    restoreTitle = () => {
      // A route change may already have set the title of another page.
      if (document.title === printTitle) document.title = previousTitle
    }
    document.title = printTitle
    // Let the browser receive the new tab title before preparing the PDF.
    await new Promise<void>((resolve) =>
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve())),
    )
    // Fallback for browsers without afterprint; no patient data survives in storage.
    cleanupTimer = window.setTimeout(cleanup, 120_000)
    target.print()
  } catch (error) {
    cleanup()
    throw error
  }
}
