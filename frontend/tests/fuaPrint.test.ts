import { afterEach, expect, test, vi } from 'vitest'

import type { FuaPrintSnapshot } from '../src/types/fua'
import {
  FUA_DEFAULT_PAPER_MM,
  defaultFuaLayout,
  emptyFuaInput,
  fuaDeliveryBox,
  fuaFieldFont,
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
  document.title = ''
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

test('imprime solo las semanas guardadas de la gestante en la casilla oficial', () => {
  const source = { ...snapshot, grupo_atencion_codigo: 'GESTANTES',
    fecha_probable_parto: '2026-12-27', edad_gestacional_semanas: 30,
    edad_gestacional_dias: 2, edad_gestacional_fuente: 'FPP' as const }
  const values = fuaValues(source)
  expect(values.edad_gestacional_semanas).toBe('30')
  expect(fuaWarnings(source)).not.toContain('Edad gestacional')
  const layout = defaultFuaLayout()
  const field = layout.fields.find(f => f.id === 'edad_gestacional_semanas')!
  const doc = new DOMParser().parseFromString(fuaPrintHtml(layout, values), 'text/html')
  expect(doc.body.children[layout.fields.indexOf(field)]?.textContent).toBe('30')
  expect(field.x).toBeGreaterThanOrEqual(21)
  expect(field.x + field.width).toBeLessThan(27)
  expect(field.y).toBeGreaterThan(230)
  expect(field.y + field.height).toBeLessThan(237)
  expect(fuaValues({ ...source, grupo_atencion_codigo: 'PUERPERAS' }).edad_gestacional_semanas).toBe('')
  expect(fuaValues({ ...source, edad_gestacional_semanas: 0 }).edad_gestacional_semanas).toBe('0')
  expect(fuaWarnings({ ...source, edad_gestacional_semanas: 0 })).not.toContain('Edad gestacional')
})

test('la FPP de una copia histórica no se recalcula al imprimir', () => {
  const legacy = { ...snapshot, grupo_atencion_codigo: 'GESTANTES', fecha_probable_parto: '2026-12-27' }
  expect(fuaValues(legacy).edad_gestacional_semanas).toBe('')
  expect(fuaWarnings(legacy)).toContain('Edad gestacional')
})

test('una calibración sin edad gestacional conserva posiciones y añade la casilla para revisar', () => {
  const old = { ...defaultFuaLayout(), calibrated: true, offsetY: 1 }
  old.fields = old.fields.filter(f => f.id !== 'edad_gestacional_semanas')
  old.fields.find(f => f.id === 'peso_kg')!.x += 1.5
  old.fields.find(f => f.id === 'peso_kg')!.y += 2
  const upgraded = parseFuaLayout(JSON.stringify(old))
  expect(upgraded.calibrated).toBe(false)
  expect(upgraded.offsetY).toBe(1)
  for (const field of old.fields) expect(upgraded.fields.find(f => f.id === field.id)).toEqual(field)
  const base = defaultFuaLayout().fields.find(f => f.id === 'edad_gestacional_semanas')!
  expect(upgraded.fields.find(f => f.id === base.id)).toMatchObject({ x: base.x + 1.5, y: base.y + 2 })
})

test('referencia imprime una sola X y sus tres datos de origen en las casillas FUA', () => {
  const values = fuaValues({
    ...snapshot, referencia_renipress: '00001234',
    referencia_nombre: 'IPRESS ORIGEN', referencia_hoja: 'REF-0001',
  })
  expect(values.atencion_referencia).toBe('X')
  expect(values.atencion_ambulatoria).toBe('')
  expect(values.atencion_emergencia).toBe('')
  const layout = defaultFuaLayout()
  const fields = layout.fields.filter(field => field.enabled)
  const doc = new DOMParser().parseFromString(fuaPrintHtml(layout, values), 'text/html')
  for (const [key, value] of Object.entries({
    referencia_renipress: '00001234', referencia_nombre: 'IPRESS ORIGEN', referencia_hoja: 'REF-0001',
  })) {
    expect(doc.body.children[fields.findIndex(field => field.id === key)]?.textContent).toBe(value)
  }
})

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

test.each(['PAS', 'DE', 'OTRO'])(
  'prints %s and its number with an explicit local legend',
  (tipo_documento) => {
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
  },
)

test('old calibration preserves coordinates and requires review of the new legend', () => {
  const layout = { ...defaultFuaLayout(), calibrated: true }
  layout.fields = layout.fields.filter((f) => f.id !== 'identity_note')
  layout.fields[0]!.x = 20
  const migrated = parseFuaLayout(JSON.stringify(layout))
  expect(migrated.fields[0]!.x).toBe(20)
  expect(migrated.fields.some((f) => f.id === 'identity_note')).toBe(true)
  expect(migrated.calibrated).toBe(false)
})

test.each([undefined, 'historica'])(
  'a %s profile moves to the single reference while retaining coordinates for review',
  (template) => {
    const legacy = { ...defaultFuaLayout(), template, calibrated: true }
    legacy.fields[0]!.x = 25
    const restored = parseFuaLayout(JSON.stringify(legacy))
    expect(restored.template).toBe('sis-v02')
    expect(restored.calibrated).toBe(false)
    expect(restored.fields).toEqual(legacy.fields)
    expect(defaultFuaLayout().template).toBe('sis-v02')
  },
)

test('PDF review includes an escaped reference image and identical field geometry; paper and test outputs stay data-only', () => {
  const layout = defaultFuaLayout()
  const values = fuaValues(snapshot)
  const review = fuaPrintHtml(layout, values, false, '/reference.png', 10)
  const paper = fuaPrintHtml(layout, values)
  const reviewDoc = new DOMParser().parseFromString(review, 'text/html')
  const paperDoc = new DOMParser().parseFromString(paper, 'text/html')
  expect(reviewDoc.querySelector('img')?.getAttribute('style')).toContain(
    'left:10mm;top:10mm;width:196mm;height:336mm',
  )
  expect(review).toContain('PRELLENADO PARCIAL')
  expect([...reviewDoc.body.children].slice(2).map((field) => field.outerHTML)).toEqual(
    [...paperDoc.body.children].map((field) => field.outerHTML),
  )
  expect(paper).not.toContain('<img')
  const testDoc = fuaPrintHtml(layout, values, true, '/reference.png')
  expect(testDoc).not.toContain('<img')
  expect(testDoc).not.toContain(snapshot.numero_documento)
  expect(fuaPrintHtml(layout, {}, false, 'x" onerror="alert(1)')).toContain('&quot;')
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
  expect(v.sis_tipo).toBe('2')
  expect(v.sis_numero).toBe('01234567')
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
    ...snapshot,
    grupo_atencion_codigo: 'GESTANTES',
    fecha_probable_parto: '2027-01-15',
    fecha_parto: null,
  })
  expect([gestante.parto_dia, gestante.parto_mes, gestante.parto_anio]).toEqual([
    '15',
    '01',
    '2027',
  ])
  expect(gestante.gestante).toBe('X')
  expect(gestante.puerpera).toBe('')

  const puerpera = fuaValues({
    ...snapshot,
    grupo_atencion_codigo: 'PUERPERAS',
    fecha_probable_parto: null,
    fecha_parto: '2026-09-20',
  })
  expect([puerpera.parto_dia, puerpera.parto_mes, puerpera.parto_anio]).toEqual([
    '20',
    '09',
    '2026',
  ])
  expect(puerpera.puerpera).toBe('X')
  expect(puerpera.gestante).toBe('')
})

