import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import ProfessionalsPanel from '@/components/configuracion/ProfessionalsPanel.vue'
import ProfessionalQualificationsFields from '@/components/configuracion/ProfessionalQualificationsFields.vue'
import type { ProfessionalResponse } from '@/services/profesionales'

const { list, create, update, replaceSpecialties, deactivate } = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  replaceSpecialties: vi.fn(),
  deactivate: vi.fn(),
}))

const { catalogos } = vi.hoisted(() => ({
  catalogos: { profesiones: vi.fn(), especialidades: vi.fn() },
}))

vi.mock('@/services/profesionales', () => ({
  profesionales: { list, create, update, replaceSpecialties, deactivate },
}))
vi.mock('@/services/catalogos', () => ({ catalogos }))

function aProfessional(overrides: Partial<ProfessionalResponse> = {}): ProfessionalResponse {
  return {
    id: 1,
    codigo_legacy: null,
    numero_documento: '12345678',
    nombre_completo: 'Ana Quispe',
    profesion_id: 10,
    colegiatura: 'CMP-001',
    activo: true,
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    especialidades: [],
    ...overrides,
  }
}

const mounted: { unmount: () => void }[] = []

async function mountPanel(props: Partial<InstanceType<typeof ProfessionalsPanel>['$props']> = {}) {
  const wrapper = mount(ProfessionalsPanel, {
    props: {
      rows: [aProfessional()],
      loading: false,
      incluirInactivos: false,
      linkedProfessionalIds: [],
      canCreateAccount: false,
      ...props,
    },
    global: { plugins: [ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

function button(wrapper: VueWrapper, label: string) {
  const found = wrapper.findAll('button').find((item) => item.text().includes(label))
  if (!found) throw new Error(`No se encontró el botón "${label}"`)
  return found
}

async function setField(wrapper: VueWrapper, label: string, value: string): Promise<void> {
  const item = wrapper
    .findAll('.el-form-item')
    .find((element) => element.find('.el-form-item__label').text().startsWith(label))
  if (!item) throw new Error(`No se encontró el campo "${label}"`)
  await item.find('input').setValue(value)
}

beforeEach(() => {
  vi.clearAllMocks()
  catalogos.profesiones.mockResolvedValue([
    { id: 10, codigo: 'MED', nombre: 'Médico', activo: true },
  ])
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'CARD', nombre: 'Cardiología', activo: true, grupo: null },
  ])
  create.mockResolvedValue(aProfessional({ id: 2 }))
  update.mockResolvedValue(aProfessional())
  replaceSpecialties.mockResolvedValue(aProfessional())
  deactivate.mockResolvedValue(aProfessional({ activo: false }))
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
})

test('recarga los catálogos cuando se crea una profesión o especialidad desde Personal', async () => {
  const wrapper = await mountPanel({ catalogRevision: 0 })
  expect(catalogos.profesiones).toHaveBeenCalledTimes(1)
  await wrapper.setProps({ catalogRevision: 1 })
  await flushPromises()
  expect(catalogos.profesiones).toHaveBeenCalledTimes(2)
  expect(catalogos.especialidades).toHaveBeenCalledTimes(2)
})

test('excluye servicios de las opciones nuevas y conserva asignaciones históricas al editar', async () => {
  catalogos.especialidades.mockResolvedValue([
    { codigo: 'ESP_NUTRICION:002', nombre: 'CANASTA TBC', grupo: 'Esp_Nutricion', activo: true },
    {
      codigo: 'ESPECIALIDADES:005',
      nombre: 'NUTRICIÓN',
      grupo: 'Especialidades',
      es_area: true,
      activo: true,
    },
  ])
  const wrapper = await mountPanel({
    rows: [
      aProfessional({
        especialidades: [{ especialidad_codigo: 'ESP_NUTRICION:002', es_principal: true }],
      }),
    ],
  })
  await button(wrapper, 'Especialidades').trigger('click')
  await flushPromises()
  expect(
    wrapper.findAllComponents({ name: 'ElOption' }).map((item) => item.props('label')),
  ).toContain('CANASTA TBC (registro anterior)')
  await button(wrapper, 'Quitar').trigger('click')
  await button(wrapper, 'Agregar especialidad').trigger('click')
  await flushPromises()
  const labels = wrapper.findAllComponents({ name: 'ElOption' }).map((item) => item.props('label'))
  expect(labels).toContain('NUTRICIÓN')
  expect(labels).not.toContain('CANASTA TBC (registro anterior)')
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})

test('muestra la lista con la profesión del catálogo y el estado de cuenta', async () => {
  const wrapper = await mountPanel({ linkedProfessionalIds: [1] })

  expect(wrapper.text()).toContain('Ana Quispe')
  expect(wrapper.text()).toContain('Médico')
  expect(wrapper.text()).toContain('Con cuenta')
})

test('incluir inactivos delega el cambio al contenedor', async () => {
  const wrapper = await mountPanel()
  const switchComponent = wrapper.findComponent({ name: 'ElSwitch' })
  switchComponent.vm.$emit('update:modelValue', true)
  await flushPromises()

  expect(wrapper.emitted('update:incluirInactivos')?.[0]).toEqual([true])
})

test('la baja es informativa y pide refrescar la lista', async () => {
  const wrapper = await mountPanel()
  await button(wrapper, 'Dar de baja').trigger('click')
  await flushPromises()

  expect(ElMessageBox.confirm).toHaveBeenCalledWith(
    expect.stringContaining('La baja es lógica'),
    'Dar de baja profesional',
    expect.objectContaining({ type: 'info' }),
  )
  expect(deactivate).toHaveBeenCalledWith(1)
  expect(wrapper.emitted('refresh')).toBeTruthy()
})

test('el alta envía el contrato y normaliza los vacíos a null', async () => {
  const wrapper = await mountPanel()
  await button(wrapper, 'Nuevo profesional').trigger('click')
  await flushPromises()

  await setField(wrapper, 'Nombre completo', 'Luis Torres')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()

  expect(create).toHaveBeenCalledWith({
    nombre_completo: 'Luis Torres',
    numero_documento: null,
    profesion_id: null,
    colegiatura: null,
    especialidades: [],
  })
  expect(wrapper.emitted('refresh')).toBeTruthy()
})

test('crea la ficha con su profesión, área y especialidad en una sola petición', async () => {
  const wrapper = await mountPanel()
  await button(wrapper, 'Nuevo profesional').trigger('click')
  await flushPromises()
  await setField(wrapper, 'Nombre completo', 'Profesional de prueba')
  const profession = wrapper
    .findAllComponents({ name: 'ElSelect' })
    .find((item) => item.props('placeholder') === 'Seleccione una profesión')!
  profession.vm.$emit('update:modelValue', 10)
  const qualifications = wrapper.findComponent(ProfessionalQualificationsFields)
  qualifications.vm.$emit('update:selected', ['ESPECIALIDADES:003', 'CARD'])
  qualifications.vm.$emit('update:principal', 'CARD')
  await flushPromises()
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({
      profesion_id: 10,
      especialidades: [
        { especialidad_codigo: 'ESPECIALIDADES:003', es_principal: false },
        { especialidad_codigo: 'CARD', es_principal: true },
      ],
    }),
  )
  expect(replaceSpecialties).not.toHaveBeenCalled()
})

test('editar llama al PATCH del recurso', async () => {
  const wrapper = await mountPanel()
  await button(wrapper, 'Editar').trigger('click')
  await flushPromises()

  await setField(wrapper, 'Nombre completo', 'Ana Quispe Rojas')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()

  expect(update).toHaveBeenCalledWith(1, {
    nombre_completo: 'Ana Quispe Rojas',
    numero_documento: '12345678',
    profesion_id: 10,
    colegiatura: 'CMP-001',
  })
})

test('no se envía el alta sin nombre', async () => {
  const wrapper = await mountPanel()
  await button(wrapper, 'Nuevo profesional').trigger('click')
  await flushPromises()

  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()

  expect(create).not.toHaveBeenCalled()
  expect(wrapper.find('.el-form-item.is-error').exists()).toBe(true)
})

test('las especialidades se reemplazan conservando la principal', async () => {
  const wrapper = await mountPanel({
    rows: [
      aProfessional({ especialidades: [{ especialidad_codigo: 'CARD', es_principal: true }] }),
    ],
  })
  await button(wrapper, 'Especialidades').trigger('click')
  await flushPromises()

  await button(wrapper, 'Guardar especialidades').trigger('click')
  await flushPromises()

  expect(replaceSpecialties).toHaveBeenCalledWith(1, [
    { especialidad_codigo: 'CARD', es_principal: true },
  ])
})

test('con especialidades se exige marcar una principal', async () => {
  const wrapper = await mountPanel()
  await button(wrapper, 'Especialidades').trigger('click')
  await flushPromises()

  await button(wrapper, 'Agregar especialidad').trigger('click')
  await flushPromises()
  const select = wrapper.findAllComponents({ name: 'ElSelect' }).at(-1)
  select!.vm.$emit('update:modelValue', 'CARD')
  await flushPromises()

  await button(wrapper, 'Guardar especialidades').trigger('click')
  await flushPromises()

  expect(replaceSpecialties).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('Marque una especialidad como principal.')
})

test('un rechazo del backend se muestra con su mensaje', async () => {
  create.mockRejectedValue(new Error('El documento o código del profesional ya está registrado.'))
  const wrapper = await mountPanel()
  await button(wrapper, 'Nuevo profesional').trigger('click')
  await flushPromises()

  await setField(wrapper, 'Nombre completo', 'Luis Torres')
  await button(wrapper, 'Guardar').trigger('click')
  await flushPromises()

  expect(wrapper.find('.el-alert__title').text()).toContain(
    'El documento o código del profesional ya está registrado.',
  )
})

test('solo con permiso de cuentas y sin cuenta se ofrece crear una', async () => {
  const noButton = await mountPanel({ canCreateAccount: false })
  expect(noButton.text()).not.toContain('Crear cuenta')

  const withPermission = await mountPanel({ canCreateAccount: true, linkedProfessionalIds: [] })
  await button(withPermission, 'Crear cuenta').trigger('click')

  expect(withPermission.emitted('create-account')?.[0]?.[0]).toMatchObject({ id: 1 })
})
