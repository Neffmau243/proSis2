import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import PatientInsuranceBrand from '@/components/patients/PatientInsuranceBrand.vue'

test('resuelve por código o régimen, incluso con IDs distintos y planes SIS históricos', async () => {
  const wrapper = mount(PatientInsuranceBrand)
  expect(wrapper.text()).toBe('Sin registro')
  await wrapper.setProps({ insuranceId: 99 })
  expect(wrapper.text()).toBe('Seguro')
  for (const codigo of [
    'SIS',
    'SIS_GRATUITO',
    'SIS_PARA_TODOS',
    'SIS_AFILIACION_TEMPORAL',
    'SIS_SEMI_SUBSIDIADO',
    'SIS_NRUS',
  ]) {
    await wrapper.setProps({ insurance: { id: 99, codigo, nombre: codigo, activo: true } })
    expect(wrapper.get('img').attributes('alt')).toContain('Seguro Integral de Salud')
  }
  await wrapper.setProps({
    insurance: {
      id: 99,
      codigo: 'PLAN_LOCAL',
      regimen: 'ESSALUD',
      nombre: 'EsSalud',
      activo: true,
    },
  })
  expect(wrapper.get('img').attributes('alt')).toContain('EsSalud')
  await wrapper.get('img').trigger('error')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.text()).toContain('EsSalud')
  await wrapper.setProps({ insurance: { id: 99, codigo: 'SIS', nombre: 'SIS', activo: true } })
  expect(wrapper.find('img').exists()).toBe(true)
  wrapper.unmount()
})

test.each([
  ['SIN_SEGURO', 'NINGUNO', 'Sin seguro'],
  ['SANIDAD', 'SANIDAD', 'Sanidad'],
  ['PARTICULAR', 'PARTICULAR', 'Particular'],
  ['OTRO', 'OTRO', 'Otro seguro'],
  ['CUSTOM', null, 'Plan de prueba'],
])('no atribuye una aseguradora a %s', (codigo, regimen, label) => {
  const wrapper = mount(PatientInsuranceBrand, {
    props: { insurance: { id: 99, codigo, regimen, nombre: 'Plan de prueba', activo: true } },
  })
  expect(wrapper.text()).toBe(label)
  expect(wrapper.find('img').exists()).toBe(false)
  wrapper.unmount()
})
