import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { OfficeAssignmentResponse, OfficeResponse } from '@/services/consultorios'
import ConsultoriosView from '@/views/ConsultoriosView.vue'

const { list, create, update, deactivate, listAssignments, assign, closeAssignment } = vi.hoisted(
  () => ({
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    deactivate: vi.fn(),
    listAssignments: vi.fn(),
    assign: vi.fn(),
    closeAssignment: vi.fn(),
  }),
)

const { catalogos } = vi.hoisted(() => ({
  catalogos: {
    establecimientos: vi.fn(),
    especialidades: vi.fn(),
    consultorios: vi.fn(),
    profesionales: vi.fn(),
  },
}))

vi.mock('@/services/consultorios', () => ({
  consultorios: { list, create, update, deactivate, listAssignments, assign, closeAssignment },
}))
vi.mock('@/services/catalogos', () => ({ catalogos }))

function page<T>(items: T[], limit = 25) {
  return { items, total: items.length, limit, offset: 0, has_more: false }
}

function anOffice(overrides: Partial<OfficeResponse> = {}): OfficeResponse {
  return {
    id: 1,
    establecimiento_id: 1,
    consultorio_padre_id: null,
    codigo: 'CONS-01',
    nombre: 'Consultorio A',
    especialidad_codigo: 'CARD',
    activo: true,
    ...overrides,
  }
}

function anAssignment(overrides: Partial<OfficeAssignmentResponse> = {}): OfficeAssignmentResponse {
  return {
    consultorio_id: 1,
    profesional_id: 5,
    fecha_inicio: '2026-01-01',
    fecha_fin: null,
    es_responsable: false,
    ...overrides,
  }
}

const mounted: { unmount: () => void }[] = []

async function mountView() {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: stub }],
  })
  const wrapper = mount(ConsultoriosView, {
    global: { plugins: [router, ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return wrapper
}

function button(wrapper: VueWrapper, label: string) {
  const found = wrapper.findAll('button').find((item) => item.text().includes(label))
  if (!found) throw new Error(`No se encontró el botón "${label}"`)
  return found
}

function fieldItem(wrapper: VueWrapper, label: string) {
  const item = wrapper
    .findAll('.el-form-item')
    .find((element) => element.find('.el-form-item__label').text().startsWith(label))
  if (!item) throw new Error(`No se encontró el campo "${label}"`)
  return item
}

async function setField(wrapper: VueWrapper, label: string, value: string): Promise<void> {
  await fieldItem(wrapper, label).find('input').setValue(value)
}

async function selectField(wrapper: VueWrapper, label: string, value: unknown): Promise<void> {
  fieldItem(wrapper, label).findComponent({ name: 'ElSelect' }).vm.$emit('update:modelValue', value)
  await flushPromises()
}

async function setDate(wrapper: VueWrapper, label: string, value: string): Promise<void> {
  fieldItem(wrapper, label)
    .findComponent({ name: 'ElDatePicker' })
    .vm.$emit('update:modelValue', value)
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  list.mockResolvedValue([anOffice()])
  create.mockResolvedValue(anOffice())
  update.mockResolvedValue(anOffice())
  deactivate.mockResolvedValue(anOffice({ activo: false }))
  listAssignments.mockResolvedValue([])
  assign.mockResolvedValue(anAssignment())
  closeAssignment.mockResolvedValue(anAssignment({ fecha_fin: '2026-06-30' }))
  catalogos.establecimientos.mockResolvedValue(
    page([
      {
        id: 1,
        codigo_renaes: null,
        codigo_ideess: null,
        nombre: 'Hospital Central',
        abreviatura: null,
        activo: true,
      },
    ]),
  )
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'CARD', nombre: 'Cardiología', activo: true, grupo: null },
  ])
  catalogos.consultorios.mockResolvedValue(page([]))
  catalogos.profesionales.mockResolvedValue(
    page([{ id: 5, nombre_completo: 'Luis Torres', colegiatura: 'CMP-009', activo: true }]),
  )
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})

