import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus, { ElDatePicker, ElFormItem, ElInputNumber, ElSelect } from 'element-plus'
import { afterEach, expect, test, vi } from 'vitest'
import AtencionNuevaView from '@/views/AtencionNuevaView.vue'
import AdmissionPatientSummary from '@/components/admission/AdmissionPatientSummary.vue'
import AdmissionHistory from '@/components/admission/AdmissionHistory.vue'
import AdmissionEncounterHeader from '@/components/admission/AdmissionEncounterHeader.vue'
import NutritionFollowupPanel from '@/components/admission/NutritionFollowupPanel.vue'
import { aPatient } from '../fixtures/patient'

const { create, get, listByPatient, previewNutritionalIndicators } = vi.hoisted(() => ({
  previewNutritionalIndicators: vi.fn(async () => ({
    estado: 'DATOS_INCOMPLETOS',
    mensaje: 'Ingrese peso y talla',
    pe: null,
    te: null,
    pt: null,
  })),
  create: vi.fn(),
  get: vi.fn(),
  listByPatient: vi.fn(async () => []),
}))
vi.mock('@/services/pacientes', () => ({ pacientes: { get } }))
vi.mock('@/services/atenciones', () => ({
  atenciones: { create, listByPatient, previewNutritionalIndicators },
}))
vi.mock('@/services/catalogos', () => ({
  catalogos: {
    especialidades: async () => [
      { codigo: '001', nombre: 'MEDICINA' },
      { codigo: 'ESP_MEDICINA:003', nombre: 'PEDIATRIA' },
      { codigo: 'ESP_NUTRICION:001', nombre: 'CONSULTA NUTRICIONAL' },
    ],
    establecimientos: async () => ({ items: [{ id: 1, nombre: 'Sede de prueba' }] }),
    profesionales: async () => ({ items: [{ id: 2, nombre_completo: 'Profesional de prueba' }] }),
    consultorios: async () => ({
      items: [
        {
          id: 3,
          nombre: 'Consultorio de prueba',
          establecimiento_id: 1,
          codigo: 'MED',
          especialidad_codigo: '001',
          area_codigo: 'ESPECIALIDADES:003',
          area_nombre: 'Medicina',
          servicios_habilitados: [
            { codigo: '001', nombre: 'MEDICINA GENERAL', activo: true },
            { codigo: 'ESP_MEDICINA:003', nombre: 'PEDIATRIA', activo: true },
          ],
        },
      ],
    }),
    gruposEtarios: async () => [],
    tiposDocumento: async () => [],
    gruposRiesgo: async () => [],
  },
}))

const mounted: { unmount: () => void }[] = []

test('la edad y la valoración se actualizan con nacimiento y fecha de atención', async () => {
  const wrapper = await mountAdmission()
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  previewNutritionalIndicators.mockResolvedValueOnce({
    estado: 'CALCULADO',
    grupo_referencia: 'INFANTIL',
    mensaje: 'OMS 2006',
    imc: '16.799',
    pe: '-0.147',
    te: '-0.243',
    pt: '-0.056',
    diagnostico_peso_edad: 'Normal',
    diagnostico_talla_edad: 'Normal',
    diagnostico_peso_talla: 'Normal',
  } as never)
  wrapper
    .getComponent(AdmissionPatientSummary)
    .vm.$emit('saved', aPatient({ fecha_nacimiento: '2025-01-15' }))
  wrapper
    .getComponent(AdmissionEncounterHeader)
    .vm.$emit('update:modelValue', '2026-01-15T09:00:00')
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 9.5)
  field('Talla (cm)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 75.2)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  expect(wrapper.get('.nutrition-age__value').text()).toMatch(/^1 año/)
  expect(previewNutritionalIndicators).toHaveBeenLastCalledWith(
    expect.objectContaining({
      paciente_id: 100,
      fecha_atencion: '2026-01-15T09:00:00',
      peso_kg: 9.5,
      talla_cm: 75.2,
    }),
  )
  const rows = wrapper.findAll('.nutrition-results__diagnosis-row')
  expect(rows.map((row) => row.get('label').text())).toEqual(['P/E', 'T/E', 'P/T'])
  expect((rows[0]!.get('input').element as HTMLInputElement).value).toBe('Normal · Z: -0.147')
})

