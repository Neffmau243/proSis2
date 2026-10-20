import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElPagination, ElTabs } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { Attention } from '@/services/atenciones'
import PacienteDetalleView from '@/views/PacienteDetalleView.vue'
import { aPatient } from '../fixtures/patient'

const { search, getPatient, hasPermission } = vi.hoisted(() => ({
  search: vi.fn(),
  getPatient: vi.fn(),
  hasPermission: vi.fn(),
}))

vi.mock('@/services/atenciones', () => ({ atenciones: { search } }))
vi.mock('@/services/pacientes', () => ({ pacientes: { get: getPatient } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ hasPermission }) }))
vi.mock('@/services/catalogos', () => ({
  catalogos: {
    tiposDocumento: async () => [],
    sexos: async () => [],
    seguros: async () => [],
    establecimientos: async () => ({ items: [] }),
    gruposRiesgo: async () => [],
  },
}))

const mounted: { unmount: () => void }[] = []

beforeEach(() => {
  vi.clearAllMocks()
  getPatient.mockResolvedValue(aPatient())
  hasPermission.mockReturnValue(true)
  search.mockImplementation(async ({ offset }: { offset: number }) => ({
    items: (offset === 0 ? [7, 6, 5, 4, 3] : [2, 1]).map(
      (id) =>
        ({
          id,
          paciente_id: 100,
          fecha_atencion: `2026-10-0${id}T09:00:00`,
          modalidad_atencion_codigo: 'AMBULATORIA',
          grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
          estado: 'ATENDIDO',
        }) as Attention,
    ),
    total: 7,
    limit: 5,
    offset,
    has_more: offset === 0,
  }))
})

afterEach(() => mounted.splice(0).forEach((wrapper) => wrapper.unmount()))

async function mountPatient() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/pacientes/:id', name: 'paciente-detalle', component: { template: '<div />' } },
    ],
  })
  await router.push('/pacientes/100?tab=atenciones')
  await router.isReady()
  const wrapper = mount(PacienteDetalleView, {
    global: {
      plugins: [router, ElementPlus],
      stubs: { ResponsibleDialog: true, RiskDialog: true },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

test('muestra cinco recientes y permite consultar las anteriores sin cargar todo', async () => {
  const wrapper = await mountPatient()
  expect(wrapper.getComponent(ElTabs).props('modelValue')).toBe('atenciones')
  expect(search).toHaveBeenCalledExactlyOnceWith({ paciente_id: 100, limit: 5, offset: 0 })
  const pagination = wrapper.getComponent(ElPagination)
  expect(pagination.props('pageSize')).toBe(5)
  expect(pagination.props('total')).toBe(7)
  const visibleIds = () =>
    wrapper
      .get('#pane-atenciones')
      .findAll('tbody tr')
      .map((row) => row.get('td .cell').text())
  expect(visibleIds()).toEqual(['7', '6', '5', '4', '3'])

  await wrapper.get('.el-pagination .btn-next').trigger('click')
  await flushPromises()
  expect(search).toHaveBeenCalledTimes(2)
  expect(search).toHaveBeenLastCalledWith({ paciente_id: 100, limit: 5, offset: 5 })
  expect(pagination.props('currentPage')).toBe(2)
  expect(visibleIds()).toEqual(['2', '1'])

  await wrapper.get('.el-pagination .btn-prev').trigger('click')
  await flushPromises()
  expect(search).toHaveBeenCalledTimes(3)
  expect(search).toHaveBeenLastCalledWith({ paciente_id: 100, limit: 5, offset: 0 })
  expect(pagination.props('currentPage')).toBe(1)
})

test('sin permiso de lectura clínica no consulta ni ofrece paginar atenciones', async () => {
  hasPermission.mockImplementation((permission: string) => permission !== 'ATENCION_LEER')
  const wrapper = await mountPatient()
  expect(search).not.toHaveBeenCalled()
  expect(wrapper.findComponent(ElPagination).exists()).toBe(false)
})
