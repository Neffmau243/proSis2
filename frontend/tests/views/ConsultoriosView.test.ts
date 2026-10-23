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
import OfficeActions from '@/components/configuracion/OfficeActions.vue'
import { serviciosAsistenciales } from '@/services/serviciosAsistenciales'

const {
  list,
  create,
  update,
  deactivate,
  listAssignments,
  assign,
  closeAssignment,
  listServices,
  addService,
  get,
  updateAssignment,
} = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  deactivate: vi.fn(),
  listAssignments: vi.fn(),
  assign: vi.fn(),
  closeAssignment: vi.fn(),
  listServices: vi.fn(),
  addService: vi.fn(),
  get: vi.fn(),
  updateAssignment: vi.fn(),
}))

const { catalogos } = vi.hoisted(() => ({
  catalogos: {
    establecimientos: vi.fn(),
    especialidades: vi.fn(),
    consultorios: vi.fn(),
    profesionales: vi.fn(),
  },
}))

vi.mock('@/services/consultorios', () => ({
  consultorios: {
    list,
    create,
    update,
    deactivate,
    listAssignments,
    assign,
    closeAssignment,
    listServices,
    addService,
    get,
    updateAssignment,
  },
}))
vi.mock('@/services/catalogos', () => ({ catalogos }))
vi.mock('@/services/serviciosAsistenciales', () => ({
  serviciosAsistenciales: { get: vi.fn(), update: vi.fn() },
}))

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

async function mountView(
  permissions = ['CONSULTORIO_GESTIONAR', 'PROFESIONAL_GESTIONAR'],
  officeId?: number,
  initialPath = '/',
) {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'consultorios', component: stub },
      { path: '/configuracion/establecimientos', name: 'establecimientos', component: stub },
      {
        path: '/configuracion/establecimientos/:establishmentId',
        name: 'establecimiento-detalle',
        component: stub,
      },
      { path: '/configuracion/areas', name: 'areas-atencion', component: stub },
      { path: '/configuracion/servicios', name: 'servicios-asistenciales', component: stub },
      {
        path: '/configuracion/consultorios/:officeId',
        name: 'consultorio-servicios',
        component: stub,
      },
    ],
  })
  await router.push(initialPath)
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permisos = permissions
  const wrapper = mount(ConsultoriosView, {
    props: { officeId },
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
    .find(
      (item) =>
        item.text().includes(label) ||
        String(item.attributes('aria-label')).startsWith(`${label} `),
    )
  if (!found) throw new Error(`No se encontró el botón "${label}"`)
  return found
}

async function officeAction(wrapper: VueWrapper, label: string): Promise<void> {
  if (label === 'Dar de baja') {
    await button(wrapper, 'Más').trigger('click')
    await flushPromises()
    await wrapper
      .findAllComponents({ name: 'ElDropdownItem' })
      .find((item) => item.text() === label)!
      .get('[role="menuitem"]')
      .trigger('click')
  } else {
    await button(wrapper, label).trigger('click')
  }
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
  const field = fieldItem(wrapper, label)
  const select = field.findComponent({ name: 'ElSelect' })
  const control = select.exists() ? select : field.findComponent({ name: 'ElRadioGroup' })
  control.vm.$emit('update:modelValue', value)
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
  listServices.mockResolvedValue([])
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
  vi.unstubAllGlobals()
})

test('carga la lista y resuelve el establecimiento y la especialidad', async () => {
  const wrapper = await mountView()

  expect(list).toHaveBeenCalledTimes(1)
  expect(wrapper.text()).toContain('Consultorio A')
  expect(wrapper.text()).toContain('Hospital Central')
  expect(wrapper.text()).toContain('Cardiología')
})

