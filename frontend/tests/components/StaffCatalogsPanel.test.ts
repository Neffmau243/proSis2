import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import StaffCatalogsPanel from '@/components/configuracion/StaffCatalogsPanel.vue'
import StaffCatalogSection from '@/components/configuracion/StaffCatalogSection.vue'
import StaffCatalogForm from '@/components/configuracion/StaffCatalogForm.vue'

const {
  professions,
  specialties,
  createProfession,
  createSpecialty,
  updateProfession,
  updateSpecialty,
  deleteProfession,
  deleteSpecialty,
} = vi.hoisted(() => ({
  professions: vi.fn(),
  specialties: vi.fn(),
  createProfession: vi.fn(),
  createSpecialty: vi.fn(),
  updateProfession: vi.fn(),
  updateSpecialty: vi.fn(),
  deleteProfession: vi.fn(),
  deleteSpecialty: vi.fn(),
}))
vi.mock('@/services/catalogos', () => ({
  catalogos: { profesiones: professions, especialidades: specialties },
}))
vi.mock('@/services/catalogosPersonal', () => ({
  catalogosPersonal: {
    createProfession,
    createSpecialty,
    updateProfession,
    updateSpecialty,
    deleteProfession,
    deleteSpecialty,
  },
}))

const mounted: VueWrapper[] = []
beforeEach(() => {
  vi.clearAllMocks()
  professions.mockResolvedValue([{ id: 1, codigo: '1', nombre: 'MEDICO', activo: true }])
  specialties.mockResolvedValue([{ codigo: 'MED', nombre: 'MEDICINA', grupo: null, activo: true }])
  createProfession.mockResolvedValue({ id: 2, codigo: '2', nombre: 'TERAPEUTA', activo: true })
  createSpecialty.mockResolvedValue({
    codigo: 'ESP-NUEVA',
    nombre: 'TERAPIA',
    grupo: 'REHABILITACION',
    activo: true,
  })
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
})
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})
async function panel(kind: 'profesion' | 'especialidad' = 'especialidad') {
  const wrapper = mount(StaffCatalogsPanel, { props: { kind }, global: { plugins: [ElementPlus] } })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}
function button(wrapper: VueWrapper, label: string) {
  const result = wrapper.findAll('button').find((item) => item.text() === label)
  if (!result) throw new Error(`Missing ${label}`)
  return result
}

test.each(['profesion', 'especialidad'] as const)(
  'elimina una %s solo después de confirmar',
  async (kind) => {
    deleteProfession.mockResolvedValue(undefined)
    deleteSpecialty.mockResolvedValue(undefined)
    const wrapper = await panel(kind)
    await button(wrapper, 'Eliminar').trigger('click')
    await flushPromises()
    expect(deleteProfession).not.toHaveBeenCalled()
    expect(deleteSpecialty).not.toHaveBeenCalled()
    await button(wrapper, 'Eliminar registro').trigger('click')
    await flushPromises()
    if (kind === 'profesion') expect(deleteProfession).toHaveBeenCalledWith(1)
    else expect(deleteSpecialty).toHaveBeenCalledWith('MED')
    expect(wrapper.text()).toContain('0 registros')
    expect(ElMessage.success).toHaveBeenCalledWith('Registro eliminado.')
    expect(wrapper.emitted('created')).toHaveLength(1)
  },
)

test('cancelar no elimina y un vínculo en uso conserva la fila con el motivo', async () => {
  deleteSpecialty.mockRejectedValue(new Error('Está vinculada a un profesional.'))
  const wrapper = await panel()
  await button(wrapper, 'Eliminar').trigger('click')
  await flushPromises()
  await button(wrapper, 'Cancelar').trigger('click')
  expect(deleteSpecialty).not.toHaveBeenCalled()
  await button(wrapper, 'Eliminar').trigger('click')
  await flushPromises()
  await button(wrapper, 'Eliminar registro').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Está vinculada a un profesional.')
  expect(wrapper.text()).toContain('1 registros')
  expect(wrapper.emitted('created')).toBeUndefined()
})

