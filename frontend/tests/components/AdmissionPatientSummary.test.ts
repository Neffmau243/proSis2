import { flushPromises, mount } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus, { ElMessageBox, ElOption, ElSelect, type MessageBoxData } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import AdmissionPatientSummary from '@/components/admission/AdmissionPatientSummary.vue'
import AdmissionDocumentTypes from '@/components/admission/AdmissionDocumentTypes.vue'
import PatientConditionSelect from '@/components/patients/PatientConditionSelect.vue'
import PatientSisCodeFields from '@/components/patients/PatientSisCodeFields.vue'
import FamilyHistorySelector from '@/components/patients/FamilyHistorySelector.vue'
import type { Patient } from '@/services/pacientes'
import { aPatient } from '../fixtures/patient'

const { update, deactivate, historiasFamiliares } = vi.hoisted(() => ({
  update: vi.fn<(id: number, payload: Record<string, unknown>) => Promise<Patient>>(),
  deactivate: vi.fn<(id: number) => Promise<{ id: number; estado: boolean; mensaje: string }>>(),
  historiasFamiliares: vi.fn(),
}))

const emptyPage = { items: [], total: 0, limit: 25, offset: 0 }

vi.mock('@/services/pacientes', () => ({ pacientes: { update, deactivate } }))
vi.mock('@/services/catalogos', () => ({
  catalogos: {
    sexos: vi.fn(async () => []),
    seguros: vi.fn(async () => [
      {
        id: 2,
        codigo: 'SIS_GRATUITO',
        nombre: 'S.I.S. Gratuito',
        activo: true,
        codigo_sis: '002',
        regimen: 'SIS',
      },
      {
        id: 1,
        codigo: 'SIN_SEGURO',
        nombre: 'Sin seguro',
        activo: true,
        codigo_sis: '001',
        regimen: 'NINGUNO',
      },
      {
        id: 3,
        codigo: 'ESSALUD',
        nombre: 'EsSalud',
        activo: true,
        codigo_sis: '007',
        regimen: 'ESSALUD',
      },
      {
        id: 10,
        codigo: 'SIS_NRUS',
        nombre: 'S.I.S. NRUS',
        activo: true,
        codigo_sis: '005',
        regimen: 'SIS',
      },
    ]),
    etnias: vi.fn(async () => [
      { codigo: '1', nombre: 'Quechua', activo: true },
      { codigo: '58', nombre: 'Mestizo', activo: true },
    ]),
    historiasFamiliares,
    establecimientos: vi.fn(async () => ({
      ...emptyPage,
      items: [
        {
          id: 2,
          codigo_renaes: '1300',
          codigo_ideess: '1300',
          disa_codigo: '040',
          nombre: 'P.S. APURIMAC',
          abreviatura: null,
          activo: true,
        },
      ],
    })),
    ubigeos: vi.fn(async () => emptyPage),
    localidades: vi.fn(async () => emptyPage),
  },
}))

const mounted: { unmount: () => void }[] = []

