import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import EstablishmentsPanel from '@/components/configuracion/EstablishmentsPanel.vue'
import AreasPanel from '@/components/configuracion/AreasPanel.vue'
import EstablishmentDetailPanel from '@/components/configuracion/EstablishmentDetailPanel.vue'
import {
  establecimientosAdmin,
  areasAtencion,
  type EstablishmentAdmin,
  type CareArea,
} from '@/services/configuracionAtencion'
import { catalogos } from '@/services/catalogos'
import { consultorios } from '@/services/consultorios'
vi.mock('@/services/configuracionAtencion', () => ({
  establecimientosAdmin: { list: vi.fn(), get: vi.fn(), save: vi.fn(), setActive: vi.fn() },
  areasAtencion: { list: vi.fn(), save: vi.fn(), setActive: vi.fn() },
}))
vi.mock('@/services/catalogos', () => ({ catalogos: { ubigeos: vi.fn() } }))
vi.mock('@/services/consultorios', () => ({ consultorios: { list: vi.fn() } }))
const site: EstablishmentAdmin = {
  id: 1,
  nombre: 'Sede norte',
  activo: true,
  abreviatura: null,
  codigo_renaes: '00001291',
  codigo_ideess: null,
  ubigeo_codigo: null,
  ubicacion: null,
  consultorios_total: 1,
  fua_personal_atiende: 'IPRESS',
  fua_lugar_atencion: 'EXTRAMURAL',
  fua_codigo_aisped: null,
  fua_renipress_preimpreso: false,
}
const area: CareArea = {
  codigo: 'MED',
  nombre: 'Medicina',
  activo: true,
  es_area_base: true,
  consultorios: [
    {
      id: 3,
      nombre: 'Medicina 1',
      establecimiento_id: 1,
      establecimiento_nombre: 'Sede norte',
      activo: true,
    },
  ],
}
const mounted: VueWrapper[] = []
async function render(
  component: typeof EstablishmentsPanel | typeof AreasPanel | typeof EstablishmentDetailPanel,
  props = {},
) {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: stub },
      { path: '/configuracion/establecimientos', name: 'establecimientos', component: stub },
      {
        path: '/configuracion/establecimientos/:establishmentId',
        name: 'establecimiento-detalle',
        component: stub,
      },
      { path: '/configuracion/areas', name: 'areas-atencion', component: stub },
      { path: '/configuracion/servicios', name: 'servicios-asistenciales', component: stub },
      { path: '/configuracion/consultorios', name: 'consultorios', component: stub },
      {
        path: '/configuracion/consultorios/:officeId',
        name: 'consultorio-servicios',
        component: stub,
      },
    ],
  })
  await router.push('/')
  const wrapper = mount(component, { props, global: { plugins: [router, ElementPlus] } })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}
function button(wrapper: VueWrapper, label: string) {
  const result = wrapper.findAll('button').find((item) => item.text() === label)
  if (!result) throw new Error(label)
  return result
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(establecimientosAdmin.list).mockResolvedValue({
    items: [site],
    total: 1,
    limit: 25,
    offset: 0,
    has_more: false,
  })
  vi.mocked(establecimientosAdmin.get).mockResolvedValue(site)
  vi.mocked(establecimientosAdmin.save).mockResolvedValue(site)
  vi.mocked(areasAtencion.list).mockResolvedValue([area])
  vi.mocked(areasAtencion.save).mockResolvedValue(area)
  vi.mocked(catalogos.ubigeos).mockResolvedValue({
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
    has_more: false,
  })
  vi.mocked(consultorios.list).mockResolvedValue([
    {
      id: 3,
      nombre: 'Medicina 1',
      codigo: 'MED',
      area_codigo: 'MED',
      area_nombre: 'Medicina',
      establecimiento_id: 1,
      consultorio_padre_id: null,
      especialidad_codigo: null,
      activo: true,
    },
  ])
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
})
afterEach(() => {
  mounted.splice(0).forEach((item) => item.unmount())
  vi.restoreAllMocks()
})

test('editar un establecimiento envía solo datos administrativos y conserva el formulario ante error', async () => {
  vi.mocked(establecimientosAdmin.save).mockRejectedValueOnce(new Error('Código duplicado.'))
  const wrapper = await render(EstablishmentsPanel)
  await button(wrapper, 'Editar').trigger('click')
  await flushPromises()
  await wrapper.get('input[aria-label="Nombre del establecimiento"]').setValue('Nombre cambiado')
  await button(wrapper, 'Guardar establecimiento').trigger('click')
  await flushPromises()
  expect(establecimientosAdmin.save).toHaveBeenCalledWith(
    {
      nombre: 'Nombre cambiado',
      abreviatura: null,
      codigo_renaes: '00001291',
      codigo_ideess: null,
      ubigeo_codigo: null,
    },
    1,
  )
  expect(wrapper.text()).toContain('Código duplicado.')
  expect(wrapper.findComponent({ name: 'EstablishmentFormDialog' }).props('modelValue')).toBe(true)
  await button(wrapper, 'Guardar establecimiento').trigger('click')
  await flushPromises()
  expect(wrapper.findComponent({ name: 'EstablishmentFormDialog' }).props('modelValue')).toBe(false)
})

