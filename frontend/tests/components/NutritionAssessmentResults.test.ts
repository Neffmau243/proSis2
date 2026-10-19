import { flushPromises, mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import NutritionAssessmentResults from '@/components/admission/NutritionAssessmentResults.vue'
import type { NutritionalIndicatorsPreview } from '@/services/atenciones'

const adult: NutritionalIndicatorsPreview = {
  grupo_referencia: 'ADULTO',
  imc: '24.691',
  diagnostico_imc: 'Normal',
  pe: null,
  te: null,
  pt: null,
  estado: 'CALCULADO',
  referencia: 'OMS IMC adulto',
  mensaje: '',
}
const defaults = {
  careGroup: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES' as const,
  referenceGroup: 'ADULTO' as const,
  ageMonths: 274,
  result: adult,
  loading: false,
  error: null,
}
const labels = (wrapper: ReturnType<typeof mount>) =>
  wrapper.findAll('.nutrition-results__diagnosis-label, th').map((cell) => cell.text())
const values = (wrapper: ReturnType<typeof mount>) =>
  wrapper
    .findAll('.nutrition-results__diagnosis-value input, td')
    .map((cell) => (cell.element instanceof HTMLInputElement ? cell.element.value : cell.text()))

test('la valoración adulta presenta resultados de solo lectura y etiquetas accesibles', async () => {
  const wrapper = mount(NutritionAssessmentResults, { props: defaults })
  await flushPromises()
  expect(wrapper.get('.nutrition-results__diagnosis-title').text()).toBe('VALORACIÓN')
  expect(wrapper.find('table').exists()).toBe(false)
  for (const label of ['IMC', 'Dx IMC']) {
    const input = wrapper.get(`input[aria-label="Diagnóstico ${label}"]`)
    expect(input.attributes('readonly')).toBeDefined()
    expect(wrapper.get(`label[for="${input.attributes('id')}"]`).text()).toBe(label)
  }
  wrapper.unmount()
})

test.each(['ADULTO', 'ADULTO_MAYOR'] as const)(
  'la valoración de %s muestra IMC y clasificación aplicable',
  (referenceGroup) => {
    const wrapper = mount(NutritionAssessmentResults, {
      props: {
        ...defaults,
        referenceGroup,
        result: { ...adult, grupo_referencia: referenceGroup },
      },
    })
    expect(labels(wrapper)).toEqual(['IMC', 'Dx IMC'])
    expect(values(wrapper)).toEqual(['24.691', 'Normal'])
    wrapper.unmount()
  },
)

test('la vista infantil conserva las clasificaciones y los puntajes calculados', () => {
  const wrapper = mount(NutritionAssessmentResults, {
    props: {
      ...defaults,
      referenceGroup: 'INFANTIL',
      ageMonths: 24,
      result: {
        ...adult,
        grupo_referencia: 'INFANTIL',
        pe: '-0.250',
        te: '-0.500',
        pt: '0.125',
        diagnostico_peso_edad: 'Normal',
        diagnostico_talla_edad: 'Normal',
        diagnostico_peso_talla: 'Normal',
        diagnostico_imc: null,
      },
    },
  })
  expect(labels(wrapper)).toEqual(['P/E', 'T/E', 'P/T'])
  expect(values(wrapper)).toEqual(['Normal · Z: -0.250', 'Normal · Z: -0.500', 'Normal · Z: 0.125'])
  wrapper.unmount()
})

test('un adolescente muestra T/E e IMC/edad sin extrapolar P/E ni P/T', () => {
  const wrapper = mount(NutritionAssessmentResults, {
    props: {
      ...defaults,
      referenceGroup: 'ESCOLAR',
      ageMonths: 180,
      result: { ...adult, grupo_referencia: 'ESCOLAR', te: '-0.500', imc_edad: '0.750' },
    },
  })
  expect(labels(wrapper)).toEqual(['IMC/edad', 'T/E'])
  expect(values(wrapper)).toEqual(['Normal · Z: 0.750', 'Z: -0.500'])
  wrapper.unmount()
})

test('cambiar el grupo de atención selecciona tres vistas distintas', async () => {
  const wrapper = mount(NutritionAssessmentResults, { props: defaults })
  expect(labels(wrapper)).toEqual(['IMC', 'Dx IMC'])
  await wrapper.setProps({
    careGroup: 'GESTANTES',
    referenceGroup: 'GESTANTE',
    result: {
      ...adult,
      grupo_referencia: 'GESTANTE',
      imc_pregestacional: '21.5',
      ganancia_peso_kg: '8',
    },
  })
  expect(labels(wrapper)).toEqual(['IMC', 'Dx IMC', 'Ganancia de peso'])
  expect(values(wrapper)).toEqual(['21.5', 'Normal', '8 kg'])
  await wrapper.setProps({ careGroup: 'PUERPERAS', referenceGroup: 'PUERPERA' })
  expect(labels(wrapper)).toEqual(['IMC', 'Dx IMC'])
  expect(wrapper.find('.nutrition-results__bmi').exists()).toBe(false)
  wrapper.unmount()
})

test('la carga y el error distinguen faltantes de indicadores no aplicables', async () => {
  const wrapper = mount(NutritionAssessmentResults, {
    props: { ...defaults, referenceGroup: 'ESCOLAR', ageMonths: 180, result: null, loading: true },
  })
  expect(values(wrapper)).toEqual(['Calculando…', 'Calculando…'])
  await wrapper.setProps({ loading: false, error: 'No se pudo calcular la valoración.' })
  expect(values(wrapper)).toEqual(['No disponible', 'No disponible'])
  expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo calcular la valoración.')
  expect(wrapper.text()).not.toContain('Normal')
  wrapper.unmount()
})
