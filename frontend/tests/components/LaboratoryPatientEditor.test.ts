import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus, { ElSelect } from 'element-plus'
import { beforeEach, expect, test, vi } from 'vitest'
import LaboratoryPatientPanel from '@/components/laboratory/LaboratoryPatientPanel.vue'
import { aPatient } from '../fixtures/patient'
import type { Patient } from '@/services/pacientes'

const api = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('@/services/pacientes', () => ({ pacientes: { update: api.update } }))
beforeEach(() => vi.resetAllMocks())

function setup(canEdit = true) {
  const patient = aPatient({
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '00112233',
    sis_secuencia: '01',
    etnia_codigo: '58',
  })
  const wrapper = mount(LaboratoryPatientPanel, {
    props: {
      patient,
      options: [patient],
      documentType: 'DNI',
      documents: [
        { codigo: 'DNI', nombre: 'DNI', activo: true },
        { codigo: 'CE', nombre: 'Carné de extranjería', activo: true },
      ],
      sexes: [
        { codigo: 'F', nombre: 'Femenino', activo: true },
        { codigo: 'M', nombre: 'Masculino', activo: true },
      ],
      establishments: [
        {
          id: 1,
          nombre: 'Centro 1',
          activo: true,
          codigo_renaes: null,
          codigo_ideess: null,
          disa_codigo: null,
          abreviatura: null,
        },
        {
          id: 3,
          nombre: 'Centro 3',
          activo: true,
          codigo_renaes: null,
          codigo_ideess: null,
          disa_codigo: null,
          abreviatura: null,
        },
      ],
      insurances: [
        { id: 2, codigo: 'SIS', nombre: 'SIS', regimen: 'SIS', codigo_sis: null, activo: true },
        {
          id: 1,
          codigo: 'SIN_SEGURO',
          nombre: 'Sin seguro',
          regimen: 'NINGUNO',
          codigo_sis: null,
          activo: true,
        },
      ],
      date: '2026-10-12T09:00:00',
      loading: false,
      disabled: false,
      canEdit,
      error: '',
      searchHint: '',
      onSaved: (value: Patient) => void wrapper.setProps({ patient: value }),
    },
    global: { plugins: [ElementPlus] },
  })
  let confirmed = patient
  api.update.mockImplementation(async (_id, patch) => {
    confirmed = { ...confirmed, ...patch }
    return confirmed
  })
  const select = (label: string) =>
    wrapper
      .findAllComponents(ElSelect)
      .find((item) => item.find(`input[aria-label="${label}"]`).exists())!
  const save = async () => {
    await wrapper.get('form').trigger('submit')
    await flushPromises()
  }
  return { wrapper, patient, select, save }
}

test('edita la ficha con un PATCH explícito, conserva ceros y actualiza la fuente confirmada', async () => {
  const { wrapper, patient, select, save } = setup()
  await wrapper.get('input[aria-label="N.° documento del paciente"]').setValue('01234567')
  await wrapper.get('input[aria-label="N.° historia clínica"]').setValue('00004')
  await wrapper.get('input[aria-label="Apellido paterno"]').setValue('Apellido corregido')
  await wrapper.get('input[aria-label="Primer nombre"]').setValue('Nombre corregido')
  await wrapper.get('input[aria-label="Secuencia SIS / N.º de hijo"]').setValue('02')
  select('Sexo').vm.$emit('update:modelValue', 'M')
  select('Establecimiento de registro').vm.$emit('update:modelValue', 3)
  await nextTick()
  expect(api.update).not.toHaveBeenCalled()
  expect(patient.numero_documento).toBe('12345678')
  expect(wrapper.emitted('dirtyChange')?.at(-1)).toEqual([true])
  expect(wrapper.get('input[aria-label="Buscar paciente"]').attributes('disabled')).toBeDefined()
  await save()
  expect(api.update).toHaveBeenCalledTimes(1)
  expect(api.update).toHaveBeenCalledWith(patient.id, {
    numero_documento: '01234567',
    historia_clinica: '00004',
    apellido_paterno: 'Apellido corregido',
    primer_nombre: 'Nombre corregido',
    sis_secuencia: '02',
    sexo_codigo: 'M',
    establecimiento_registro_id: 3,
  })
  expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({ numero_documento: '01234567' })
  expect(wrapper.emitted('dirtyChange')?.at(-1)).toEqual([false])
  wrapper.unmount()
})

test('Sin seguro limpia la afiliación, permite descartar y guarda sin modificar la etnia', async () => {
  const { wrapper, select, save } = setup()
  select('Seguro registrado').vm.$emit('update:modelValue', 1)
  await nextTick()
  expect(wrapper.get('.lab-patient__sis-brand').text()).toBe('Sin seguro')
  expect(wrapper.find('.sis-code').exists()).toBe(false)
  expect(wrapper.find('.lab-patient__sequence').exists()).toBe(false)
  expect(wrapper.get('.lab-patient__insurance-hint').text()).toContain('Sin seguro')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Descartar')!
    .trigger('click')
  expect(wrapper.find('.sis-code').exists()).toBe(true)
  expect(api.update).not.toHaveBeenCalled()
  select('Seguro registrado').vm.$emit('update:modelValue', 1)
  await nextTick()
  await save()
  expect(api.update).toHaveBeenCalledWith(100, {
    seguro_id: 1,
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
    sis_secuencia: null,
  })
  select('Seguro registrado').vm.$emit('update:modelValue', undefined)
  await nextTick()
  expect(wrapper.get('.lab-patient__sis-brand').text()).toBe('Sin registro')
  expect(wrapper.get('.lab-patient__insurance-hint').text()).toContain('Seguro sin registrar')
  await save()
  expect(api.update).toHaveBeenLastCalledWith(100, { seguro_id: null })
  wrapper.unmount()
})

test('valida antes de guardar y conserva el borrador tras un fallo para reintentar', async () => {
  const { wrapper, save } = setup()
  await wrapper.get('input[aria-label="N.° documento del paciente"]').setValue('12')
  await save()
  expect(api.update).not.toHaveBeenCalled()
  expect(
    wrapper.get('input[aria-label="N.° documento del paciente"]').attributes('aria-invalid'),
  ).toBe('true')
  await wrapper.get('input[aria-label="N.° documento del paciente"]').setValue('87654321')
  api.update.mockRejectedValueOnce(new Error('Sin conexión'))
  await save()
  expect(wrapper.text()).toContain('Sin conexión')
  expect(wrapper.get('input[aria-label="N.° documento del paciente"]').element).toHaveProperty(
    'value',
    '87654321',
  )
  await save()
  expect(api.update).toHaveBeenCalledTimes(2)
  wrapper.unmount()
})

test('respeta permiso, bloqueo de atención guardada y ausencia de paciente', async () => {
  const { wrapper, save } = setup(false)
  expect(wrapper.get('input[aria-label="Primer nombre"]').attributes('readonly')).toBeDefined()
  await save()
  expect(api.update).not.toHaveBeenCalled()
  await wrapper.setProps({ canEdit: true, disabled: true })
  expect(wrapper.get('input[aria-label="Primer nombre"]').attributes('readonly')).toBeDefined()
  await wrapper.setProps({ patient: null, disabled: false })
  await save()
  expect(api.update).not.toHaveBeenCalled()
  expect(wrapper.get('.lab-patient__sis-brand').text()).toBe('Sin registro')
  wrapper.unmount()
})