test('el recuadro de parto del formato depende del grupo declarado', () => {
  expect(
    fuaDeliveryBox({
      ...snapshot,
      grupo_atencion_codigo: 'GESTANTES',
      fecha_probable_parto: '2027-01-15',
    }),
  ).toEqual({ label: 'Fecha probable de parto', value: '2027-01-15' })
  expect(
    fuaDeliveryBox({ ...snapshot, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: '2026-09-20' }),
  ).toEqual({ label: 'Fecha del parto', value: '2026-09-20' })
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

  const puerpera = fuaWarnings({
    ...maternal,
    grupo_atencion_codigo: 'PUERPERAS',
    fecha_parto: '2026-09-20',
  })
  expect(fuaUsesAbdominalPerimeter({ ...maternal, grupo_atencion_codigo: 'PUERPERAS' })).toBe(false)
  expect(puerpera).not.toContain('Perímetro abdominal')
  expect(puerpera).not.toContain('Fecha del parto')
  // La FPP no es un campo de la puérpera: no debe pedirse.
  expect(puerpera).not.toContain('Fecha probable de parto')

  const gestante = fuaWarnings({
    ...maternal,
    grupo_atencion_codigo: 'GESTANTES',
    fecha_probable_parto: '2027-01-15',
  })
  expect(gestante).not.toContain('Perímetro abdominal')
  expect(gestante).not.toContain('Fecha probable de parto')
  expect(gestante).not.toContain('Fecha del parto')

  // Sin la fecha del recuadro, sí se advierte el faltante real de cada grupo.
  expect(
    fuaWarnings({ ...maternal, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: null }),
  ).toContain('Fecha del parto')
  expect(
    fuaWarnings({ ...maternal, grupo_atencion_codigo: 'GESTANTES', fecha_probable_parto: null }),
  ).toContain('Fecha probable de parto')
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
  expect(html).toMatch(
    new RegExp(`size:${FUA_DEFAULT_PAPER_MM.width}mm ${FUA_DEFAULT_PAPER_MM.height}mm;margin:0`),
  )
  expect(html).toMatch(/&lt;script&gt;/)
  expect(html).not.toMatch(/<script>|<img|<button|border:/)
  const testPrint = fuaPrintHtml(defaultFuaLayout(), fuaValues(snapshot), true)
  expect(testPrint).not.toMatch(/01234567|alert\(1\)/)
  expect(testPrint).toMatch(/outline/)
})

