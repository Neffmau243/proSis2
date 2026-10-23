import { beforeEach, expect, test, vi } from 'vitest'

import router from '@/router'
import { saveSession, type PersistedSession } from '@/services/session-storage'

// Las vistas se cargan de forma diferida: se sustituyen por marcadores para que
// estas pruebas midan la guarda de navegación y no el tiempo de carga real.
// ``vi.mock`` se eleva sobre los imports, así que su fábrica debe crearse antes.
const { stub } = vi.hoisted(() => ({ stub: () => ({ default: { template: '<div />' } }) }))
vi.mock('@/views/LoginView.vue', stub)
vi.mock('@/views/DashboardView.vue', stub)
vi.mock('@/layouts/AppLayout.vue', stub)
vi.mock('@/views/LaboratorioView.vue', stub)
vi.mock('@/views/CambiarContrasenaView.vue', stub)
vi.mock('@/views/AdmisionView.vue', stub)
vi.mock('@/views/PacienteNuevoView.vue', stub)
vi.mock('@/views/PacienteDetalleView.vue', stub)
vi.mock('@/views/AtencionesListView.vue', stub)
vi.mock('@/views/AtencionNuevaView.vue', stub)
vi.mock('@/views/AtencionDetalleView.vue', stub)
vi.mock('@/views/PersonalView.vue', stub)
vi.mock('@/views/AuditoriaView.vue', stub)
vi.mock('@/views/GruposEtariosView.vue', stub)
vi.mock('@/views/ConsultoriosView.vue', stub)
vi.mock('@/views/PacienteEditarView.vue', stub)
vi.mock('@/views/AreasAtencionView.vue', stub)
vi.mock('@/views/EstablecimientosView.vue', stub)
vi.mock('@/views/EstablecimientoDetalleView.vue', stub)
vi.mock('@/views/ServiciosView.vue', stub)

function session(overrides: Partial<PersistedSession> = {}): PersistedSession {
  return {
    access_token: 'token',
    expires_at: Date.now() + 3_600_000,
    usuario_id: 1,
    nombre_usuario: 'admin',
    roles: ['ADMIN'],
    permisos: ['PACIENTE_LEER'],
    ...overrides,
  }
}

async function goTo(path: string) {
  await router.push(path).catch(() => undefined)
  return router.currentRoute.value
}

beforeEach(async () => {
  localStorage.clear()
  await router.replace('/login')
})

test('sin sesión cualquier ruta protegida lleva al login recordando el destino', async () => {
  const route = await goTo('/atenciones/42')

  expect(route.name).toBe('login')
  expect(route.query.redirect).toBe('/atenciones/42')
})

test('la raíz también está protegida', async () => {
  const route = await goTo('/')

  expect(route.name).toBe('login')
  expect(route.query.redirect).toBe('/')
})

test('una sesión vencida no da acceso', async () => {
  saveSession(session({ expires_at: Date.now() - 1000 }))

  const route = await goTo('/atenciones/42')

  expect(route.name).toBe('login')
  expect(route.query.redirect).toBe('/atenciones/42')
})

test('sin el permiso de la ruta se vuelve a la base de datos', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER'] }))

  const route = await goTo('/atenciones/42')

  expect(route.name).toBe('inicio')
})

test('con el permiso la ruta se abre normalmente', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER', 'ATENCION_LEER'] }))

  const route = await goTo('/atenciones/42')

  expect(route.name).toBe('atencion-detalle')
  expect(route.path).toBe('/atenciones/42')
})

test('las pantallas clínicas generales están ocultas incluso con permisos', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER', 'ATENCION_LEER', 'ATENCION_CREAR'] }))
  expect((await goTo('/atenciones')).name).toBe('inicio')
  expect((await goTo('/atenciones/nueva')).name).toBe('inicio')
  expect((await goTo('/atenciones/nueva?patientId=42')).name).toBe('admision')
  expect(router.currentRoute.value.query.patientId).toBe('42')
})

test('un usuario autenticado no vuelve a ver el login', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER', 'PACIENTE_EDITAR'] }))

  // Se parte de otra ruta: repetir el destino actual no dispara la guarda.
  const before = await goTo('/pacientes/nuevo')
  expect(before.name).toBe('paciente-nuevo')

  const route = await goTo('/login')

  expect(route.name).toBe('inicio')
})

test('admin puede editar pacientes sin permiso de crear atención', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER', 'PACIENTE_EDITAR'] }))
  const route = await goTo('/pacientes/42/editar')
  expect(route.name).toBe('paciente-editar')
  expect(route.params.id).toBe('42')
  expect((await goTo('/admision?patientId=42')).name).toBe('inicio')
})

test('crear atenciones no concede permiso de editar pacientes', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER', 'ATENCION_CREAR'] }))
  expect((await goTo('/pacientes/42/editar')).name).toBe('inicio')
})

test.each([
  '/configuracion/establecimientos',
  '/configuracion/establecimientos/1',
  '/configuracion/areas',
])('la nueva configuración usa los permisos administrativos existentes: %s', async (path) => {
  saveSession(session({ permisos: ['PACIENTE_LEER'] }))
  expect((await goTo(path)).name).toBe('inicio')
  saveSession(session({ permisos: ['PACIENTE_LEER', 'CONSULTORIO_GESTIONAR'] }))
  expect((await goTo(path)).path).toBe(path)
})

test('el listado clásico de pacientes conserva su redirección y el título se actualiza', async () => {
  saveSession(session())

  const route = await goTo('/pacientes')

  expect(route.name).toBe('inicio')
  expect(document.title).toBe('Base de datos · Sistema de Salud IPRESS')
})

test('una ruta desconocida cae en la base de datos', async () => {
  saveSession(session())

  const route = await goTo('/ruta/que/no/existe')

  expect(route.name).toBe('inicio')
})

test('la vista unificada exige al menos uno de los permisos de gestión', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER'] }))
  expect((await goTo('/configuracion/personal')).name).toBe('inicio')

  saveSession(session({ permisos: ['PACIENTE_LEER', 'USUARIO_GESTIONAR'] }))
  expect((await goTo('/configuracion/personal')).name).toBe('personal')
})

test('los enlaces antiguos redirigen a la vista unificada con su pestaña', async () => {
  saveSession(
    session({ permisos: ['PACIENTE_LEER', 'PROFESIONAL_GESTIONAR', 'USUARIO_GESTIONAR'] }),
  )

  const professionals = await goTo('/configuracion/profesionales')
  expect(professionals.name).toBe('personal')

  const users = await goTo('/configuracion/usuarios')
  expect(users.name).toBe('personal')
  expect(users.query.tab).toBe('cuentas')
})

test('el detalle de consultorio exige el mismo permiso que el directorio', async () => {
  saveSession(session({ permisos: ['PACIENTE_LEER'] }))
  expect((await goTo('/configuracion/consultorios/1')).name).toBe('inicio')
  saveSession(session({ permisos: ['CONSULTORIO_GESTIONAR'] }))
  const detail = await goTo('/configuracion/consultorios/1')
  expect(detail.name).toBe('consultorio-servicios')
  expect(detail.params.officeId).toBe('1')
  expect(document.title).toBe('Servicios del consultorio · Sistema de Salud IPRESS')
})
