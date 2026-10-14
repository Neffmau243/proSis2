import { onBeforeUnmount, ref, watch } from 'vue'
import { defaultFuaLayout, FUA_LAYOUT_KEY, parseFuaLayout } from '@/utils/fuaPrint'

/** One printer geometry per browser origin, shared by all accounts and patients. */
export function useFuaCalibration(isOpen: () => boolean) {
  const layout = ref(defaultFuaLayout())
  const storageError = ref('')
  const saved = ref(false)
  let restoring = false

  function restore(): void {
    restoring = true
    try {
      const raw = localStorage.getItem(FUA_LAYOUT_KEY)
      layout.value = raw ? parseFuaLayout(raw) : defaultFuaLayout()
      saved.value = Boolean(raw)
      storageError.value = ''
      // Persist the normalized reference once, keeping the saved coordinates.
      if (raw && raw !== JSON.stringify(layout.value)) save()
    } catch {
      saved.value = false
      storageError.value =
        'No se pudo leer la calibración guardada. Importe una copia o guarde una calibración revisada.'
    } finally {
      restoring = false
    }
  }

  function save(): boolean {
    try {
      localStorage.setItem(
        FUA_LAYOUT_KEY,
        JSON.stringify(parseFuaLayout(JSON.stringify(layout.value))),
      )
      saved.value = true
      storageError.value = ''
      return true
    } catch {
      saved.value = false
      storageError.value =
        'No se pudo guardar la calibración. Exporte una copia y revise el almacenamiento del navegador.'
      return false
    }
  }

  watch(
    isOpen,
    (open) => {
      if (open) restore()
    },
    { immediate: true },
  )
  // Synchronous persistence also covers closing the dialog immediately after an edit.
  watch(
    layout,
    () => {
      if (!restoring) save()
    },
    { deep: true, flush: 'sync' },
  )

  function changed(): void {
    layout.value.calibrated = false
  }
  function exportLayout(): void {
    const geometry = parseFuaLayout(JSON.stringify(layout.value))
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(geometry, null, 2)], { type: 'application/json' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = 'calibracion-fua.json'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  async function importLayout(file: File): Promise<void> {
    try {
      if (file.size > 100_000) throw new Error('El archivo supera 100 KB.')
      layout.value = { ...parseFuaLayout(await file.text()), calibrated: false }
      // Another browser can have a different printer/driver: keep positions,
      // require physical confirmation once in the destination environment.
    } catch {
      storageError.value =
        'No se pudo importar la calibración. Use el archivo JSON exportado desde este módulo.'
    }
  }
  function storageChanged(event: StorageEvent): void {
    if (event.key === FUA_LAYOUT_KEY || event.key === null) restore()
  }
  window.addEventListener('storage', storageChanged)
  onBeforeUnmount(() => window.removeEventListener('storage', storageChanged))

  return {
    layout,
    storageError,
    saved,
    save,
    changed,
    exportLayout,
    importLayout,
  }
}
