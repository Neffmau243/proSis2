import { flushPromises, mount } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import AppLayout from '@/layouts/AppLayout.vue'
import type { Patient } from '@/services/pacientes'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/services/pacientes', () => ({
  pacientes: { deactivate: vi.fn(), search: vi.fn() },
}))

const { pacientes } = await import('@/services/pacientes')
const deactivate = vi.mocked(pacientes.deactivate)

const patient = {
  id: 77,
  estado: true,
  tipo_documento_codigo: 'DNI',
  numero_documento: '12345678',
  historia_clinica: 'HC-0001',
  apellido_paterno: 'Quispe',
  apellido_materno: 'Mamani',
  primer_nombre: 'Ana',
  otros_nombres: null,
} as unknown as Patient

const mounted: { unmount: () => void }[] = []

async function mountLayout(permissions: string[], path = '/') {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' }, meta: { title: 'Base de datos' } },
      { path: '/atenciones', component: stub, meta: { title: 'Atenciones' } },
      { path: '/login', name: 'login', component: stub, meta: { title: 'Iniciar sesión' } },
      { path: '/pacientes/nuevo', name: 'paciente-nuevo', component: stub },
      { path: '/pacientes/:id', name: 'paciente-detalle', component: stub },
      { path: '/pacientes/:id/editar', name: 'paciente-editar', component: stub },
      { path: '/configuracion/establecimientos', component: stub },
      { path: '/configuracion/areas', component: stub },
      { path: '/configuracion/consultorios', component: stub },
      { path: '/configuracion/servicios', component: stub },
      { path: '/admision', name: 'admision', component: stub },
      { path: '/laboratorio', name: 'laboratorio', component: stub },
      { path: '/cuenta/cambiar-contrasena', name: 'cambiar-contrasena', component: stub },
      { path: '/configuracion/personal', name: 'personal', component: stub },
    ],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push(path)
  await router.isReady()

  const auth = useAuthStore()
  auth.permisos = permissions
  auth.nombreUsuario = 'ana.quispe'
  auth.roles = ['ADMIN']

  const wrapper = mount(AppLayout, {
    global: { plugins: [router, pinia, ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router, auth }
}

function button(wrapper: Awaited<ReturnType<typeof mountLayout>>['wrapper'], label: string) {
  const found = wrapper.findAll('button').find((item) => item.text().includes(label))
  if (!found) throw new Error(`No se encontró el botón "${label}"`)
  return found
}

beforeEach(() => {
  vi.clearAllMocks()
  usePacienteSeleccionado().seleccionar(null)
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})

test('el menú se arma con permisos, no con roles escritos', async () => {
  const { wrapper } = await mountLayout(['PACIENTE_LEER', 'ATENCION_LEER', 'ATENCION_CREAR'])
  const links = wrapper.findAll('.side__link').map((item) => item.text())

  expect(links).toEqual(['Pacientes'])
  expect(wrapper.text()).not.toContain('Clínico')
  expect(wrapper.text()).not.toContain('Historial de atenciones')
  expect(wrapper.text()).not.toContain('Nueva atención')
  expect(wrapper.text()).not.toContain('Usuarios')
  expect(wrapper.text()).not.toContain('Auditoría')
  // Acciones principales: solo las permitidas.
  expect(button(wrapper, 'Admisión').exists()).toBe(true)
  expect(wrapper.text()).not.toContain('Paciente nuevo')
})

test('los permisos administrativos revelan sus secciones y la corrección de datos', async () => {
  const { wrapper } = await mountLayout([
    'PACIENTE_LEER',
    'PACIENTE_EDITAR',
    'ATENCION_CREAR',
    'USUARIO_GESTIONAR',
    'AUDITORIA_LEER',
    'GRUPO_ETARIO_CONFIGURAR',
    'PROFESIONAL_GESTIONAR',
    'CONSULTORIO_GESTIONAR',
  ])
  const links = wrapper.findAll('.side__link').map((item) => item.text())

  expect(links).toEqual([
    'Pacientes',
    'Establecimientos',
    'Áreas de atención',
    'Consultorios',
    'Servicios / especialidades',
    'Personal y cuentas',
    'Auditoría',
    'Grupos etarios',
  ])
  expect(wrapper.text()).toContain('Paciente nuevo')
  // OCULTO temporalmente: el botón "Modificar datos" está comentado en el layout.
  // expect(button(wrapper, 'Modificar datos').exists()).toBe(true)
})

test('sin paciente seleccionado las acciones quedan deshabilitadas y se explica por qué', async () => {
  const { wrapper } = await mountLayout(['PACIENTE_LEER', 'ATENCION_CREAR', 'PACIENTE_EDITAR'])

  expect(wrapper.find('.side__patient-hint').text()).toContain(
    'Seleccione un paciente en la tabla Base de datos',
  )
  expect(button(wrapper, 'Ver paciente').attributes('disabled')).toBeDefined()
  expect(button(wrapper, 'Admisión').attributes('disabled')).toBeDefined()
})

test('el paciente seleccionado muestra su nombre, documento e historia clínica', async () => {
  const { wrapper } = await mountLayout(['PACIENTE_LEER'])
  usePacienteSeleccionado().seleccionar(patient)
  await flushPromises()

  expect(wrapper.find('.side__patient-name').text()).toBe('Quispe Mamani Ana')
  expect(wrapper.find('.side__patient-meta').text()).toContain('DNI 12345678')
  expect(wrapper.find('.side__patient-meta').text()).toContain('HC HC-0001')
  expect(button(wrapper, 'Ver paciente').attributes('disabled')).toBeUndefined()
})

test('ver paciente navega al destino documentado', async () => {
  const { wrapper, router } = await mountLayout([
    'PACIENTE_LEER',
    'PACIENTE_EDITAR',
    'ATENCION_CREAR',
  ])
  usePacienteSeleccionado().seleccionar(patient)
  await flushPromises()

  await button(wrapper, 'Ver paciente').trigger('click')
  await flushPromises()
  await flushPromises()
  expect(router.currentRoute.value.name).toBe('paciente-detalle')
  expect(router.currentRoute.value.params.id).toBe('77')
})

test('el administrador edita al paciente sin entrar a Admisión', async () => {
  const { wrapper, router } = await mountLayout(['PACIENTE_LEER', 'PACIENTE_EDITAR'])
  usePacienteSeleccionado().seleccionar(patient)
  await flushPromises()
  await button(wrapper, 'Editar paciente').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.name).toBe('paciente-editar')
  expect(router.currentRoute.value.params.id).toBe('77')
  expect(wrapper.findAll('button').some((item) => item.text() === 'Admisión')).toBe(false)
})

test('la admisión exige un paciente y viaja con su identificador', async () => {
  const { wrapper, router } = await mountLayout(['PACIENTE_LEER', 'ATENCION_CREAR'])

  usePacienteSeleccionado().seleccionar(null)
  await flushPromises()
  await button(wrapper, 'Admisión').trigger('click')
  await flushPromises()
  await flushPromises()
  expect(router.currentRoute.value.name).not.toBe('admision')

  usePacienteSeleccionado().seleccionar(patient)
  await flushPromises()
  await button(wrapper, 'Admisión').trigger('click')
  await flushPromises()
  await flushPromises()
  expect(router.currentRoute.value.name).toBe('admision')
  expect(router.currentRoute.value.query.patientId).toBe('77')
})

test('borrar paciente pide confirmación, da de baja y refresca la tabla', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
  deactivate.mockResolvedValue({
    id: 77,
    estado: false,
    mensaje: 'Paciente dado de baja.',
  })
  const { wrapper } = await mountLayout(['PACIENTE_LEER', 'PACIENTE_DAR_BAJA'])
  const state = usePacienteSeleccionado()
  state.seleccionar(patient)
  await flushPromises()
  const version = state.dataVersion.value

  await button(wrapper, 'Borrar paciente').trigger('click')
  await flushPromises()

  expect(confirm).toHaveBeenCalledWith(
    expect.stringContaining('¿Dar de baja a Quispe Mamani Ana?'),
    'Borrar paciente',
    expect.objectContaining({ type: 'warning' }),
  )
  expect(deactivate).toHaveBeenCalledWith(77)
  expect(ElMessage.success).toHaveBeenCalledWith('Paciente dado de baja.')
  expect(state.seleccionado.value).toBeNull()
  expect(state.dataVersion.value).toBe(version + 1)
})

