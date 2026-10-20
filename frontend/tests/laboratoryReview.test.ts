import { effectScope, nextTick, shallowRef } from 'vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useLaboratoryReview } from '@/composables/useLaboratoryReview'
import type { Attention } from '@/services/atenciones'

const get = vi.hoisted(() => vi.fn())
vi.mock('@/services/atenciones', () => ({ atenciones: { get } }))
const scopes: ReturnType<typeof effectScope>[] = []
beforeEach(() => get.mockReset())
afterEach(() => scopes.splice(0).forEach((scope) => scope.stop()))
const row = (overrides = {}) =>
  ({
    id: 41,
    paciente_id: 14,
    consultorio_id: 8,
    numero_referencia_ingreso: '001565',
    numero_contrarreferencia_ingreso: '00007',
    fua_impresion: { referencia_hoja: '001565', sis_tipo: '2', sis_numero: '00112233' },
    ...overrides,
  }) as Attention

function setup(canRead = true) {
  const patient = shallowRef(14)
  const office = shallowRef(8)
  const scope = effectScope()
  scopes.push(scope)
  const state = scope.run(() =>
    useLaboratoryReview({
      patientId: () => patient.value,
      officeId: () => office.value,
      canRead: () => canRead,
    }),
  )!
  return { state, patient, office }
}

test('consulta la copia persistida sin crear una nueva atención', async () => {
  const { state } = setup()
  get.mockResolvedValue(row())
  await state.open(row())
  expect(get).toHaveBeenCalledWith(41)
  expect(state.attention.value?.numero_referencia_ingreso).toBe('001565')
  expect(state.attention.value?.numero_contrarreferencia_ingreso).toBe('00007')
  expect(state.attention.value?.fua_impresion?.referencia_hoja).toBe('001565')
  expect(state.opened.value).toBe(true)
  expect(state.loading.value).toBe(false)
})

test('no consulta pacientes, consultorios o permisos que no corresponden', async () => {
  const { state } = setup()
  await state.open(row({ paciente_id: 99 }))
  await state.open(row({ consultorio_id: 99 }))
  await setup(false).state.open(row())
  expect(get).not.toHaveBeenCalled()
})

test('descarta una respuesta al cambiar paciente o cerrar la consulta', async () => {
  const { state, patient } = setup()
  let resolve!: (value: Attention) => void
  get.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  const pending = state.open(row())
  patient.value = 15
  await nextTick()
  resolve(row())
  await pending
  expect(state.attention.value).toBeNull()
  expect(state.opened.value).toBe(false)
  get.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  patient.value = 14
  const second = state.open(row())
  state.opened.value = false
  await nextTick()
  resolve(row())
  await second
  expect(state.attention.value).toBeNull()
})

test('un fallo o respuesta de otro paciente nunca habilita la impresión', async () => {
  const { state } = setup()
  get.mockRejectedValueOnce(new Error('Sin conexión'))
  await state.open(row())
  expect(state.error.value).toBe('Sin conexión')
  expect(state.attention.value).toBeNull()
  get.mockResolvedValue(row({ paciente_id: 99 }))
  await state.open(row())
  expect(state.error.value).toContain('no corresponde')
  expect(state.attention.value).toBeNull()
})