test('el nombre sugerido del PDF usa nombres, apellidos y fecha de la atención guardada', () => {
  const values = {
    primer_nombre: '  ANA ', otros_nombres: 'MARÍA',
    apellido_paterno: 'DE LA CRUZ', apellido_materno: 'PEÑA',
    fecha_atencion: '2026-09-19',
  }
  for (const reference of [undefined, '/reference.png']) {
    const html = fuaPrintHtml(defaultFuaLayout(), values, false, reference)
    expect(new DOMParser().parseFromString(html, 'text/html').title).toBe(
      'atencion-ANA MARÍA DE LA CRUZ PEÑA-2026-09-19',
    )
  }
  const title = (data: Record<string, string>, test = false) =>
    new DOMParser().parseFromString(fuaPrintHtml(defaultFuaLayout(), data, test), 'text/html').title
  expect(title({ primer_nombre: 'Ana', apellido_paterno: 'Prueba' })).toBe('atencion-Ana Prueba')
  expect(title({ primer_nombre: 'Ana / : \\ < > | ? *', apellido_paterno: 'Prueba.' })).toBe('atencion-Ana Prueba')
  expect(title({ primer_nombre: 'Ana & Elena' })).toBe('atencion-Ana & Elena')
  expect(title({})).toBe('atencion')
  expect(title({ ...values, fecha_atencion: '2026-09-19T09:05:00' })).toBe(
    'atencion-ANA MARÍA DE LA CRUZ PEÑA-2026-09-19',
  )
  expect(title({ ...values, fecha_atencion: '' })).toBe('atencion-ANA MARÍA DE LA CRUZ PEÑA')
  expect(title(values, true)).toBe('Impresión FUA')
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

test('la historia clínica se ajusta a la casilla calibrada sin moverla ni recortar caracteres', () => {
  const layout = { ...defaultFuaLayout(), calibrated: true }
  const history = layout.fields.find((field) => field.id === 'historia_clinica')!
  const before = { ...history }
  const value = 'DEMO-ETNIA-98032888'
  const values = { historia_clinica: value }
  const font = fuaFieldFont(history, value)
  expect(font).toBeGreaterThanOrEqual(5)
  expect(font).toBeLessThan(history.font)
  expect(layoutProblems(layout, values)).toEqual([])
  const html = fuaPrintHtml(layout, values)
  expect(html).toContain(`font-size:${font}pt`)
  expect(html).toContain(value)
  expect(html).toContain(`left:${history.x}mm;top:${history.y}mm;width:${history.width}mm`)
  expect(history).toEqual(before)
  expect(layout.calibrated).toBe(true)
})

test('el autoajuste no altera el paso de las casillas y bloquea el texto que tampoco cabe a 5 pt', () => {
  const layout = defaultFuaLayout()
  const history = layout.fields.find((field) => field.id === 'historia_clinica')!
  expect(fuaFieldFont(history, 'HC-1')).toBe(history.font)
  expect(fuaFieldFont(history, 'N'.repeat(100))).toBe(5)
  expect(layoutProblems(layout, { historia_clinica: 'N'.repeat(100) })).toContain(
    'Historia clínica: texto no cabe; ajuste ancho, paso o fuente',
  )
  history.step = 3
  expect(fuaFieldFont(history, 'DEMO-ETNIA-98032888')).toBe(history.font)
  expect(layoutProblems(layout, { historia_clinica: 'DEMO-ETNIA-98032888' })).toHaveLength(1)
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

test('supplement validation matches the backend optional DIRESA and conditional reference/AISPED contract', () => {
  const affiliate = { ...emptyFuaInput(), sis_tipo: '2', sis_numero: '00000001' }
  expect(validateFuaInput(affiliate)).toEqual([])
  expect(validateFuaInput({ ...affiliate, sis_diresa: 'A01' })).toEqual([])
  expect(validateFuaInput({ ...emptyFuaInput(), codigo_aisped: 'A001' })).not.toEqual([])
  expect(validateFuaInput({ ...emptyFuaInput(), referencia_hoja: '001' })).not.toEqual([])
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
  const createElement = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag, options) =>
    tag === 'iframe' ? frame : createElement(tag, options),
  )
  return { frame, print, focus, addEventListener }
}

test('la impresión real exige calibración y mediciones válidas antes de abrir el diálogo', async () => {
  const uncalibrated = defaultFuaLayout()
  await expect(printFua(uncalibrated, fuaValues(snapshot))).rejects.toThrow(
    'Revise la calibración antes de imprimir.',
  )

  const calibrated = { ...defaultFuaLayout(), calibrated: true }
  await expect(printFua(calibrated, { primer_nombre: 'N'.repeat(100) })).rejects.toThrow(
    'Revise la calibración antes de imprimir.',
  )

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

test.each([false, true])('conserva el título del PDF hasta cerrar impresión y lo restaura al terminar (error: %s)', async (fail) => {
  document.title = 'Admisión de paciente · Sistema de Salud IPRESS'
  const { frame, print, addEventListener } = stubIframe()
  const originalTitle = document.title
  print.mockImplementation(() => {
    expect(document.title).toBe('atencion-ANA PRUEBA')
    if (fail) throw new Error('Impresora no disponible')
  })
  const pending = printFua({ ...defaultFuaLayout(), calibrated: true }, {
    primer_nombre: 'ANA', apellido_paterno: 'PRUEBA',
  })
  frame.onload?.(new Event('load'))
  if (fail) await expect(pending).rejects.toThrow('Impresora no disponible')
  else {
    await pending
    // print() can return while the browser is still preparing its preview.
    expect(document.title).toBe('atencion-ANA PRUEBA')
    const [, afterprint] = addEventListener.mock.calls[0] as [string, () => void]
    afterprint()
  }
  expect(document.title).toBe(originalTitle)
  expect(frame.srcdoc).toContain('<title>atencion-ANA PRUEBA</title>')
})

test('cerrar impresión no reemplaza el título de una página a la que se navegó después', async () => {
  const { frame, addEventListener } = stubIframe()
  const pending = printFua({ ...defaultFuaLayout(), calibrated: true }, { primer_nombre: 'ANA' })
  frame.onload?.(new Event('load'))
  await pending
  document.title = 'Historia del paciente'
  const [, afterprint] = addEventListener.mock.calls[0] as [string, () => void]
  afterprint()
  expect(document.title).toBe('Historia del paciente')
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
  expect(v.sis_tipo).toBe('2')
  expect(v.sis_numero).toBe('01234567-01')
  expect(fuaPrintHtml(defaultFuaLayout(), v)).not.toMatch(/98765432|LEGACY/)
  expect(
    fuaValues({ ...snapshot, codigo_renipress: '98765432', renipress_preimpreso: false })
      .codigo_renipress,
  ).toBe('98765432')
})

test('la impresión coloca DIRESA, tipo y número de afiliación en tres casillas independientes', () => {
  const v = fuaValues({ ...snapshot, sis_diresa: '040', sis_tipo: '2', sis_numero: '72769512' })
  // La DIRESA proviene de la afiliación del asegurado, no de la sede actual.
  expect(v.sis_diresa).toBe('040')
  expect(v.sis_tipo).toBe('2')
  expect(v.sis_numero).toBe('72769512')
  const layout = defaultFuaLayout()
  const sisFields = ['sis_diresa', 'sis_tipo', 'sis_numero'].map(
    (id) => layout.fields.find((field) => field.id === id)!,
  )
  expect(sisFields.map((field) => field.label)).toEqual([
    'SIS · DIRESA', 'SIS · Tipo', 'SIS · Número / RN',
  ])
  for (let i = 1; i < sisFields.length; i++) {
    expect(sisFields[i]!.x).toBeGreaterThan(sisFields[i - 1]!.x + sisFields[i - 1]!.width)
  }
  for (const background of [undefined, '/reference.png']) {
    const html = fuaPrintHtml(layout, v, false, background, 10)
    const doc = new DOMParser().parseFromString(html, 'text/html')
    const printed = [...doc.body.children].filter((el) => el.getAttribute('style')?.includes('font-size:'))
    expect(sisFields.map((field) => printed[layout.fields.indexOf(field)]!.textContent)).toEqual([
      '040', '2', '72769512',
    ])
    expect(html).not.toContain('2-72769512')
  }
})

test.each([true, false])('migra el campo SIS combinado sin perder las demás posiciones (leyenda: %s)', (withLegend) => {
  const legacy = { ...defaultFuaLayout(), calibrated: true, offsetX: 1.5 }
  const diresa = legacy.fields.find((f) => f.id === 'sis_diresa')!
  diresa.x += 2
  diresa.y += 3
  legacy.fields = legacy.fields.filter((f) =>
    !['sis_tipo', 'sis_numero', ...(!withLegend ? ['identity_note'] : [])].includes(f.id),
  )
  legacy.fields[0]!.x = 21
  legacy.fields.push({
    id: 'sis_numero_completo', label: 'SIS · Tipo / número / RN',
    x: 150, y: 82, width: 33, height: 4, font: 7, step: 2, skip: 1, enabled: true,
  })
  const migrated = parseFuaLayout(JSON.stringify(legacy))
  expect(migrated.calibrated).toBe(false)
  expect(migrated.offsetX).toBe(1.5)
  for (const original of legacy.fields.filter((f) => f.id !== 'sis_numero_completo')) {
    expect(migrated.fields.find((f) => f.id === original.id)).toEqual(original)
  }
  for (const original of defaultFuaLayout().fields.filter((f) => ['sis_tipo', 'sis_numero'].includes(f.id))) {
    const field = migrated.fields.find((f) => f.id === original.id)!
    expect(field.x).toBeCloseTo(original.x + 2)
    expect(field.y).toBeCloseTo(original.y + 3)
    expect(field).toMatchObject({
      width: original.width, font: 7, step: 0, skip: 0,
    })
  }
  expect(migrated.fields.some((f) => f.id === 'sis_numero_completo')).toBe(false)
  expect(migrated.fields.some((f) => f.id === 'identity_note')).toBe(true)
  const confirmed = { ...migrated, calibrated: true }
  expect(parseFuaLayout(JSON.stringify(confirmed))).toEqual(confirmed)
})

test.each([
  { version: 2 as const, sis_secuencia: '01', sis_componente: 'LEGACY', suffix: '01' },
  { version: 1 as const, sis_secuencia: '99', sis_componente: '02', suffix: '02' },
])('conserva ceros iniciales y el sufijo RN de las copias versión $version', (source) => {
  const values = fuaValues({ ...snapshot, ...source, sis_tipo: '05', sis_numero: '00000001' })
  expect(values.sis_tipo).toBe('05')
  expect(values.sis_numero).toBe(`00000001-${source.suffix}`)
  const html = fuaPrintHtml(defaultFuaLayout(), values)
  expect(html).toContain(`00000001-${source.suffix}`)
  expect(html).not.toContain('05-00000001')
  expect(layoutProblems(defaultFuaLayout(), values)).toEqual([])
})

test('sin afiliación, las tres casillas SIS permanecen vacías', () => {
  const values = fuaValues({ ...snapshot, sis_diresa: null, sis_tipo: null, sis_numero: null })
  expect([values.sis_diresa, values.sis_tipo, values.sis_numero]).toEqual(['', '', ''])
})

test('REF.Lab distingue el FUA de laboratorio y usa la fecha guardada, en ambas salidas', () => {
  const values = {
    primer_nombre: 'ANA',
    otros_nombres: 'MARÍA',
    apellido_paterno: 'PRUEBA',
    fecha_atencion: '2026-10-18T09:15:00',
  }
  for (const background of [undefined, '/reference.png']) {
    const html = fuaPrintHtml(defaultFuaLayout(), values, false, background, 0, 'REF.Lab')
    expect(new DOMParser().parseFromString(html, 'text/html').title).toBe(
      'REF.Lab-ANA MARÍA PRUEBA-2026-10-18',
    )
  }
  expect(
    new DOMParser().parseFromString(fuaPrintHtml(defaultFuaLayout(), values), 'text/html').title,
  ).toBe('atencion-ANA MARÍA PRUEBA-2026-10-18')
})

test('REF.Lab se aplica al título del iframe y de la pestaña hasta terminar la impresión', async () => {
  document.title = 'Laboratorio · Sistema de Salud IPRESS'
  const { frame, print, addEventListener } = stubIframe()
  const expected = 'REF.Lab-ANA PRUEBA-2026-10-18'
  print.mockImplementation(() => {
    expect(document.title).toBe(expected)
  })
  const pending = printFua(
    { ...defaultFuaLayout(), calibrated: true },
    {
      primer_nombre: 'ANA',
      apellido_paterno: 'PRUEBA',
      fecha_atencion: '2026-10-18',
    },
    false,
    undefined,
    0,
    'REF.Lab',
  )
  frame.onload?.(new Event('load'))
  await pending
  expect(print).toHaveBeenCalledOnce()
  expect(frame.srcdoc).toContain(`<title>${expected}</title>`)
  expect(document.title).toBe(expected)
  const [, afterprint] = addEventListener.mock.calls[0] as [string, () => void]
  afterprint()
  expect(document.title).toBe('Laboratorio · Sistema de Salud IPRESS')
})
