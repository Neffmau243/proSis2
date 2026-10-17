import { watch, type MaybeRefOrGetter, toValue } from 'vue'
import type { EstablishmentCatalogItem, IdCatalogItem } from '@/services/catalogos'
import type { PatientSisData } from '@/utils/patientSis'
import { isSisInsurance } from '@/utils/patientInsurance'

type DefaultKey = 'sis_diresa' | 'sis_tipo' | 'sis_numero'
type AffiliationDraft = PatientSisData & {
  seguro_id: number | null
  establecimiento_registro_id: number | null
  tipo_documento_codigo: string | null
  numero_documento: string | null
}

/** FUA V.02, p. 19: contract format, distinct from EESS_SIS's plan lookup code. */
export function sisFormatDefault(insurance: IdCatalogItem | undefined, document: string | null) {
  if (!isSisInsurance(insurance)) return null
  if (insurance?.codigo === 'SIS_AFILIACION_TEMPORAL') return 'E'
  if (insurance?.codigo === 'SIS_NRUS') return 'R'
  if (['SIS_GRATUITO', 'SIS_PARA_TODOS'].includes(insurance?.codigo ?? '')) {
    return document === 'DNI' ? '2' : document === 'CE' ? '3' : null
  }
  // Semi-subsidized legacy labels do not distinguish Independiente (9) from
  // Microempresas (8). Generic SIS likewise does not identify a contract format.
  return null
}

/** FUA V.02, p. 20: the document is the number only for subsidized plans. */
function documentAffiliationNumber(
  insurance: IdCatalogItem | undefined,
  document: string | null,
  number: string | null,
  format: string | null,
) {
  if (
    !isSisInsurance(insurance) ||
    !['SIS_GRATUITO', 'SIS_PARA_TODOS'].includes(insurance?.codigo ?? '')
  )
    return null
  const text = number?.trim() ?? ''
  if (document === 'DNI' && format === '2' && /^\d{8}$/.test(text)) return text
  if (document === 'CE' && format === '3' && /^\d{8,9}$/.test(text)) return text
  return null
}

/** Editable suggestions; no residence-based contract or API write. */
export function useSisAffiliationDefaults(options: {
  draft: AffiliationDraft
  insurance: MaybeRefOrGetter<IdCatalogItem | undefined>
  establishment: MaybeRefOrGetter<EstablishmentCatalogItem | undefined>
  enabled?: MaybeRefOrGetter<boolean>
  initialize: boolean
  resetKey?: MaybeRefOrGetter<unknown>
}) {
  const manual = new Set<DefaultKey>()
  const pending = new Map<DefaultKey, string | null | undefined>()
  watch(
    () => {
      const insurance = toValue(options.insurance)
      const site = toValue(options.establishment)
      const format = sisFormatDefault(insurance, options.draft.tipo_documento_codigo)
      const effectiveFormat = manual.has('sis_tipo')
        ? options.draft.sis_tipo
        : options.draft.sis_tipo || format
      return {
        insuranceId: options.draft.seguro_id,
        siteId: options.draft.establecimiento_registro_id,
        document: options.draft.tipo_documento_codigo,
        documentNumber: options.draft.numero_documento,
        inputFormat: options.draft.sis_tipo,
        effectiveFormat,
        diresa: isSisInsurance(insurance) ? (site?.disa_codigo ?? null) : null,
        format,
        number: documentAffiliationNumber(
          insurance,
          options.draft.tipo_documento_codigo,
          options.draft.numero_documento,
          effectiveFormat,
        ),
        resetKey: options.resetKey ? toValue(options.resetKey) : undefined,
        hasSis: isSisInsurance(insurance),
        insuranceLoaded: Boolean(insurance),
        siteLoaded: Boolean(site),
      }
    },
    (next, previous) => {
      if (previous && next.resetKey !== previous.resetKey) {
        manual.clear()
        pending.clear()
        return
      }
      if (!next.hasSis) {
        if (next.insuranceId != null && !next.insuranceLoaded) {
          if (next.insuranceId !== previous?.insuranceId) {
            pending.set('sis_diresa', previous?.diresa)
            pending.set('sis_tipo', previous?.format)
            pending.set('sis_numero', previous?.number)
          }
          return
        }
        if (next.insuranceId !== previous?.insuranceId) manual.clear()
        pending.clear()
        return
      }
      if (options.enabled !== undefined && !toValue(options.enabled)) return
      const insuranceChanged = next.insuranceId !== previous?.insuranceId
      const numberChanged =
        next.documentNumber !== previous?.documentNumber ||
        next.inputFormat !== previous?.inputFormat
      const selectorsChanged =
        insuranceChanged ||
        next.siteId !== previous?.siteId ||
        next.document !== previous?.document ||
        numberChanged
      // Loading a saved patient's catalogs must not change its confirmed codes.
      if (!options.initialize && !selectorsChanged && !pending.size) return
      const defaults: [DefaultKey, string | null, string | null | undefined, boolean][] = [
        [
          'sis_diresa',
          next.diresa,
          previous?.diresa,
          insuranceChanged || next.siteId !== previous?.siteId,
        ],
        [
          'sis_tipo',
          next.format,
          previous?.format,
          insuranceChanged || next.document !== previous?.document,
        ],
        [
          'sis_numero',
          next.number,
          previous?.number,
          insuranceChanged || next.document !== previous?.document || numberChanged,
        ],
      ]
      for (const [key, suggestion, priorSuggestion, relevantChange] of defaults) {
        if (manual.has(key)) {
          pending.delete(key)
          continue
        }
        if (!options.initialize && !relevantChange && !pending.has(key)) continue
        if (
          !options.initialize &&
          key === 'sis_tipo' &&
          !insuranceChanged &&
          !options.draft.sis_tipo &&
          !options.draft.sis_numero &&
          !next.number
        )
          continue
        if (key === 'sis_diresa' && next.siteId != null && !next.siteLoaded) {
          if (!pending.has(key)) pending.set(key, priorSuggestion)
          continue
        }
        const previousDefault = pending.has(key) ? pending.get(key) : priorSuggestion
        pending.delete(key)
        const current = options.draft[key]
        // An explicit plan change starts a different format selection; a stored
        // old format is not a manual correction made in this editing session.
        if (key === 'sis_tipo' && insuranceChanged) {
          options.draft[key] = suggestion
          continue
        }
        // Preserve a different saved accreditation (e.g. affiliation from Puno
        // while attending in Arequipa), and explicit corrections in this draft.
        if (!current || (previousDefault != null && current === previousDefault)) {
          options.draft[key] = suggestion
        }
      }
    },
  )
  function markManual(changes: Partial<PatientSisData>) {
    for (const key of ['sis_diresa', 'sis_tipo', 'sis_numero'] as const) {
      if (key in changes) manual.add(key)
    }
  }
  return { markManual }
}
