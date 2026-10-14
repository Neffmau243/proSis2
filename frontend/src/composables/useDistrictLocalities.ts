import { onScopeDispose, shallowRef } from 'vue'
import { catalogos, type LocalidadCatalogItem } from '@/services/catalogos'
import { allCatalogPages } from '@/services/catalogPages'

/** Clear old district options immediately and discard requests that finish late. */
export function useDistrictLocalities() {
  const items = shallowRef<LocalidadCatalogItem[]>([])
  const loading = shallowRef(false)
  const error = shallowRef<string | null>(null)
  let version = 0

  async function load(ubigeo: string | null): Promise<void> {
    const request = ++version
    items.value = []
    error.value = null
    loading.value = Boolean(ubigeo)
    if (!ubigeo) return
    try {
      const result = await allCatalogPages((offset) =>
        catalogos.localidades(ubigeo, undefined, 100, offset),
      )
      if (request === version) items.value = result
    } catch {
      if (request === version) error.value = 'No se cargaron las localidades del distrito.'
    } finally {
      if (request === version) loading.value = false
    }
  }

  onScopeDispose(() => { version += 1 })
  return { items, loading, error, load }
}
