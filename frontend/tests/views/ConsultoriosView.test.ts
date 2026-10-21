import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

import type { OfficeAssignmentResponse, OfficeResponse } from '@/services/consultorios'
import ConsultoriosView from '@/views/ConsultoriosView.vue'
import OfficeAssignmentDialog from '@/components/configuracion/OfficeAssignmentDialog.vue'
import StaffCatalogsPanel from '@/components/configuracion/StaffCatalogsPanel.vue'

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

async function mountView(permissions = ['CONSULTORIO_GESTIONAR', 'PROFESIONAL_GESTIONAR']) {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: stub }],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permisos = permissions
  const wrapper = mount(ConsultoriosView, {
    global: { plugins: [router, pinia, ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return wrapper
}

function button(wrapper: VueWrapper, label: string) {
  const found = wrapper
    .findAllComponents({ name: 'ElButton' })
    .find((item) => item.text().includes(label))
  if (!found) throw new Error(`No se encontró el botón "${label}"`)
  return found
}

function fieldItem(wrapper: VueWrapper, label: string) {
  const item = wrapper
    .findAllComponents({ name: 'ElFormItem' })
    .find((element) => String(element.props('label')).startsWith(label))
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

test('refresca las áreas sin ofrecer un selector de especialidad en el consultorio', async () => {
  const wrapper = await mountView()
  expect(wrapper.findComponent(StaffCatalogsPanel).exists()).toBe(false)
  await wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.text() === 'Áreas de atención')!
    .trigger('click')
  await flushPromises()
  const panel = wrapper.findComponent(StaffCatalogsPanel)
  expect(panel.props('kind')).toBe('especialidad')
  expect(panel.props('areasOnly')).toBe(true)
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'AREA-NUEVA', nombre: 'REHABILITACIÓN', es_area: true, activo: true, grupo: null },
    { codigo: 'ESP-NUEVA', nombre: 'TERAPIA', es_area: false, activo: true, grupo: null },
  ])
  panel.vm.$emit('created')
  await flushPromises()
  await wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.text() === 'Consultorios')!
    .trigger('click')
  await button(wrapper, 'Nuevo consultorio').trigger('click')
  await flushPromises()
  const areaOptions = fieldItem(wrapper, 'Área asistencial').findAllComponents({ name: 'ElOption' })
  expect(areaOptions.map((option) => option.props('label'))).toContain('REHABILITACIÓN')
  expect(
    wrapper.findAllComponents({ name: 'ElFormItem' }).map((item) => item.props('label')),
  ).not.toContain('Especialidad requerida')
  expect(wrapper.find('[placeholder="Sin requisito adicional"]').exists()).toBe(false)
})

test('sin permiso de gestión de personal conserva consultorios y oculta su catálogo', async () => {
  const wrapper = await mountView(['CONSULTORIO_GESTIONAR'])
  expect(wrapper.text()).toContain('Consultorio A')
  expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).not.toContain(
    'Áreas de atención',
  )
  expect(wrapper.findComponent(StaffCatalogsPanel).exists()).toBe(false)
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
    especialidad_codigo: null,
    area_codigo: 'CARD',
    servicios_codigos: null,
  })
  expect(list).toHaveBeenLastCalledWith({ establecimientoId: undefined, incluirInactivos: false })
})

test('editar conserva las referencias anteriores sin mostrar el selector de especialidad', async () => {
  list.mockResolvedValue([anOffice({ area_codigo: 'MED', especialidad_codigo: 'CARD' })])
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true },
    { codigo: 'CARD', nombre: 'Cardiología anterior', es_area: false, activo: true },
  ])
  const wrapper = await mountView()
  await button(wrapper, 'Editar').trigger('click')
  await flushPromises()
  expect(
    wrapper.findAllComponents({ name: 'ElFormItem' }).map((item) => item.props('label')),
  ).not.toContain('Especialidad requerida')
  expect(wrapper.find('[placeholder="Sin requisito adicional"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('Cardiología anterior')
  await setField(wrapper, 'Nombre', 'Consultorio renombrado')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(
    1,
    expect.objectContaining({
      nombre: 'Consultorio renombrado',
      especialidad_codigo: 'CARD',
      area_codigo: 'MED',
    }),
  )
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
    vincular_area: true,
  })
  // Un GET inicial al abrir el diálogo y otro tras asignar.
  expect(listAssignments).toHaveBeenCalledTimes(2)
})