test('el directorio oculta los subconsultorios y filtra por servicio', async () => {
  list.mockResolvedValue([
    anOffice({ servicios_habilitados: [{ codigo: 'CARD', nombre: 'Cardiología', activo: true }] }),
    anOffice({ id: 2, nombre: 'Sala hija', consultorio_padre_id: 1 }),
    anOffice({
      id: 3,
      nombre: 'Laboratorio',
      especialidad_codigo: null,
      servicios_habilitados: [],
    }),
  ])
  const wrapper = await mountView()
  expect(wrapper.get('.office-mobile-list').text()).not.toContain('Sala hija')
  await wrapper.get('input[aria-label="Buscar consultorio o servicio"]').setValue('cardiología')
  expect(wrapper.get('.office-mobile-list').text()).toContain('Consultorio A')
  expect(wrapper.get('.office-mobile-list').text()).not.toContain('Laboratorio')
  await wrapper.get('input[aria-label="Buscar consultorio o servicio"]').setValue('inexistente')
  expect(wrapper.text()).toContain('No hay coincidencias')
})

test('el detalle carga también los inactivos y permite volver al directorio', async () => {
  const wrapper = await mountView(undefined, 1)
  expect(list).toHaveBeenCalledWith({ establecimientoId: undefined, incluirInactivos: true })
  expect(wrapper.text()).toContain('Servicios / especialidades')
  expect(wrapper.find('[role="tablist"]').exists()).toBe(false)
  await button(wrapper, 'Volver a consultorios').trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.name).toBe('consultorios')
})

test('un enlace a un consultorio inexistente ofrece volver al directorio', async () => {
  const wrapper = await mountView(undefined, 999)
  expect(wrapper.text()).toContain('No se encontró este consultorio')
})

test('un enlace directo identifica la sede, área y consultorio y vuelve a su lista filtrada', async () => {
  list.mockResolvedValue([
    anOffice({
      establecimiento_nombre: 'Sede norte',
      area_codigo: 'MED',
      area_nombre: 'Medicina',
      nombre: 'Medicina 2',
    }),
  ])
  const wrapper = await mountView(undefined, 1, '/configuracion/consultorios/1')
  const nav = wrapper.get('nav[aria-label="Ruta actual"]')
  expect(nav.text()).toContain('Sede norte')
  expect(nav.text()).toContain('Área: Medicina')
  expect(nav.get('[aria-current="page"]').text()).toBe('Medicina 2')
  expect(nav.get('a[href="/configuracion/establecimientos/1"]').text()).toBe('Sede norte')
  const directoryLink = nav.findAll('a').find((item) => item.text() === 'Consultorios')!
  await directoryLink.trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.name).toBe('consultorios')
  expect(wrapper.vm.$router.currentRoute.value.query).toEqual({
    establecimientoId: '1',
    areaCodigo: 'MED',
  })
})

test('el directorio muestra el contexto filtrado y lo retira al quitar los filtros', async () => {
  const wrapper = await mountView(undefined, undefined, '/?establecimientoId=1&areaCodigo=CARD')
  expect(wrapper.get('nav[aria-label="Ruta actual"]').text()).toContain('Hospital Central')
  expect(wrapper.get('nav[aria-label="Ruta actual"]').text()).toContain('Área: Cardiología')
  const selects = wrapper.findAllComponents({ name: 'ElSelect' })
  selects
    .find((item) => item.props('placeholder') === 'Filtrar por establecimiento')!
    .vm.$emit('update:modelValue', null)
  selects
    .find((item) => item.props('placeholder') === 'Filtrar por área')!
    .vm.$emit('update:modelValue', null)
  await flushPromises()
  const nav = wrapper.get('nav[aria-label="Ruta actual"]')
  expect(nav.text()).not.toContain('Hospital Central')
  expect(nav.text()).not.toContain('Área: Cardiología')
  expect(nav.get('[aria-current="page"]').text()).toBe('Consultorios')
  expect(wrapper.vm.$router.currentRoute.value.query).toEqual({})
})

test('volver utiliza el consultorio actual y retira filtros de área que ya no le corresponden', async () => {
  list.mockResolvedValue([anOffice({ especialidad_codigo: null, area_codigo: null })])
  const wrapper = await mountView(
    undefined,
    1,
    '/configuracion/consultorios/1?establecimientoId=99&areaCodigo=ANTERIOR',
  )
  await button(wrapper, 'Volver a consultorios').trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.query).toEqual({ establecimientoId: '1' })
})

