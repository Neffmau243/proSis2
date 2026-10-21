import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import type { Patient } from '@/services/pacientes'
import { useAuthStore } from '@/stores/auth'
import DashboardView from '@/views/DashboardView.vue'

vi.mock('@/services/pacientes', () => ({
  pacientes: { search: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn() },
}))

vi.mock('@/services/catalogos', () => ({
  catalogos: { sexos: vi.fn() },
}))

const { pacientes } = await import('@/services/pacientes')
const { catalogos } = await import('@/services/catalogos')
const search = vi.mocked(pacientes.search)

function patient(overrides: Partial<Patient> = {}): Patient {
  return {
    id: 1,
    historia_clinica: 'HC-0001',
    historia_familiar: null,
    tipo_documento_codigo: 'DNI',
    numero_documento: '12345678',
    fecha_nacimiento: '1990-05-10',
    apellido_paterno: 'Quispe',
    apellido_materno: 'Mamani',
    primer_nombre: 'Ana',
    otros_nombres: 'María',
    sexo_codigo: 'F',
    ubigeo_residencia_codigo: null,
    distrito_residencia: null,
    localidad: null,
    direccion: null,
    establecimiento_registro_id: null,
    seguro_id: null,
    telefono_principal: null,
    condicion: null,
    estado: true,
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    responsables: [],
    riesgos: [],
    ...overrides,
  } as Patient
}

function pageOf(items: Patient[]) {
  return { items, total: items.length, limit: 100, offset: 0, has_more: false }
}

const mounted: { unmount: () => void }[] = []

