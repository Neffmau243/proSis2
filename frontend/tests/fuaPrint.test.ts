import { afterEach, expect, test, vi } from 'vitest'

import type { FuaPrintSnapshot } from '../src/types/fua'
import {
  FUA_DEFAULT_PAPER_MM,
  defaultFuaLayout,
  emptyFuaInput,
  fuaDeliveryBox,
  fuaPrintHtml,
  fuaValues,
  fuaWarnings,
  fuaIdentityProblem,
  fuaUsesAbdominalPerimeter,
  layoutProblems,
  normalizeFuaText,
  parseFuaLayout,
  printFua,
  validateFuaInput,
} from '../src/utils/fuaPrint'

afterEach(() => {
  document.body.innerHTML = ''
})

const snapshot: FuaPrintSnapshot = {
  ...emptyFuaInput(),
  version: 1,
  personal_atiende: 'IPRESS',
  lugar_atencion: 'INTRAMURAL',
  tipo_atencion: 'REFERENCIA',
  tdi: '2',
  numero_documento: '01234567',
  tipo_documento: 'DNI',
  fecha_nacimiento: '1990-01-02',
  fecha_atencion: '2026-09-19',
  hora_atencion: '09:05:00',
  fecha_probable_parto: null,
  fecha_parto: null,
  grupo_atencion_codigo: 'GENERAL',
  sexo_codigo: 'F',
  apellido_paterno: '<script>alert(1)</script>',
  apellido_materno: null,
  peso_kg: '60.00',
  talla_cm: '160.00',
  presion_sistolica: 120,
  presion_diastolica: 80,
  imc: '23.438',
  perimetro_abdominal_cm: '80.00',
  sis_diresa: '001',
  sis_tipo: '2',
  sis_numero: '01234567',
  sis_componente: null,
  ipress_nombre: 'CS PRUEBA',
  profesional_nombre: 'DRA. PRUEBA',
  profesional_documento: null,
  profesional_colegiatura: 'CMP-1',
  primer_nombre: 'Ana',
  otros_nombres: null,
  historia_clinica: 'HC-0001',
}

test('local document labels print without invented TDI; inconsistent identity still blocks', () => {
  expect(fuaIdentityProblem(snapshot)).toBeNull()
  expect(fuaIdentityProblem({ ...snapshot, tipo_documento: 'CE', tdi: '3' })).toBeNull()
  for (const tipo_documento of ['PAS', 'DE', 'OTRO']) {
    expect(fuaIdentityProblem({ ...snapshot, tipo_documento, tdi: null })).toBeNull()
    expect(fuaIdentityProblem({ ...snapshot, tipo_documento, tdi: '2' })).toBeTruthy()
  }
  expect(fuaIdentityProblem({ ...snapshot, tdi: '3' })).toBeTruthy()
  expect(fuaIdentityProblem({ ...snapshot, tipo_documento: 'UNKNOWN', tdi: null })).toBeTruthy()
  expect(fuaIdentityProblem({ ...snapshot, numero_documento: ' ' })).toBeTruthy()
})

test.each(['PAS', 'DE', 'OTRO'])('prints %s and its number with an explicit local legend', (tipo_documento) => {
  const source = { ...snapshot, tipo_documento, tdi: null, numero_documento: 'AB001234' }
  const values = fuaValues(source)
  expect(values.tdi).toBe(tipo_documento)
  expect(values.numero_documento).toBe('AB001234')
  expect(values.identity_note).toContain('Uso local; no es un código TDI SIS')
  const layout = defaultFuaLayout()
  expect(layoutProblems(layout, values)).toEqual([])
  const html = fuaPrintHtml(layout, values)
  expect(html).toContain('AB001234')
  expect(html).toContain(values.identity_note)
  expect(fuaPrintHtml(layout, values, true)).not.toContain('AB001234')
  expect(source.tdi).toBeNull()
  layout.fields.find((f) => f.id === 'identity_note')!.enabled = false
  expect(layoutProblems(layout, values).length).toBeGreaterThan(0)
})