test('agrega un servicio directamente al consultorio sin crear un subconsultorio', async () => {
  const office = anOffice({ servicios_habilitados: [] })
  list.mockResolvedValue([office])
  addService.mockResolvedValue({
    consultorio: {
      ...office,
      servicios_habilitados: [{ codigo: 'NUEVO', nombre: 'Servicio nuevo', activo: true }],
    },
    servicio: { codigo: 'NUEVO', nombre: 'Servicio nuevo', activo: true },
  })
  const wrapper = await mountView(undefined, 1)
  await button(wrapper, 'Agregar servicio').trigger('click')
  await flushPromises()
  await wrapper.get('input[aria-label="Nombre del nuevo servicio"]').setValue('Servicio nuevo')
  await button(wrapper, 'Agregar servicio').trigger('click')
  await flushPromises()
  expect(addService).toHaveBeenCalledWith(1, { nombre: 'Servicio nuevo' })
  expect(create).not.toHaveBeenCalled()
})

test('quitar un servicio actualiza solo los servicios del consultorio y conserva los demás', async () => {
  const office = anOffice({
    servicios_habilitados: [
      { codigo: 'CARD', nombre: 'Cardiología', activo: true },
      { codigo: 'PED', nombre: 'Pediatría', activo: true },
    ],
  })
  list.mockResolvedValue([office])
  const wrapper = await mountView(undefined, 1)
  await wrapper.get('button[aria-label="Quitar Cardiología"]').trigger('click')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(1, { servicios_codigos: ['PED'] })
  expect(ElMessageBox.confirm).toHaveBeenCalledWith(
    expect.stringContaining('se conservarán las atenciones anteriores'),
    'Quitar servicio del consultorio',
    expect.any(Object),
  )
})

test('el error al quitar un servicio queda visible sin perder la lista', async () => {
  list.mockResolvedValue([
    anOffice({ servicios_habilitados: [{ codigo: 'CARD', nombre: 'Cardiología', activo: true }] }),
  ])
  update.mockRejectedValue(new Error('El servicio está en uso por un subconsultorio.'))
  const wrapper = await mountView(undefined, 1)
  await wrapper.get('button[aria-label="Quitar Cardiología"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('El servicio está en uso por un subconsultorio.')
  expect(wrapper.find('button[aria-label="Quitar Cardiología"]').exists()).toBe(true)
})

test('un consultorio inactivo impide agregar y quitar servicios', async () => {
  list.mockResolvedValue([
    anOffice({
      activo: false,
      servicios_habilitados: [{ codigo: 'CARD', nombre: 'Cardiología', activo: true }],
    }),
  ])
  const wrapper = await mountView(undefined, 1)
  expect(button(wrapper, 'Agregar servicio').props('disabled')).toBe(true)
  expect(
    wrapper.get('button[aria-label="Quitar Cardiología"]').attributes('disabled'),
  ).toBeDefined()
})

test('la vista inicial muestra el servicio y permite abrir cada consultorio', async () => {
  list.mockResolvedValue([
    anOffice({
      area_codigo: 'MED',
      especialidad_codigo: null,
      servicios_habilitados: [
        { codigo: 'CARD', nombre: 'Cardiología', activo: true },
        { codigo: 'PED', nombre: 'Pediatría', activo: true },
      ],
    }),
  ])
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true },
  ])
  const wrapper = await mountView()
  const columns = wrapper.findAllComponents({ name: 'ElTableColumn' })
  expect(columns.map((column) => column.props('label'))).toEqual([
    'Consultorio',
    'Establecimiento',
    'Servicio / especialidad',
    'Acciones',
  ])
  expect(columns.every((column) => !column.props('fixed'))).toBe(true)
  const table = wrapper.get('.offices-table')
  expect(table.text()).toContain('CONS-01')
  expect(table.text()).toContain('Activo')
  expect(table.text()).toContain('Medicina')
  expect(table.find('.office-parent').exists()).toBe(false)
  expect(table.get('.office-service-names').text()).toBe('Cardiología, Pediatría')
  await table
    .get('.office-actions')
    .get('button[aria-label="Gestionar servicios de Consultorio A"]')
    .trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.name).toBe('consultorio-servicios')
  expect(wrapper.vm.$router.currentRoute.value.params.officeId).toBe('1')
  expect(button(wrapper, 'Editar').props('link')).toBe(true)
  expect(button(wrapper, 'Asignaciones').exists()).toBe(true)
  await officeAction(wrapper, 'Editar')
  await flushPromises()
  expect(wrapper.text()).toContain('Editar consultorio')
})

