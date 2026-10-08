import { expect, test, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FuaPrintDialog from '@/components/admission/FuaPrintDialog.vue'
import { emptyFuaInput, FUA_LAYOUT_KEY } from '@/utils/fuaPrint'
import type { FuaPrintSnapshot } from '@/types/fua'

vi.mock('@/assets/fua-referencia.webp', () => ({ default: 'referencia.webp' }))

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
  profesional_documento: null,
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

test('el resumen de la puérpera muestra la fecha real del parto y no el PAB', async () => {
  const body = openSummary({ ...base, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: '2026-09-20' })
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

test('la puérpera sin fecha de parto exige confirmar el faltante antes de imprimir', async () => {
  const body = openSummary({ ...base, grupo_atencion_codigo: 'PUERPERAS', fecha_parto: null })
  await vi.waitFor(() => expect(body.textContent).toContain('Campos pendientes de revisar'))

  const warning = body.querySelector('.el-alert--warning')?.textContent ?? ''
  expect(warning).toContain('Fecha del parto')
  expect(warning).not.toContain('Perímetro abdominal')
  const printButton = findButton(body, 'Imprimir solo datos')
  expect(printButton?.disabled).toBe(true)
})

test('el flujo de calibración habilita la impresión, guarda solo geometría y se recupera', async () => {
  let body = openCalibration(base)
  const printButton = () => findButton(body, 'Imprimir solo datos')

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
