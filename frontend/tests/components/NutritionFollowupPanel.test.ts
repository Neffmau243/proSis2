import { flushPromises, mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import NutritionFollowupPanel from '@/components/admission/NutritionFollowupPanel.vue'
import RiskDialog from '@/components/patient/RiskDialog.vue'
import { aPatient } from '../fixtures/patient'
import type { Attention, NutritionalIndicatorsPreview } from '@/services/atenciones'

const result: NutritionalIndicatorsPreview = {
  imc: '16.327',
  pe: null,
  te: null,
  pt: null,
  estado: 'CALCULADO',
  mensaje: '',
  referencia: 'MINSA',
  seguimiento: {
    version: '1',
    mensaje: 'Requiere confirmación profesional.',
    tamizaje: 'NO_EVALUADO',
    tendencia: { estado: 'NO_APLICA', mensaje: '' },
    sugerencias: [
      {
        codigo: 'NUT_HALLAZGO',
        motivo: 'Delgadez grado II',
        metodo: 'HALLAZGO_ANTROPOMETRICO',
        requiere_confirmacion: true,
      },
    ],
  },
}
const groups = [
  {
    id: 5,
    codigo: 'NUT_HALLAZGO',
    nombre: 'Seguimiento de hallazgo nutricional',
    activo: true,
    descripcion: null,
  },
]
const attention = { id: 42, fecha_atencion: '2026-10-17T10:00:00' } as Attention
const props = { result, patient: aPatient(), groups, canEdit: true }

test('la vista previa muestra la alerta y exige guardar antes de confirmarla', () => {
  const wrapper = mount(NutritionFollowupPanel, { props })
  expect(wrapper.text()).toContain('Delgadez grado II')
  expect(wrapper.text()).toContain('Guarde primero la atención')
  expect(wrapper.find('button').exists()).toBe(false)
  expect(wrapper.emitted('saved')).toBeUndefined()
  wrapper.unmount()
})

test('confirmar una atención guardada conserva su origen y solicita la decisión profesional', async () => {
  const wrapper = mount(NutritionFollowupPanel, {
    props: { ...props, attention },
    global: { stubs: { RiskDialog: true } },
  })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  const dialog = wrapper.getComponent(RiskDialog)
  expect(dialog.props('sourceAttentionId')).toBe(42)
  expect(dialog.props('initialCode')).toBe('NUT_HALLAZGO')
  expect(dialog.props('initialReason')).toBe('Delgadez grado II')
  expect(wrapper.emitted('saved')).toBeUndefined()
  wrapper.unmount()
})

test('un periodo que cubre el control impide duplicar el seguimiento sugerido', () => {
  const patient = aPatient({
    riesgos: [
      {
        grupo_riesgo_id: 5,
        fecha_inicio: '2026-10-01',
        fecha_fin: null,
        observacion: 'Evaluado',
        grupo_riesgo_codigo: 'NUT_HALLAZGO',
        grupo_riesgo_nombre: null,
      },
    ],
  })
  const wrapper = mount(NutritionFollowupPanel, { props: { ...props, patient, attention } })
  expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  expect(wrapper.text()).toContain('Seguimiento registrado')
  wrapper.unmount()
})