test('carga la lista y resuelve el establecimiento y la especialidad', async () => {
  const wrapper = await mountView()

  expect(list).toHaveBeenCalledTimes(1)
  expect(wrapper.text()).toContain('Consultorio A')
  expect(wrapper.text()).toContain('Hospital Central')
  expect(wrapper.text()).toContain('Cardiología')
})

test('incluir inactivos recarga la lista con el filtro', async () => {
  const wrapper = await mountView()
  wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', true)
  await flushPromises()

  expect(list).toHaveBeenCalledWith({ establecimientoId: undefined, incluirInactivos: true })
})

test('el alta envía el contrato del consultorio y refresca', async () => {
  const wrapper = await mountView()
  await button(wrapper, 'Nuevo consultorio').trigger('click')
  await flushPromises()

  await selectField(wrapper, 'Establecimiento', 1)
  await selectField(wrapper, 'Área asistencial', 'CARD')
  await setField(wrapper, 'Código', 'CONS-02')
  await setField(wrapper, 'Nombre', 'Consultorio B')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()

  expect(create).toHaveBeenCalledWith({
    establecimiento_id: 1,
    codigo: 'CONS-02',
    nombre: 'Consultorio B',
    consultorio_padre_id: null,
    especialidad_codigo: 'CARD',
    area_codigo: 'CARD',
    servicios_codigos: null,
  })
  expect(list).toHaveBeenLastCalledWith({ establecimientoId: undefined, incluirInactivos: false })
})

test('la tabla de asignaciones se muestra aunque venga vacía', async () => {
  const wrapper = await mountView()
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()

  expect(listAssignments).toHaveBeenCalledWith(1)
  expect(wrapper.text()).toContain('Sin asignaciones registradas')
})

test('asignar profesional envía el payload y recarga las asignaciones', async () => {
  const wrapper = await mountView()
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()

  await button(wrapper, 'Asignar profesional').trigger('click')
  await flushPromises()
  await selectField(wrapper, 'Profesional', 5)
  await setDate(wrapper, 'Fecha de inicio', '2026-02-01')
  await button(wrapper, 'Guardar asignación').trigger('click')
  await flushPromises()

  expect(assign).toHaveBeenCalledWith(1, {
    profesional_id: 5,
    fecha_inicio: '2026-02-01',
    fecha_fin: null,
    es_responsable: false,
  })
  // Un GET inicial al abrir el diálogo y otro tras asignar.
  expect(listAssignments).toHaveBeenCalledTimes(2)
})

test('cerrar asignación envía la fecha de fin y recarga', async () => {
  listAssignments.mockResolvedValue([anAssignment()])
  const wrapper = await mountView()
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()

  await button(wrapper, 'Cerrar').trigger('click')
  await flushPromises()
  await setDate(wrapper, 'Fecha de fin', '2026-06-30')
  await button(wrapper, 'Cerrar asignación').trigger('click')
  await flushPromises()

  expect(closeAssignment).toHaveBeenCalledWith(1, 5, '2026-01-01', '2026-06-30')
  expect(listAssignments).toHaveBeenCalledTimes(2)
})

test('la baja es informativa y refresca la lista', async () => {
  const wrapper = await mountView()
  await button(wrapper, 'Dar de baja').trigger('click')
  await flushPromises()

  expect(ElMessageBox.confirm).toHaveBeenCalledWith(
    expect.stringContaining('subconsultorios activos'),
    'Dar de baja consultorio',
    expect.objectContaining({ type: 'info' }),
  )
  expect(deactivate).toHaveBeenCalledWith(1)
  expect(list).toHaveBeenCalledTimes(2)
})

test('un rechazo del backend se muestra con su mensaje', async () => {
  create.mockRejectedValue(
    new Error('Ya existe un consultorio con ese código en el establecimiento.'),
  )
  const wrapper = await mountView()
  await button(wrapper, 'Nuevo consultorio').trigger('click')
  await flushPromises()

  await selectField(wrapper, 'Establecimiento', 1)
  await setField(wrapper, 'Código', 'CONS-01')
  await setField(wrapper, 'Nombre', 'Duplicado')
  await selectField(wrapper, 'Área asistencial', 'CARD')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()

  expect(wrapper.find('.el-alert__title').text()).toContain(
    'Ya existe un consultorio con ese código en el establecimiento.',
  )
})
