import type { PatientSisData } from './patientSis.ts'

export function isSisInsurance(insurance?: { codigo: string; regimen?: string | null }): boolean {
  return insurance?.regimen === 'SIS' || insurance?.codigo === 'SIS'
}

/** Deliberately preserve ethnicity; it is not an insurance attribute. */
export function clearSisAffiliation(patient: Partial<PatientSisData>): void {
  patient.sis_diresa = null
  patient.sis_tipo = null
  patient.sis_numero = null
  patient.sis_secuencia = null
}