test('la ruta identifica consultorios y el formulario solo ofrece áreas', async () => {
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'AREA-NUEVA', nombre: 'REHABILITACIÓN', es_area: true, activo: true },
    { codigo: 'ESP-NUEVA', nombre: 'TERAPIA', es_area: false, activo: true },
  ])
  const wrapper = await mountView(['CONSULTORIO_GESTIONAR'])
  expect(wrapper.find('[role="tablist"]').exists()).toBe(false)
  expect(wrapper.get('nav[aria-label="Ruta actual"] [aria-current="page"]').text()).toBe(
    'Consultorios',
  )
  await button(wrapper, 'Nuevo consultorio').trigger('click')
  await flushPromises()
  const areaOptions = fieldItem(wrapper, 'Área asistencial').findAllComponents({ name: 'ElOption' })
  expect(areaOptions.map((item) => item.props('label'))).toContain('REHABILITACIÓN')
  expect(areaOptions.map((item) => item.props('label'))).not.toContain('TERAPIA')
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
    area_codigo: 'CARD',
  })
  expect(list).toHaveBeenCalledWith({ establecimientoId: undefined, incluirInactivos: false })
  expect(wrapper.vm.$router.currentRoute.value.name).toBe('consultorio-servicios')
})

test.each([null, 9])(
  'editar identidad conserva servicios, especialidad y relaciones existentes: padre %s',
  async (parentId) => {
    list.mockResolvedValue([
      anOffice({
        area_codigo: 'MED',
        especialidad_codigo: 'CARD',
        consultorio_padre_id: parentId,
        servicios_codigos: ['PED'],
        servicios_habilitados: [{ codigo: 'PED', nombre: 'Pediatría', activo: true }],
      }),
    ])
    catalogos.especialidades.mockResolvedValue([
      { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true },
      { codigo: 'CARD', nombre: 'Cardiología anterior', es_area: false, activo: true },
    ])
    const wrapper = await mountView(undefined, 1)
    await button(wrapper, 'Editar consultorio').trigger('click')
    await flushPromises()
    expect(
      wrapper.findAllComponents({ name: 'ElFormItem' }).map((item) => item.props('label')),
    ).toEqual(['Establecimiento', 'Código', 'Nombre del consultorio', 'Área asistencial'])
    const dialog = wrapper.findComponent({ name: 'OfficeFormDialog' })
    expect(dialog.text()).not.toContain('Consultorio padre')
    expect(dialog.text()).not.toContain('Usar servicios del área')
    expect(dialog.text()).toContain('Gestionar servicios')
    // Abrir el formulario no vuelve a consultar una jerarquía de consultorios.
    expect(list).toHaveBeenCalledTimes(1)
    await setField(wrapper, 'Nombre', 'Consultorio renombrado')
    await button(wrapper, 'Guardar').trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalledWith(1, {
      codigo: 'CONS-01',
      nombre: 'Consultorio renombrado',
    })
  },
)

test('cambiar área envía solo el área y deja al servidor validar la compatibilidad sin borrar servicios', async () => {
  list.mockResolvedValue([anOffice({ area_codigo: 'MED', servicios_codigos: ['PED'] })])
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true },
    { codigo: 'LAB', nombre: 'Laboratorio', es_area: true, activo: true },
  ])
  update.mockRejectedValueOnce(new Error('Los servicios configurados no corresponden al área.'))
  const wrapper = await mountView()
  await officeAction(wrapper, 'Editar')
  await flushPromises()
  await selectField(wrapper, 'Área asistencial', 'LAB')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(1, {
    codigo: 'CONS-01',
    nombre: 'Consultorio A',
    area_codigo: 'LAB',
  })
  expect(wrapper.findComponent({ name: 'OfficeFormDialog' }).props('modelValue')).toBe(true)
  expect(wrapper.text()).toContain('Los servicios configurados no corresponden al área.')
  expect(list).toHaveBeenCalledTimes(1)
})

