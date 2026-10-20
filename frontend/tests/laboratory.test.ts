import { effectScope, nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useLaboratory } from '@/composables/useLaboratory'
import { aPatient } from './fixtures/patient'

const api = vi.hoisted(() => ({
  create: vi.fn(),
  search: vi.fn(),
  patients: vi.fn(),
  get: vi.fn(),
  types: vi.fn(),
  sexes: vi.fn(),
  insurance: vi.fn(),
  sites: vi.fn(),
  rooms: vi.fn(),
  staff: vi.fn(),
}))
vi.mock('@/services/atenciones', () => ({ atenciones: { create: api.create, search: api.search } }))
vi.mock('@/services/pacientes', () => ({ pacientes: { search: api.patients, get: api.get } }))
vi.mock('@/services/catalogos', () => ({
  catalogos: {
    profesionales: api.staff,
    tiposDocumento: api.types,
    sexos: api.sexes,
    seguros: api.insurance,
    establecimientos: api.sites,
    consultorios: api.rooms,
  },
}))
const scopes: ReturnType<typeof effectScope>[] = []
beforeEach(() => {
  vi.resetAllMocks()
  api.search.mockResolvedValue({ items: [], total: 0 })
  api.staff.mockResolvedValue({
    items: [{ id: 4, nombre_completo: 'Profesional asignado' }],
    has_more: false,
  })
})

test('inicializar carga todas las páginas, filtra laboratorios activos y recupera el paciente solicitado', async () => {
  const state = setup()
  const lab = { id: 9, establecimiento_id: 2, codigo: 'LAB', nombre: 'Laboratorio', activo: true }
  api.types.mockResolvedValue([{ codigo: 'DNI' }])
  api.sexes.mockResolvedValue([{ codigo: 'F' }])
  api.insurance.mockResolvedValue([{ id: 1 }])
  api.sites
    .mockResolvedValueOnce({ items: [{ id: 2 }], has_more: true })
    .mockResolvedValueOnce({ items: [], has_more: false })
  api.rooms.mockResolvedValue({
    items: [
      lab,
      { ...lab, id: 10, activo: false },
      { ...lab, id: 11, codigo: 'MED', nombre: 'Medicina' },
    ],
    has_more: false,
  })
  api.get.mockResolvedValue(aPatient({ id: 22, establecimiento_registro_id: 2 }))
  await state.initialize(22)
  await flushPromises()
  expect(state.offices.value.map((item) => item.id)).toEqual([9])
  expect(state.form.officeId).toBe(9)
  expect(state.patient.value?.id).toBe(22)
  expect(state.documents.value).toEqual([{ codigo: 'DNI' }])
  expect(state.establishment.value?.id).toBe(2)
  expect(api.sites).toHaveBeenCalledTimes(2)
  expect(state.loading.value).toBe(false)
})

test('un catálogo caído bloquea el guardado y una búsqueda fallida permite reintentar', async () => {
  const state = setup()
  api.types.mockRejectedValue(new Error('Catálogo sin conexión'))
  await state.initialize()
  expect(state.catalogError.value).toBe('Catálogo sin conexión')
  expect(state.loading.value).toBe(false)
  expect(await state.save()).toBe(false)
  expect(api.create).not.toHaveBeenCalled()
  await state.searchPatients('a')
  expect(api.patients).not.toHaveBeenCalled()
  api.patients.mockRejectedValueOnce('fallo de red')
  await state.searchPatients('Ana')
  expect(state.searchError.value).toContain('Intente nuevamente')
  expect(state.searching.value).toBe(false)
  api.patients.mockResolvedValue({ items: [aPatient({ id: 25 })], has_more: true })
  await state.searchPatients('Ana')
  expect(state.patients.value[0]?.id).toBe(25)
  expect(state.searchHint.value).toContain('más coincidencias')
  expect(state.searchError.value).toBe('')
})

test('al cambiar de consultorio descarta un profesional que dejó de estar asignado', async () => {
  const state = setup()
  await flushPromises()
  api.staff.mockResolvedValue({
    items: [{ id: 6, nombre_completo: 'Nueva asignación' }],
    has_more: false,
  })
  state.form.officeId = 99
  await flushPromises()
  expect(state.professionals.value.map((item) => item.id)).toEqual([6])
  expect(state.form.professionalId).toBeNull()
  api.staff.mockRejectedValue(new Error('Asignaciones sin conexión'))
  state.form.officeId = 8
  await flushPromises()
  expect(state.professionals.value).toEqual([])
  expect(state.professionalsLoading.value).toBe(false)
  expect(state.catalogError.value).toBe('Asignaciones sin conexión')
  state.form.officeId = null
  await flushPromises()
  expect(state.form.professionalId).toBeNull()
})
afterEach(() => scopes.splice(0).forEach((scope) => scope.stop()))

