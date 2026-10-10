import { mount } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { expect, test } from 'vitest'

import FamilyHistorySelector from '@/components/patients/FamilyHistorySelector.vue'

const options = [
  {
    codigo: 'AM',
    nombre: 'AMARILLO',
    tipo: 'COLOR' as const,
    color_hex: '#F2C94C',
    activo: true,
  },
  {
    codigo: 'AP',
    nombre: 'APURÍMAC',
    tipo: 'SECTOR' as const,
    color_hex: null,
    activo: true,
  },
]

test('compone prefijo y número sin perder ceros iniciales', async () => {
  const wrapper = mount(FamilyHistorySelector, {
    props: { modelValue: null, options },
    global: { plugins: [ElementPlus] },
  })

  wrapper.getComponent(ElSelect).vm.$emit('update:modelValue', 'AM')
  await wrapper.setProps({ modelValue: 'AM-' })
  await wrapper.get('input[aria-label="Número de historia familiar"]').setValue('00042')

  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['AM-00042'])
})

test('muestra un valor legado sin modificarlo automáticamente', () => {
  const wrapper = mount(FamilyHistorySelector, {
    props: { modelValue: 'HF-ANTIGUA-9', options },
    global: { plugins: [ElementPlus] },
  })

  expect(wrapper.text()).toContain('Valor anterior: HF-ANTIGUA-9')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
})