test('crea un área y permite cambiar su tipo al editar sin duplicar el registro', async () => {
  createSpecialty.mockResolvedValue({
    codigo: 'ESP-AREA',
    nombre: 'REHABILITACIÓN',
    activo: true,
    grupo: null,
    es_area: true,
    es_area_base: false,
  })
  updateSpecialty.mockResolvedValue({
    codigo: 'ESP-AREA',
    nombre: 'REHABILITACIÓN',
    activo: true,
    grupo: null,
    es_area: false,
    es_area_base: false,
  })
  const wrapper = await panel()
  await button(wrapper, 'Nueva área o especialidad').trigger('click')
  await wrapper.find('form input[value="true"]').setValue(true)
  await wrapper.find('form input:not([type="radio"])').setValue('Rehabilitación')
  await button(wrapper, 'Guardar área').trigger('click')
  await flushPromises()
  expect(createSpecialty).toHaveBeenCalledWith({ nombre: 'Rehabilitación', es_area: true })
  const row = wrapper.findAll('tr').find((entry) => entry.text().includes('REHABILITACIÓN'))!
  expect(row.text()).toContain('Área')
  expect(
    row.find('button[aria-label="Eliminar REHABILITACIÓN"]').attributes('disabled'),
  ).toBeUndefined()
  await row.find('button[aria-label="Editar REHABILITACIÓN"]').trigger('click')
  expect((wrapper.find('form input[value="true"]').element as HTMLInputElement).checked).toBe(true)
  await wrapper.find('form input[value="false"]').setValue(true)
  await button(wrapper, 'Guardar cambios').trigger('click')
  await flushPromises()
  expect(updateSpecialty).toHaveBeenCalledWith('ESP-AREA', 'REHABILITACIÓN', false)
  expect(
    wrapper.findAll('tr').filter((entry) => entry.text().includes('REHABILITACIÓN')),
  ).toHaveLength(1)
  expect(
    wrapper
      .findAll('tr')
      .find((entry) => entry.text().includes('REHABILITACIÓN'))!
      .text(),
  ).toContain('Especialidad')
})

test('explica por qué el tipo de un área base no se cambia', async () => {
  specialties.mockResolvedValue([
    {
      codigo: 'ESPECIALIDADES:003',
      nombre: 'MEDICINA',
      activo: true,
      grupo: null,
      es_area: true,
      es_area_base: true,
    },
  ])
  const wrapper = await panel()
  await button(wrapper, 'Editar').trigger('click')
  const radios = wrapper.findAll('form input[type="radio"]')
  expect(radios).toHaveLength(2)
  expect(radios.every((input) => input.attributes('disabled') !== undefined)).toBe(true)
  expect(wrapper.text()).toContain(
    'Esta área base organiza servicios existentes; su tipo se conserva.',
  )
})

test.each(['profesion', 'especialidad'] as const)(
  'crea una %s y avisa al formulario profesional',
  async (kind) => {
    const wrapper = await panel(kind)
    const section = wrapper
      .findAllComponents(StaffCatalogSection)
      .find((item) => item.props('kind') === kind)!
    await button(
      section,
      kind === 'profesion' ? 'Nueva profesión' : 'Nueva área o especialidad',
    ).trigger('click')
    const form = wrapper.findComponent(StaffCatalogForm)
    await form
      .findAll('input:not([type="radio"])')[0]!
      .setValue(kind === 'profesion' ? 'Terapeuta' : 'Terapia')
    expect(form.findAll('input:not([type="radio"])')).toHaveLength(1)
    expect(form.find('[role="dialog"]').exists()).toBe(true)
    await button(form, kind === 'profesion' ? 'Guardar profesión' : 'Guardar especialidad').trigger(
      'click',
    )
    await flushPromises()
    expect(wrapper.emitted('created')).toHaveLength(1)
    expect(wrapper.findComponent(StaffCatalogForm).exists()).toBe(false)
    if (kind === 'profesion') {
      expect(createProfession).toHaveBeenCalledWith('Terapeuta')
      expect(section.text()).toContain('TERAPEUTA')
      expect(createSpecialty).not.toHaveBeenCalled()
    } else {
      expect(createSpecialty).toHaveBeenCalledWith({ nombre: 'Terapia', es_area: false })
      expect(section.text()).toContain('TERAPIA')
      expect(createProfession).not.toHaveBeenCalled()
    }
  },
)

test('conserva el nombre y muestra el error cuando el servidor rechaza un duplicado', async () => {
  createProfession.mockRejectedValue(new Error('Ya existe una profesión con ese nombre.'))
  const wrapper = await panel('profesion')
  await button(wrapper, 'Nueva profesión').trigger('click')
  await wrapper.findComponent(StaffCatalogForm).find('input:not([type="radio"])').setValue('Medico')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('Ya existe una profesión con ese nombre.')
  expect((wrapper.find('form input:not([type="radio"])').element as HTMLInputElement).value).toBe(
    'Medico',
  )
  expect(wrapper.emitted('created')).toBeUndefined()
})

test('un nombre vacío no envía peticiones y cancelar cierra el alta', async () => {
  const wrapper = await panel()
  await button(wrapper, 'Nueva área o especialidad').trigger('click')
  await wrapper.find('form input:not([type="radio"])').setValue('   ')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(createSpecialty).not.toHaveBeenCalled()
  await button(wrapper, 'Cancelar').trigger('click')
  expect(wrapper.findComponent(StaffCatalogForm).exists()).toBe(false)
})

