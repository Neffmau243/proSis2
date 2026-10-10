import { flushPromises, mount } from '@vue/test-utils'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import PatientRegistrationBaseSection from '@/components/patients/PatientRegistrationBaseSection.vue'
import PatientRegistrationFamilySections from '@/components/patients/PatientRegistrationFamilySections.vue'
import type { Patient } from '@/services/pacientes'
import PacienteNuevoView from '@/views/PacienteNuevoView.vue'
import { aPatient } from '../fixtures/patient'

const { create } = vi.hoisted(() => ({
  create: vi.fn<(payload: Record<string, unknown>) => Promise<Patient>>(),
}))
const { catalogos } = vi.hoisted(() => ({
  catalogos: {
    tiposDocumento: vi.fn(),
    sexos: vi.fn(),
    seguros: vi.fn(),
    gruposRiesgo: vi.fn(),
    historiasFamiliares: vi.fn(),
    establecimientos: vi.fn(),
    ubigeos: vi.fn(),
  },
}))

vi.mock('@/services/pacientes', () => ({ pacientes: { create } }))
vi.mock('@/services/catalogos', () => ({ catalogos }))

const mounted: { unmount: () => void }[] = []

async function mountView(routeName = 'paciente-nuevo') {
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/pacientes/nuevo', name: 'paciente-nuevo', component: stub },
      { path: '/admision', name: 'admision', component: stub },
      { path: '/', name: 'inicio', component: stub },
      { path: '/pacientes/:id', name: 'paciente-detalle', component: stub },
    ],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push({ name: routeName })
  await router.isReady()

  const wrapper = mount(PacienteNuevoView, {
    global: { plugins: [router, pinia, ElementPlus], components: ElementPlusIconsVue },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

/** La sección base comunica los cambios del formulario con un solo evento. */
async function fillIdentity(
  wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'],
  changes: Record<string, unknown>,
) {
  wrapper.findComponent(PatientRegistrationBaseSection).vm.$emit('update', changes)
  await flushPromises()
}

/** La fecha de inscripción arranca en hoy y se puede corregir antes de guardar. */
async function setRegistrationDate(
  wrapper: Awaited<ReturnType<typeof mountView>>['wrapper'],
  value: string,
) {
  const item = wrapper.find('.form-actions__date')
  item.findComponent({ name: 'ElDatePicker' }).vm.$emit('update:modelValue', value)
  await flushPromises()
}

async function submit(wrapper: Awaited<ReturnType<typeof mountView>>['wrapper']) {
  const button = wrapper.findAll('button').find((item) => item.text().includes('Registrar paciente'))
  await button!.trigger('click')
  await flushPromises()
  await vi.advanceTimersByTimeAsync(150)
  await flushPromises()
}

const validIdentity = {
  tipo_documento_codigo: 'DNI',
  numero_documento: '12345678',
  primer_nombre: 'Ana',
  fecha_nacimiento: '1990-05-10',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  // Mediodía local: la fecha de inscripción que envía el alta es determinista.
  vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  catalogos.tiposDocumento.mockResolvedValue([{ codigo: 'DNI', nombre: 'DNI', activo: true }])
  catalogos.sexos.mockResolvedValue([{ codigo: 'F', nombre: 'Femenino', activo: true }])
  catalogos.seguros.mockResolvedValue([{ id: 2, codigo: 'SIS', nombre: 'SIS', activo: true }])
  catalogos.gruposRiesgo.mockResolvedValue([])
  catalogos.historiasFamiliares.mockResolvedValue({
    items: [
      {
        codigo: 'AM',
        nombre: 'AMARILLO',
        tipo: 'COLOR',
        color_hex: '#F2C94C',
        activo: true,
      },
    ],
    total: 1,
    has_more: false,
  })
  catalogos.establecimientos.mockResolvedValue({ items: [], total: 0, has_more: false })
  catalogos.ubigeos.mockResolvedValue({ items: [], total: 0, has_more: false })
  create.mockResolvedValue(aPatient({ id: 77 }))
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.useRealTimers()
})

test('sin datos obligatorios no se registra nada y el formulario lo señala', async () => {
  const { wrapper } = await mountView()

  await submit(wrapper)

  expect(create).not.toHaveBeenCalled()
  expect(wrapper.find('.el-form-item.is-error').exists()).toBe(true)
})

test('un número de pasaporte no se envía como DNI al cambiar el selector', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, { ...validIdentity, tipo_documento_codigo: 'PAS', numero_documento: 'PASUI000033' })
  await fillIdentity(wrapper, { tipo_documento_codigo: 'DNI' })
  await submit(wrapper)
  expect(create).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('8 dígitos')
  await fillIdentity(wrapper, { numero_documento: '00112233' })
  await submit(wrapper)
  expect(create).toHaveBeenCalledWith(expect.objectContaining({ tipo_documento_codigo: 'DNI', numero_documento: '00112233' }))
})

