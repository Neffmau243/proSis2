import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, effectScope, ref } from 'vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { useAdmissionPatientDetails } from '@/composables/useAdmissionPatientDetails'
import { useLoginUsernames } from '@/composables/useLoginUsernames'
import { useNutritionalIndicatorsPreview } from '@/composables/useNutritionalIndicatorsPreview'
import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import { usePagination } from '@/composables/usePagination'
import { useRemoteCatalog } from '@/composables/useRemoteCatalog'

vi.mock('@/services/auth', () => ({
  listActiveLoginUsernames: vi.fn(),
}))

vi.mock('@/services/atenciones', () => ({
  atenciones: { previewNutritionalIndicators: vi.fn() },
}))

vi.mock('@/services/catalogos', () => ({
  catalogos: {
    sexos: vi.fn(),
    seguros: vi.fn(),
    etnias: vi.fn(),
    historiasFamiliares: vi.fn(),
    establecimientos: vi.fn(),
    ubigeos: vi.fn(),
  },
}))

const { listActiveLoginUsernames } = await import('@/services/auth')
const { atenciones } = await import('@/services/atenciones')
const { catalogos } = await import('@/services/catalogos')

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 25, offset: 0, has_more: false })

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

test('la paginación nunca confunde una página incompleta con la última', () => {
  const pagination = usePagination()

  expect(pagination.limit.value).toBe(25)
  expect(pagination.offset.value).toBe(0)
  expect(pagination.currentPage.value).toBe(1)

  pagination.applyPage({ total: 120, has_more: true })
  expect(pagination.total.value).toBe(120)
  expect(pagination.hasMore.value).toBe(true)

  pagination.goToPage(3)
  expect(pagination.offset.value).toBe(50)
  expect(pagination.currentPage.value).toBe(3)

  // Cambiar el tamaño de página vuelve al inicio del listado.
  pagination.changeLimit(10)
  expect(pagination.limit.value).toBe(10)
  expect(pagination.offset.value).toBe(0)

  pagination.reset()
  expect(pagination.offset.value).toBe(0)
  expect(pagination.total.value).toBe(0)
  expect(pagination.hasMore.value).toBe(false)
  expect(pagination.limit.value).toBe(10)
})

test('el catálogo remoto deduplica por clave y conserva lo ya seleccionado', async () => {
  const fetch = vi.fn().mockResolvedValue({
    items: [
      { id: 2, nombre: 'Segunda' },
      { id: 1, nombre: 'Primera' },
    ],
  })
  const scope = effectScope()
  const catalog = scope.run(() =>
    useRemoteCatalog({
      fetch,
      key: (item: { id: number; nombre: string }) => item.id,
    }),
  )!

  await catalog.load('algo', [
    { id: 1, nombre: 'Seleccionada antes' },
    { id: 9, nombre: 'Fuera de la búsqueda' },
  ])

  expect(fetch).toHaveBeenCalledWith('algo')
  // La opción retenida gana en su clave y no se duplica; las demás se agregan.
  expect(catalog.items.value).toEqual([
    { id: 1, nombre: 'Primera' },
    { id: 9, nombre: 'Fuera de la búsqueda' },
    { id: 2, nombre: 'Segunda' },
  ])
  expect(catalog.loading.value).toBe(false)
  expect(catalog.error.value).toBeNull()
  scope.stop()
})

test('el catálogo remoto ignora respuestas viejas y publica errores legibles', async () => {
  let resolveFirst: (value: { items: { id: number }[] }) => void = () => {}
  const fetch = vi
    .fn()
    .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
    .mockResolvedValueOnce({ items: [{ id: 2 }] })
  const scope = effectScope()
  const catalog = scope.run(() => useRemoteCatalog({ fetch, key: (item: { id: number }) => item.id }))!

  const first = catalog.load('vieja')
  const second = catalog.load('nueva')
  await second
  resolveFirst({ items: [{ id: 1 }] })
  await first

  expect(catalog.items.value).toEqual([{ id: 2 }])
  expect(catalog.loading.value).toBe(false)

  fetch.mockRejectedValueOnce(new Error('Servidor ocupado'))
  await catalog.load('otra')
  expect(catalog.error.value).toBe('Servidor ocupado')

  fetch.mockRejectedValueOnce('texto suelto')
  await catalog.load('otra-mas')
  expect(catalog.error.value).toBe('No se pudieron cargar las opciones.')
  scope.stop()
})

