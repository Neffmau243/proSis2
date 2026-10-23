import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import CareServiceCatalogPanel from '@/components/configuracion/CareServiceCatalogPanel.vue'
import CareServiceFormDialog from '@/components/configuracion/CareServiceFormDialog.vue'
import { serviciosAsistenciales, type CareService } from '@/services/serviciosAsistenciales'
import { catalogos } from '@/services/catalogos'

vi.mock('@/services/serviciosAsistenciales', () => ({
  serviciosAsistenciales: { list: vi.fn(), create: vi.fn(), update: vi.fn(), setActive: vi.fn() },
}))
vi.mock('@/services/catalogos', () => ({ catalogos: { especialidades: vi.fn() } }))

const service: CareService = {
  codigo: 'PED',
  nombre: 'Pediatría',
  activo: true,
  area_codigos: ['MED'],
  consultorios: [
    {
      id: 43,
      nombre: 'Medicina',
      establecimiento_id: 1,
      establecimiento_nombre: 'Sede norte',
      consultorio_padre_id: null,
      activo: true,
    },
  ],
}
const wrappers: VueWrapper[] = []
function button(wrapper: VueWrapper, label: string) {
  const found = wrapper
    .findAllComponents({ name: 'ElButton' })
    .find((item) => item.text() === label)
  if (!found) throw new Error(`No se encontró ${label}`)
  return found
}
async function render() {
  const wrapper = mount(CareServiceCatalogPanel, {
    global: {
      plugins: [ElementPlus],
      stubs: { RouterLink: { name: 'RouterLink', props: ['to'], template: '<a><slot /></a>' } },
    },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(serviciosAsistenciales.list).mockResolvedValue([service])
  vi.mocked(catalogos.especialidades).mockResolvedValue([
    { codigo: 'MED', nombre: 'Medicina', activo: true, grupo: null, es_area: true },
  ])
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
})
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

test('el catálogo muestra el servicio y dónde se utiliza, con búsqueda e inactivos', async () => {
  const wrapper = await render()
  expect(wrapper.text()).toContain('Pediatría')
  expect(wrapper.text()).toContain('Habilitado en 1 consultorio')
  expect(wrapper.text()).toContain('Sede norte')
  expect(
    wrapper.findAll('summary').some((summary) => summary.text().startsWith('Ver subconsultorios')),
  ).toBe(false)
  expect(wrapper.findComponent({ name: 'RouterLink' }).props('to')).toEqual({
    name: 'consultorio-servicios',
    params: { officeId: 43 },
  })
  await wrapper.get('input[aria-label="Buscar servicio"]').setValue('Laboratorio')
  expect(wrapper.text()).toContain('No hay servicios para estos filtros.')
  wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', true)
  await flushPromises()
  expect(serviciosAsistenciales.list).toHaveBeenLastCalledWith(true)
})

test('el catálogo conserva los consultorios históricos en una lista sin una jerarquía de subconsultorios', async () => {
  vi.mocked(serviciosAsistenciales.list).mockResolvedValue([
    {
      ...service,
      nombre: 'Ginecología',
      consultorios: [
        service.consultorios[0]!,
        {
          id: 44,
          nombre: 'Ginecología 2',
          establecimiento_id: 1,
          establecimiento_nombre: 'Sede norte',
          consultorio_padre_id: 43,
          consultorio_padre_nombre: 'Medicina',
          activo: true,
        },
      ],
    },
  ])
  const wrapper = await render()
  const usage = wrapper.get('.catalog-usage-detail')
  expect(wrapper.findAll('.catalog-usage-detail')).toHaveLength(1)
  expect(usage.get('summary').text()).toBe('Habilitado en 2 consultorios')
  expect(usage.findAll('.service-office-name').map((item) => item.text())).toEqual([
    'Medicina',
    'Ginecología 2',
  ])
  expect(usage.findAllComponents({ name: 'RouterLink' })[1]!.props('to')).toEqual({
    name: 'consultorio-servicios',
    params: { officeId: 44 },
  })
  expect(usage.text()).toContain('Sede norte')
  expect(wrapper.text()).not.toContain('Ver subconsultorios')
  expect(wrapper.text()).not.toContain('Consultorio principal:')
})

test('el servicio general explica su función sin repetir el nombre del área', async () => {
  vi.mocked(serviciosAsistenciales.list).mockResolvedValue([{ ...service, nombre: 'MEDICINA' }])
  const wrapper = await render()
  const identity = wrapper.get('.catalog-identity')
  expect(identity.get('h3').text()).toBe('MEDICINA')
  expect(identity.get('.catalog-context').text()).toBe('Servicio general del área')
})

test('registra un servicio independiente con nombre y área', async () => {
  vi.mocked(serviciosAsistenciales.create).mockResolvedValue({ ...service, consultorios: [] })
  const wrapper = await render()
  await button(wrapper, 'Registrar servicio').trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent(CareServiceFormDialog)
  await dialog.get('input[aria-label="Nombre del servicio"]').setValue('Nuevo servicio')
  dialog.findComponent({ name: 'ElSelect' }).vm.$emit('update:modelValue', 'MED')
  await flushPromises()
  await button(dialog, 'Registrar servicio').trigger('click')
  await flushPromises()
  expect(serviciosAsistenciales.create).toHaveBeenCalledWith({
    nombre: 'Nuevo servicio',
    area_codigo: 'MED',
  })
  expect(dialog.props('modelValue')).toBe(false)
})

test('editar conserva el código y explica el efecto sobre los consultorios', async () => {
  vi.mocked(serviciosAsistenciales.update).mockResolvedValue(service)
  const wrapper = await render()
  await wrapper.get('button[aria-label="Editar servicio Pediatría"]').trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent(CareServiceFormDialog)
  expect(dialog.text()).toContain('1 consultorios vinculados')
  await dialog.get('input[aria-label="Nombre del servicio"]').setValue('Pediatría actualizada')
  await button(dialog, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(serviciosAsistenciales.update).toHaveBeenCalledWith('PED', 'Pediatría actualizada')
})

test('un error conserva el formulario y sus datos para reintentar', async () => {
  vi.mocked(serviciosAsistenciales.update).mockRejectedValue(
    new Error('Ya existe un servicio con ese nombre.'),
  )
  const wrapper = await render()
  await wrapper.get('button[aria-label="Editar servicio Pediatría"]').trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent(CareServiceFormDialog)
  await dialog.get('input[aria-label="Nombre del servicio"]').setValue('Nombre repetido')
  await button(dialog, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(dialog.props('modelValue')).toBe(true)
  expect(dialog.text()).toContain('Ya existe un servicio con ese nombre.')
  expect(
    (dialog.get('input[aria-label="Nombre del servicio"]').element as HTMLInputElement).value,
  ).toBe('Nombre repetido')
})

test('la baja muestra las dependencias devueltas por el servidor y conserva la lista', async () => {
  vi.mocked(serviciosAsistenciales.setActive).mockRejectedValue(
    new Error('Quite primero el servicio de Medicina.'),
  )
  const wrapper = await render()
  await wrapper.get('button[aria-label="Dar de baja servicio Pediatría"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Quite primero el servicio de Medicina.')
  expect(wrapper.text()).toContain('Pediatría')
})
