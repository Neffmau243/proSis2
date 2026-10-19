import { expect, test, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FuaPrintDialog from '@/components/admission/FuaPrintDialog.vue'
import { defaultFuaLayout, emptyFuaInput, FUA_LAYOUT_KEY } from '@/utils/fuaPrint'
import type { FuaPrintSnapshot } from '@/types/fua'

vi.mock('@/assets/fua-v02-referencia.png', () => ({ default: '/fua-v02-referencia.png' }))

const base: FuaPrintSnapshot = {
  ...emptyFuaInput(),
  version: 2,
  renipress_preimpreso: true,
  personal_atiende: 'IPRESS',
  lugar_atencion: 'INTRAMURAL',
  tipo_atencion: 'AMBULATORIA',
  codigo_renipress: null,
  sis_diresa: '040',
  sis_tipo: '2',
  sis_numero: '00000001',
  etnia_codigo: '58',
  ipress_nombre: 'CS PRUEBA',
  profesional_nombre: 'DRA. PRUEBA',
  profesional_documento: '00000002',
  profesional_colegiatura: 'CMP-1',
  tipo_documento: 'DNI',
  tdi: '2',
  numero_documento: '01234567',
  apellido_paterno: 'PRUEBA',
  apellido_materno: null,
  primer_nombre: 'ANA',
  otros_nombres: null,
  sexo_codigo: 'F',
  fecha_nacimiento: '1994-02-10',
  historia_clinica: 'HC-1',
  fecha_atencion: '2026-10-01',
  hora_atencion: '09:00:00',
  peso_kg: '60.00',
  talla_cm: '160.00',
  presion_sistolica: 110,
  presion_diastolica: 70,
  imc: '23.438',
  perimetro_abdominal_cm: '80.00',
  grupo_atencion_codigo: 'GENERAL',
  fecha_probable_parto: null,
  fecha_parto: null,
}

const mounted: { unmount: () => void }[] = []

function openSummary(snapshot: FuaPrintSnapshot) {
  const wrapper = mount(FuaPrintDialog, {
    props: { modelValue: true, snapshot },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
  mounted.push(wrapper)
  return document.body
}

function findButton(body: HTMLElement, text: string) {
  return [...body.querySelectorAll('button')].find((button) => button.textContent?.trim() === text)
}

function findCheckbox(body: HTMLElement, text: string) {
  const label = [...body.querySelectorAll('label.el-checkbox')].find((item) =>
    item.textContent?.includes(text),
  )
  return label?.querySelector<HTMLInputElement>('input[type="checkbox"]')
}

/** Abre la vista previa y cambia a la pestaña de calibración, como el usuario. */
function openCalibration(snapshot: FuaPrintSnapshot) {
  const body = openSummary(snapshot)
  const tab = [...body.querySelectorAll<HTMLElement>('.el-tabs__item')].find((item) =>
    item.textContent?.includes('Vista previa y calibración'),
  )
  tab?.click()
  return body
}

afterEach(() => {
  while (mounted.length) mounted.pop()?.unmount()
  document.body.innerHTML = ''
  localStorage.clear()
})

test('el resumen distingue responsable y categoría, y muestra el RENIPRESS aunque no se imprima', async () => {
  const body = openSummary({ ...base, codigo_renipress: '00001291' })
  await vi.waitFor(() =>
    expect(body.textContent).toContain('Profesional responsable de la atención'),
  )
  expect(body.textContent).toContain('DRA. PRUEBA')
  expect(body.textContent).toContain('Personal que atiende · categoría FUA')
  expect(body.textContent).toContain('De la IPRESS')
  expect(body.textContent).toContain('IPRESS de la atención')
  expect(body.textContent).toContain('00001291')
  expect(body.textContent).toContain('Configurado como preimpreso')
})

test('el bloqueo por calibración explica el paso pendiente y abre la pestaña correcta', async () => {
  const body = openSummary(base)
  await vi.waitFor(() => expect(body.textContent).toContain('Falta confirmar la calibración'))
  findButton(body, 'Ir a calibración')!.click()
  await vi.waitFor(() =>
    expect(body.querySelector('.el-tabs__item.is-active')?.textContent).toContain(
      'Vista previa y calibración',
    ),
  )
  findButton(body, 'Usar A4 (210 × 297 mm)')!.click()
  findButton(body, 'Guardar calibración')!.click()
  const saved = JSON.parse(localStorage.getItem(FUA_LAYOUT_KEY)!)
  expect(saved).toMatchObject({ width: 210, height: 297, calibrated: false })
})

test('la vista previa y el resumen separan DIRESA, tipo y número SIS', async () => {
  const body = openCalibration(base)
  await vi.waitFor(() =>
    expect(body.querySelector('[aria-label="Ajustar SIS · Tipo"]')?.textContent?.trim()).toBe('2'),
  )
  expect(body.querySelector('[aria-label="Ajustar SIS · DIRESA"]')?.textContent?.trim()).toBe('040')
  expect(body.querySelector('[aria-label="Ajustar SIS · Número / RN"]')?.textContent?.trim()).toBe('00000001')
  expect(body.textContent).toContain('040 · 2 · 00000001')
  expect(body.textContent).not.toContain('2-00000001')
})

test('una historia clínica larga no bloquea la impresión con posiciones ya calibradas', async () => {
  localStorage.setItem(FUA_LAYOUT_KEY, JSON.stringify({ ...defaultFuaLayout(), calibrated: true }))
  const body = openCalibration({ ...base, historia_clinica: 'DEMO-ETNIA-98032888' })
  await vi.waitFor(() =>
    expect(findButton(body, 'Imprimir sobre FUA preimpresa')?.disabled).toBe(false),
  )
  expect(body.textContent).not.toContain('Historia clínica: texto no cabe')
  const preview = body.querySelector<HTMLElement>('[aria-label="Ajustar Historia clínica"]')!
  expect(Number.parseFloat(preview.style.fontSize)).toBeLessThan(8)
  expect(preview.textContent).toContain('DEMO-ETNIA-98032888')
})

test('el resumen de la puérpera muestra la fecha real del parto y no el PAB', async () => {
  const body = openSummary({
    ...base,
    grupo_atencion_codigo: 'PUERPERAS',
    fecha_parto: '2026-09-20',
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Fecha del parto'))

  expect(body.textContent).toContain('2026-09-20')
  expect(body.textContent).not.toContain('Fecha probable de parto')
  expect(body.textContent).not.toContain('Perímetro abdominal')
})

test('el resumen de la gestante muestra la FPP y no la fecha del parto', async () => {
  const body = openSummary({
    ...base,
    grupo_atencion_codigo: 'GESTANTES',
    fecha_probable_parto: '2027-01-15',
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Fecha probable de parto'))

  expect(body.textContent).toContain('2027-01-15')
  expect(body.textContent).not.toContain('Fecha del parto')
  expect(body.textContent).not.toContain('Perímetro abdominal')
})

test('el resumen del grupo general conserva el perímetro abdominal', async () => {
  const body = openSummary(base)
  await vi.waitFor(() => expect(body.textContent).toContain('Perímetro abdominal'))

  expect(body.textContent).toContain('80')
  expect(body.textContent).not.toContain('Fecha del parto')
  expect(body.textContent).not.toContain('Fecha probable de parto')
})

test('la FUA conserva la tabla nutricional específica del grupo', async () => {
  let body = openSummary({
    ...base,
    grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    pe: '0.125',
    te: '-0.250',
    pt: '0.375',
    diagnostico_peso_edad: 'Normal',
    diagnostico_talla_edad: 'Normal',
    diagnostico_peso_talla: 'Normal',
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Valoración nutricional conservada'))
  expect([...body.querySelectorAll('.nutrition-table th')].map((cell) => cell.textContent)).toEqual(
    ['P/E', 'T/E', 'P/T'],
  )

  while (mounted.length) mounted.pop()?.unmount()
  document.body.innerHTML = ''
  body = openSummary({
    ...base,
    grupo_atencion_codigo: 'GESTANTES',
    imc_pregestacional: '21.484',
    diagnostico_imc: 'Normal',
    ganancia_peso_kg: '10',
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Ganancia de peso'))
  expect([...body.querySelectorAll('.nutrition-table th')].map((cell) => cell.textContent)).toEqual(
    ['IMC', 'Dx IMC', 'Ganancia de peso'],
  )

  while (mounted.length) mounted.pop()?.unmount()
  document.body.innerHTML = ''
  body = openSummary({
    ...base,
    grupo_atencion_codigo: 'PUERPERAS',
    imc_pregestacional: '21.484',
    diagnostico_imc: 'Normal',
    ganancia_peso_kg: '9',
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Dx IMC'))
  expect([...body.querySelectorAll('.nutrition-table th')].map((cell) => cell.textContent)).toEqual(
    ['IMC', 'Dx IMC'],
  )
  expect(body.querySelector('.nutrition-table')?.textContent).not.toContain('Ganancia de peso')
})

test('un niño sin puntajes conserva la tabla infantil indicada por el servidor', async () => {
  const body = openSummary({
    ...base,
    grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    grupo_referencia: 'INFANTIL',
    estado_nutricional: 'DATOS_INCOMPLETOS',
    pe: null,
    te: null,
    pt: null,
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Valoración nutricional conservada'))
  expect([...body.querySelectorAll('.nutrition-table th')].map((cell) => cell.textContent)).toEqual(
    ['P/E', 'T/E', 'P/T'],
  )
  expect(body.querySelector('.nutrition-table')?.textContent).not.toContain('Dx IMC')
})

test('un adolescente conserva el grupo escolar con indicadores parcialmente aplicables', async () => {
  const body = openSummary({
    ...base,
    grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    grupo_referencia: 'ESCOLAR',
    estado_nutricional: 'CALCULADO',
    pe: null,
    te: '-0.500',
    pt: null,
  })
  await vi.waitFor(() => expect(body.textContent).toContain('Valoración nutricional conservada'))
  const rows = [...body.querySelectorAll('.nutrition-table tr')]
  expect(rows.map((row) => row.querySelector('th')?.textContent)).toEqual(['P/E', 'T/E', 'P/T'])
  expect(rows.map((row) => row.querySelector('td')?.textContent)).toEqual([
    'No aplica',
    'Z: -0.500',
    'No aplica',
  ])
})

test('la puérpera sin fecha de parto exige confirmar el faltante antes de imprimir', async () => {
  const body = openSummary({ ...base, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: null })
  await vi.waitFor(() => expect(body.textContent).toContain('Campos pendientes de revisar'))

  const warning = body.querySelector('.el-alert--warning')?.textContent ?? ''
  expect(warning).toContain('Fecha del parto')
  expect(warning).not.toContain('Perímetro abdominal')
  const printButton = findButton(body, 'Imprimir sobre FUA preimpresa')
  expect(printButton?.disabled).toBe(true)
})

test('el flujo de calibración habilita la impresión, guarda solo geometría y se recupera', async () => {
  let body = openCalibration(base)
  const printButton = () => findButton(body, 'Imprimir sobre FUA preimpresa')

  // Sin calibrar, la impresión real queda bloqueada aunque los datos estén completos.
  await vi.waitFor(() => expect(findCheckbox(body, 'Comprobé')).toBeTruthy())
  expect(printButton()?.disabled).toBe(true)

  // Confirmar la prueba física habilita la impresión.
  findCheckbox(body, 'Comprobé')!.click()
  await vi.waitFor(() => expect(printButton()?.disabled).toBe(false))

  // Guardar persiste solo geometría: nunca datos clínicos del paciente.
  findButton(body, 'Guardar calibración')!.click()
  const saved = localStorage.getItem(FUA_LAYOUT_KEY)
  expect(saved).toBeTruthy()
  expect(saved).not.toContain(base.numero_documento!)
  expect(saved).not.toContain(base.apellido_paterno!)
  expect(JSON.parse(saved!).calibrated).toBe(true)

  // Reabrir el diálogo reutiliza la calibración guardada.
  while (mounted.length) mounted.pop()?.unmount()
  document.body.innerHTML = ''
  body = openCalibration(base)
  await vi.waitFor(() => expect(printButton()?.disabled).toBe(false))

  // Cualquier ajuste de geometría invalida la calibración hasta revisarla de nuevo.
  findCheckbox(body, 'Imprimir este campo')!.click()
  await vi.waitFor(() => expect(printButton()?.disabled).toBe(true))
})

test('la impresión de prueba para calibrar no lleva datos del paciente', async () => {
  const body = openCalibration(base)
  await vi.waitFor(() => expect(findButton(body, 'Imprimir prueba sin datos')).toBeTruthy())

  findButton(body, 'Imprimir prueba sin datos')!.click()

  await vi.waitFor(() =>
    expect(document.querySelector('iframe[title="Salida de impresión FUA"]')).toBeTruthy(),
  )
  const output = document.querySelector('iframe[title="Salida de impresión FUA"]')
  const srcdoc = output?.getAttribute('srcdoc') ?? ''
  expect(srcdoc).toContain('outline')
  expect(srcdoc).not.toContain(base.numero_documento!)
  expect(srcdoc).not.toContain(base.historia_clinica!)
})

test('confirmar calibración se guarda automáticamente y cambiar paciente o campo no la invalida', async () => {
  let body = openCalibration(base)
  await vi.waitFor(() => expect(findCheckbox(body, 'Comprobé')).toBeTruthy())
  findCheckbox(body, 'Comprobé')!.click()
  await vi.waitFor(() =>
    expect(JSON.parse(localStorage.getItem(FUA_LAYOUT_KEY)!).calibrated).toBe(true),
  )
  body.querySelector<HTMLButtonElement>('[aria-label="Ajustar Historia clínica"]')!.click()
  await vi.waitFor(() =>
    expect(findButton(body, 'Imprimir sobre FUA preimpresa')?.disabled).toBe(false),
  )
  while (mounted.length) mounted.pop()?.unmount()
  document.body.innerHTML = ''
  body = openCalibration({ ...base, numero_documento: '00000003', historia_clinica: 'HC-OTRO' })
  await vi.waitFor(() =>
    expect(findButton(body, 'Imprimir sobre FUA preimpresa')?.disabled).toBe(false),
  )
  expect(localStorage.getItem(FUA_LAYOUT_KEY)).not.toContain('HC-OTRO')
  expect(localStorage.getItem(FUA_LAYOUT_KEY)).not.toContain('00000003')
  findButton(body, 'Usar A4 (210 × 297 mm)')!.click()
  await vi.waitFor(() =>
    expect(JSON.parse(localStorage.getItem(FUA_LAYOUT_KEY)!)).toMatchObject({
      width: 210,
      height: 297,
      calibrated: false,
    }),
  )
})

test('la revisión con referencia permite comprobar el PDF antes de confirmar la prueba física', async () => {
  const body = openCalibration(base)
  await vi.waitFor(() => expect(findButton(body, 'Ver FUA / guardar PDF')?.disabled).toBe(false))
  expect(findButton(body, 'Imprimir sobre FUA preimpresa')?.disabled).toBe(true)
  expect(findButton(body, 'Ver FUA / guardar PDF')?.classList.contains('el-button--primary')).toBe(
    true,
  )
  expect(
    findButton(body, 'Imprimir sobre FUA preimpresa')?.classList.contains('el-button--primary'),
  ).toBe(false)
  findButton(body, 'Ver FUA / guardar PDF')!.click()
  await vi.waitFor(() =>
    expect(document.querySelector('iframe')?.getAttribute('srcdoc')).toContain('<img'),
  )
  const srcdoc = document.querySelector('iframe')?.getAttribute('srcdoc') ?? ''
  expect(srcdoc).toContain('PRELLENADO PARCIAL')
  expect(srcdoc).toContain(base.numero_documento)
})

test('un fallo al leer la calibración sigue visible al abrir el diálogo', async () => {
  localStorage.setItem(FUA_LAYOUT_KEY, '{')
  const body = openSummary(base)
  await vi.waitFor(() =>
    expect(body.textContent).toContain('No se pudo leer la calibración guardada'),
  )
  expect(localStorage.getItem(FUA_LAYOUT_KEY)).toBe('{')
})

test('una calibración antigua muestra la referencia única sin perder posiciones y migra una sola vez', async () => {
  const legacy = { ...defaultFuaLayout(), template: 'historica', calibrated: true }
  legacy.fields.find((field) => field.id === 'historia_clinica')!.x = 120
  localStorage.setItem(FUA_LAYOUT_KEY, JSON.stringify(legacy))
  let body = openCalibration(base)
  await vi.waitFor(() =>
    expect(body.querySelector<HTMLImageElement>('.fua-background')?.getAttribute('src')).toBe(
      '/fua-v02-referencia.png',
    ),
  )
  expect(body.querySelector('#fua-scan')).toBeNull()
  const restored = JSON.parse(localStorage.getItem(FUA_LAYOUT_KEY)!)
  expect(restored.template).toBe('sis-v02')
  expect(restored.calibrated).toBe(false)
  expect(restored.fields).toEqual(legacy.fields)
  findCheckbox(body, 'Comprobé')!.click()
  await vi.waitFor(() =>
    expect(JSON.parse(localStorage.getItem(FUA_LAYOUT_KEY)!).calibrated).toBe(true),
  )
  while (mounted.length) mounted.pop()?.unmount()
  document.body.innerHTML = ''
  body = openCalibration(base)
  await vi.waitFor(() =>
    expect(findButton(body, 'Imprimir sobre FUA preimpresa')?.disabled).toBe(false),
  )
})