test('el catálogo remoto debounce la escritura y no busca con un solo carácter', async () => {
  vi.useFakeTimers()
  const fetch = vi.fn().mockResolvedValue({ items: [] })
  const scope = effectScope()
  const catalog = scope.run(() => useRemoteCatalog({ fetch, key: (item: { id: number }) => item.id }))!

  catalog.search('A')
  await vi.advanceTimersByTimeAsync(300)
  expect(fetch).not.toHaveBeenCalled()
  expect(catalog.loading.value).toBe(false)

  catalog.search('  Hi  ')
  catalog.search('  Hosp')
  await vi.advanceTimersByTimeAsync(300)
  // Solo cuenta el último texto tecleado, ya sin espacios sobrantes.
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch).toHaveBeenCalledWith('Hosp')

  catalog.search('   ')
  await vi.advanceTimersByTimeAsync(300)
  expect(fetch).toHaveBeenLastCalledWith(undefined)
  scope.stop()
})

test('el catálogo remoto deja de buscar cuando su componente muere', async () => {
  vi.useFakeTimers()
  const fetch = vi.fn().mockResolvedValue({ items: [] })
  const scope = effectScope()
  const catalog = scope.run(() => useRemoteCatalog({ fetch, key: (item: { id: number }) => item.id }))!

  catalog.search('Hospital')
  scope.stop()
  await vi.advanceTimersByTimeAsync(500)

  expect(fetch).not.toHaveBeenCalled()
})

test('el paciente seleccionado es estado compartido entre la tabla y la barra lateral', () => {
  const fromTable = usePacienteSeleccionado()
  const fromSidebar = usePacienteSeleccionado()

  expect(fromSidebar.seleccionado.value).toBeNull()
  const start = fromSidebar.dataVersion.value

  fromTable.seleccionar({ id: 5, historia_clinica: 'HC-5' } as never)
  expect(fromSidebar.seleccionado.value).toMatchObject({ id: 5 })

  fromSidebar.notificarCambio()
  expect(fromTable.dataVersion.value).toBe(start + 1)

  fromTable.seleccionar(null)
  expect(fromSidebar.seleccionado.value).toBeNull()
})

test('el directorio de usuarios del login no bloquea el formulario si falla', async () => {
  let state!: ReturnType<typeof useLoginUsernames>
  const Host = defineComponent({
    setup() {
      state = useLoginUsernames()
      return () => null
    },
  })

  vi.mocked(listActiveLoginUsernames).mockResolvedValue(['admin', 'medico.demo'])
  mount(Host)
  await flushPromises()
  expect(state.usernames.value).toEqual(['admin', 'medico.demo'])
  expect(state.unavailable.value).toBe(false)
  expect(state.loading.value).toBe(false)

  vi.mocked(listActiveLoginUsernames).mockRejectedValue(new Error('caído'))
  mount(Host)
  await flushPromises()
  expect(state.unavailable.value).toBe(true)
  expect(state.usernames.value).toEqual([])
  expect(state.loading.value).toBe(false)
})

test('los indicadores nutricionales se piden al servidor solo con paciente y fecha', async () => {
  vi.useFakeTimers()
  const preview = vi.mocked(atenciones.previewNutritionalIndicators)
  const patientId = ref<number | null>(null)
  const attendedAt = ref('')
  const weight = ref<number | null>(null)
  const height = ref<number | null>(null)
  const scope = effectScope()
  const state = scope.run(() =>
    useNutritionalIndicatorsPreview({
      patientId,
      attendedAt,
      weightKg: weight,
      heightCm: height,
    }),
  )!

  await vi.advanceTimersByTimeAsync(400)
  expect(preview).not.toHaveBeenCalled()
  expect(state.indicators.value).toBeNull()

  patientId.value = 5
  attendedAt.value = '2026-09-19'
  weight.value = 60
  height.value = 160
  await flushPromises()
  expect(state.loading.value).toBe(true)

  preview.mockResolvedValue({
    imc: '23.438',
    pe: null,
    te: null,
    pt: null,
    estado: 'OK',
    mensaje: 'Calculado',
    referencia: null,
  })
  await vi.advanceTimersByTimeAsync(300)

  expect(preview).toHaveBeenCalledTimes(1)
  expect(preview).toHaveBeenCalledWith({
    paciente_id: 5,
    fecha_atencion: '2026-09-19',
    peso_kg: 60,
    talla_cm: 160,
  })
  expect(state.indicators.value?.imc).toBe('23.438')
  expect(state.loading.value).toBe(false)
  scope.stop()
})