test('cambiar de SIS a sin seguro limpia los cuatro campos y conserva etnia', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, { ...validIdentity, seguro_id: 2, sis_diresa: '040', sis_tipo: '2', sis_numero: '00112233', sis_secuencia: '01', etnia_codigo: '58' })
  await fillIdentity(wrapper, { seguro_id: null })
  await submit(wrapper)
  expect(create).toHaveBeenCalledWith(expect.objectContaining({ seguro_id: null, sis_diresa: null, sis_tipo: null, sis_numero: null, sis_secuencia: null, etnia_codigo: '58' }))
})

test('el alta envía solo los campos del contrato y navega a la ficha creada', async () => {
  const { wrapper, router } = await mountView()
  await fillIdentity(wrapper, { ...validIdentity, apellido_paterno: 'Quispe', otros_nombres: '' })

  await submit(wrapper)

  expect(create).toHaveBeenCalledWith({
    sufijo_documento: null,
    tipo_documento_codigo: 'DNI',
    numero_documento: '12345678',
    historia_clinica: null,
    historia_familiar: null,
    fecha_nacimiento: '1990-05-10',
    // La inscripción no se pide en el formulario: el alta envía el día de hoy.
    fecha_inscripcion: '2026-03-15',
    apellido_paterno: 'Quispe',
    apellido_materno: null,
    primer_nombre: 'Ana',
    otros_nombres: null,
    sexo_codigo: null,
    ubigeo_residencia_codigo: null,
    localidad: null,
    localidad_id: null,
    direccion: null,
    establecimiento_registro_id: null,
    seguro_id: null,
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
    sis_secuencia: null,
    etnia_codigo: null,
    telefono_principal: null,
    condicion: null,
    responsables: [],
    riesgos: [],
  })
  expect(router.currentRoute.value.name).toBe('paciente-detalle')
  expect(router.currentRoute.value.params.id).toBe('77')
})

test('el alta conserva el identificador familiar compuesto y sus ceros iniciales', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, { ...validIdentity, historia_familiar: 'AM-00042' })

  await submit(wrapper)

  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({ historia_familiar: 'AM-00042' }),
  )
})

test('la fecha de inscripción elegida reemplaza a la de hoy', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, validIdentity)

  await setRegistrationDate(wrapper, '2019-07-04')
  await submit(wrapper)

  expect(create.mock.calls[0]![0].fecha_inscripcion).toBe('2019-07-04')
})

test('una inscripción futura o previa al nacimiento no se envía', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, validIdentity)

  await setRegistrationDate(wrapper, '2026-03-16')
  await submit(wrapper)
  expect(create).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('La fecha de inscripción no puede estar en el futuro.')

  await setRegistrationDate(wrapper, '1989-01-01')
  await submit(wrapper)
  expect(create).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('No puede ser anterior a la fecha de nacimiento.')
})

test('los responsables viajan con el parentesco y los riesgos con su grupo', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, validIdentity)

  const family = wrapper.findComponent(PatientRegistrationFamilySections)
  family.vm.$emit('update:responsables', [
    {
      parentesco: 'MADRE',
      nombre_completo: 'Ana Quispe',
      tipo_documento_codigo: 'DNI',
      numero_documento: '87654321',
      telefono: null,
      es_principal: true,
    },
  ])
  family.vm.$emit('update:riesgos', [
    {
      grupo_riesgo_id: 3,
      fecha_inicio: '2026-01-01',
      fecha_fin: null,
      observacion: '',
    },
  ])
  await flushPromises()

  await submit(wrapper)

  const payload = create.mock.calls[0]![0]
  expect(payload.responsables).toEqual([
    {
      parentesco: 'MADRE',
      nombre_completo: 'Ana Quispe',
      tipo_documento_codigo: 'DNI',
      numero_documento: '87654321',
      telefono: null,
      es_principal: true,
      activo: true,
    },
  ])
  expect(payload.riesgos).toEqual([
    {
      grupo_riesgo_id: 3,
      fecha_inicio: '2026-01-01',
      fecha_fin: null,
      observacion: null,
    },
  ])
})

