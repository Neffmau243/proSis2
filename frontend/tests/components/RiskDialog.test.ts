import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElDatePicker, ElInput } from 'element-plus'
import { expect, test } from 'vitest'
import RiskDialog from '@/components/patient/RiskDialog.vue'
import RiskGroupSelect from '@/components/patient/RiskGroupSelect.vue'

test('una sugerencia abre el diálogo con grupo, fecha y motivo desde el primer render', async () => {
  const wrapper = mount(RiskDialog, {
    props: {
      modelValue: true,
      patientId: 100,
      riesgo: null,
      sourceAttentionId: 42,
      initialCode: 'NUT_HALLAZGO',
      initialReason: 'Delgadez grado II',
      initialDate: '2026-10-17',
      gruposRiesgo: [
        {
          id: 5,
          codigo: 'NUT_HALLAZGO',
          nombre: 'Seguimiento de hallazgo nutricional',
          activo: true,
          descripcion: null,
        },
      ],
    },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
  await flushPromises()
  expect(wrapper.getComponent(RiskGroupSelect).props('modelValue')).toBe(5)
  expect(wrapper.findAllComponents(ElDatePicker)[0]?.props('modelValue')).toBe('2026-10-17')
  expect(
    wrapper
      .findAllComponents(ElInput)
      .some((input) => input.props('modelValue') === 'Delgadez grado II'),
  ).toBe(true)
  await wrapper.setProps({ modelValue: false })
  await wrapper.setProps({ modelValue: true, initialReason: 'Motivo revisado' })
  await flushPromises()
  expect(
    wrapper
      .findAllComponents(ElInput)
      .some((input) => input.props('modelValue') === 'Motivo revisado'),
  ).toBe(true)
  wrapper.unmount()
})