function setup(canCreate = true) {
  const scope = effectScope()
  scopes.push(scope)
  return scope.run(() => {
    const state = useLaboratory(
      () => canCreate,
      () => true,
    )
    state.offices.value = [
      {
        id: 8,
        establecimiento_id: 2,
        codigo: 'LAB',
        nombre: 'LABORATORIO',
        especialidad_codigo: '002',
        activo: true,
      },
    ]
    state.selectPatient(aPatient({ id: 11, establecimiento_registro_id: 2 }))
    state.form.professionalId = 4
    state.form.date = '2026-10-10T09:30:00'
    return state
  })!
}

test('guarda usando la sede y especialidad del laboratorio y bloquea duplicados incluso si falla el historial', async () => {
  const state = setup()
  state.form.reference = '001565'
  state.form.counterReference = '00007'
  await flushPromises()
  api.create.mockResolvedValue({ id: 99, paciente_id: 11, fua_impresion: { version: 2 } })
  api.search.mockRejectedValue(new Error('Sin conexión'))
  expect(await state.save()).toBe(true)
  expect(api.create).toHaveBeenCalledWith(
    expect.objectContaining({
      paciente_id: 11,
      consultorio_id: 8,
      establecimiento_id: 2,
      especialidad_codigo: '002',
    }),
  )
  expect(api.create).toHaveBeenCalledWith(
    expect.objectContaining({
      numero_referencia_ingreso: '001565',
      numero_contrarreferencia_ingreso: '00007',
    }),
  )
  expect(state.attentionCreated.value).toBe(true)
  expect(state.historyError.value).toBe('Sin conexión')
  expect(state.fuaSnapshot.value).toEqual({ version: 2 })
  expect(await state.save()).toBe(false)
  expect(api.create).toHaveBeenCalledTimes(1)
  state.newAttention()
  expect(state.attentionCreated.value).toBe(false)
  expect(state.fuaSnapshot.value).toBeNull()
})

test('un fallo de guardado permite reintentar sin mostrar una atención guardada', async () => {
  const state = setup()
  api.create.mockRejectedValue(new Error('Profesional no disponible'))
  expect(await state.save()).toBe(false)
  expect(state.error.value).toBe('Profesional no disponible')
  expect(state.attentionCreated.value).toBe(false)
  expect(state.saving.value).toBe(false)
})

test('referencia requiere origen completo y usa el mismo número recibido en el FUA', async () => {
  const state = setup()
  state.form.mode = 'REFERENCIA'
  state.form.reference = ' 001565 '
  expect(await state.save()).toBe(false)
  expect(state.error.value).toContain('RENIPRESS')
  state.form.originRenipress = '00001234'
  expect(await state.save()).toBe(false)
  expect(state.error.value).toContain('nombre de la IPRESS')
  state.form.originName = ' IPRESS ORIGEN '
  state.form.reference = ''
  expect(await state.save()).toBe(false)
  expect(state.error.value).toContain('referencia recibida')
  expect(api.create).not.toHaveBeenCalled()
  state.form.reference = ' 001565 '
  api.create.mockResolvedValue({
    id: 99,
    paciente_id: 11,
    fua_impresion: { tipo_atencion: 'REFERENCIA', referencia_hoja: '001565' },
  })
  expect(await state.save()).toBe(true)
  expect(api.create).toHaveBeenCalledWith(
    expect.objectContaining({
      modalidad_atencion_codigo: 'REFERENCIA',
      numero_referencia_ingreso: '001565',
      fua_datos: expect.objectContaining({
        tipo_atencion: 'REFERENCIA',
        referencia_hoja: '001565',
        referencia_renipress: '00001234',
        referencia_nombre: 'IPRESS ORIGEN',
      }),
    }),
  )
  expect(state.fuaSnapshot.value?.referencia_hoja).toBe('001565')
  state.newAttention()
  expect(state.form).toMatchObject({
    mode: 'AMBULATORIA',
    reference: '',
    originRenipress: '',
    originName: '',
  })
})

