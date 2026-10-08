import type { PatientSisData } from './patientSis.ts'

export function isSisInsurance(insurance?: { codigo: string; regimen?: string | null }): boolean {
  return insurance?.regimen === 'SIS' || insurance?.codigo === 'SIS'
}

/**
 * El flujo histórico guarda el tipo SIS con dos dígitos, mientras que el
 * catálogo ETLSIS lo identifica con tres. Ejemplo: 005 (NRUS) -> 05.
 */
export function sisTypeFromInsurance(
  insurance?: { codigo: string; regimen?: string | null; codigo_sis?: string | null },
): string | null {
  if (!isSisInsurance(insurance) || !insurance?.codigo_sis?.match(/^\d{3}$/)) return null
  return insurance.codigo_sis.slice(-2)
}

/** Deliberately preserve ethnicity; it is not an insurance attribute. */
export function clearSisAffiliation(patient: Partial<PatientSisData>): void {
  patient.sis_diresa = null
  patient.sis_tipo = null
  patient.sis_numero = null
  patient.sis_secuencia = null
}
