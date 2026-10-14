import { effectScope } from 'vue'
import { expect, test, vi } from 'vitest'
import { useDistrictLocalities } from '@/composables/useDistrictLocalities'

const { localidades } = vi.hoisted(() => ({ localidades: vi.fn() }))
vi.mock('@/services/catalogos', () => ({ catalogos: { localidades } }))

test('un distrito nuevo descarta respuestas anteriores y carga todas sus páginas', async () => {
  const scope = effectScope()
  const catalog = scope.run(() => useDistrictLocalities())!
  let finishOld!: (value: unknown) => void
  const old = new Promise((resolve) => { finishOld = resolve })
  const rows = Array.from({ length: 100 }, (_, id) => ({
    id, nombre: `Sector ${id}`, ubigeo_codigo: '040103', codigo_sis: String(id), activo: true,
  }))
  localidades.mockImplementation((district, _q, _limit, offset) =>
    district === '040102' ? old : Promise.resolve({
      items: offset === 0 ? rows : [{ ...rows[0], id: 100, nombre: 'Último sector' }],
      total: 101, limit: 100, offset, has_more: offset === 0,
    }),
  )
  const first = catalog.load('040102')
  await catalog.load('040103')
  expect(catalog.items.value).toHaveLength(101)
  expect(localidades).toHaveBeenCalledWith('040103', undefined, 100, 100)
  finishOld({ items: [{ ...rows[0], ubigeo_codigo: '040102' }], has_more: false })
  await first
  expect(catalog.items.value.every((row) => row.ubigeo_codigo === '040103')).toBe(true)
  await catalog.load(null)
  expect(catalog.items.value).toEqual([])
  expect(catalog.loading.value).toBe(false)
  scope.stop()
})

test('limpiar el distrito invalida la petición pendiente y los errores permiten reintentar', async () => {
  const scope = effectScope()
  const catalog = scope.run(() => useDistrictLocalities())!
  let reject!: (reason: Error) => void
  localidades.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
  const pending = catalog.load('040102')
  await catalog.load(null)
  reject(new Error('Respuesta anterior'))
  await pending
  expect(catalog.error.value).toBeNull()
  expect(catalog.loading.value).toBe(false)
  localidades.mockRejectedValueOnce(new Error('Sin conexión'))
  await catalog.load('040103')
  expect(catalog.error.value).toContain('No se cargaron')
  localidades.mockResolvedValueOnce({ items: [], has_more: false })
  await catalog.load('040103')
  expect(catalog.error.value).toBeNull()
  scope.stop()
})
