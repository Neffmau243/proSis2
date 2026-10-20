import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { Attention } from '@/services/atenciones'
import type { Patient } from '@/services/pacientes'
import type { FuaPrintSnapshot } from '@/types/fua'
import { emptyFuaInput } from '@/utils/fuaPrint'
import AtencionDetalleView from '@/views/AtencionDetalleView.vue'

const { getAttention } = vi.hoisted(() => ({
  getAttention: vi.fn<(id: number) => Promise<Attention>>(),
}))
const { getPatient } = vi.hoisted(() => ({
  getPatient: vi.fn<(id: number) => Promise<Patient>>(),
}))

vi.mock('@/services/atenciones', () => ({
  atenciones: {
    get: getAttention,
    cancel: vi.fn(),
    emitirFua: vi.fn(),
    emitirCertificado: vi.fn(),
    crearReferencia: vi.fn(),
  },
}))
vi.mock('@/services/pacientes', () => ({ pacientes: { get: getPatient } }))
vi.mock('@/services/catalogos', () => ({
  catalogos: { prestaciones: vi.fn(async () => []), establecimientos: vi.fn(async () => []) },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))
vi.mock('@/assets/fua-referencia.webp', () => ({ default: 'referencia.webp' }))

/** Sustituto del diálogo: expone la copia FUA que la vista le entrega. */
const FuaStub = {
  name: 'FuaPrintDialog',
  props: { modelValue: { type: Boolean, required: true }, snapshot: { type: Object, required: true } },
  template: '<div class="fua-stub" />',
}

function snapshot(overrides: Partial<FuaPrintSnapshot> = {}): FuaPrintSnapshot {
  return {
    ...emptyFuaInput(),
    version: 2,
    renipress_preimpreso: true,
    personal_atiende: 'IPRESS',
    lugar_atencion: 'INTRAMURAL',
    tipo_atencion: 'AMBULATORIA',
    ipress_nombre: 'CS PRUEBA',
    profesional_nombre: 'DRA. PRUEBA',
    profesional_documento: null,
    profesional_colegiatura: 'CMP-1',
    tipo_documento: 'DNI',
    tdi: '2',
    numero_documento: '87654321',
    apellido_paterno: 'HISTORIAL',
    apellido_materno: null,
    primer_nombre: 'ALFA',
    otros_nombres: null,
    sexo_codigo: 'F',
    fecha_nacimiento: '1994-02-10',
    historia_clinica: 'HC-A',
    fecha_atencion: '2026-10-08',
    hora_atencion: '09:00:00',
    peso_kg: '60',
    talla_cm: '160',
    presion_sistolica: 110,
    presion_diastolica: 70,
    imc: '23.44',
    perimetro_abdominal_cm: '80',
    grupo_atencion_codigo: 'GENERAL',
    fecha_probable_parto: null,
    fecha_parto: null,
    ...overrides,
  }
}

function attention(overrides: Partial<Attention> = {}): Attention {
  return {
    id: 5,
    paciente_id: 100,
    establecimiento_id: 7,
    profesional_id: 72,
    especialidad_codigo: null,
    consultorio_id: 43,
    consultorio_nombre: null,
    modalidad_atencion_codigo: 'AMBULATORIA',
    grupo_etario_codigo: 'ADULTO',
    grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    fecha_atencion: '2026-10-08',
    fecha_atendido: '2026-10-08',
    historia_clinica_snapshot: 'HC-A',
    edad_anios: 32,
    edad_detallada: '32 años',
    peso_kg: '60',
    talla_cm: '160',
    perimetro_abdominal_cm: '80',
    tipo_embarazo_codigo: null,
    peso_antes_embarazo_kg: null,
    fecha_probable_parto: null,
    fecha_parto: null,
    presion_sistolica: 110,
    presion_diastolica: 70,
    temperatura_c: null,
    imc: '23.44',
    pe: null,
    te: null,
    pt: null,
    referencia_nutricional: null,
    hora_inicio: '09:00',
    hora_fin: '09:30',
    admision: null,
    observaciones: null,
    estado: 'ATENDIDO',
    created_by_usuario_id: 1,
    created_at: '2026-10-08T09:00:00',
    updated_at: '2026-10-08T09:00:00',
    prestaciones: [],
    diagnosticos: [],
    fua_impresion: snapshot(),
    ...overrides,
  }
}

const mounted: { unmount: () => void }[] = []

async function mountView(query: Record<string, string> = {}) {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/atenciones/:id', name: 'atencion-detalle', component: stub },
      { path: '/', name: 'inicio', component: stub },
    ],
  })
  await router.push({ name: 'atencion-detalle', params: { id: '5' }, query })
  await router.isReady()
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(AtencionDetalleView, {
    global: { plugins: [router, pinia, ElementPlus], stubs: { FuaPrintDialog: FuaStub } },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  getAttention.mockReset()
  getPatient.mockReset()
  getAttention.mockResolvedValue(attention())
  // La ficha actual difiere del FUA guardado: la impresión no debe usar estos datos.
  getPatient.mockResolvedValue({ id: 100, primer_nombre: 'ACTUAL' } as unknown as Patient)
})

afterEach(() => {
  while (mounted.length) mounted.pop()?.unmount()
})

test('la impresión usa la copia FUA guardada, no los datos actuales de la ficha', async () => {
  const wrapper = await mountView({ imprimirFua: '1' })

  const dialog = wrapper.findComponent(FuaStub)
  expect(dialog.exists()).toBe(true)
  expect(dialog.props('modelValue')).toBe(true)
  expect(dialog.props('snapshot')).toMatchObject({
    historia_clinica: 'HC-A',
    primer_nombre: 'ALFA',
    numero_documento: '87654321',
  })
})

test('el botón Imprimir S.I.S. abre el diálogo con la copia del paciente', async () => {
  const wrapper = await mountView()
  expect(wrapper.findComponent(FuaStub).props('modelValue')).toBe(false)

  const button = wrapper.findAll('button').find((item) => item.text().includes('Imprimir S.I.S.'))
  expect(button).toBeTruthy()
  await button!.trigger('click')

  expect(wrapper.findComponent(FuaStub).props('modelValue')).toBe(true)
})

test('una atención sin copia FUA no ofrece imprimir y lo advierte', async () => {
  getAttention.mockResolvedValue(attention({ fua_impresion: null }))
  const wrapper = await mountView({ imprimirFua: '1' })

  expect(wrapper.findComponent(FuaStub).exists()).toBe(false)
  expect(
    wrapper.findAll('button').some((item) => item.text().includes('Imprimir S.I.S.')),
  ).toBe(false)
  expect(wrapper.text()).toContain('No se reconstruye con datos actuales del paciente')
})

test('consulta los números recibidos conservando ceros sin reconstruirlos desde el paciente', async () => {
  getAttention.mockResolvedValue(attention({ numero_referencia_ingreso: '001565', numero_contrarreferencia_ingreso: '00007' }))
  const wrapper = await mountView()
  expect(wrapper.text()).toContain('N.º de referencia recibida')
  expect(wrapper.text()).toContain('001565')
  expect(wrapper.text()).toContain('N.º de contrarreferencia recibida')
  expect(wrapper.text()).toContain('00007')
})
