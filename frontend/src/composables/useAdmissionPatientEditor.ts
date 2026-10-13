import { computed, reactive, shallowRef, toValue, watch, type MaybeRefOrGetter } from 'vue'

import type { Patient, PatientUpdatePayload } from '../services/pacientes'
import {
  buildPatientPatch,
  createPatientDraft,
  validatePatientDraft,
  type PatientDraftErrors,
} from '../utils/patientDraft.ts'

export function useAdmissionPatientEditor(options: {
  patient: MaybeRefOrGetter<Patient | null>
  canEdit: MaybeRefOrGetter<boolean>
  blocked: MaybeRefOrGetter<boolean>
  update: (id: number, payload: PatientUpdatePayload) => Promise<Patient>
  onSaved: (patient: Patient) => void
}) {
  const source = () => toValue(options.patient)
  const baseline = shallowRef(createPatientDraft(source()))
  const draft = reactive({ ...baseline.value })
  const saving = shallowRef(false)
  const error = shallowRef<string | null>(null)
  const fieldErrors = shallowRef<PatientDraftErrors>({})
  const patch = computed(() => buildPatientPatch(baseline.value, draft))
  const dirty = computed(() => Object.keys(patch.value).length > 0)

  function reset() {
    baseline.value = createPatientDraft(source())
    Object.assign(draft, baseline.value)
    fieldErrors.value = {}
    error.value = null
  }

  // Related-record updates must not erase an unfinished patient draft.
  watch(source, (patient, previous) => {
    if (patient?.id !== previous?.id || (!dirty.value && !saving.value)) reset()
  })

  async function save(): Promise<void> {
    const patient = source()
    if (!patient) return
    if (saving.value || toValue(options.blocked) || !toValue(options.canEdit) || !dirty.value)
      return
    const now = new Date()
    const today = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
      .toISOString()
      .slice(0, 10)
    fieldErrors.value = validatePatientDraft(draft, today, baseline.value)
    if (Object.keys(fieldErrors.value).length) {
      error.value = 'Revise los campos indicados antes de guardar.'
      return
    }
    saving.value = true
    error.value = null
    try {
      const updated = await options.update(patient.id, patch.value)
      baseline.value = createPatientDraft(updated)
      Object.assign(draft, baseline.value)
      options.onSaved(updated)
    } catch (cause) {
      // Preserve the draft so a failed request can be corrected/retried.
      error.value =
        cause instanceof Error
          ? cause.message
          : 'No se pudieron guardar los cambios. Intente nuevamente.'
    } finally {
      saving.value = false
    }
  }

  return { draft, saving, error, fieldErrors, dirty, save, reset }
}