test('el adulto muestra IMC y diagnóstico en la valoración compacta', async () => {
  const wrapper = await mountAdmission()
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  previewNutritionalIndicators.mockResolvedValueOnce({
    estado: 'CALCULADO',
    grupo_referencia: 'ADULTO',
    imc: '24.691',
    diagnostico_imc: 'Normal',
    mensaje: 'Valoración por IMC; interpretar junto con la evaluación clínica.',
    pe: null,
    te: null,
    pt: null,
  } as never)
  for (const [label, value] of [
    ['Peso actual (kg)', '80'],
    ['Talla (cm)', '180'],
  ]) {
    const input = field(label!).get('input')
    ;(input.element as HTMLInputElement).value = value!
    await input.trigger('input')
  }
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  expect(previewNutritionalIndicators).toHaveBeenLastCalledWith(
    expect.objectContaining({ peso_kg: 80, talla_cm: 180 }),
  )
  expect(
    wrapper.findAll('.nutrition-results__diagnosis-row').map((row) => row.get('label').text()),
  ).toEqual(['IMC', 'Dx IMC'])
  expect(
    wrapper
      .findAll('.nutrition-results__diagnosis-row')
      .map((row) => (row.get('input').element as HTMLInputElement).value),
  ).toEqual(['24.691', 'Normal'])
  expect(wrapper.text()).not.toContain('Datos complementarios de nutrición')
  expect(wrapper.text()).not.toContain('Códigos del registro legado')
  const height = field('Talla (cm)').get('input')
  ;(height.element as HTMLInputElement).value = ''
  await height.trigger('input')
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  expect(wrapper.text()).not.toContain('24.691')
})

test('la gestante identifica el IMC pregestacional y su diagnóstico', async () => {
  const wrapper = await mountAdmission()
  await wrapper.get('input[value="GESTANTES"]').setValue(true)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  previewNutritionalIndicators.mockResolvedValueOnce({
    estado: 'CALCULADO',
    grupo_referencia: 'GESTANTE',
    imc: '25.391',
    imc_pregestacional: '22.491',
    ganancia_peso_kg: '10',
    diagnostico_imc: 'Normal',
    mensaje: 'Valoración materna',
    pe: null,
    te: null,
    pt: null,
  } as never)
  field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 68)
  field('Talla (cm)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 163)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const rows = wrapper.findAll('.nutrition-results__diagnosis-row')
  expect(rows.map((row) => row.get('label').text())).toEqual(['IMC', 'Dx IMC', 'Ganancia de peso'])
  expect(rows.map((row) => (row.get('input').element as HTMLInputElement).value)).toEqual([
    '22.491',
    'Normal',
    '10 kg',
  ])
})

test('la puérpera muestra solo IMC y Dx IMC', async () => {
  const wrapper = await mountAdmission()
  await wrapper.get('input[value="PUERPERAS"]').setValue(true)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  previewNutritionalIndicators.mockResolvedValueOnce({
    estado: 'CALCULADO',
    grupo_referencia: 'PUERPERA',
    imc: '25.000',
    imc_pregestacional: '21.484',
    ganancia_peso_kg: '9',
    diagnostico_imc: 'Normal',
    mensaje: 'Seguimiento puerperal',
    pe: null,
    te: null,
    pt: null,
  } as never)
  field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 64)
  field('Talla (cm)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 160)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const rows = wrapper.findAll('.nutrition-results__diagnosis-row')
  expect(rows.map((row) => row.get('label').text())).toEqual(['IMC', 'Dx IMC'])
  expect(rows.map((row) => (row.get('input').element as HTMLInputElement).value)).toEqual([
    '21.484',
    'Normal',
  ])
  expect(wrapper.get('.nutrition-results').text()).not.toContain('Ganancia de peso')
})