test('un recién nacido se registra el mismo día con condición y responsable', async () => {
  const { wrapper, router } = await mountView()
  await fillIdentity(wrapper, {
    tipo_documento_codigo: 'OTRO',
    numero_documento: 'RN-20260315',
    primer_nombre: 'Bebé',
    fecha_nacimiento: '2026-03-15',
    sexo_codigo: 'F',
    condicion: 'RECIEN NACIDO',
  })
  wrapper.findComponent(PatientRegistrationFamilySections).vm.$emit('update:responsables', [
    {
      parentesco: 'MADRE',
      nombre_completo: 'Madre ficticia',
      tipo_documento_codigo: 'DNI',
      numero_documento: '87654321',
      telefono: null,
      es_principal: true,
    },
  ])
  await flushPromises()

  await submit(wrapper)

  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({
      tipo_documento_codigo: 'OTRO',
      numero_documento: 'RN-20260315',
      fecha_nacimiento: '2026-03-15',
      fecha_inscripcion: '2026-03-15',
      condicion: 'RECIEN NACIDO',
      responsables: [
        expect.objectContaining({
          parentesco: 'MADRE',
          nombre_completo: 'Madre ficticia',
          activo: true,
        }),
      ],
    }),
  )
  expect(router.currentRoute.value.name).toBe('paciente-detalle')
})

test('una afiliación SIS incompleta bloquea el alta con su motivo', async () => {
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, { ...validIdentity, sis_tipo: '2' })

  await submit(wrapper)

  expect(create).not.toHaveBeenCalled()
  expect(wrapper.find('.el-alert__title').text()).toMatch(/número de afiliación/i)
})

test('un rechazo del backend se muestra con su mensaje y conserva lo escrito', async () => {
  create.mockRejectedValue(new Error('El número de documento ya está registrado.'))
  const { wrapper, router } = await mountView()
  await fillIdentity(wrapper, validIdentity)

  await submit(wrapper)

  expect(wrapper.find('.el-alert__title').text()).toBe(
    'El número de documento ya está registrado.',
  )
  expect(wrapper.findComponent(PatientRegistrationBaseSection).props('form')).toMatchObject({
    numero_documento: '12345678',
  })
  expect(router.currentRoute.value.name).toBe('paciente-nuevo')
})

test('un fallo sin mensaje usa el texto por defecto', async () => {
  create.mockRejectedValue('caída de red')
  const { wrapper } = await mountView()
  await fillIdentity(wrapper, validIdentity)

  await submit(wrapper)

  expect(wrapper.find('.el-alert__title').text()).toBe('No se pudo registrar el paciente.')
})

test('la misma vista sirve al flujo de admisión y lo advierte', async () => {
  const { wrapper } = await mountView('admision')
  // El título lo aporta la barra superior del layout, la vista no lo repite.
  expect(wrapper.find('h2').exists()).toBe(false)
  expect(wrapper.text()).toContain('Admisión: registre al paciente')
  expect(wrapper.text()).toContain('Fecha de inscripción')
})

test('las búsquedas de establecimiento y ubigeo consultan al catálogo', async () => {
  const { wrapper } = await mountView()

  wrapper.findComponent(PatientRegistrationBaseSection).vm.$emit('searchEstablecimientos', 'CS')
  wrapper.findComponent(PatientRegistrationBaseSection).vm.$emit('searchUbigeos', 'AQP')
  await flushPromises()

  expect(catalogos.establecimientos).toHaveBeenCalledWith('CS', 25, 0)
  expect(catalogos.ubigeos).toHaveBeenCalledWith('AQP', 25, 0)
})
