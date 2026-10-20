import { shallowRef, watch } from 'vue'
import { atenciones, type Attention } from '@/services/atenciones'

/** Consulta histórica independiente del borrador y de la atención recién guardada. */
export function useLaboratoryReview(options: {
  patientId: () => number | null
  officeId: () => number | null
  canRead: () => boolean
}) {
  const opened = shallowRef(false)
  const attention = shallowRef<Attention | null>(null)
  const loading = shallowRef(false)
  const error = shallowRef('')
  let version = 0

  function close(): void {
    ++version
    opened.value = false
    attention.value = null
    loading.value = false
    error.value = ''
  }

  async function open(row: Attention): Promise<void> {
    close()
    if (!options.canRead() || !options.patientId() || !options.officeId()) return
    if (row.paciente_id !== options.patientId() || row.consultorio_id !== options.officeId()) return
    opened.value = true
    loading.value = true
    const request = ++version
    try {
      const result = await atenciones.get(row.id)
      if (request !== version) return
      if (
        result.paciente_id !== options.patientId() ||
        result.consultorio_id !== options.officeId()
      )
        throw new Error('La atención no corresponde al paciente y laboratorio seleccionados.')
      attention.value = result
    } catch (cause) {
      if (request === version)
        error.value = cause instanceof Error ? cause.message : 'No se pudo consultar la atención.'
    } finally {
      if (request === version) loading.value = false
    }
  }

  watch([options.patientId, options.officeId], close, { flush: 'sync' })
  watch(opened, (value) => {
    if (!value) close()
  })
  return { opened, attention, loading, error, open, close }
}