test('la tabla de asignaciones se muestra aunque venga vacía', async () => {
  const wrapper = await mountView()
  await officeAction(wrapper, 'Asignaciones')
  await flushPromises()

  expect(listAssignments).toHaveBeenCalledWith(1, {
    includeInherited: true,
    serviceCode: undefined,
  })
  expect(wrapper.text()).toContain('Sin asignaciones registradas')
})

test('asignar profesional envía el payload y recarga las asignaciones', async () => {
  const wrapper = await mountView()
  await officeAction(wrapper, 'Asignaciones')
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
  await officeAction(wrapper, 'Asignaciones')
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
  await officeAction(wrapper, 'Asignaciones')
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
  await officeAction(wrapper, 'Asignaciones')
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
  await officeAction(wrapper, 'Asignaciones')
  await flushPromises()

  await wrapper.get('button[aria-label="Cerrar asignación de Luis Torres"]').trigger('click')
  await flushPromises()
  const closeDialog = wrapper
    .findAllComponents({ name: 'ElDialog' })
    .find((dialog) => dialog.props('title') === 'Cerrar asignación')!
  expect(closeDialog.text()).toContain('Luis Torres')
  await setDate(closeDialog, 'Fecha de fin', '2026-06-30')
  await button(closeDialog, 'Cerrar asignación').trigger('click')
  await flushPromises()

  expect(closeAssignment).toHaveBeenCalledWith(1, 5, '2026-01-01', '2026-06-30')
  expect(listAssignments).toHaveBeenCalledTimes(2)
})

test('la baja es informativa y refresca la lista', async () => {
  const wrapper = await mountView()
  await officeAction(wrapper, 'Dar de baja')
  await flushPromises()

  expect(ElMessageBox.confirm).toHaveBeenCalledWith(
    expect.stringContaining('Se conservará el historial.'),
    'Dar de baja consultorio',
    expect.objectContaining({ type: 'info' }),
  )
  expect(deactivate).toHaveBeenCalledWith(1)
  expect(list).toHaveBeenCalledTimes(2)
})

test.each([
  { activo: false, activo_efectivo: false, bajaDisabled: true },
  { activo: true, activo_efectivo: false, bajaDisabled: false },
])('el menú respeta las restricciones de actividad: %j', async (state) => {
  list.mockResolvedValue([anOffice(state)])
  const wrapper = await mountView()
  await button(wrapper, 'Más').trigger('click')
  await flushPromises()
  const items = wrapper.findAllComponents({ name: 'ElDropdownItem' })
  expect(items.some((item) => item.text() === 'Nuevo subconsultorio')).toBe(false)
  const deactivateItem = items.find((item) => item.text() === 'Dar de baja')!
  expect(deactivateItem.props('disabled')).toBe(state.bajaDisabled)
  expect(wrapper.findAllComponents({ name: 'ElFormItem' })).toHaveLength(0)
  if (state.bajaDisabled) {
    await deactivateItem.get('[role="menuitem"]').trigger('click')
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
  }
  // El controlador también rechaza comandos que no estén permitidos.
  if (state.bajaDisabled)
    wrapper
      .findComponent(OfficeActions)
      .findComponent({ name: 'ElDropdown' })
      .vm.$emit('command', 'deactivate')
  expect(wrapper.findAllComponents({ name: 'ElFormItem' })).toHaveLength(0)
  expect(deactivate).not.toHaveBeenCalled()
})