async function mountPanel(canDelete: boolean, overrides: Partial<Patient> = {}) {
  const wrapper = mount(AdmissionPatientSummary, {
    props: {
      patient: aPatient(overrides),
      canEdit: true,
      canDelete,
      tiposDocumento: [
        { codigo: 'DNI', nombre: 'DNI', activo: true },
        { codigo: 'CE', nombre: 'Carné de extranjería', activo: true },
      ],
    },
    global: { plugins: [ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

function deleteButton(wrapper: Awaited<ReturnType<typeof mountPanel>>) {
  return wrapper.findAll('button').find((button) => button.text().includes('Eliminar paciente'))
}

beforeEach(() => {
  update.mockReset()
  deactivate.mockReset()
  historiasFamiliares.mockReset()
  historiasFamiliares.mockResolvedValue(emptyPage)
  deactivate.mockResolvedValue({ id: 100, estado: false, mensaje: 'Paciente dado de baja.' })
})

test('cambiar seguro limpia SIS en el borrador y envía el borrado por PATCH', async () => {
  const wrapper = await mountPanel(false, {
    seguro_id: 2,
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '00112233',
    sis_secuencia: '01',
    etnia_codigo: '58',
  })
  const select = wrapper.get('.patient-context__insurance-selector').getComponent(ElSelect)
  select.vm.$emit('update:modelValue', 1)
  select.vm.$emit('change', 1)
  await flushPromises()
  update.mockResolvedValue(
    aPatient({
      seguro_id: 1,
      sis_diresa: null,
      sis_tipo: null,
      sis_numero: null,
      sis_secuencia: null,
      etnia_codigo: '58',
    }),
  )
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, {
    seguro_id: 1,
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
    sis_secuencia: null,
  })
  expect(wrapper.findComponent(PatientSisCodeFields).exists()).toBe(false)
})

test('no expone el código técnico ETLSIS en el formulario', async () => {
  const wrapper = await mountPanel(false, { seguro_id: 2 })
  expect(wrapper.find('.patient-context__insurance-code').exists()).toBe(false)
})

test('la localidad de texto del legado se muestra, se puede editar y se puede limpiar', async () => {
  const wrapper = await mountPanel(false, {
    ubigeo_residencia_codigo: '040102',
    localidad_id: null,
    localidad: 'ALTO SELVA ALEGRE',
  })
  const field = wrapper
    .findAllComponents(ElSelect)
    .find((item) => item.find('input[role="combobox"]').attributes('aria-label') === 'Localidad')!
  expect(field.props('modelValue')).toBe('ALTO SELVA ALEGRE')
  field.vm.$emit('update:modelValue', 'Barrio declarado')
  await flushPromises()
  expect(field.props('modelValue')).toBe('Barrio declarado')
  field.vm.$emit('update:modelValue', null)
  await flushPromises()
  expect(field.props('modelValue')).toBeNull()
  update.mockResolvedValue(
    aPatient({ ubigeo_residencia_codigo: '040102', localidad_id: null, localidad: null }),
  )
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, { localidad: null })
})

test('cambiar distrito limpia localidad, pero descartar o cambiar paciente restaura la pareja', async () => {
  const wrapper = await mountPanel(false, {
    ubigeo_residencia_codigo: '040102',
    localidad_id: 12,
    localidad: 'Sector guardado',
  })
  const field = (label: string) =>
    wrapper
      .findAllComponents(ElSelect)
      .find((select) => select.find('input[role="combobox"]').attributes('aria-label') === label)!
  field('Distrito').vm.$emit('update:modelValue', '040103')
  await flushPromises()
  expect(field('Localidad').props('modelValue')).toBeNull()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Descartar cambios')!
    .trigger('click')
  await flushPromises()
  expect(field('Localidad').props('modelValue')).toBe(12)
  expect(wrapper.text()).not.toContain('Guardar cambios pendientes')
  await wrapper.setProps({
    patient: aPatient({
      id: 101,
      ubigeo_residencia_codigo: '040104',
      localidad_id: 14,
      localidad: 'Otro sector',
    }),
  })
  await flushPromises()
  expect(field('Localidad').props('modelValue')).toBe(14)
})

test('la marca sigue el borrador, el descarte y el seguro guardado por PATCH', async () => {
  const wrapper = await mountPanel(false, { seguro_id: 2 })
  const select = wrapper.get('.patient-context__insurance-selector').getComponent(ElSelect)
  expect(wrapper.get('.patient-context__sis-brand img').attributes('alt')).toContain('SIS')
  select.vm.$emit('update:modelValue', 3)
  select.vm.$emit('change', 3)
  await flushPromises()
  expect(wrapper.get('.patient-context__sis-brand img').attributes('alt')).toContain('EsSalud')
  expect(wrapper.findComponent(PatientSisCodeFields).exists()).toBe(false)

  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Descartar cambios')!
    .trigger('click')
  expect(wrapper.get('.patient-context__sis-brand img').attributes('alt')).toContain('SIS')

  select.vm.$emit('update:modelValue', 3)
  select.vm.$emit('change', 3)
  await flushPromises()
  update.mockResolvedValue(aPatient({ seguro_id: 3 }))
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, { seguro_id: 3 })
  expect(wrapper.get('.patient-context__sis-brand img').attributes('alt')).toContain('EsSalud')
  await wrapper.setProps({ patient: aPatient({ seguro_id: 1 }) })
  expect(wrapper.get('.patient-context__sis-brand').text()).toBe('Sin seguro')
  expect(wrapper.find('.patient-context__sis-brand img').exists()).toBe(false)
})

test('abrir la ficha no rellena ni modifica los códigos de afiliación confirmados', async () => {
  const wrapper = await mountPanel(false, {
    establecimiento_registro_id: 2,
    seguro_id: 10,
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
  })

  const fields = wrapper.findAll('.sis-code input')
  expect(fields.map((field) => (field.element as HTMLInputElement).value)).toEqual(['', '', ''])
  expect(wrapper.text()).not.toContain('Tiene cambios sin guardar.')
})

test('cambiar de plan sugiere formato en el borrador, descartar lo restaura y guardar lo fija', async () => {
  const wrapper = await mountPanel(false, {
    establecimiento_registro_id: 2,
    seguro_id: 2,
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '00112233',
  })
  const insurance = wrapper.get('.patient-context__insurance-selector').getComponent(ElSelect)
  insurance.vm.$emit('update:modelValue', 10)
  insurance.vm.$emit('change', 10)
  await flushPromises()
  expect(wrapper.getComponent(PatientSisCodeFields).props('value')).toMatchObject({
    sis_diresa: '040',
    sis_tipo: 'R',
    sis_numero: '00112233',
  })
  expect(update).not.toHaveBeenCalled()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === 'Descartar cambios')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.getComponent(PatientSisCodeFields).props('value').sis_tipo).toBe('2')
  expect(insurance.props('modelValue')).toBe(2)
  insurance.vm.$emit('update:modelValue', 10)
  insurance.vm.$emit('change', 10)
  await flushPromises()
  update.mockResolvedValue(
    aPatient({
      establecimiento_registro_id: 2,
      seguro_id: 10,
      sis_diresa: '040',
      sis_tipo: 'R',
      sis_numero: '00112233',
    }),
  )
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, { seguro_id: 10, sis_tipo: 'R' })
})