test('old calibration preserves coordinates and requires review of the new legend', () => {
  const layout = { ...defaultFuaLayout(), calibrated: true }
  layout.fields = layout.fields.filter((f) => f.id !== 'identity_note')
  layout.fields[0]!.x = 20
  const migrated = parseFuaLayout(JSON.stringify(layout))
  expect(migrated.fields[0]!.x).toBe(20)
  expect(migrated.fields.some((f) => f.id === 'identity_note')).toBe(true)
  expect(migrated.calibrated).toBe(false)
})

test('typing a multi-word IPRESS name preserves space separators', () => {
  let text = ''
  for (const char of 'Hospital San Juan') {
    text = normalizeFuaText('referencia_nombre', text + char) ?? ''
  }
  expect(text).toBe('HOSPITAL SAN JUAN')
  expect(normalizeFuaText('referencia_nombre', 'HOSPITAL ')).toBe('HOSPITAL ')
  expect(normalizeFuaText('sis_tipo', ' e ')).toBe('E')
})

test('FUA fields use marks, preserve leading zeros, split dates and never invent identifiers', () => {
  const v = fuaValues(snapshot)
  expect(v.personal_ipress).toBe('X')
  expect(v.personal_itinerante).toBe('')
  expect(v.atencion_referencia).toBe('X')
  expect(v.atencion_ambulatoria).toBe('')
  expect(v.nacimiento_dia).toBe('02')
  expect(v.atencion_anio).toBe('2026')
  expect(v.hora_mm).toBe('05')
  expect(v.sis_numero_completo).toBe('2-01234567')
  expect(v.pa).toBe('120/80')
  expect(v.imc).toBe('23.44')
  expect(v.peso_kg).toBe('60')
  // El FUA impreso no trae número propio: lo asigna el backend al emitirlo.
  expect('numero_fua' in v).toBe(false)
  const missing = fuaValues({ ...snapshot, tdi: null, presion_diastolica: null })
  expect(missing.numero_documento).toBe('01234567')
  expect(missing.pa).toBe('')
})

test('el recuadro de parto imprime la FPP de la gestante y la fecha real de la puérpera', () => {
  const gestante = fuaValues({
    ...snapshot, grupo_atencion_codigo: 'GESTANTES', fecha_probable_parto: '2027-01-15', fecha_parto: null,
  })
  expect([gestante.parto_dia, gestante.parto_mes, gestante.parto_anio]).toEqual(['15', '01', '2027'])
  expect(gestante.gestante).toBe('X')
  expect(gestante.puerpera).toBe('')

  const puerpera = fuaValues({
    ...snapshot, grupo_atencion_codigo: 'PUERPERAS', fecha_probable_parto: null, fecha_parto: '2026-09-20',
  })
  expect([puerpera.parto_dia, puerpera.parto_mes, puerpera.parto_anio]).toEqual(['20', '09', '2026'])
  expect(puerpera.puerpera).toBe('X')
  expect(puerpera.gestante).toBe('')
})

test('el recuadro de parto del formato depende del grupo declarado', () => {
  expect(fuaDeliveryBox({ ...snapshot, grupo_atencion_codigo: 'GESTANTES', fecha_probable_parto: '2027-01-15' }))
    .toEqual({ label: 'Fecha probable de parto', value: '2027-01-15' })
  expect(fuaDeliveryBox({ ...snapshot, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: '2026-09-20' }))
    .toEqual({ label: 'Fecha del parto', value: '2026-09-20' })
  // El grupo general no tiene fecha de parto en el formato.
  expect(fuaDeliveryBox({ ...snapshot, grupo_atencion_codigo: 'GENERAL' })).toBeNull()
})

