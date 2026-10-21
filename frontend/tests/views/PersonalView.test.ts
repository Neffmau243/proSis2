import { flushPromises, mount } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import ProfessionalsPanel from '@/components/configuracion/ProfessionalsPanel.vue'
import UsersPanel from '@/components/configuracion/UsersPanel.vue'
import StaffCatalogsPanel from '@/components/configuracion/StaffCatalogsPanel.vue'
import type { ProfessionalResponse } from '@/services/profesionales'
import { useAuthStore } from '@/stores/auth'
import PersonalView from '@/views/PersonalView.vue'

const { listProfessionals } = vi.hoisted(() => ({ listProfessionals: vi.fn() }))
const { listUsers } = vi.hoisted(() => ({ listUsers: vi.fn() }))

vi.mock('@/services/profesionales', () => ({
  profesionales: {
    list: listProfessionals,
    create: vi.fn(),
    update: vi.fn(),
    replaceSpecialties: vi.fn(),
    deactivate: vi.fn(),
  },
}))
vi.mock('@/services/usuarios', () => ({
  usuarios: {
    list: listUsers,
    create: vi.fn(),
    updateRoles: vi.fn(),
    resetPassword: vi.fn(),
    deactivate: vi.fn(),
  },
}))
vi.mock('@/services/catalogos', () => ({
  catalogos: {
    profesiones: vi.fn().mockResolvedValue([]),
    especialidades: vi.fn().mockResolvedValue([]),
    profesionales: vi.fn(),
  },
}))

const aProfessional: ProfessionalResponse = {
  id: 5,
  codigo_legacy: null,
  numero_documento: '12345678',
  nombre_completo: 'Luis Torres',
  profesion_id: null,
  colegiatura: 'CMP-009',
  activo: true,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  especialidades: [],
}

const mounted: { unmount: () => void }[] = []

async function mountView(permissions: string[]) {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: stub },
      { path: '/configuracion/personal', name: 'personal', component: stub },
    ],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/configuracion/personal')
  await router.isReady()

  const auth = useAuthStore()
  auth.permisos = permissions

  const wrapper = mount(PersonalView, {
    global: { plugins: [router, pinia, ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  listProfessionals.mockResolvedValue([aProfessional])
  listUsers.mockResolvedValue([])
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})

test('con ambos permisos carga las dos listas y muestra las dos pestañas', async () => {
  const wrapper = await mountView(['PROFESIONAL_GESTIONAR', 'USUARIO_GESTIONAR'])

  expect(listProfessionals).toHaveBeenCalledTimes(1)
  expect(listUsers).toHaveBeenCalledTimes(1)
  expect(wrapper.findComponent(ProfessionalsPanel).exists()).toBe(true)
  expect(wrapper.findComponent(UsersPanel).exists()).toBe(true)
  expect(wrapper.findComponent({ name: 'ElTabs' }).props('modelValue')).toBe('profesionales')
})

test('con solo permiso de profesionales no consulta ni monta cuentas', async () => {
  const wrapper = await mountView(['PROFESIONAL_GESTIONAR'])

  expect(listProfessionals).toHaveBeenCalledTimes(1)
  expect(listUsers).not.toHaveBeenCalled()
  expect(wrapper.findComponent(ProfessionalsPanel).exists()).toBe(true)
  expect(wrapper.findComponent(UsersPanel).exists()).toBe(false)
})

test('con solo permiso de cuentas no consulta profesionales y abre esa pestaña', async () => {
  const wrapper = await mountView(['USUARIO_GESTIONAR'])

  expect(listUsers).toHaveBeenCalledTimes(1)
  expect(listProfessionals).not.toHaveBeenCalled()
  expect(wrapper.findComponent(UsersPanel).exists()).toBe(true)
  expect(wrapper.findComponent(ProfessionalsPanel).exists()).toBe(false)
  expect(wrapper.findComponent({ name: 'ElTabs' }).props('modelValue')).toBe('cuentas')
})

test('crear cuenta desde la ficha cambia de pestaña y vincula al profesional', async () => {
  const wrapper = await mountView(['PROFESIONAL_GESTIONAR', 'USUARIO_GESTIONAR'])

  wrapper.findComponent(ProfessionalsPanel).vm.$emit('create-account', aProfessional)
  await flushPromises()

  expect(wrapper.findComponent({ name: 'ElTabs' }).props('modelValue')).toBe('cuentas')
  // UsersPanel emite consume-prefill cuando recibe un id, lo que prueba el vínculo.
  expect(wrapper.findComponent(UsersPanel).emitted('consume-prefill')).toBeTruthy()
})

test('el catálogo es exclusivo de gestión de profesionales y actualiza los selectores sin remontar la ficha', async () => {
  const wrapper = await mountView(['PROFESIONAL_GESTIONAR', 'USUARIO_GESTIONAR'])
  const professionalPanel = wrapper.findComponent(ProfessionalsPanel)
  const panelElement = professionalPanel.element
  expect(professionalPanel.props('catalogRevision')).toBe(0)
  const tab = wrapper.findAll('[role="tab"]').find((item) => item.text() === 'Profesiones')!
  await tab.trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(StaffCatalogsPanel).props('kind')).toBe('profesion')
  expect(wrapper.findAll('[role="tab"]').map((item) => item.text())).not.toContain(
    'Áreas y especialidades',
  )
  wrapper.findComponent(StaffCatalogsPanel).vm.$emit('created')
  await flushPromises()
  expect(professionalPanel.props('catalogRevision')).toBe(1)
  expect(wrapper.findComponent(ProfessionalsPanel).element).toBe(panelElement)
})

test('una cuenta sin permiso de gestionar profesionales no tiene acceso al catálogo', async () => {
  const wrapper = await mountView(['USUARIO_GESTIONAR'])
  expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).not.toContain('Profesiones')
  expect(wrapper.findComponent(StaffCatalogsPanel).exists()).toBe(false)
})
