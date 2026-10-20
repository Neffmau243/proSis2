import { flushPromises } from '@vue/test-utils'
import { effectScope, shallowRef } from 'vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useAttentionHistory } from '@/composables/useAttentionHistory'
import type { Attention } from '@/services/atenciones'
import type { PageResponse } from '@/types/api'

const { listByPatient, search } = vi.hoisted(() => ({
  listByPatient: vi.fn(),
  search: vi.fn(),
}))
vi.mock('@/services/atenciones', () => ({ atenciones: { listByPatient, search } }))
const scopes: ReturnType<typeof effectScope>[] = []
const row = (id: number, patientId = 10) => ({ id, paciente_id: patientId }) as Attention
const page = (items: Attention[], offset = 0, hasMore = false): PageResponse<Attention> => ({
  items,
  offset,
  limit: 100,
  total: hasMore ? 102 : offset + items.length,
  has_more: hasMore,
})

beforeEach(() => {
  vi.resetAllMocks()
  listByPatient.mockResolvedValue([row(5), row(4), row(3), row(2), row(1)])
})
afterEach(() => scopes.splice(0).forEach((scope) => scope.stop()))

function setup(id: number | null = 10) {
  const patient = shallowRef(id)
  const scope = effectScope()
  scopes.push(scope)
  const state = scope.run(() => useAttentionHistory(patient))!
  return { patient, scope, state }
}

test('carga solo las cinco recientes al seleccionar un paciente', async () => {
  const { state } = setup()
  await flushPromises()
  expect(listByPatient).toHaveBeenCalledExactlyOnceWith(10)
  expect(search).not.toHaveBeenCalled()
  expect(state.entries.value.map((item) => item.id)).toEqual([5, 4, 3, 2, 1])
  expect(state.allLoaded.value).toBe(false)
})

test('traer todas recorre las páginas y refrescar conserva la vista completa', async () => {
  const first = Array.from({ length: 100 }, (_, index) => row(102 - index))
  search
    .mockResolvedValueOnce(page(first, 0, true))
    .mockResolvedValueOnce(page([row(2), row(1)], 100))
  const { state } = setup()
  await flushPromises()
  await state.showAll()
  expect(search.mock.calls).toEqual([
    [{ paciente_id: 10, limit: 100, offset: 0 }],
    [{ paciente_id: 10, limit: 100, offset: 100 }],
  ])
  expect(state.entries.value).toHaveLength(102)
  expect(state.entries.value.at(-1)?.id).toBe(1)
  expect(state.allLoaded.value).toBe(true)

  search.mockResolvedValueOnce(page([row(103)]))
  await state.refresh()
  expect(state.entries.value.map((item) => item.id)).toEqual([103])
  expect(state.allLoaded.value).toBe(true)
  await state.showRecent()
  expect(state.allLoaded.value).toBe(false)
  expect(state.entries.value).toHaveLength(5)
  await state.refresh()
  expect(listByPatient).toHaveBeenCalledTimes(3)
  expect(search).toHaveBeenCalledTimes(3)
})

test('al cambiar paciente descarta la carga anterior y vuelve a las cinco recientes', async () => {
  const { state, patient } = setup()
  await flushPromises()
  let resolve!: (value: PageResponse<Attention>) => void
  search.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const pending = state.showAll()
  listByPatient.mockResolvedValueOnce([row(20, 11)])
  patient.value = 11
  await flushPromises()
  resolve(page([row(9)], 0, true))
  await pending
  expect(search).toHaveBeenCalledTimes(1)
  expect(state.entries.value.map((item) => item.paciente_id)).toEqual([11])
  expect(state.allLoaded.value).toBe(false)
  expect(state.loading.value).toBe(false)
})

test('si una página falla no presenta un historial parcial como completo y permite reintentar', async () => {
  const { state } = setup()
  await flushPromises()
  search
    .mockResolvedValueOnce(page([row(9)], 0, true))
    .mockRejectedValueOnce(new Error('Sin conexión'))
  await state.showAll()
  expect(state.error.value).toBe('Sin conexión')
  expect(state.allLoaded.value).toBe(false)
  expect(state.entries.value.map((item) => item.id)).toEqual([5, 4, 3, 2, 1])
  expect(state.loading.value).toBe(false)
  search.mockResolvedValueOnce(page([row(9)]))
  await state.showAll()
  expect(state.error.value).toBeNull()
  expect(state.allLoaded.value).toBe(true)
})

test('no consulta sin paciente y detiene la paginación cuando la respuesta está vacía', async () => {
  const { state, patient } = setup(null)
  await state.showAll()
  expect(listByPatient).not.toHaveBeenCalled()
  expect(search).not.toHaveBeenCalled()
  patient.value = 10
  await flushPromises()
  search.mockResolvedValueOnce(page([], 0, true))
  await state.showAll()
  expect(search).toHaveBeenCalledTimes(1)
  expect(state.entries.value).toEqual([])
})

test('al salir no publica la respuesta pendiente ni consulta más páginas', async () => {
  const { state, scope } = setup()
  await flushPromises()
  let resolve!: (value: PageResponse<Attention>) => void
  search.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const pending = state.showAll()
  scope.stop()
  resolve(page([row(9)], 0, true))
  await pending
  expect(search).toHaveBeenCalledTimes(1)
  expect(state.entries.value).toHaveLength(5)
  expect(state.allLoaded.value).toBe(false)
})