async function mountView(permissions: string[] = ['PACIENTE_EDITAR', 'PACIENTE_DAR_BAJA']) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'inicio', component: { template: '<div />' } },
      { path: '/pacientes/nuevo', name: 'paciente-nuevo', component: { template: '<div />' } },
    ],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/')
  await router.isReady()

  const auth = useAuthStore()
  auth.permisos = permissions

  const wrapper = mount(DashboardView, {
    // ``main.ts`` registra los iconos de Element Plus en la aplicación real.
    global: { plugins: [router, pinia, ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

/**
 * Element Plus escucha el `change` del input nativo, y happy-dom no activa un
 * input al hacer clic en su etiqueta: se marca y se dispara el cambio real.
 */
async function toggleCheckbox(checkbox: { find: (selector: string) => { element: unknown; trigger: (event: string) => Promise<void> } }) {
  const input = checkbox.find('input')
  ;(input.element as HTMLInputElement).checked = true
  await input.trigger('change')
}

/** La búsqueda se dispara tras el retardo anti-ráfaga de la vista. */
async function typeAndSettle(wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'], text: string) {
  await wrapper.find('.filters__input input').setValue(text)
  await vi.advanceTimersByTimeAsync(300)
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  catalogos.sexos = vi.fn().mockResolvedValue([{ codigo: 'F', nombre: 'Femenino', activo: true }])
  search.mockResolvedValue(pageOf([]))
  usePacienteSeleccionado().seleccionar(null)
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'info').mockImplementation(() => ({}) as never)
})

afterEach(() => {
  // Las vistas comparten el estado singleton del paciente seleccionado, así que
  // cada montaje debe desmontarse para no dejar vigilantes escuchando.
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.useRealTimers()
  vi.restoreAllMocks()
})

test('sin término la tabla lista la base completa con el límite máximo de la API', async () => {
  search.mockResolvedValue(pageOf([patient()]))
  const { wrapper } = await mountView()

  expect(search).toHaveBeenCalledWith({ incluir_inactivos: false, limit: 100, offset: 0 })
  expect(wrapper.text()).toContain('Quispe')
  expect(wrapper.text()).toContain('1 paciente(s) registrado(s)')
  // Sin término escrito no se autoselecciona nada.
  expect(usePacienteSeleccionado().seleccionado.value).toBeNull()
})

test('muestra el total del padrón aunque solo haya cargado el primer bloque', async () => {
  const items = Array.from({ length: 100 }, (_, index) => patient({ id: index + 1 }))
  search.mockResolvedValue({ ...pageOf(items), total: 28962, has_more: true })
  const { wrapper } = await mountView()

  expect(wrapper.find('.page-header__sub').text()).toContain('28962 paciente(s) registrado(s)')
  expect(wrapper.findAll('.el-table__body-wrapper tbody tr')).toHaveLength(100)
  expect(search).toHaveBeenCalledTimes(1)
})

test('el DNI se busca con q y el criterio de historia clínica exacta cambia el filtro', async () => {
  const { wrapper } = await mountView()
  search.mockClear()

  await typeAndSettle(wrapper, '12345678')
  expect(search).toHaveBeenLastCalledWith({
    incluir_inactivos: false,
    limit: 100,
    offset: 0,
    q: '12345678',
  })

  // H. Clínica exacta restringe por número completo, no por coincidencia parcial.
  const checkboxes = wrapper.findAll('.filters__modes .el-checkbox')
  expect(checkboxes).toHaveLength(5)
  const exacta = checkboxes.find((item) => item.text() === 'H. Clínica exacta')!
  await toggleCheckbox(exacta)
  await vi.advanceTimersByTimeAsync(300)
  await flushPromises()

  expect(search).toHaveBeenLastCalledWith({
    incluir_inactivos: false,
    limit: 100,
    offset: 0,
    historia_clinica: '12345678',
  })
})

test('una única coincidencia queda seleccionada para Ver / Borrar; varias no', async () => {
  const only = patient()
  search.mockResolvedValue(pageOf([only]))
  const { wrapper } = await mountView()

  await typeAndSettle(wrapper, 'Quispe')

  expect(usePacienteSeleccionado().seleccionado.value).toEqual(only)
  expect(wrapper.text()).toContain('1 coincidencia · paciente seleccionado.')

  search.mockResolvedValue(pageOf([only, patient({ id: 2, numero_documento: '87654321' })]))
  await typeAndSettle(wrapper, 'Quispe Mamani')

  expect(usePacienteSeleccionado().seleccionado.value).toEqual(only)
  expect(wrapper.text()).toContain('2 coincidencias.')
})

test('hacer clic en una fila define el paciente de la barra lateral', async () => {
  const row = patient()
  search.mockResolvedValue(pageOf([row]))
  const { wrapper } = await mountView()

  const table = wrapper.findComponent({ name: 'ElTable' })
  table.vm.$emit('row-click', row)
  await flushPromises()

  expect(usePacienteSeleccionado().seleccionado.value).toEqual(row)
  expect(wrapper.text()).toContain('Quispe Mamani Ana María seleccionado')
})

test('el nombre del DNI solo se anuncia cuando la coincidencia es exacta', async () => {
  const { wrapper } = await mountView()
  search.mockResolvedValue(pageOf([patient({ numero_documento: '12345678' })]))

  await typeAndSettle(wrapper, '12345678')
  expect(wrapper.text()).toContain('Quispe Mamani Ana María')

  // Otro criterio distinto del DNI no anuncia coincidencia de documento.
  search.mockResolvedValue(pageOf([patient({ numero_documento: '11111111' })]))
  await typeAndSettle(wrapper, '111')
  expect(wrapper.text()).not.toContain('11111111 -')
})

test('incluir bajas viaja como flag y solo lo ve quien puede dar de baja', async () => {
  const { wrapper } = await mountView(['PACIENTE_EDITAR'])
  const criteria = wrapper.find('.filters__criteria')
  expect(criteria.text()).not.toContain('Incluir bajas')

  const { wrapper: adminWrapper } = await mountView(['PACIENTE_DAR_BAJA'])
  search.mockClear()

  const checkbox = adminWrapper
    .findAll('.filters__criteria > .el-checkbox')
    .find((item) => item.text().includes('Incluir bajas'))!
  await toggleCheckbox(checkbox)
  await vi.advanceTimersByTimeAsync(300)
  await flushPromises()

  expect(search).toHaveBeenLastCalledWith({ incluir_inactivos: true, limit: 100, offset: 0 })
})

test('el botón de refresco repite la búsqueda sin esperar el debounce', async () => {
  const { wrapper } = await mountView()
  search.mockClear()

  await wrapper.find('.filters__row .el-button').trigger('click')
  await flushPromises()

  expect(search).toHaveBeenCalledTimes(1)
})

test('un error del backend se muestra al usuario sin romper la tabla', async () => {
  const { wrapper } = await mountView()
  const failure = Object.assign(new Error('No se pudo consultar la base de datos.'), {
    name: 'ApiError',
  })
  search.mockRejectedValue(failure)

  await typeAndSettle(wrapper, 'Quispe')

  expect(ElMessage.error).toHaveBeenCalledWith('No se pudo consultar la base de datos.')
  expect(wrapper.text()).toContain('Sin resultados')
})

test('tras dar de baja al paciente seleccionado la tabla se recarga', async () => {
  const { wrapper } = await mountView()
  search.mockClear()

  usePacienteSeleccionado().notificarCambio()
  await flushPromises()

  expect(search).toHaveBeenCalledTimes(1)
  expect(wrapper.text()).toContain('0 paciente(s) registrado(s)')
})

test('el buscador rota criterios hasta que el backend admita el filtro', async () => {
  const { wrapper } = await mountView()
  const modes = wrapper.findAll('.filters__modes .el-checkbox')
  const labels = modes.map((item) => item.text())
  expect(labels).toEqual([
    'DNI',
    'H. Clínica exacta',
    'H. Clínica similar',
    'Apellidos y nombres',
    'H. Familiar',
  ])
  // Historia familiar sigue deshabilitada hasta que la API la soporte.
  const familiar = modes[4]!
  expect(familiar.classes()).toContain('is-disabled')
  expect(familiar.find('input').attributes('disabled')).toBeDefined()

  const placeholder = wrapper.find('.filters__input input').attributes('placeholder')
  expect(placeholder).toMatch(/DNI/)
})
