import type { Patient, PatientUpdatePayload } from '../services/pacientes'
import { patientSisErrors, patientSisFields } from './patientSis.ts'
import { documentProblem } from './patientDocument.ts'
import { familyHistoryProblem } from './familyHistory.ts'

/** General controls; the SIS contract is grouped directly below the insurance selector. */
export const patientFields = [
  { key: 'historia_clinica', label: 'N.° H. clínica', kind: 'text', max: 255 },
  { key: 'historia_familiar', label: 'Historia familiar', kind: 'text' },
  { key: 'tipo_documento_codigo', label: 'Tipo documento', kind: 'select', required: true },
  { key: 'numero_documento', label: 'N.° documento', kind: 'text', max: 30, required: true },
  { key: 'sufijo_documento', label: 'Sufijo documento (origen)', kind: 'text', max: 10 },
  { key: 'fecha_nacimiento', label: 'Fecha nacimiento', kind: 'date', required: true },
  { key: 'apellido_paterno', label: 'Apellido paterno', kind: 'text', max: 100 },
  { key: 'apellido_materno', label: 'Apellido materno', kind: 'text', max: 100 },
  { key: 'primer_nombre', label: 'Primer nombre', kind: 'text', max: 100 },
  { key: 'otros_nombres', label: 'Otros nombres', kind: 'text', max: 150 },
  { key: 'sexo_codigo', label: 'Sexo', kind: 'select' },
  { key: 'ubigeo_residencia_codigo', label: 'Distrito', kind: 'select' },
  // La localidad se elige del catálogo SIS del distrito; su nombre se copia al
  // campo de texto ``localidad`` para conservarlo y solo se define su código.
  { key: 'localidad_id', label: 'Localidad', kind: 'select' },
  { key: 'direccion', label: 'Dirección', kind: 'text', max: 300 },
  { key: 'establecimiento_registro_id', label: 'Establecimiento', kind: 'select' },
  { key: 'seguro_id', label: 'Seguro', kind: 'select' },
  { key: 'telefono_principal', label: 'Teléfono', kind: 'text', max: 30 },
  { key: 'fecha_inscripcion', label: 'Fecha inscripción', kind: 'date' },
  { key: 'condicion', label: 'Condición', kind: 'select' },
] as const satisfies ReadonlyArray<{
  key: keyof PatientUpdatePayload
  label: string
  kind: 'text' | 'date' | 'select'
  max?: number
  required?: boolean
}>

export type PatientField = (typeof patientFields)[number]
// ``localidad`` no se edita directamente: lo alimenta el catálogo SIS.
const localityNameField = { key: 'localidad', label: 'Localidad', kind: 'text', max: 150 } as const
const editableFields = [...patientFields, localityNameField, ...patientSisFields] as const
export type PatientFieldKey = (typeof editableFields)[number]['key']
export type PatientDraft = { [K in PatientFieldKey]: Exclude<PatientUpdatePayload[K], undefined> }
export type PatientDraftErrors = Partial<Record<PatientFieldKey, string>>

function normalized(value: string | number | null | undefined): string | number | null {
  return typeof value === 'string' ? value.trim() || null : (value ?? null)
}

export function createPatientDraft(patient: Patient): PatientDraft {
  return Object.fromEntries(
    editableFields.map(({ key }) => [key, patient[key] ?? null]),
  ) as PatientDraft
}

/** Compare only whitelisted fields, preserving explicit nulls and omitting unchanged data. */
export function buildPatientPatch(
  baseline: PatientDraft,
  draft: PatientDraft,
): PatientUpdatePayload {
  return Object.fromEntries(
    editableFields
      .filter(({ key }) => normalized(draft[key]) !== normalized(baseline[key]))
      .map(({ key }) => [key, normalized(draft[key])]),
  ) as PatientUpdatePayload
}

export function validatePatientDraft(
  draft: PatientDraft,
  today: string,
  baseline?: PatientDraft,
): PatientDraftErrors {
  const errors: PatientDraftErrors = { ...patientSisErrors(draft) }
  if (draft.sufijo_documento && !/^[A-Za-z0-9]{1,10}$/.test(draft.sufijo_documento.trim()))
    errors.sufijo_documento = 'Use de 1 a 10 letras o dígitos; deje vacío si no lo conoce.'
  for (const field of patientFields) {
    const value = normalized(draft[field.key])
    if ('required' in field && field.required && value === null) {
      errors[field.key] = 'Complete este campo.'
    } else if ('max' in field && typeof value === 'string' && value.length > field.max) {
      errors[field.key] = `Máximo ${field.max} caracteres.`
    }
    if (field.kind === 'date' && value) {
      const text = String(value)
      const parsed = new Date(`${text}T00:00:00Z`)
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(text) ||
        Number.isNaN(parsed.getTime()) ||
        parsed.toISOString().slice(0, 10) !== text
      ) {
        errors[field.key] = 'Ingrese una fecha válida.'
      } else if (text > today) {
        errors[field.key] = 'La fecha no puede estar en el futuro.'
      }
    }
  }
  if (draft.fecha_inscripcion && draft.fecha_nacimiento > draft.fecha_inscripcion) {
    errors.fecha_nacimiento = 'Debe ser anterior o igual a la inscripción.'
  }
  if (draft.localidad_id && !draft.ubigeo_residencia_codigo) {
    errors.localidad_id = 'Seleccione primero el distrito.'
  } else if (
    normalized(draft.localidad) &&
    normalized(draft.localidad) === draft.ubigeo_residencia_codigo
  ) {
    errors.localidad_id = 'La localidad debe ser un nombre, no el código de ubigeo.'
  }
  // A legacy invalid number must not block unrelated corrections. The API uses
  // the same rule: revalidate the complete pair whenever either part changes.
  const documentChanged =
    !baseline ||
    normalized(draft.tipo_documento_codigo) !== normalized(baseline.tipo_documento_codigo) ||
    normalized(draft.numero_documento) !== normalized(baseline.numero_documento)
  const documentError = documentChanged
    ? documentProblem(draft.tipo_documento_codigo, draft.numero_documento)
    : null
  if (documentError) errors.numero_documento = documentError
  const familyHistoryChanged =
    !baseline ||
    normalized(draft.historia_familiar) !== normalized(baseline.historia_familiar)
  const familyHistoryError = familyHistoryChanged
    ? familyHistoryProblem(draft.historia_familiar)
    : null
  if (familyHistoryError) errors.historia_familiar = familyHistoryError
  return errors
}