test('permite reintentar una carga fallida y buscar sin modificar los registros', async () => {
  professions.mockRejectedValueOnce(new Error('Servidor no disponible'))
  const wrapper = await panel('profesion')
  expect(wrapper.text()).toContain('Servidor no disponible')
  await button(wrapper, 'Reintentar').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('MEDICO')
  const section = wrapper.findComponent(StaffCatalogSection)
  await section.find('input:not([type="radio"])').setValue('no existe')
  expect(section.text()).toContain('0 resultados')
})

test('distingue áreas de especialidades y no ofrece servicios ni nombres de tablas del ETL', async () => {
  specialties.mockResolvedValue([
    {
      codigo: 'ESPECIALIDADES:005',
      nombre: 'NUTRICIÓN',
      grupo: 'Especialidades',
      activo: true,
      es_area: true,
    },
    {
      codigo: 'ESP_NUTRICION:002',
      nombre: 'CANASTA TBC',
      grupo: 'Esp_Nutricion',
      activo: true,
      es_area: false,
    },
    { codigo: 'ESP-NUEVA', nombre: 'CARDIOLOGÍA', grupo: null, activo: true, es_area: false },
  ])
  const wrapper = await panel()
  const list = wrapper.get('.catalog-table')
  expect(list.text()).toContain('NUTRICIÓN')
  expect(list.text()).toContain('Área')
  expect(list.text()).toContain('CARDIOLOGÍA')
  expect(list.text()).not.toContain('CANASTA TBC')
  expect(wrapper.text()).not.toContain('Esp_Nutricion')
  expect(wrapper.findAllComponents(StaffCatalogSection)).toHaveLength(1)
})

test('cerrar el modal cancela el alta y al reabrirlo el nombre está vacío', async () => {
  const wrapper = await panel()
  await button(wrapper, 'Nueva área o especialidad').trigger('click')
  await wrapper.find('form input:not([type="radio"])').setValue('Borrador')
  wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
  await flushPromises()
  expect(wrapper.findComponent(StaffCatalogForm).exists()).toBe(false)
  expect(createSpecialty).not.toHaveBeenCalled()
  await button(wrapper, 'Nueva área o especialidad').trigger('click')
  await flushPromises()
  expect((wrapper.find('form input:not([type="radio"])').element as HTMLInputElement).value).toBe(
    '',
  )
})

test('mantiene el modal abierto mientras guarda y evita un segundo envío', async () => {
  let complete!: (value: unknown) => void
  createSpecialty.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve
      }),
  )
  const wrapper = await panel()
  await button(wrapper, 'Nueva área o especialidad').trigger('click')
  await wrapper.find('form input:not([type="radio"])').setValue('Cardiología')
  await button(wrapper, 'Guardar especialidad').trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent({ name: 'ElDialog' })
  expect(dialog.props('closeOnPressEscape')).toBe(false)
  expect(dialog.props('showClose')).toBe(false)
  dialog.vm.$emit('update:modelValue', false)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(wrapper.findComponent(StaffCatalogForm).exists()).toBe(true)
  expect(createSpecialty).toHaveBeenCalledTimes(1)
  complete({ codigo: 'ESP-NUEVA', nombre: 'CARDIOLOGÍA', grupo: null, activo: true })
  await flushPromises()
  expect(wrapper.findComponent(StaffCatalogForm).exists()).toBe(false)
  expect(wrapper.get('.catalog-table').text()).toContain('CARDIOLOGÍA')
})

test.each(['profesion', 'especialidad'] as const)(
  'edita una %s desde su modal sin duplicar la fila',
  async (kind) => {
    updateProfession.mockResolvedValue({
      id: 1,
      codigo: '1',
      nombre: 'MÉDICO CORREGIDO',
      activo: true,
    })
    updateSpecialty.mockResolvedValue({
      codigo: 'MED',
      nombre: 'MEDICINA CORREGIDA',
      grupo: null,
      activo: true,
    })
    const wrapper = await panel(kind)
    await button(wrapper, 'Editar').trigger('click')
    await flushPromises()
    const input = wrapper.find('form input:not([type="radio"])')
    expect((input.element as HTMLInputElement).value).toBe(
      kind === 'profesion' ? 'MEDICO' : 'MEDICINA',
    )
    await input.setValue('Nombre corregido')
    await button(wrapper, 'Guardar cambios').trigger('click')
    await flushPromises()
    if (kind === 'profesion') expect(updateProfession).toHaveBeenCalledWith(1, 'Nombre corregido')
    else expect(updateSpecialty).toHaveBeenCalledWith('MED', 'Nombre corregido', false)
    expect(createProfession).not.toHaveBeenCalled()
    expect(createSpecialty).not.toHaveBeenCalled()
    expect(wrapper.findComponent(StaffCatalogForm).exists()).toBe(false)
    expect(wrapper.text()).toContain('1 registros')
    expect(wrapper.emitted('created')).toHaveLength(1)
  },
)
