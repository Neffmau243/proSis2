import type { FuaPrintInput, FuaPrintSnapshot } from '../types/fua.ts'

export function emptyFuaInput(): FuaPrintInput {
  return {
    personal_atiende: null, lugar_atencion: null, tipo_atencion: null,
    codigo_aisped: null, codigo_renipress: null, sis_diresa: null,
    sis_tipo: null, sis_numero: null, sis_componente: null, etnia_codigo: null,
    referencia_renipress: null, referencia_nombre: null, referencia_hoja: null,
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
    ['sis_diresa', /^\d{3}$/, 'DIRESA debe tener 3 dígitos.'],
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
  if ((affiliate.some(Boolean) || value.sis_componente) && !affiliate.every(Boolean)) {
    errors.push('Complete DIRESA, tipo y número de afiliación SIS juntos.')
  }
  if (value.personal_atiende === 'AISPED' && !value.codigo_aisped) errors.push('Indique el código AISPED.')
  if (value.tipo_atencion === 'REFERENCIA' &&
    ![value.referencia_renipress, value.referencia_nombre, value.referencia_hoja].every(Boolean)) {
    errors.push('Complete RENIPRESS, nombre de origen y hoja de referencia.')
  }
  return errors
}

const LOCAL_DOCUMENT_LABELS: Record<string, string> = {
  PAS: 'Pasaporte', DE: 'Documento extranjero', OTRO: 'Otro documento',
}

export function fuaIdentityProblem(s: FuaPrintSnapshot): string | null {
  if (!s.numero_documento?.trim()) return 'Falta el número de documento. Revise la identificación guardada.'
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
export function fuaDeliveryBox(s: FuaPrintSnapshot): { label: string; value: string | null } | null {
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

export function fuaWarnings(s: FuaPrintSnapshot): string[] {
  const result: string[] = []
  const delivery = fuaDeliveryBox(s)
  const required: [unknown, string][] = [
    [s.personal_atiende, 'Personal que atiende'], [s.lugar_atencion, 'Lugar de atención'],
    [s.renipress_preimpreso !== false || s.codigo_renipress, 'RENIPRESS'],
    [s.sis_diresa && s.sis_tipo && s.sis_numero, 'Afiliación SIS completa'],
    [s.historia_clinica, 'Historia clínica'], [s.peso_kg, 'Peso'], [s.talla_cm, 'Talla'],
    [s.presion_sistolica && s.presion_diastolica, 'Presión arterial completa'],
    [s.imc, 'IMC'],
    // En gestantes y puérperas el recuadro lo ocupa la fecha de parto, no el PAB.
    [!fuaUsesAbdominalPerimeter(s) || s.perimetro_abdominal_cm, 'Perímetro abdominal'],
    ...(delivery ? [[delivery.value, delivery.label] as [unknown, string]] : []),
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
  width: number
  height: number
  offsetX: number
  offsetY: number
  calibrated: boolean
  fields: FuaField[]
}

/** Baseline paper profile used by the FUA preview and the printed page. */
export const FUA_DEFAULT_PAPER_MM = Object.freeze({ width: 216, height: 356 })
const FUA_REFERENCE_GRID_PX = Object.freeze({ width: 607, height: 1006 })
const FUA_REFERENCE_MARGIN_MM = 10

// Approximate starting positions only. They use the grid of the visual reference
// and are not an assertion that the reference is the currently valid SIS FUA.
// A physical test with the IPRESS stock is still required before printing data.
const seeds: [string, string, number, number, number, number?][] = [
  ['codigo_renipress', 'RENIPRESS', 5, 105, 135],
  ['ipress_nombre', 'Nombre IPRESS', 155, 105, 444],
  ['personal_ipress', 'X · De la IPRESS', 59, 138, 10],
  ['personal_itinerante', 'X · Itinerante', 59, 154, 10],
  ['personal_aisped', 'X · AISPED', 59, 170, 10],
  ['codigo_aisped', 'Código AISPED', 72, 155, 72],
  ['lugar_intramural', 'X · Intramural', 199, 138, 10],
  ['lugar_extramural', 'X · Extramural', 199, 154, 10],
  ['atencion_ambulatoria', 'X · Ambulatoria', 272, 138, 10],
  ['atencion_referencia', 'X · Referencia', 272, 154, 10],
  ['atencion_emergencia', 'X · Emergencia', 272, 170, 10],
  ['referencia_renipress', 'Referencia · RENIPRESS', 289, 156, 77],
  ['referencia_nombre', 'Referencia · IPRESS origen', 374, 156, 121],
  ['referencia_hoja', 'Referencia · Hoja', 501, 156, 97],
  ['tdi', 'TDI', 13, 216, 27], ['numero_documento', 'Documento', 49, 216, 72],
  ['sis_diresa', 'SIS · DIRESA', 130, 216, 62],
  ['sis_numero_completo', 'SIS · Tipo / número / RN', 200, 216, 67],
  ['apellido_paterno', 'Apellido paterno', 5, 242, 261],
  ['apellido_materno', 'Apellido materno', 279, 242, 320],
  ['primer_nombre', 'Primer nombre', 5, 268, 261],
  ['otros_nombres', 'Otros nombres', 279, 268, 320],
  ['sexo_m', 'X · Masculino', 53, 295, 10], ['sexo_f', 'X · Femenino', 53, 307, 10],
  ['nacimiento_dia', 'Nacimiento · Día', 140, 319, 39, 7],
  ['nacimiento_mes', 'Nacimiento · Mes', 185, 319, 36, 7],
  ['nacimiento_anio', 'Nacimiento · Año', 230, 319, 87, 8],
  ['historia_clinica', 'Historia clínica', 327, 297, 95],
  ['etnia_codigo', 'Código etnia', 440, 297, 154],
  ['gestante', 'X · Gestante', 53, 337, 10], ['puerpera', 'X · Puérpera', 53, 356, 10],
  ['parto_dia', 'Parto · Día', 140, 295, 39, 7],
  ['parto_mes', 'Parto · Mes', 185, 295, 36, 7],
  ['parto_anio', 'Parto · Año', 230, 295, 87, 8],
  ['atencion_dia', 'Atención · Día', 5, 404, 27, 5],
  ['atencion_mes', 'Atención · Mes', 36, 404, 26, 5],
  ['atencion_anio', 'Atención · Año', 68, 404, 70, 6.5],
  ['hora_hh', 'Hora', 151, 404, 17, 3], ['hora_mm', 'Minutos', 178, 404, 16, 3],
  ['peso_kg', 'Peso (kg)', 4, 589, 44], ['talla_cm', 'Talla (cm)', 61, 589, 66],
  ['pa', 'PA (mmHg)', 145, 589, 65], ['imc', 'IMC (kg/m²)', 220, 589, 52],
  ['perimetro_abdominal_cm', 'PAB (cm)', 285, 589, 45],
  ['profesional_documento', 'Responsable · DNI', 5, 873, 98],
  ['profesional_nombre', 'Responsable · Nombre', 120, 873, 308],
  ['profesional_colegiatura', 'Responsable · Colegiatura', 445, 873, 151],
  ['identity_note', 'Leyenda de documento · uso local', 5, 955, 590],
]

export function defaultFuaLayout(): FuaLayout {
  const printableWidth = FUA_DEFAULT_PAPER_MM.width - FUA_REFERENCE_MARGIN_MM * 2
  const printableHeight = FUA_DEFAULT_PAPER_MM.height - FUA_REFERENCE_MARGIN_MM * 2
  return {
    version: 1, width: FUA_DEFAULT_PAPER_MM.width, height: FUA_DEFAULT_PAPER_MM.height,
    offsetX: 0, offsetY: 0, calibrated: false,
    fields: seeds.map(([id, label, x, y, width, step]) => ({
      id, label, x: +(FUA_REFERENCE_MARGIN_MM + x * printableWidth / FUA_REFERENCE_GRID_PX.width).toFixed(2),
      y: +(FUA_REFERENCE_MARGIN_MM + y * printableHeight / FUA_REFERENCE_GRID_PX.height).toFixed(2),
      width: +(width * printableWidth / FUA_REFERENCE_GRID_PX.width).toFixed(2),
      height: 4, font: 8, step: step ?? 0, skip: 0, enabled: true,
    })),
  }
}

export const FUA_LAYOUT_KEY = 'ipress.fua-layout.v1'
const bounded = (v: unknown, min: number, max: number): v is number =>
  typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max

/** Allowlist geometry only: local storage must never contain clinical values. */
export function parseFuaLayout(raw: string): FuaLayout {
  const v = JSON.parse(raw) as FuaLayout
  const template = defaultFuaLayout()
  if (v.version !== 1 || !bounded(v.width, 100, 400) || !bounded(v.height, 150, 600) ||
    !bounded(v.offsetX, -50, 50) || !bounded(v.offsetY, -50, 50) ||
    !Array.isArray(v.fields) ||
    (v.fields.length !== template.fields.length &&
      !(v.fields.length === template.fields.length - 1 && !v.fields.some((f) => f.id === 'identity_note')))) throw new Error('Calibración inválida.')
  const migrated = !v.fields.some((f) => f.id === 'identity_note')
  const fields = template.fields.map((original) => {
    const f = v.fields.find((entry) => entry.id === original.id)
    if (!f && original.id === 'identity_note' && migrated) return original
    if (!f || !bounded(f.x, 0, 400) || !bounded(f.y, 0, 600) ||
      !bounded(f.width, 1, 400) || !bounded(f.height, 1, 30) ||
      !bounded(f.font, 5, 20) || !bounded(f.step, 0, 15) ||
      !Number.isInteger(f.skip) || !bounded(f.skip, 0, 2)) throw new Error('Posición inválida.')
    return { ...original, x: f.x, y: f.y, width: f.width, height: f.height,
      font: f.font, step: f.step, skip: f.skip, enabled: f.enabled !== false }
  })
  return { version: 1, width: v.width, height: v.height, offsetX: v.offsetX,
    offsetY: v.offsetY, calibrated: v.calibrated === true && !migrated, fields }
}

export function fuaValues(s: FuaPrintSnapshot): Record<string, string> {
  const v: Record<string, string> = {}
  for (const [key, value] of Object.entries(s)) v[key] = value == null ? '' : String(value)
  const mark = (condition: boolean) => condition ? 'X' : ''
  for (const code of ['IPRESS', 'ITINERANTE', 'AISPED']) v[`personal_${code.toLowerCase()}`] = mark(s.personal_atiende === code)
  for (const code of ['INTRAMURAL', 'EXTRAMURAL']) v[`lugar_${code.toLowerCase()}`] = mark(s.lugar_atencion === code)
  for (const code of ['AMBULATORIA', 'REFERENCIA', 'EMERGENCIA']) v[`atencion_${code.toLowerCase()}`] = mark(s.tipo_atencion === code)
  v.sexo_m = mark(s.sexo_codigo === 'M')
  v.sexo_f = mark(s.sexo_codigo === 'F')
  v.gestante = mark(s.grupo_atencion_codigo === 'GESTANTES')
  v.puerpera = mark(s.grupo_atencion_codigo === 'PUERPERAS')
  v.sis_numero_completo = [s.sis_tipo, s.sis_numero, s.version === 2 ? s.sis_secuencia : s.sis_componente].filter(Boolean).join('-')
  // Even a previously saved calibration must not overprint a preprinted RENIPRESS.
  if (s.renipress_preimpreso !== false) v.codigo_renipress = ''
  // Local paper labels are not SIS codes; never mutate the saved snapshot/TDI.
  const localLabel = Object.hasOwn(LOCAL_DOCUMENT_LABELS, s.tipo_documento)
    ? LOCAL_DOCUMENT_LABELS[s.tipo_documento] : undefined
  if (localLabel && s.tdi == null) {
    v.tdi = s.tipo_documento
    v.identity_note = `${s.tipo_documento} = ${localLabel}. Uso local; no es un código TDI SIS.`
  }
  const partoDate = fuaDeliveryBox(s)?.value ?? null
  for (const [prefix, date] of [['nacimiento', s.fecha_nacimiento], ['atencion', s.fecha_atencion], ['parto', partoDate]]) {
    const [year = '', month = '', day = ''] = (date || '').slice(0, 10).split('-')
    v[`${prefix}_dia`] = day
    v[`${prefix}_mes`] = month
    v[`${prefix}_anio`] = year
  }
  v.hora_hh = s.hora_atencion.slice(0, 2)
  v.hora_mm = s.hora_atencion.slice(3, 5)
  v.pa = s.presion_sistolica && s.presion_diastolica ? `${s.presion_sistolica}/${s.presion_diastolica}` : ''
  for (const key of ['peso_kg', 'talla_cm', 'imc', 'perimetro_abdominal_cm']) {
    if (v[key]) v[key] = String(Number(Number(v[key]).toFixed(2)))
  }
  return v
}

export function layoutProblems(layout: FuaLayout, values: Record<string, string>): string[] {
  const errors: string[] = []
  for (const id of ['tdi', 'numero_documento', 'identity_note']) {
    if (!values[id]) continue
    const field = layout.fields.find((f) => f.id === id)
    if (!field?.enabled || field.skip !== 0) errors.push('La identificación y su leyenda deben imprimirse completas; active los campos y no omita caracteres.')
  }
  for (const f of layout.fields.filter((field) => field.enabled)) {
    const value = (values[f.id] || '').slice(f.skip)
    if (!value) continue
    if (f.x + layout.offsetX < 0 || f.y + layout.offsetY < 0 ||
      f.x + layout.offsetX + f.width > layout.width || f.y + layout.offsetY + f.height > layout.height) {
      errors.push(`${f.label}: fuera de la hoja`)
    }
    // Font is Courier (fixed pitch, about 0.6 em). Block rather than truncate data.
    const charWidth = f.font * 25.4 / 72 * 0.61
    const needed = f.step ? Math.max(0, value.length - 1) * f.step + charWidth : value.length * charWidth
    if (needed > f.width || f.font * 25.4 / 72 * 1.2 > f.height) errors.push(`${f.label}: texto no cabe; ajuste ancho, paso o fuente`)
  }
  return errors
}

const escapeHtml = (s: string) => s.replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]!))

export function fuaPrintHtml(layout: FuaLayout, values: Record<string, string>, test = false): string {
  const safe = parseFuaLayout(JSON.stringify(layout))
  const fields = safe.fields.filter((f) => f.enabled).map((f) => {
    const value = test ? '+' : (values[f.id] || '').slice(f.skip)
    const content = f.step && !test ? [...value].map((char, i) =>
      `<span style="position:absolute;left:${i * f.step}mm">${escapeHtml(char)}</span>`).join('') : escapeHtml(value)
    return `<div style="position:absolute;left:${f.x + safe.offsetX}mm;top:${f.y + safe.offsetY}mm;width:${f.width}mm;height:${f.height}mm;font-size:${f.font}pt;${test ? 'outline:0.2mm solid #000;' : ''}">${content}</div>`
  }).join('')
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Impresión FUA</title><style>
    @page{size:${safe.width}mm ${safe.height}mm;margin:0}
    html,body{margin:0;padding:0;width:${safe.width}mm;height:${safe.height}mm}
    body{position:relative;color:#000;background:#fff;font-family:Courier New,monospace;line-height:1.2;white-space:nowrap}
    </style></head><body>${fields}</body></html>`
}

export async function printFua(layout: FuaLayout, values: Record<string, string>, test = false): Promise<void> {
  if (!test && (!layout.calibrated || layoutProblems(layout, values).length)) throw new Error('Revise la calibración antes de imprimir.')
  const frame = document.createElement('iframe')
  frame.title = 'Salida de impresión FUA'
  frame.style.cssText = 'position:fixed;left:-10000px;width:1px;height:1px;border:0'
  frame.setAttribute('aria-hidden', 'true')
  const ready = new Promise<void>((resolve, reject) => {
    frame.onload = () => resolve()
    frame.onerror = () => reject(new Error('No se pudo preparar la impresión.'))
  })
  frame.srcdoc = fuaPrintHtml(layout, values, test)
  document.body.appendChild(frame)
  try {
    await ready
    await frame.contentDocument?.fonts.ready
    const target = frame.contentWindow
    if (!target) throw new Error('El navegador no permite abrir la impresión.')
    target.addEventListener('afterprint', () => frame.remove(), { once: true })
    target.focus()
    target.print()
    // Fallback for browsers without afterprint; no patient data survives in storage.
    window.setTimeout(() => frame.remove(), 120_000)
  } catch (error) {
    frame.remove()
    throw error
  }
}
