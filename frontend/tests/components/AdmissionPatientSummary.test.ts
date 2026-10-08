import { flushPromises, mount } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus, { ElMessageBox, ElSelect, type MessageBoxData } from 'element-plus'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import AdmissionPatientSummary from '@/components/admission/AdmissionPatientSummary.vue'
import AdmissionDocumentTypes from '@/components/admission/AdmissionDocumentTypes.vue'
import PatientConditionSelect from '@/components/patients/PatientConditionSelect.vue'
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
    ]),
    etnias: vi.fn(async () => []),
    historiasFamiliares,
    establecimientos: vi.fn(async () => emptyPage),
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
  const wrapper = await mountPanel(false, { seguro_id: 2, sis_diresa: '040', sis_tipo: '2', sis_numero: '00112233', sis_secuencia: '01', etnia_codigo: '58' })
  const select = wrapper.get('.patient-context__insurance-selector').getComponent(ElSelect)
  select.vm.$emit('update:modelValue', 1)
  select.vm.$emit('change', 1)
  await flushPromises()
  update.mockResolvedValue(aPatient({ seguro_id: 1, sis_diresa: null, sis_tipo: null, sis_numero: null, sis_secuencia: null, etnia_codigo: '58' }))
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(100, { seguro_id: 1, sis_diresa: null, sis_tipo: null, sis_numero: null, sis_secuencia: null })
  expect(wrapper.findAll('.sis-code input').every((input) => input.attributes('disabled') !== undefined)).toBe(true)
})

test('no expone el código técnico ETLSIS en el formulario', async () => {
  const wrapper = await mountPanel(false, { seguro_id: 2 })
  expect(wrapper.find('.patient-context__insurance-code').exists()).toBe(false)
})

test('Historia familiar permite elegir un código reutilizable y lo guarda por PATCH', async () => {
  historiasFamiliares.mockResolvedValue({
    items: [{ codigo: 'HF-VERDE-01' }],
    total: 1,
    limit: 25,
    offset: 0,
    has_more: false,
  })
  const wrapper = await mountPanel(false)
  const familyField = wrapper
    .findAll('.el-form-item')
    .find((field) => field.find('label').text() === 'Historia familiar')

  expect(familyField).toBeDefined()
  const selector = familyField!.getComponent(ElSelect)
  expect(selector.find('input[aria-label="Historia familiar"]').exists()).toBe(true)
  // Las opciones del catálogo viven en el desplegable teleportado: se abre para comprobarlas.
  await selector.get('.el-select__wrapper').trigger('click')
  await vi.waitFor(() => expect(document.body.textContent).toContain('HF-VERDE-01'))

  selector.vm.$emit('update:modelValue', 'HF-VERDE-01')
  await flushPromises()
  update.mockResolvedValue(aPatient({ historia_familiar: 'HF-VERDE-01' }))
  await wrapper.find('form').trigger('submit')
  await flushPromises()

  expect(update).toHaveBeenCalledWith(100, { historia_familiar: 'HF-VERDE-01' })
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
    expect(documentRow.previousElementSibling?.querySelector('label')?.textContent).toBe(
      'Historia familiar',
    )
    expect(documentRow.nextElementSibling?.querySelector('label')?.textContent).toBe(
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
    expect(update).toHaveBeenCalledWith(100, { tipo_documento_codigo: 'CE' })
    await wrapper.setProps({ blocked: true })
    expect(documentSelect.props('disabled')).toBe(true)
  },
)

// El panel reúne grupo de riesgo, nombre de madre y grupo etario, en ese orden.
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