test('guarda los códigos de la acreditación ingresados junto al número SIS', async () => {
  const wrapper = await mountPanel(false, {
    establecimiento_registro_id: 2,
    seguro_id: 10,
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
  })
  wrapper
    .getComponent(PatientSisCodeFields)
    .vm.$emit('update', { sis_diresa: '039', sis_tipo: '2', sis_numero: '00112233' })
  await flushPromises()

  update.mockResolvedValue(
    aPatient({
      establecimiento_registro_id: 2,
      seguro_id: 10,
      sis_diresa: '039',
      sis_tipo: '2',
      sis_numero: '00112233',
    }),
  )
  await wrapper.find('form').trigger('submit')
  await flushPromises()

  expect(update).toHaveBeenCalledWith(100, {
    sis_diresa: '039',
    sis_tipo: '2',
    sis_numero: '00112233',
  })
})

test('Historia familiar permite elegir un código reutilizable y lo guarda por PATCH', async () => {
  historiasFamiliares.mockResolvedValue({
    items: [
      {
        codigo: 'VC',
        nombre: 'VERDE CLARO',
        tipo: 'COLOR',
        color_hex: '#86C766',
        activo: true,
      },
    ],
    total: 1,
    limit: 25,
    offset: 0,
    has_more: false,
  })
  const wrapper = await mountPanel(false)
  const familyField = wrapper.findAll('.el-form-item').find((field) => {
    const label = field.find('.el-form-item__label')
    return label.exists() && label.text() === 'Historia familiar'
  })

  expect(familyField).toBeDefined()
  const selector = familyField!.getComponent(FamilyHistorySelector)
  expect(selector.find('input[aria-label="Color o sector de historia familiar"]').exists()).toBe(
    true,
  )
  await selector.getComponent(ElSelect).get('.el-select__wrapper').trigger('click')
  await vi.waitFor(() => expect(document.body.textContent).toContain('VERDE CLARO'))

  selector.vm.$emit('update:modelValue', 'VC-0007')
  await flushPromises()
  update.mockResolvedValue(aPatient({ historia_familiar: 'VC-0007' }))
  await wrapper.find('form').trigger('submit')
  await flushPromises()

  expect(update).toHaveBeenCalledWith(100, { historia_familiar: 'VC-0007' })
})

afterEach(() => {
  vi.restoreAllMocks()
  while (mounted.length) mounted.pop()?.unmount()
})