test('los indicadores nutricionales explican el error y se descartan al cambiar de paciente', async () => {
  vi.useFakeTimers()
  const preview = vi.mocked(atenciones.previewNutritionalIndicators)
  const patientId = ref<number | null>(5)
  const attendedAt = ref('2026-09-19')
  const scope = effectScope()
  const state = scope.run(() =>
    useNutritionalIndicatorsPreview({
      patientId,
      attendedAt,
      weightKg: ref<number | null>(60),
      heightCm: ref<number | null>(160),
    }),
  )!

  preview.mockRejectedValue(new Error('500'))
  await vi.advanceTimersByTimeAsync(300)
  expect(state.error.value).toMatch(/No se pudo calcular los indicadores/)
  expect(state.indicators.value).toBeNull()
  expect(state.loading.value).toBe(false)

  patientId.value = null
  await vi.advanceTimersByTimeAsync(300)
  expect(state.error.value).toBeNull()

  // Una respuesta que llega después de morir el componente no escribe estado.
  patientId.value = 6
  preview.mockImplementation(
    () =>
      new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              imc: null,
              pe: null,
              te: null,
              pt: null,
              estado: 'OK',
              mensaje: '',
              referencia: null,
            }),
          300,
        ),
      ),
  )
  await vi.advanceTimersByTimeAsync(300)
  scope.stop()
  await vi.advanceTimersByTimeAsync(300)
  expect(state.indicators.value).toBeNull()
})

test('el panel de admisión traduce catálogos y ubigeos del paciente', async () => {
  vi.mocked(catalogos.sexos).mockResolvedValue([{ codigo: 'F', nombre: 'Femenino', activo: true }])
  vi.mocked(catalogos.seguros).mockResolvedValue([
    {
      id: 2,
      codigo: 'SIS',
      nombre: 'SIS',
      activo: true,
      codigo_sis: null,
      regimen: 'SIS',
    },
  ])
  vi.mocked(catalogos.etnias).mockResolvedValue([
    { codigo: '2', nombre: 'Mestizo', activo: true },
  ])
  vi.mocked(catalogos.historiasFamiliares).mockResolvedValue(
    page([{ codigo: 'HF-VERDE-01' }]) as never,
  )
  vi.mocked(catalogos.establecimientos).mockResolvedValue(
    page([{ id: 1, nombre: 'CS Prueba', activo: true }]) as never,
  )
  vi.mocked(catalogos.ubigeos).mockResolvedValue(
    page([{ codigo: '040101', departamento: 'AREQUIPA', provincia: 'AREQUIPA', distrito: 'CERCADO', localidad: null }]) as never,
  )

  const scope = effectScope()
  const details = scope.run(() =>
    useAdmissionPatientDetails(() => ({
      id: 1,
      sexo_codigo: 'F',
      seguro_id: 2,
      etnia_codigo: '2',
      ubigeo_residencia_codigo: '040101',
    }) as never),
  )!
  await flushPromises()

  expect(details.sexos.value[0]?.codigo).toBe('F')
  expect(details.seguros.value[0]?.id).toBe(2)
  expect(details.etnias.value[0]?.nombre).toBe('Mestizo')
  expect(details.catalogError.value).toBeNull()
  // Los buscadores remotos se lanzan con el ubigeo del paciente ya cargado.
  expect(catalogos.establecimientos).toHaveBeenCalledWith(undefined, 50, 0)
  expect(catalogos.historiasFamiliares).toHaveBeenCalledWith(undefined, 50, 0)
  expect(catalogos.ubigeos).toHaveBeenCalledWith('040101', 25, 0)
  expect(details.districts.items.value).toHaveLength(1)
  expect(details.familyHistories.items.value).toEqual([{ codigo: 'HF-VERDE-01' }])
  scope.stop()
})

test('el panel de admisión avisa cuando algún catálogo no cargó', async () => {
  vi.mocked(catalogos.sexos).mockResolvedValue([])
  vi.mocked(catalogos.seguros).mockRejectedValue(new Error('500'))
  vi.mocked(catalogos.etnias).mockResolvedValue([])
  vi.mocked(catalogos.historiasFamiliares).mockResolvedValue(page([]) as never)
  vi.mocked(catalogos.establecimientos).mockResolvedValue(page([]) as never)
  vi.mocked(catalogos.ubigeos).mockResolvedValue(page([]) as never)

  const scope = effectScope()
  const details = scope.run(() =>
    useAdmissionPatientDetails(() => ({ id: 1, ubigeo_residencia_codigo: null }) as never),
  )!
  await flushPromises()

  expect(details.catalogError.value).toMatch(/No se cargaron todos los catálogos/)
  // Sin ubigeo del paciente el buscador de distritos queda sin filtro.
  expect(catalogos.ubigeos).toHaveBeenCalledWith(undefined, 25, 0)

  // Reintentar conserva los cambios del usuario: solo vuelve a pedir catálogos.
  vi.mocked(catalogos.seguros).mockResolvedValue([])
  await details.loadCatalogs()
  expect(details.catalogError.value).toBeNull()
  scope.stop()
})