test('una baja rechazada deja visible la sede y explica sus dependencias', async () => {
  vi.mocked(establecimientosAdmin.setActive).mockRejectedValue(
    new Error('Dé de baja primero los consultorios activos.'),
  )
  const wrapper = await render(EstablishmentsPanel)
  await button(wrapper, 'Dar de baja').trigger('click')
  await flushPromises()
  expect(establecimientosAdmin.setActive).toHaveBeenCalledWith(1, false)
  expect(wrapper.text()).toContain('Dé de baja primero los consultorios activos.')
  expect(wrapper.text()).toContain('Sede norte')
})

test('la búsqueda de establecimientos consulta el servidor y no filtra solo la página visible', async () => {
  const wrapper = await render(EstablishmentsPanel)
  await wrapper.get('input[aria-label="Buscar establecimiento"]').setValue('Otra sede')
  await wrapper.get('form.filters').trigger('submit')
  await flushPromises()
  expect(establecimientosAdmin.list).toHaveBeenLastCalledWith('Otra sede', false, 0)
})

test('las áreas comparten su identidad entre sedes y protegen las áreas base', async () => {
  vi.mocked(areasAtencion.list).mockResolvedValue([
    {
      ...area,
      consultorios: [
        ...area.consultorios,
        {
          id: 4,
          nombre: 'Medicina 2',
          establecimiento_id: 2,
          establecimiento_nombre: 'Sede sur',
          activo: true,
        },
      ],
    },
  ])
  const wrapper = await render(AreasPanel)
  expect(wrapper.text()).toContain('Sede norte')
  expect(wrapper.text()).toContain('Sede sur')
  expect(button(wrapper, 'Dar de baja').attributes('disabled')).toBeDefined()
  expect(wrapper.find('a[href="/configuracion/consultorios?areaCodigo=MED"]').exists()).toBe(true)
  await wrapper.get('button[aria-label="Editar área Medicina"]').trigger('click')
  await flushPromises()
  await wrapper.get('input[aria-label="Nombre del área"]').setValue('Medicina integral')
  await button(wrapper, 'Guardar área').trigger('click')
  await flushPromises()
  expect(areasAtencion.save).toHaveBeenCalledWith('Medicina integral', 'MED')
})

test('cancelar el alta de área no crea categorías ni modifica consultorios', async () => {
  const wrapper = await render(AreasPanel)
  await button(wrapper, 'Nueva área').trigger('click')
  await flushPromises()
  await wrapper.get('input[aria-label="Nombre del área"]').setValue('Sin guardar')
  await button(wrapper, 'Cancelar').trigger('click')
  expect(areasAtencion.save).not.toHaveBeenCalled()
})

test('desde la sede se crea un consultorio con establecimiento y área precargados', async () => {
  const wrapper = await render(EstablishmentDetailPanel, { establishmentId: 1 })
  expect(wrapper.text()).toContain('EXTRAMURAL')
  wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('update:modelValue', 'MED')
  await flushPromises()
  const link = wrapper
    .findAll('a')
    .find((item) => item.text() === 'Crear consultorio en esta área')!
  await link.trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.query).toEqual({
    establecimientoId: '1',
    areaCodigo: 'MED',
    nuevo: '1',
  })
  expect(establecimientosAdmin.save).not.toHaveBeenCalled()
})

test('el detalle permite editar la sede y gestionar su baja sin salir del contexto', async () => {
  const wrapper = await render(EstablishmentDetailPanel, { establishmentId: 1 })
  expect(establecimientosAdmin.list).not.toHaveBeenCalled()
  await button(wrapper, 'Editar establecimiento').trigger('click')
  await flushPromises()
  const form = wrapper.findComponent({ name: 'EstablishmentFormDialog' })
  await form.get('input[aria-label="Nombre del establecimiento"]').setValue('Sede actualizada')
  vi.mocked(establecimientosAdmin.get).mockResolvedValue({ ...site, nombre: 'Sede actualizada' })
  await button(form, 'Guardar establecimiento').trigger('click')
  await flushPromises()
  expect(establecimientosAdmin.save).toHaveBeenCalledWith(
    expect.objectContaining({ nombre: 'Sede actualizada' }),
    1,
  )
  expect(wrapper.get('h2').text()).toBe('Sede actualizada')
  vi.mocked(establecimientosAdmin.setActive).mockRejectedValueOnce(
    new Error('Hay consultorios activos.'),
  )
  await button(wrapper, 'Dar de baja establecimiento').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Hay consultorios activos.')
  expect(wrapper.get('h2').text()).toBe('Sede actualizada')
})
