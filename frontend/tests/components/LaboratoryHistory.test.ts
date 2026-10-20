import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElPagination } from 'element-plus'
import { expect, test } from 'vitest'
import LaboratoryHistory from '@/components/laboratory/LaboratoryHistory.vue'
import type { Attention } from '@/services/atenciones'
import { aPatient } from '../fixtures/patient'

test('separa los nombres como la referencia y conserva la historia de la instantánea y diez registros', async () => {
  const wrapper = mount(LaboratoryHistory, {
    props: {
      entries: [
        {
          id: 900,
          fecha_atencion: '2026-10-12T09:00:00',
          estado: 'ATENDIDO',
          historia_clinica_snapshot: 'HC-HISTORICA',
          numero_referencia_ingreso: '001565',
          numero_contrarreferencia_ingreso: '00007',
        } as Attention,
      ],
      patient: aPatient({ historia_clinica: 'HC-ACTUAL', apellido_materno: 'Visual' }),
      loading: false,
      error: '',
      total: 11,
      page: 1,
      canRead: true,
      hasOffice: true,
    },
    global: { plugins: [ElementPlus], stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
  await flushPromises()
  expect(wrapper.findAll('thead th .cell').map((cell) => cell.text())).toEqual([
    'N° historia',
    'N° DNI',
    'F. atención',
    'Apellido pat.',
    'Apellido mat.',
    'Primer nombre',
    'Otros nombres',
    'Ref. recibida',
    'Contrarref. recibida',
  ])
  const row = wrapper.get('tbody tr').text()
  expect(row).toContain('HC-HISTORICA')
  expect(row).not.toContain('HC-ACTUAL')
  expect(row).toContain('12345678')
  expect(row).toContain('Prueba')
  expect(row).toContain('Visual')
  expect(row).toContain('Paciente')
  expect(row).toContain('001565')
  expect(row).toContain('00007')
  expect(wrapper.get('.lab-history__status').text()).toContain('ATENDIDO')
  expect(wrapper.get('.lab-history__status').text()).toContain('Ver #900')
  await wrapper.get('.lab-history__footer button').trigger('click')
  expect(wrapper.emitted('open')?.[0]?.[0]).toMatchObject({ id: 900 })
  const pagination = wrapper.getComponent(ElPagination)
  expect(pagination.props('pageSize')).toBe(10)
  pagination.vm.$emit('update:current-page', 2)
  expect(wrapper.emitted('page')).toEqual([[2]])
  wrapper.unmount()
})