test('una lista larga se puede buscar y cancelar el submodal conserva la lista', async () => {
  const professionals = Array.from({ length: 80 }, (_, index) => ({
    id: index + 5,
    nombre_completo: index ? `Profesional ${index}` : 'Luis Torres',
    colegiatura: null,
    activo: true,
  }))
  catalogos.profesionales.mockResolvedValue(page(professionals))
  listAssignments.mockResolvedValue(
    professionals.map((item) => anAssignment({ profesional_id: item.id })),
  )
  const wrapper = await mountView()
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()
  const search = wrapper.find('input[aria-label="Buscar profesional asignado"]')
  await search.setValue('Luis')
  expect(wrapper.findAllComponents({ name: 'ElTable' }).at(-1)!.props('data')).toHaveLength(1)
  await button(wrapper, 'Asignar profesional').trigger('click')
  await flushPromises()
  const child = wrapper.findComponent(OfficeAssignmentDialog)
  expect(child.props('modelValue')).toBe(true)
  expect(child.findComponent({ name: 'ElDialog' }).props('appendToBody')).toBe(true)
  await selectField(wrapper, 'Profesional', 5)
  await setDate(wrapper, 'Fecha de inicio', '2026-02-01')
  await button(child, 'Cancelar').trigger('click')
  await flushPromises()
  expect(child.props('modelValue')).toBe(false)
  expect((search.element as HTMLInputElement).value).toBe('Luis')
  expect(listAssignments).toHaveBeenCalledTimes(1)
  expect(assign).not.toHaveBeenCalled()
  await button(wrapper, 'Asignar profesional').trigger('click')
  await flushPromises()
  expect(
    fieldItem(wrapper, 'Profesional').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBeNull()
})

test('el rechazo se muestra dentro del submodal sin perder los datos', async () => {
  assign.mockRejectedValue(new Error('El profesional no tiene la especialidad requerida.'))
  const wrapper = await mountView()
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()
  await button(wrapper, 'Asignar profesional').trigger('click')
  await flushPromises()
  await selectField(wrapper, 'Profesional', 5)
  await setDate(wrapper, 'Fecha de inicio', '2026-02-01')
  await button(wrapper, 'Guardar asignación').trigger('click')
  await flushPromises()
  const child = wrapper.findComponent(OfficeAssignmentDialog)
  expect(child.props('modelValue')).toBe(true)
  expect(child.findComponent({ name: 'ElAlert' }).text()).toContain(
    'El profesional no tiene la especialidad requerida.',
  )
  expect(
    fieldItem(wrapper, 'Profesional').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBe(5)
  expect(listAssignments).toHaveBeenCalledTimes(1)
})

test('el submodal impide cierres y duplicados mientras guarda y vuelve a la lista', async () => {
  let complete!: (value: OfficeAssignmentResponse) => void
  assign.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve
      }),
  )
  const wrapper = await mountView()
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()
  await button(wrapper, 'Asignar profesional').trigger('click')
  await flushPromises()
  await selectField(wrapper, 'Profesional', 5)
  await setDate(wrapper, 'Fecha de inicio', '2026-02-01')
  await button(wrapper, 'Guardar asignación').trigger('click')
  await flushPromises()
  const child = wrapper.findComponent(OfficeAssignmentDialog)
  child.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
  child.vm.$emit('submit', {
    profesional_id: 5,
    fecha_inicio: '2026-02-01',
    fecha_fin: null,
    es_responsable: false,
    vincular_area: true,
  })
  await flushPromises()
  expect(child.props('modelValue')).toBe(true)
  expect(assign).toHaveBeenCalledTimes(1)
  complete(anAssignment())
  await flushPromises()
  expect(child.props('modelValue')).toBe(false)
  expect(listAssignments).toHaveBeenCalledTimes(2)
  const listDialog = wrapper
    .findAllComponents({ name: 'ElDialog' })
    .find((dialog) => String(dialog.props('title')).startsWith('Profesionales ·'))!
  expect(listDialog.props('modelValue')).toBe(true)
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

test('nuevo subconsultorio hereda sede y área sin pedir especialidad adicional', async () => {
  list.mockResolvedValue([anOffice({ area_codigo: 'CARD', especialidad_codigo: null })])
  const wrapper = await mountView()
  await button(wrapper, 'Nuevo subconsultorio').trigger('click')
  await flushPromises()
  expect(
    fieldItem(wrapper, 'Establecimiento').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBe(1)
  expect(
    fieldItem(wrapper, 'Área asistencial').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBe('CARD')
  expect(
    fieldItem(wrapper, 'Consultorio padre').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBe(1)
  expect(wrapper.find('details.additional-settings').attributes('open')).toBeUndefined()
  await setField(wrapper, 'Código', 'SUB-01')
  await setField(wrapper, 'Nombre', 'Medicina 01')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({
      establecimiento_id: 1,
      area_codigo: 'CARD',
      consultorio_padre_id: 1,
      especialidad_codigo: null,
      servicios_codigos: null,
    }),
  )
})