test('el escolar muestra IMC/edad y T/E en el panel compacto', async () => {
  const wrapper = await mountAdmission()
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  previewNutritionalIndicators.mockResolvedValueOnce({
    estado: 'CALCULADO',
    grupo_referencia: 'ESCOLAR',
    imc: '18.200',
    imc_edad: '1.250',
    diagnostico_imc: 'Sobrepeso',
    mensaje: 'OMS 2007',
    pe: null,
    te: '-0.500',
    pt: null,
  } as never)
  field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 42)
  field('Talla (cm)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 152)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  const rows = wrapper.findAll('.nutrition-results__diagnosis-row')
  expect(rows.map((row) => row.get('label').text())).toEqual(['IMC/edad', 'T/E'])
  expect(rows.map((row) => (row.get('input').element as HTMLInputElement).value)).toEqual([
    'Sobrepeso · Z: 1.250',
    'Z: -0.500',
  ])
})

test('la valoración muestra cálculos de solo lectura y descarta resultados al borrar medidas', async () => {
  const wrapper = await mountAdmission()
  wrapper
    .getComponent(AdmissionPatientSummary)
    .vm.$emit('saved', aPatient({ fecha_nacimiento: '2025-01-15' }))
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  previewNutritionalIndicators.mockResolvedValueOnce({
    estado: 'CALCULADO',
    mensaje: 'OMS 2006',
    pe: '-0.147',
    te: '-0.243',
    pt: '-0.056',
    diagnostico_peso_edad: 'Normal',
    diagnostico_talla_edad: 'Normal',
    diagnostico_peso_talla: 'Normal',
  } as never)
  field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 9.5)
  field('Talla (cm)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 75.2)
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  expect(
    (
      wrapper.findAll('.nutrition-results__diagnosis-row')[0]!.get('input')
        .element as HTMLInputElement
    ).value,
  ).toBe('Normal · Z: -0.147')
  field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', null)
  await flushPromises()
  expect(
    (
      wrapper.findAll('.nutrition-results__diagnosis-row')[0]!.get('input')
        .element as HTMLInputElement
    ).value,
  ).toBe('Calculando…')
  await new Promise((resolve) => setTimeout(resolve, 400))
  await flushPromises()
  expect(
    (
      wrapper.findAll('.nutrition-results__diagnosis-row')[0]!.get('input')
        .element as HTMLInputElement
    ).value,
  ).toBe('No disponible')
})
afterEach(() => {
  while (mounted.length) mounted.pop()?.unmount()
  vi.clearAllMocks()
})

