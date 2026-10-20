import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { expect, test } from 'vitest'
import LaboratoryEncounterReview from '@/components/laboratory/LaboratoryEncounterReview.vue'
import type { Attention } from '@/services/atenciones'

test('muestra el documento guardado y pide reimpresión sin emitir una atención', async () => {
  const wrapper = mount(LaboratoryEncounterReview, {
    props: {
      modelValue: true, loading: false, error: '', printing: false, sisReady: true,
      attention: {
        id: 41, estado: 'ATENDIDO', numero_referencia_ingreso: '001565',
        numero_contrarreferencia_ingreso: '00007',
        fua_impresion: { apellido_paterno: 'HISTORICO', primer_nombre: 'PACIENTE', referencia_nombre: 'ORIGEN GUARDADO', referencia_renipress: '00001234' },
      } as Attention,
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('001565')
  expect(wrapper.text()).toContain('00007')
  expect(wrapper.text()).toContain('ORIGEN GUARDADO')
  await wrapper.findAll('button').find((button) => button.text() === 'Imprimir FUA guardado')!.trigger('click')
  expect(wrapper.emitted('print')).toEqual([[]])
  await wrapper.setProps({ attention: null, loading: true, sisReady: false })
  expect(wrapper.findAll('button').find((button) => button.text() === 'Imprimir FUA guardado')!.attributes('disabled')).toBeDefined()
  wrapper.unmount()
})