test('los avisos de FUA se adaptan al grupo: el PAB solo aplica al grupo general', () => {
  const maternal = { ...snapshot, perimetro_abdominal_cm: null }

  const general = fuaWarnings({ ...maternal, grupo_atencion_codigo: 'GENERAL' })
  expect(fuaUsesAbdominalPerimeter({ ...maternal, grupo_atencion_codigo: 'GENERAL' })).toBe(true)
  expect(general).toContain('Perímetro abdominal')
  expect(general).not.toContain('Fecha del parto')
  expect(general).not.toContain('Fecha probable de parto')

  const puerpera = fuaWarnings({ ...maternal, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: '2026-09-20' })
  expect(fuaUsesAbdominalPerimeter({ ...maternal, grupo_atencion_codigo: 'PUERPERAS' })).toBe(false)
  expect(puerpera).not.toContain('Perímetro abdominal')
  expect(puerpera).not.toContain('Fecha del parto')
  // La FPP no es un campo de la puérpera: no debe pedirse.
  expect(puerpera).not.toContain('Fecha probable de parto')

  const gestante = fuaWarnings({ ...maternal, grupo_atencion_codigo: 'GESTANTES', fecha_probable_parto: '2027-01-15' })
  expect(gestante).not.toContain('Perímetro abdominal')
  expect(gestante).not.toContain('Fecha probable de parto')
  expect(gestante).not.toContain('Fecha del parto')

  // Sin la fecha del recuadro, sí se advierte el faltante real de cada grupo.
  expect(fuaWarnings({ ...maternal, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: null })).toContain('Fecha del parto')
  expect(fuaWarnings({ ...maternal, grupo_atencion_codigo: 'GESTANTES', fecha_probable_parto: null }))
    .toContain('Fecha probable de parto')
})

test('geometry storage is allowlisted and rejects malformed or out-of-range values', () => {
  const l = defaultFuaLayout()
  const result = parseFuaLayout(JSON.stringify({ ...l, patient: snapshot }))
  // Lo que no está en la lista permitida no sobrevive al parseo.
  expect('patient' in result).toBe(false)
  expect(result.calibrated).toBe(false)
  expect(() => parseFuaLayout('{')).toThrow()
  expect(() => parseFuaLayout(JSON.stringify({ ...l, width: -1 }))).toThrow()
  l.fields[0]!.font = 100
  expect(() => parseFuaLayout(JSON.stringify(l))).toThrow()
})

test('print output escapes names, uses custom page size and excludes background/chrome', () => {
  const html = fuaPrintHtml(defaultFuaLayout(), fuaValues(snapshot))
  expect(defaultFuaLayout()).toMatchObject(FUA_DEFAULT_PAPER_MM)
  expect(html).toMatch(new RegExp(`size:${FUA_DEFAULT_PAPER_MM.width}mm ${FUA_DEFAULT_PAPER_MM.height}mm;margin:0`))
  expect(html).toMatch(/&lt;script&gt;/)
  expect(html).not.toMatch(/<script>|<img|<button|border:/)
  const testPrint = fuaPrintHtml(defaultFuaLayout(), fuaValues(snapshot), true)
  expect(testPrint).not.toMatch(/01234567|alert\(1\)/)
  expect(testPrint).toMatch(/outline/)
})

test('oversized text and fields outside the paper block printing instead of truncating', () => {
  const l = defaultFuaLayout()
  l.fields[0]!.x = 399
  expect(layoutProblems(l, { codigo_renipress: '00001234' }).some((x) => x.includes('fuera'))).toBe(
    true,
  )
  expect(
    layoutProblems(defaultFuaLayout(), {
      primer_nombre: 'N'.repeat(100),
    }).some((x) => x.includes('no cabe')),
  ).toBe(true)
})

test('partial SIS affiliation and incomplete reference are rejected; missing data is visible', () => {
  expect(validateFuaInput(emptyFuaInput())).toEqual([])
  expect(validateFuaInput({ ...emptyFuaInput(), sis_diresa: '001' }).length).toBeTruthy()
  expect(
    validateFuaInput({
      ...emptyFuaInput(),
      sis_diresa: '040',
      sis_tipo: '05',
      sis_numero: '00112233',
    }),
  ).toEqual([])
  expect(validateFuaInput({ ...emptyFuaInput(), tipo_atencion: 'REFERENCIA' }).length).toBeTruthy()
  expect(fuaWarnings({ ...snapshot, tdi: null }).some((x) => x.includes('TDI'))).toBe(true)
})

/**
 * happy-dom no implementa `document.fonts` dentro del iframe, así que la salida
 * de impresión se verifica con un iframe instrumentado: es lo que el navegador
 * ofrece y lo que el código consulta antes de imprimir.
 */
function stubIframe(contentWindow: object | null = {}) {
  const print = vi.fn()
  const focus = vi.fn()
  const addEventListener = vi.fn()
  const frame = document.createElement('iframe')
  Object.defineProperty(frame, 'contentDocument', {
    configurable: true,
    value: { fonts: { ready: Promise.resolve() } },
  })
  Object.defineProperty(frame, 'contentWindow', {
    configurable: true,
    value: contentWindow === null ? null : { print, focus, addEventListener },
  })
  vi.spyOn(document, 'createElement').mockReturnValue(frame)
  return { frame, print, focus, addEventListener }
}