test('cancelar la confirmación no toca el backend', async () => {
  vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
  const { wrapper } = await mountLayout(['PACIENTE_LEER', 'PACIENTE_DAR_BAJA'])
  const state = usePacienteSeleccionado()
  state.seleccionar(patient)
  await flushPromises()
  const version = state.dataVersion.value

  await button(wrapper, 'Borrar paciente').trigger('click')
  await flushPromises()

  expect(deactivate).not.toHaveBeenCalled()
  expect(state.seleccionado.value).toEqual(patient)
  expect(state.dataVersion.value).toBe(version)
})

test('un error al dar de baja se informa y no descarta al paciente', async () => {
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
  deactivate.mockRejectedValue(new Error('El paciente tiene atenciones.'))
  const { wrapper } = await mountLayout(['PACIENTE_LEER', 'PACIENTE_DAR_BAJA'])
  const state = usePacienteSeleccionado()
  state.seleccionar(patient)
  await flushPromises()
  const version = state.dataVersion.value

  await button(wrapper, 'Borrar paciente').trigger('click')
  await flushPromises()

  expect(ElMessage.error).toHaveBeenCalledWith('El paciente tiene atenciones.')
  expect(state.seleccionado.value).toEqual(patient)
  expect(state.dataVersion.value).toBe(version)
})