// Montar el panel es costoso (Element Plus + catálogos), así que cada caso
// reutiliza el mismo montaje cambiando solo las props.
test(
  'el botón de eliminar solo aparece con permiso y paciente activo',
  { timeout: 30_000 },
  async () => {
    const wrapper = await mountPanel(true)
    expect(deleteButton(wrapper)).toBeTruthy()

    await wrapper.setProps({ canDelete: false })
    expect(deleteButton(wrapper)).toBeUndefined()

    await wrapper.setProps({ canDelete: true, patient: aPatient({ estado: false }) })
    expect(
      deleteButton(wrapper),
      'un paciente ya inactivo no se vuelve a dar de baja',
    ).toBeUndefined()
  },
)

test(
  'eliminar pide confirmación, da de baja al paciente y avisa a la vista',
  { timeout: 30_000 },
  async () => {
    // El tipo de Element Plus cruza la acción con su payload, así que se declara
    // solo lo que este test consume.
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as unknown as MessageBoxData)
    const wrapper = await mountPanel(true)

    const button = deleteButton(wrapper)!
    expect(button.classes()).toContain('el-button--danger')
    await button.trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledOnce()
    expect(deactivate).toHaveBeenCalledWith(100)
    expect(wrapper.emitted('removed')?.[0]?.[0]).toMatchObject({ id: 100 })
  },
)

test('cancelar la confirmación no da de baja a nadie', { timeout: 30_000 }, async () => {
  vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
  const wrapper = await mountPanel(true)

  await deleteButton(wrapper)!.trigger('click')
  await flushPromises()

  expect(deactivate).not.toHaveBeenCalled()
  expect(wrapper.emitted('removed')).toBeUndefined()
})

test(
  'Grupo etáreo edita la condición por PATCH sin duplicarla ni alterar otros datos',
  { timeout: 30_000 },
  async () => {
    const wrapper = await mountPanel(false, { condicion: 'NO GESTANTE' })
    expect(wrapper.find('.patient-relations__details').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Datos adicionales')
    expect(wrapper.text()).not.toContain('Historial de riesgos')
    expect(wrapper.text()).not.toContain('Responsables (')
    expect(wrapper.text()).not.toContain('Cada responsable y periodo')
    expect(wrapper.findAllComponents(PatientConditionSelect)).toHaveLength(1)
    const condition = wrapper.getComponent(PatientConditionSelect)
    expect(condition.props('modelValue')).toBe('NO GESTANTE')
    expect(condition.get('input[role="combobox"]').attributes('aria-label')).toBe('Grupo etáreo')
    expect(condition.props('disabled')).toBe(false)
    update.mockResolvedValue(aPatient({ condicion: 'GESTANTE' }))
    wrapper.getComponent(PatientConditionSelect).vm.$emit('update:modelValue', 'GESTANTE')
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(update).toHaveBeenCalledWith(100, { condicion: 'GESTANTE' })
    expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({ condicion: 'GESTANTE' })
    expect(wrapper.getComponent(PatientConditionSelect).props('modelValue')).toBe('GESTANTE')
  },
)

test(
  'Tipo documento queda entre Historia familiar y N.° documento y conserva el guardado',
  { timeout: 30_000 },
  async () => {
    const wrapper = await mountPanel(false)
    const documentRow = wrapper.get('.patient-context__form > .document-types').element
    expect(
      documentRow.previousElementSibling?.querySelector('.el-form-item__label')?.textContent,
    ).toBe('Historia familiar')
    expect(documentRow.nextElementSibling?.querySelector('.el-form-item__label')?.textContent).toBe(
      'N.° documento',
    )
    expect(wrapper.findAll('input[role="combobox"][aria-label="Tipo de documento"]')).toHaveLength(
      1,
    )
    expect(wrapper.find('.document-types input[type="radio"]').exists()).toBe(false)
    const documentSelect = wrapper.getComponent(AdmissionDocumentTypes).getComponent(ElSelect)
    expect(documentSelect.props('modelValue')).toBe('DNI')
    expect(wrapper.find('.patient-context__sis .sis-code--compact').exists()).toBe(true)
    expect(wrapper.get('.patient-context__actions').text()).toContain(
      'Datos del paciente guardados.',
    )
    update.mockResolvedValue(aPatient({ tipo_documento_codigo: 'CE' }))
    documentSelect.vm.$emit('update:modelValue', 'CE')
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(update).toHaveBeenCalledWith(100, {
      tipo_documento_codigo: 'CE',
      sis_tipo: '3',
      sis_numero: '12345678',
    })
    await wrapper.setProps({ blocked: true })
    expect(documentSelect.props('disabled')).toBe(true)
  },
)

test('editar DNI recalcula número SIS sin guardar y descartar restaura ambos', async () => {
  const wrapper = await mountPanel(false, {
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '12345678',
  })
  const document = wrapper.get('input[aria-label="N.° documento"]')
  await document.setValue('00112233')
  await flushPromises()
  expect(wrapper.getComponent(PatientSisCodeFields).props('value').sis_numero).toBe('00112233')
  expect(update).not.toHaveBeenCalled()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === 'Descartar cambios')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.getComponent(PatientSisCodeFields).props('value').sis_numero).toBe('12345678')
  await document.setValue('00112233')
  await flushPromises()
  update.mockResolvedValue(
    aPatient({
      numero_documento: '00112233',
      sis_diresa: '040',
      sis_tipo: '2',
      sis_numero: '00112233',
    }),
  )
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, { numero_documento: '00112233', sis_numero: '00112233' })
})