test('el detalle concentra servicios y profesionales sin una segunda tabla de subconsultorios', async () => {
  const service = { codigo: 'PED', nombre: 'Pediatría', activo: true }
  list.mockResolvedValue([
    anOffice({ id: 2, nombre: 'Sala hija', consultorio_padre_id: 1 }),
    anOffice({ servicios_habilitados: [service] }),
  ])
  listServices.mockResolvedValue([service])
  const wrapper = await mountView(undefined, 1)
  expect(wrapper.text()).toContain('Servicios / especialidades')
  expect(wrapper.text()).toContain('Pediatría')
  expect(wrapper.find('button[aria-label="Ver profesionales de Pediatría"]').exists()).toBe(true)
  expect(wrapper.find('.suboffices-section').exists()).toBe(false)
  expect(wrapper.findComponent({ name: 'OfficesTable' }).exists()).toBe(false)
  expect(wrapper.text()).not.toContain('Nuevo subconsultorio')
  expect(create).not.toHaveBeenCalled()
  expect(deactivate).not.toHaveBeenCalled()
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

test('abrir profesionales de un servicio consulta las asignaciones directas e heredadas de ese servicio', async () => {
  const service = { codigo: 'PED', nombre: 'Pediatría', activo: true }
  list.mockResolvedValue([anOffice({ servicios_habilitados: [service] })])
  listAssignments.mockResolvedValue([
    anAssignment({ profesional_id: 1, profesional_nombre: 'Profesional 1' }),
    anAssignment({ profesional_id: 2, profesional_nombre: 'Profesional 2' }),
    anAssignment({
      profesional_id: 3,
      profesional_nombre: 'Profesional 3',
      heredada: true,
      consultorio_nombre: 'Origen',
    }),
  ])
  const wrapper = await mountView(undefined, 1)
  await wrapper.get('button[aria-label="Ver profesionales de Pediatría"]').trigger('click')
  await flushPromises()
  expect(listAssignments).toHaveBeenLastCalledWith(1, {
    includeInherited: true,
    serviceCode: 'PED',
  })
  expect(wrapper.text()).toContain('Profesional 3')
  expect(wrapper.text()).toContain('Heredada de Origen')
  await button(wrapper, 'Asignar profesional').trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent(OfficeAssignmentDialog)
  expect(dialog.props('initialService')).toBe('PED')
  await selectField(dialog, 'Profesional', 5)
  await setDate(dialog, 'Fecha de inicio', '2026-01-01')
  await button(dialog, 'Guardar asignación').trigger('click')
  await flushPromises()
  expect(assign).toHaveBeenCalledWith(
    1,
    expect.objectContaining({
      profesional_id: 5,
      servicios_codigos: ['PED'],
    }),
  )
})

test('el contexto de sede y área precarga el alta y se conserva al navegar al servicio', async () => {
  list.mockResolvedValue([anOffice({ area_codigo: 'MED', especialidad_codigo: null })])
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true },
  ])
  const wrapper = await mountView(
    undefined,
    undefined,
    '/?establecimientoId=1&areaCodigo=MED&nuevo=1',
  )
  expect(
    fieldItem(wrapper, 'Establecimiento').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBe(1)
  expect(
    fieldItem(wrapper, 'Área asistencial').findComponent({ name: 'ElSelect' }).props('modelValue'),
  ).toBe('MED')
  expect(wrapper.vm.$router.currentRoute.value.query.nuevo).toBeUndefined()
  expect(create).not.toHaveBeenCalled()
  await button(wrapper, 'Cancelar').trigger('click')
  await wrapper
    .get('.offices-table button[aria-label="Gestionar servicios de Consultorio A"]')
    .trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.query).toEqual({
    establecimientoId: '1',
    areaCodigo: 'MED',
  })
})