test('la baja solo se ofrece a un paciente activo y con permiso explícito', async () => {
  const { wrapper } = await mountLayout(['PACIENTE_LEER'])
  usePacienteSeleccionado().seleccionar(patient)
  await flushPromises()
  expect(wrapper.text()).not.toContain('Borrar paciente')

  const { wrapper: withPermission } = await mountLayout(['PACIENTE_LEER', 'PACIENTE_DAR_BAJA'])
  usePacienteSeleccionado().seleccionar({ ...patient, estado: false })
  await flushPromises()
  expect(button(withPermission, 'Borrar paciente').attributes('disabled')).toBeDefined()
})

test('salir cierra la sesión y vuelve al login', async () => {
  const { wrapper, router, auth } = await mountLayout(['PACIENTE_LEER'])
  auth.token = 'token'

  await button(wrapper, 'Salir').trigger('click')
  await flushPromises()
  await flushPromises()

  expect(auth.token).toBeNull()
  expect(router.currentRoute.value.name).toBe('login')
})

test('la identidad del usuario se muestra una sola vez, en la barra lateral', async () => {
  const { wrapper } = await mountLayout(['PACIENTE_LEER'])

  expect(wrapper.find('.topbar__avatar').exists()).toBe(false)
  expect(wrapper.find('.topbar__user').exists()).toBe(false)
  expect(wrapper.find('.side__avatar').text()).toBe('AQ')
  expect(wrapper.find('.side__user-name').text()).toBe('ana.quispe')
  expect(wrapper.find('.side__user-role').text()).toBe('ADMIN')
  expect(wrapper.find('.topbar').text()).not.toContain('ana.quispe')
})

test('cambiar la contraseña se ofrece desde el pie de la barra lateral', async () => {
  const { wrapper, router } = await mountLayout(['PACIENTE_LEER'])

  await button(wrapper, 'Contraseña').trigger('click')
  await flushPromises()

  expect(router.currentRoute.value.name).toBe('cambiar-contrasena')
})

test('el título de la barra superior viene de la ruta', async () => {
  const { wrapper, router } = await mountLayout(['PACIENTE_LEER'])
  expect(wrapper.find('.topbar__title').text()).toBe('Base de datos')

  await router.push('/atenciones')
  await flushPromises()
  expect(wrapper.find('.topbar__title').text()).toBe('Atenciones')
})