async function mountAdmission() {
  get.mockResolvedValue(aPatient({ condicion: 'NO GESTANTE' }))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admision', component: AtencionNuevaView },
      { path: '/', name: 'inicio', component: { template: '<div />' } },
    ],
  })
  await router.push('/admision?patientId=100')
  await router.isReady()
  const wrapper = mount(AtencionNuevaView, {
    props: { admission: true },
    global: {
      plugins: [ElementPlus, createPinia(), router],
      stubs: { AdmissionPatientSummary: true, AdmissionHistory: true, FuaPrintDialog: true },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

test('referencia exige los tres campos y los envía con la modalidad al guardar', async () => {
  const wrapper = await mountAdmission()
  expect(wrapper.find('.referral-fields').exists()).toBe(false)
  await wrapper.get('input[value="REFERENCIA"]').setValue(true)
  expect(wrapper.find('.referral-fields').exists()).toBe(true)
  expect(wrapper.get('#encounter-context-title').text()).toBe('Referencia realizada por')
  expect(wrapper.findAllComponents(ElFormItem).some(item => item.props('prop') === 'consultorio_id')).toBe(false)
  expect(wrapper.findAllComponents(ElFormItem).some(item => item.props('prop') === 'profesional_id')).toBe(false)
  expect(wrapper.get('.clinical-section--context').findAll('.referral-fields input')).toHaveLength(3)
  const save = wrapper.findAll('button').find(button => button.text() === 'Guardar atención')!
  await save.trigger('click')
  await flushPromises()
  expect(create).not.toHaveBeenCalled()
  await vi.waitFor(() => expect(wrapper.text()).toContain('Indique el RENIPRESS de origen.'))
  await wrapper.get('input[aria-label="Código RENIPRESS de origen"]').setValue('123')
  await wrapper.get('input[aria-label="Nombre de la IPRESS de origen"]').setValue('Ipress origen')
  await wrapper.get('input[aria-label="N.º de hoja de referencia"]').setValue('ref-0001')
  await save.trigger('click')
  await flushPromises()
  expect(create).not.toHaveBeenCalled()
  await vi.waitFor(() => expect(wrapper.text()).toContain('El RENIPRESS debe tener 8 dígitos.'))
  await wrapper.get('input[aria-label="Código RENIPRESS de origen"]').setValue('00001234')
  create.mockImplementation(async payload => ({ ...payload, id: 502, fua_impresion: null }))
  await save.trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledOnce()
  expect(create.mock.calls[0]?.[0]).toMatchObject({
    modalidad_atencion_codigo: 'REFERENCIA',
    consultorio_id: null, profesional_id: null, especialidad_codigo: null,
    fua_datos: {
      tipo_atencion: 'REFERENCIA', referencia_renipress: '00001234',
      referencia_nombre: 'IPRESS ORIGEN', referencia_hoja: 'REF-0001',
    },
  })
})

test.each(['AMBULATORIA', 'EMERGENCIA'])(
  'cambiar de referencia a %s limpia el origen y permite guardar sin esos datos', async mode => {
    const wrapper = await mountAdmission()
    const field = (label: string) =>
      wrapper.findAllComponents(ElFormItem).find(item => item.props('label') === label)!
    field('Consultorio').getComponent(ElSelect).vm.$emit('update:modelValue', 3)
    await flushPromises()
    field('Profesional').getComponent(ElSelect).vm.$emit('update:modelValue', 2)
    await wrapper.get('input[value="REFERENCIA"]').setValue(true)
    for (const input of wrapper.findAll('.referral-fields input')) await input.setValue('dato anterior')
    await wrapper.get(`input[value="${mode}"]`).setValue(true)
    expect(wrapper.find('.referral-fields').exists()).toBe(false)
    await wrapper.get('input[value="REFERENCIA"]').setValue(true)
    for (const input of wrapper.findAll('.referral-fields input')) {
      expect((input.element as HTMLInputElement).value).toBe('')
    }
    await wrapper.get(`input[value="${mode}"]`).setValue(true)
    create.mockImplementation(async payload => ({ ...payload, id: 503, fua_impresion: null }))
    await wrapper.findAll('button').find(button => button.text() === 'Guardar atención')!.trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledOnce()
    expect(create.mock.calls[0]?.[0]).toMatchObject({ modalidad_atencion_codigo: mode, fua_datos: null })
  },
)

test(
  'el formulario mantiene fecha, selección exclusiva y payload al guardar la atención',
  { timeout: 30_000 },
  async () => {
    const wrapper = await mountAdmission()
    const field = (label: string) =>
      wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
    expect(wrapper.text()).toContain('Fecha y hora de atención')
    expect(wrapper.getComponent(AdmissionHistory).props('compact')).toBe(true)
    expect(wrapper.findComponent(NutritionFollowupPanel).exists()).toBe(false)
    expect(wrapper.find('.encounter-header h2').exists()).toBe(false)
    expect(wrapper.get('.encounter-header').text()).not.toContain('Sede de prueba')
    field('Consultorio').getComponent(ElSelect).vm.$emit('update:modelValue', 3)
    await flushPromises()
    field('Profesional').getComponent(ElSelect).vm.$emit('update:modelValue', 2)
    await wrapper.get('input[value="EMERGENCIA"]').setValue(true)
    expect(wrapper.text()).toContain('Perímetro abdominal (cm)')
    await wrapper.get('input[value="GESTANTES"]').setValue(true)
    expect(wrapper.text()).toContain('Fecha probable de parto')
    expect(wrapper.text()).not.toContain('Fecha del parto')
    expect(wrapper.text()).not.toContain('Perímetro abdominal (cm)')
    field('Tipo de embarazo').getComponent(ElSelect).vm.$emit('update:modelValue', 'UNICO')
    field('Peso antes del embarazo (kg)')
      .getComponent(ElInputNumber)
      .vm.$emit('update:modelValue', 55)
    await wrapper.get('input[value="PUERPERAS"]').setValue(true)
    // Puérperas comparte tipo de embarazo y peso previo; la FPP deja su lugar
    // a la fecha real del parto y el perímetro abdominal no aplica.
    expect(wrapper.text()).toContain('Tipo de embarazo')
    expect(wrapper.text()).toContain('Fecha del parto')
    expect(wrapper.text()).not.toContain('Fecha probable de parto')
    expect(wrapper.text()).not.toContain('Perímetro abdominal (cm)')
    field('Fecha del parto').getComponent(ElDatePicker).vm.$emit('update:modelValue', '2026-09-20')
    field('Peso actual (kg)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 60)
    field('Talla (cm)').getComponent(ElInputNumber).vm.$emit('update:modelValue', 160)
    await flushPromises()
    create.mockImplementation(async (payload) => ({ ...payload, id: 500, fua_impresion: null }))
    const save = wrapper.findAll('button').find((b) => b.text() === 'Guardar atención')!
    await save.trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledOnce()
    expect(create.mock.calls[0]?.[0]).toMatchObject({
      paciente_id: 100,
      establecimiento_id: 1,
      consultorio_id: 3,
      profesional_id: 2,
      especialidad_codigo: '001',
      modalidad_atencion_codigo: 'EMERGENCIA',
      grupo_atencion_codigo: 'PUERPERAS',
      peso_kg: 60,
      talla_cm: 160,
      tipo_embarazo_codigo: 'UNICO',
      peso_antes_embarazo_kg: 55,
      fecha_probable_parto: null,
      fecha_parto: '2026-09-20',
    })
    expect(create.mock.calls[0]?.[0].fecha_atencion).toMatch(/^\d{4}-\d{2}-\d{2}T/)
    expect(create.mock.calls[0]?.[0]).not.toHaveProperty('condicion')
    expect(wrapper.text()).toContain('Atención guardada')
    expect(wrapper.findComponent(NutritionFollowupPanel).exists()).toBe(false)
    expect(wrapper.get('input[value="PUERPERAS"]').attributes('disabled')).toBeDefined()
    expect(listByPatient).toHaveBeenCalledTimes(2)
    await wrapper.setProps({ admission: false })
    expect(wrapper.getComponent(AdmissionHistory).props('compact')).toBe(false)
  },
)

test(
  'los cambios del paciente bloquean la atención hasta guardarlos o descartarlos',
  { timeout: 30_000 },
  async () => {
    const wrapper = await mountAdmission()
    wrapper.getComponent(AdmissionPatientSummary).vm.$emit('dirtyChange', true)
    await flushPromises()
    const save = wrapper.findAll('button').find((b) => b.text() === 'Guardar atención')!
    expect(save.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Guarde o descarte los cambios del paciente')
    expect(create).not.toHaveBeenCalled()
    for (const text of ['Otra consulta', 'FUA adicional']) {
      expect(
        wrapper
          .findAll('button')
          .find((b) => b.text() === text)
          ?.attributes('disabled'),
      ).toBeDefined()
    }
  },
)

test.each(['GESTANTES', 'PUERPERAS'])(
  'guardar %s refresca la condición confirmada por el servidor',
  async (group) => {
    const wrapper = await mountAdmission()
    const field = (label: string) =>
      wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
    field('Consultorio').getComponent(ElSelect).vm.$emit('update:modelValue', 3)
    await flushPromises()
    field('Profesional').getComponent(ElSelect).vm.$emit('update:modelValue', 2)
    await wrapper.get(`input[value="${group}"]`).setValue(true)
    const condition = group === 'GESTANTES' ? 'GESTANTE' : 'PUERPERA'
    expect(wrapper.getComponent(AdmissionPatientSummary).props('patient').condicion).toBe(
      'NO GESTANTE',
    )
    get.mockResolvedValue(aPatient({ condicion: condition }))
    create.mockImplementation(async (payload) => ({ ...payload, id: 501, fua_impresion: null }))
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Guardar atención')!
      .trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledOnce()
    expect(wrapper.getComponent(AdmissionPatientSummary).props('patient').condicion).toBe(condition)
    expect(wrapper.text()).toContain('Atención guardada')
  },
)

test('fallar el refresco de ficha después del POST no permite duplicar la atención', async () => {
  const wrapper = await mountAdmission()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  field('Consultorio').getComponent(ElSelect).vm.$emit('update:modelValue', 3)
  await flushPromises()
  field('Profesional').getComponent(ElSelect).vm.$emit('update:modelValue', 2)
  await wrapper.get('input[value="PUERPERAS"]').setValue(true)
  get.mockRejectedValue(new Error('Refresh unavailable'))
  create.mockImplementation(async (payload) => ({ ...payload, id: 502, fua_impresion: null }))
  const save = wrapper.findAll('button').find((b) => b.text() === 'Guardar atención')!
  await save.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Atención guardada')
  await save.trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledOnce()
})

test('una atención rechazada conserva la condición visible y no refresca la ficha', async () => {
  const wrapper = await mountAdmission()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  field('Consultorio').getComponent(ElSelect).vm.$emit('update:modelValue', 3)
  await flushPromises()
  field('Profesional').getComponent(ElSelect).vm.$emit('update:modelValue', 2)
  await wrapper.get('input[value="GESTANTES"]').setValue(true)
  const reads = get.mock.calls.length
  create.mockRejectedValue(new Error('Atención rechazada de prueba'))
  await wrapper
    .findAll('button')
    .find((b) => b.text() === 'Guardar atención')!
    .trigger('click')
  await flushPromises()
  expect(get.mock.calls.length).toBe(reads)
  expect(wrapper.getComponent(AdmissionPatientSummary).props('patient').condicion).toBe(
    'NO GESTANTE',
  )
  expect(wrapper.text()).toContain('Atención rechazada de prueba')
  expect(wrapper.text()).not.toContain('Atención guardada')
})

test('Medicina ofrece sus servicios habilitados y permite guardar Pediatría sin mezclar Nutrición', async () => {
  const wrapper = await mountAdmission()
  const field = (label: string) =>
    wrapper.findAllComponents(ElFormItem).find((item) => item.props('label') === label)!
  field('Consultorio').getComponent(ElSelect).vm.$emit('update:modelValue', 3)
  await flushPromises()
  const services = field('Servicio / especialidad').getComponent(ElSelect)
  expect(
    services.findAllComponents({ name: 'ElOption' }).map((item) => item.props('label')),
  ).toEqual(['MEDICINA GENERAL', 'PEDIATRIA'])
  services.vm.$emit('update:modelValue', 'ESP_MEDICINA:003')
  field('Profesional').getComponent(ElSelect).vm.$emit('update:modelValue', 2)
  await flushPromises()
  create.mockImplementation(async (payload) => ({ ...payload, id: 503, fua_impresion: null }))
  await wrapper
    .findAll('button')
    .find((item) => item.text() === 'Guardar atención')!
    .trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({
      consultorio_id: 3,
      especialidad_codigo: 'ESP_MEDICINA:003',
      profesional_id: 2,
    }),
  )
  const contextFields = wrapper
    .findAllComponents(ElFormItem)
    .map((item) => item.props('label') || '')
    .filter((label) =>
      ['Área asistencial', 'Consultorio', 'Servicio / especialidad', 'Profesional'].includes(label),
    )
  expect(contextFields).toEqual(['Consultorio', 'Servicio / especialidad', 'Profesional'])

  expect(field('Servicio / especialidad').getComponent(ElSelect).props('disabled')).toBe(true)
})
