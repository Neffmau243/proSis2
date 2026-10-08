import { computed, onScopeDispose, shallowRef, toValue, watch, type MaybeRefOrGetter } from 'vue'
import {
  catalogos,
  type CodeCatalogItem,
  type FamilyHistoryCatalogItem,
  type InsuranceCatalogItem,
  type LocalidadCatalogItem,
} from '@/services/catalogos'
import type { Patient } from '@/services/pacientes'
import { useRemoteCatalog } from '@/composables/useRemoteCatalog'

/** Read-only catalog labels for the admission patient panel. */
export function useAdmissionPatientDetails(patient: MaybeRefOrGetter<Patient>) {
  const source = computed(() => toValue(patient))
  const sexos = shallowRef<CodeCatalogItem[]>([])
  const seguros = shallowRef<InsuranceCatalogItem[]>([])
  const etnias = shallowRef<CodeCatalogItem[]>([])
  const catalogError = shallowRef<string | null>(null)
  const localities = shallowRef<LocalidadCatalogItem[]>([])
  const localitiesLoading = shallowRef(false)
  const localitiesError = shallowRef<string | null>(null)
  let version = 0
  const establishments = useRemoteCatalog({
    fetch: (query) => catalogos.establecimientos(query, 50, 0),
    key: (item) => item.id,
  })
  const districts = useRemoteCatalog({
    fetch: (query) => catalogos.ubigeos(query, 25, 0),
    key: (item) => item.codigo,
  })
  const familyHistories = useRemoteCatalog<FamilyHistoryCatalogItem>({
    fetch: (query) => catalogos.historiasFamiliares(query, 50, 0),
    key: (item) => item.codigo,
  })

  async function loadCatalogs(): Promise<void> {
    const request = ++version
    catalogError.value = null
    const results = await Promise.allSettled([
      catalogos.sexos().then((items) => {
        if (request === version) sexos.value = items
      }),
      catalogos.seguros().then((items) => {
        if (request === version) seguros.value = items
      }),
      catalogos.etnias().then((items) => {
        if (request === version) etnias.value = items
      }),
    ])
    if (request === version && results.some((result) => result.status === 'rejected')) {
      catalogError.value =
        'No se cargaron todos los catálogos. Puede reintentar y conservar sus cambios.'
    }
  }
  async function loadLocalities(ubigeo: string | null): Promise<void> {
    if (!ubigeo) {
      localities.value = []
      localitiesError.value = null
      return
    }
    localitiesLoading.value = true
    localitiesError.value = null
    try {
      localities.value = (await catalogos.localidades(ubigeo, undefined, 100, 0)).items
    } catch {
      localities.value = []
      localitiesError.value = 'No se cargaron las localidades del distrito.'
    } finally {
      localitiesLoading.value = false
    }
  }

  void loadCatalogs()
  void establishments.load()
  void familyHistories.load()
  watch(
    () => source.value.ubigeo_residencia_codigo,
    (code) => {
      void districts.load(code || undefined)
    },
    { immediate: true },
  )
  onScopeDispose(() => {
    version += 1
  })

  return {
    sexos,
    seguros,
    etnias,
    catalogError,
    loadCatalogs,
    establishments,
    districts,
    familyHistories,
    localities,
    localitiesLoading,
    localitiesError,
    loadLocalities,
  }
}