test('edita el servicio desde el consultorio, explica su alcance y conserva datos ante error', async () => {
  const service = { codigo: 'PED', nombre: 'Pediatría', activo: true }
  const original = anOffice({ servicios_habilitados: [service] })
  const renamed = anOffice({
    servicios_habilitados: [{ ...service, nombre: 'Pediatría integral' }],
  })
  list.mockResolvedValue([original])
  vi.mocked(serviciosAsistenciales.get).mockResolvedValue({
    ...service,
    area_codigos: ['MED'],
    consultorios: [
      { id: 1, nombre: 'Consultorio A', establecimiento_id: 1, activo: true },
      { id: 2, nombre: 'Consultorio B', establecimiento_id: 2, activo: true },
    ],
  })
  vi.mocked(serviciosAsistenciales.update).mockRejectedValueOnce(new Error('Nombre duplicado.'))
  const wrapper = await mountView(undefined, 1)
  await wrapper.get('button[aria-label="Editar servicio Pediatría"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('2 consultorios vinculados')
  const dialog = wrapper.findComponent({ name: 'CareServiceFormDialog' })
  await dialog.get('input[aria-label="Nombre del servicio"]').setValue('Pediatría integral')
  await button(dialog, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(dialog.text()).toContain('Nombre duplicado.')
  expect(
    (dialog.get('input[aria-label="Nombre del servicio"]').element as HTMLInputElement).value,
  ).toBe('Pediatría integral')
  get.mockResolvedValue(renamed)
  list.mockResolvedValue([renamed])
  vi.mocked(serviciosAsistenciales.update).mockResolvedValue({
    ...service,
    nombre: 'Pediatría integral',
    area_codigos: ['MED'],
    consultorios: [],
  })
  await button(dialog, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(serviciosAsistenciales.update).toHaveBeenLastCalledWith('PED', 'Pediatría integral')
  expect(wrapper.text()).toContain('Pediatría integral')
  expect(update).not.toHaveBeenCalled()
})

test('editar una asignación precarga fechas, responsable y servicios sin crear otra', async () => {
  const assignment = anAssignment({ profesional_nombre: 'Luis Torres', servicios_codigos: ['PED'] })
  listAssignments.mockResolvedValue([assignment])
  list.mockResolvedValue([
    anOffice({ servicios_habilitados: [{ codigo: 'PED', nombre: 'Pediatría', activo: true }] }),
  ])
  updateAssignment.mockRejectedValueOnce(new Error('Periodo en conflicto.'))
  const wrapper = await mountView(undefined, 1)
  await button(wrapper, 'Asignaciones').trigger('click')
  await flushPromises()
  await button(wrapper, 'Editar asignación').trigger('click')
  await flushPromises()
  const dialog = wrapper
    .findAllComponents(OfficeAssignmentDialog)
    .find((item) => item.props('editingAssignment'))!
  expect(
    fieldItem(dialog, 'Fecha de inicio')
      .findComponent({ name: 'ElDatePicker' })
      .props('modelValue'),
  ).toBe('2026-01-01')
  expect(fieldItem(dialog, 'Profesional').find('input').attributes('readonly')).toBeDefined()
  await setDate(dialog, 'Fecha de inicio', '2026-02-01')
  fieldItem(dialog, 'Responsable')
    .findComponent({ name: 'ElCheckbox' })
    .vm.$emit('update:modelValue', true)
  await button(dialog, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(updateAssignment).toHaveBeenCalledTimes(1)
  expect(dialog.props('error')).toBe('Periodo en conflicto.')
  expect(dialog.props('modelValue')).toBe(true)
  updateAssignment.mockResolvedValue({
    ...assignment,
    fecha_inicio: '2026-02-01',
    es_responsable: true,
  })
  await button(dialog, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(updateAssignment).toHaveBeenLastCalledWith(assignment, {
    fecha_inicio: '2026-02-01',
    fecha_fin: null,
    es_responsable: true,
    servicios_codigos: ['PED'],
  })
  expect(assign).not.toHaveBeenCalled()
})

test('crear en otra sede o área abre el nuevo consultorio con su contexto real', async () => {
  const created = anOffice({ id: 42, establecimiento_id: 2, area_codigo: 'LAB' })
  create.mockResolvedValue(created)
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true },
    { codigo: 'LAB', nombre: 'Laboratorio', es_area: true, activo: true },
  ])
  const wrapper = await mountView(
    undefined,
    undefined,
    '/?establecimientoId=1&areaCodigo=MED&nuevo=1',
  )
  await selectField(wrapper, 'Establecimiento', 2)
  await selectField(wrapper, 'Área asistencial', 'LAB')
  await setField(wrapper, 'Código', 'LAB-2')
  await setField(wrapper, 'Nombre', 'Laboratorio 2')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()
  expect(wrapper.vm.$router.currentRoute.value.name).toBe('consultorio-servicios')
  expect(wrapper.vm.$router.currentRoute.value.params.officeId).toBe('42')
  expect(wrapper.vm.$router.currentRoute.value.query).toEqual({
    establecimientoId: '2',
    areaCodigo: 'LAB',
  })
})