test('un número recibido no reclasifica la atención y otro paciente no hereda su origen', async () => {
  const state = setup()
  state.form.reference = '001565'
  state.form.originRenipress = '00001234'
  state.form.originName = 'ORIGEN ANTERIOR'
  api.create.mockResolvedValue({ id: 99, paciente_id: 11, fua_impresion: {} })
  expect(await state.save()).toBe(true)
  expect(api.create).toHaveBeenCalledWith(
    expect.objectContaining({ modalidad_atencion_codigo: 'AMBULATORIA', fua_datos: null }),
  )
  state.selectPatient(aPatient({ id: 12 }))
  expect(state.form).toMatchObject({
    mode: 'AMBULATORIA',
    reference: '',
    originRenipress: '',
    originName: '',
  })
})

test('sin permiso o con paciente dado de baja nunca envía el registro', async () => {
  const state = setup(false)
  expect(await state.save()).toBe(false)
  const active = setup()
  active.selectPatient(aPatient({ estado: false }))
  expect(await active.save()).toBe(false)
  expect(api.create).not.toHaveBeenCalled()
})

test('el historial se filtra por paciente y consultorio; el conteo por profesional, fecha y estado', async () => {
  const state = setup()
  await flushPromises()
  expect(api.search).toHaveBeenCalledWith({
    paciente_id: 11,
    consultorio_id: 8,
    limit: 10,
    offset: 0,
  })
  expect(api.search).toHaveBeenCalledWith({
    consultorio_id: 8,
    profesional_id: 4,
    fecha_hora_desde: '2026-10-10T07:00:00',
    fecha_hora_hasta: '2026-10-10T13:00:00',
    estado: 'ATENDIDO',
    limit: 1,
    offset: 0,
  })
  state.page.value = 2
  await nextTick()
  expect(api.search).toHaveBeenCalledWith({
    paciente_id: 11,
    consultorio_id: 8,
    limit: 10,
    offset: 10,
  })
})

test('cambiar paciente limpia observaciones e impresión y descarta respuestas antiguas de búsqueda', async () => {
  const state = setup()
  state.form.notes = 'Observación del primer paciente'
  state.remember({ id: 99, paciente_id: 11, fua_impresion: {} } as never)
  let resolve!: (value: unknown) => void
  api.patients.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  const pending = state.searchPatients('123')
  state.changeDocumentType('CE')
  resolve({ items: [aPatient({ id: 11 })] })
  await pending
  expect(state.patient.value).toBeNull()
  expect(state.patients.value).toEqual([])
  expect(state.form.notes).toBe('')
  expect(state.fuaSnapshot.value).toBeNull()
  expect(state.documentType.value).toBe('CE')
})

test('el historial de una selección anterior no reemplaza al paciente actual', async () => {
  const state = setup()
  await flushPromises()
  let resolve!: (value: unknown) => void
  api.search.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const pending = state.refreshHistory()
  state.selectPatient(aPatient({ id: 12, establecimiento_registro_id: 2 }))
  await flushPromises()
  resolve({ items: [{ id: 1, paciente_id: 11 }], total: 1 })
  await pending
  expect(state.entries.value).toEqual([])
  expect(state.total.value).toBe(0)
})

test('cambios pendientes bloquean selección y atención; la ficha confirmada conserva referencias e historial', async () => {
  const state = setup()
  await flushPromises()
  state.form.reference = '00012'
  state.entries.value = [
    { id: 99, paciente_id: 11, historia_clinica_snapshot: 'HC-ANTERIOR' },
  ] as never
  state.patientDirty.value = true
  state.selectPatient(aPatient({ id: 12 }))
  state.changeDocumentType('CE')
  expect(state.patient.value?.id).toBe(11)
  expect(state.documentType.value).toBe('DNI')
  expect(await state.save()).toBe(false)
  expect(api.create).not.toHaveBeenCalled()
  state.patientDirty.value = false
  state.patientBusy.value = true
  expect(await state.save()).toBe(false)
  state.patientSaved(
    aPatient({
      id: 11,
      numero_documento: '01234567',
      historia_clinica: 'HC-NUEVA',
      seguro_id: null,
    }),
  )
  expect(state.patient.value?.numero_documento).toBe('01234567')
  expect(state.patients.value[0]?.historia_clinica).toBe('HC-NUEVA')
  expect(state.entries.value[0]?.historia_clinica_snapshot).toBe('HC-ANTERIOR')
  expect(state.form.reference).toBe('00012')
  expect(state.form.officeId).toBe(8)
})