test('permite completar, descartar y guardar la etnia sin cambiar los demás datos', async () => {
  const wrapper = await mountPanel(false, { etnia_codigo: null })
  const row = wrapper.findAll('.el-form-item').find((field) => {
    const label = field.find('.el-form-item__label')
    return label.exists() && label.text() === 'Etnia'
  })!
  const select = row.getComponent(ElSelect)
  expect(row.element.previousElementSibling?.textContent).toContain('Grupo de riesgo')
  expect(row.element.nextElementSibling?.textContent).toContain('Nombre de madre')
  expect(select.props('modelValue')).toBeNull()
  expect(select.props('placeholder')).toBe('Sin declarar')
  expect(select.findAllComponents(ElOption).map((item) => item.props('label'))).toContain(
    '58 · Mestizo',
  )
  select.vm.$emit('update:modelValue', '58')
  await flushPromises()
  expect(update).not.toHaveBeenCalled()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === 'Descartar cambios')!
    .trigger('click')
  expect(select.props('modelValue')).toBeNull()

  select.vm.$emit('update:modelValue', '58')
  await flushPromises()
  update.mockResolvedValue(aPatient({ etnia_codigo: '58' }))
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, { etnia_codigo: '58' })
  expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({ etnia_codigo: '58' })
  expect(select.props('modelValue')).toBe('58')

  select.vm.$emit('update:modelValue', null)
  await flushPromises()
  update.mockResolvedValue(aPatient({ etnia_codigo: null }))
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenLastCalledWith(100, { etnia_codigo: null })
})

test('la etnia conserva códigos existentes y respeta bloqueos y permisos', async () => {
  const wrapper = await mountPanel(false, { etnia_codigo: '99' })
  const row = wrapper.findAll('.el-form-item').find((field) => {
    const label = field.find('.el-form-item__label')
    return label.exists() && label.text() === 'Etnia'
  })!
  const select = row.getComponent(ElSelect)
  expect(select.props('modelValue')).toBe('99')
  expect(select.findAllComponents(ElOption).map((item) => item.props('label'))).toContain(
    'Código 99',
  )
  expect(update).not.toHaveBeenCalled()
  await wrapper.setProps({ blocked: true })
  expect(select.props('disabled')).toBe(true)
  await wrapper.setProps({ blocked: false, canEdit: false })
  expect(select.props('disabled')).toBe(true)
  await wrapper.setProps({ canEdit: true, patient: aPatient({ estado: false }) })
  expect(select.props('disabled')).toBe(true)
})

// El panel reúne grupo de riesgo, etnia, nombre de madre y grupo etario, en ese orden.
test(
  'el panel muestra grupo de riesgo, nombre de madre y grupo etáreo',
  { timeout: 30_000 },
  async () => {
    const wrapper = await mountPanel(false)
    const text = wrapper.text()

    expect(text).toContain('Grupo de riesgo')
    expect(text).toContain('Nombre de madre')
    expect(text).toContain('Grupo etáreo')
    expect(text.indexOf('Grupo de riesgo')).toBeLessThan(text.indexOf('Nombre de madre'))
    expect(text.indexOf('Nombre de madre')).toBeLessThan(text.indexOf('Grupo etáreo'))
  },
)
