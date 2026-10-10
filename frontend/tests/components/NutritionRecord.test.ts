import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { expect, test, vi } from 'vitest'
import NutritionRecordSummary from '@/components/admission/NutritionRecordSummary.vue'
import NutritionExportPanel from '@/components/admission/NutritionExportPanel.vue'
import type { NutritionRecord } from '@/types/nutritionRecord'
import type { Attention } from '@/services/atenciones'

const { confirmNutritionSent, exportNutrition } = vi.hoisted(() => ({
  confirmNutritionSent: vi.fn(),
  exportNutrition: vi.fn(),
}))
vi.mock('@/services/atenciones', () => ({ atenciones: { confirmNutritionSent, exportNutrition } }))

test('el resumen histórico muestra No y cero en vez de esconderlos', () => {
  const wrapper = mount(NutritionRecordSummary, {
    props: {
      records: [
        {
          id: 1,
          tipo: 'NINO',
          juntos: false,
          nro_sachets: 0,
          hemoglobina: '12.00',
          grado: '2',
          whz: '0.000',
        } as NutritionRecord,
      ],
    },
  })
  expect(wrapper.text()).toContain('No')
  expect(wrapper.text()).toContain('0.000')
  expect(wrapper.text()).toContain('12.00')
  expect(wrapper.text()).toContain('Grado')
  wrapper.unmount()
})

test('el historial prioriza la tabla calculada del grupo guardado', () => {
  const wrapper = mount(NutritionRecordSummary, {
    props: {
      records: [{ id: 2, tipo: 'GESTANTE', imc: '25.000' } as NutritionRecord],
      indicatorRows: [
        { key: 'imc', label: 'IMC', value: '21.484' },
        { key: 'diagnostico_imc', label: 'Dx IMC', value: 'Normal' },
        { key: 'ganancia_peso', label: 'Ganancia de peso', value: '10 kg' },
      ],
    },
  })
  expect(wrapper.findAll('.nutrition-table th').map((cell) => cell.text())).toEqual([
    'IMC',
    'Dx IMC',
    'Ganancia de peso',
  ])
  expect(wrapper.find('.nutrition-table').text()).toContain('21.484')
  wrapper.unmount()
})

test('la constancia requiere exportación y maneja el error sin anunciar éxito', async () => {
  const attention = {
    id: 5,
    estado: 'ATENDIDO',
    contexto_clinico: {},
    evaluaciones_nutricionales: [{ id: 2, estado_exportacion: 'PENDIENTE' }],
  } as Attention
  const wrapper = mount(NutritionExportPanel, {
    props: { attention, canManage: true },
    global: { plugins: [ElementPlus] },
  })
  expect(wrapper.find('#nutrition-receipt').exists()).toBe(false)
  await wrapper.setProps({
    attention: {
      ...attention,
      evaluaciones_nutricionales: [{ id: 2, estado_exportacion: 'EXPORTADO' } as NutritionRecord],
    },
  })
  await wrapper.get('#nutrition-receipt').setValue('CONSTANCIA-PRUEBA')
  confirmNutritionSent.mockRejectedValueOnce(new Error('No se pudo registrar'))
  await wrapper
    .findAll('button')
    .find((b) => b.text().includes('Registrar constancia'))!
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('No se pudo registrar')
  expect(wrapper.emitted('updated')).toBeUndefined()
  confirmNutritionSent.mockResolvedValueOnce({
    ...attention,
    evaluaciones_nutricionales: [
      { id: 2, estado_exportacion: 'ENVIADO', constancia_envio: 'CONSTANCIA-PRUEBA' },
    ],
  })
  await wrapper
    .findAll('button')
    .find((b) => b.text().includes('Registrar constancia'))!
    .trigger('click')
  await flushPromises()
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