test('la impresión real exige calibración y mediciones válidas antes de abrir el diálogo', async () => {
  const uncalibrated = defaultFuaLayout()
  await expect(printFua(uncalibrated, fuaValues(snapshot))).rejects.toThrow(
    'Revise la calibración antes de imprimir.',
  )

  const calibrated = { ...defaultFuaLayout(), calibrated: true }
  await expect(
    printFua(calibrated, { primer_nombre: 'N'.repeat(100) }),
  ).rejects.toThrow('Revise la calibración antes de imprimir.')

  // El modo prueba permite calibrar sin cumplir todavía las mediciones.
  const { frame } = stubIframe()
  const pending = printFua(uncalibrated, {}, true)
  frame.onload?.(new Event('load'))
  await expect(pending).resolves.toBeUndefined()
})

test('la impresión abre un iframe oculto, lo enfoca y lo imprime', async () => {
  const { frame, print, focus, addEventListener } = stubIframe()

  const pending = printFua({ ...defaultFuaLayout(), calibrated: true }, {}, false)
  frame.onload?.(new Event('load'))
  await pending

  expect(frame.title).toBe('Salida de impresión FUA')
  expect(frame.getAttribute('aria-hidden')).toBe('true')
  expect(document.body.contains(frame)).toBe(true)
  expect(focus).toHaveBeenCalled()
  expect(print).toHaveBeenCalled()
  // El dato del paciente vive solo en el iframe: al cerrarse se elimina.
  expect(addEventListener).toHaveBeenCalledWith('afterprint', expect.any(Function), {
    once: true,
  })
  const [, remove] = addEventListener.mock.calls[0] as [string, () => void]
  remove()
  expect(document.body.contains(frame)).toBe(false)
})

test('si el navegador no puede imprimir se informa y se limpia el iframe', async () => {
  const { frame } = stubIframe(null)

  const pending = printFua({ ...defaultFuaLayout(), calibrated: true }, {}, false)
  frame.onload?.(new Event('load'))

  await expect(pending).rejects.toThrow('El navegador no permite abrir la impresión.')
  expect(document.body.contains(frame)).toBe(false)
})

test('preprinted RENIPRESS stays blank even with an enabled saved field; v2 uses contract sequence', () => {
  const v = fuaValues({
    ...snapshot,
    version: 2,
    codigo_renipress: '98765432',
    renipress_preimpreso: true,
    sis_secuencia: '01',
    sis_componente: 'LEGACY',
  })
  expect(v.codigo_renipress).toBe('')
  expect(v.sis_numero_completo).toBe('2-01234567-01')
  expect(fuaPrintHtml(defaultFuaLayout(), v)).not.toMatch(/98765432|LEGACY/)
  expect(
    fuaValues({ ...snapshot, codigo_renipress: '98765432', renipress_preimpreso: false })
      .codigo_renipress,
  ).toBe('98765432')
})

test('la impresión separa la DIRESA del tipo y el número de afiliación', () => {
  const v = fuaValues({ ...snapshot, sis_diresa: '040', sis_tipo: '2', sis_numero: '72769512' })
  // Casilla propia de DIRESA/DISA: solo los tres dígitos del establecimiento de salud.
  expect(v.sis_diresa).toBe('040')
  // Casilla de tipo/número: nunca concatena la DIRESA delante.
  expect(v.sis_numero_completo).toBe('2-72769512')
  expect(v.sis_numero_completo).not.toContain('040')
  const fields = defaultFuaLayout().fields
  const diresa = fields.find((field) => field.id === 'sis_diresa')!
  const numero = fields.find((field) => field.id === 'sis_numero_completo')!
  expect([diresa.label, numero.label]).toEqual(['SIS · DIRESA', 'SIS · Tipo / número / RN'])
  expect(diresa.x).not.toBe(numero.x)
  const html = fuaPrintHtml(defaultFuaLayout(), v)
  expect(html).toMatch(/2-72769512/)
  expect(html).not.toMatch(/040-2-72769512/)
})
