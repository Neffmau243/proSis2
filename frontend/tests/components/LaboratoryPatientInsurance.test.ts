import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { expect, test } from 'vitest'
import LaboratoryPatientPanel from '@/components/laboratory/LaboratoryPatientPanel.vue'
import { aPatient } from '../fixtures/patient'

test('laboratorio cambia la marca al recibir el seguro guardado y oculta afiliación SIS ajena', async () => {
  const wrapper = mount(LaboratoryPatientPanel, {
    props: {
      patient: aPatient({ seguro_id: 2 }),
      options: [],
      documentType: 'DNI',
      documents: [],
      sexes: [],
      insurances: [
        { id: 2, codigo: 'SIS', nombre: 'SIS', regimen: 'SIS', codigo_sis: null, activo: true },
        {
          id: 3,
          codigo: 'ESSALUD',
          nombre: 'EsSalud',
          regimen: 'ESSALUD',
          codigo_sis: '007',
          activo: true,
        },
      ],
      establishments: [],
      date: '2026-10-12',
      loading: false,
      disabled: false,
      error: '',
      searchHint: '',
    },
    global: { plugins: [ElementPlus] },
  })
  expect(wrapper.get('.lab-patient__sis-brand img').attributes('alt')).toContain('SIS')
  expect(wrapper.find('.sis-code').exists()).toBe(true)
  await wrapper.setProps({ patient: aPatient({ seguro_id: 3, sis_numero: '00112233' }) })
  expect(wrapper.get('.lab-patient__sis-brand img').attributes('alt')).toContain('EsSalud')
  expect(wrapper.find('.sis-code').exists()).toBe(false)
  expect(wrapper.find('.lab-patient__sequence').exists()).toBe(false)
  await wrapper.setProps({ patient: null })
  expect(wrapper.get('.lab-patient__sis-brand').text()).toBe('Sin registro')
  wrapper.unmount()
})
