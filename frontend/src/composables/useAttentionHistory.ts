import { onScopeDispose, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { atenciones, type Attention } from '@/services/atenciones'

/** Recent encounters by default; the complete history is loaded only on request. */
export function useAttentionHistory(patientId: MaybeRefOrGetter<number | null>) {
  const entries = ref<Attention[]>([])
  const loading = shallowRef(false)
  const error = shallowRef<string | null>(null)
  const allLoaded = shallowRef(false)
  let request = 0

  async function load(all: boolean): Promise<void> {
    const current = ++request
    const id = toValue(patientId)
    error.value = null
    if (id === null) {
      entries.value = []
      allLoaded.value = false
      loading.value = false
      return
    }
    loading.value = true
    try {
      const result: Attention[] = []
      if (all) {
        let offset = 0
        for (;;) {
          const page = await atenciones.search({ paciente_id: id, limit: 100, offset })
          if (current !== request) return
          result.push(...page.items)
          if (!page.has_more || page.items.length === 0) break
          offset += page.limit
        }
      } else {
        result.push(...(await atenciones.listByPatient(id)))
      }
      if (current !== request) return
      entries.value = result
      allLoaded.value = all
    } catch (cause) {
      if (current === request) {
        error.value =
          cause instanceof Error
            ? cause.message
            : 'No se pudo cargar el historial. Pulse Refrescar para reintentar.'
      }
    } finally {
      if (current === request) loading.value = false
    }
  }

  watch(
    () => toValue(patientId),
    () => {
      entries.value = []
      allLoaded.value = false
      void load(false)
    },
    { immediate: true, flush: 'sync' },
  )

  onScopeDispose(() => {
    request += 1
  })

  return {
    entries,
    loading,
    error,
    allLoaded,
    refresh: () => load(allLoaded.value),
    showAll: () => load(true),
    showRecent: () => load(false),
  }
}
