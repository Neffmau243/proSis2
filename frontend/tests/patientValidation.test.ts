import { expect, test } from 'vitest'
import { documentProblem } from '../src/utils/patientDocument'
import { clearSisAffiliation, isSisInsurance } from '../src/utils/patientInsurance'
import { createPatientDraft, validatePatientDraft } from '../src/utils/patientDraft'
import { aPatient } from './fixtures/patient'

test.each([
  ['DNI', '00000001', true],
  ['DNI', 'PASUI000033', false],
  ['DNI', '1234567', false],
  ['DNI', '123456789', false],
  ['DNI', '１２３４５６７８', false],
  ['CE', '000123456', true],
  ['CE', 'N12345678', true],
  ['PAS', 'PASUI000033', true],
  ['PAS', 'A 123', false],
  ['DE', 'AB-123/45', true],
  ['OTRO', 'TMP.001', true],
  ['OTRO', '<script>', false],
  ['PAS', 'A'.repeat(31), false],
])('document %s %s valid=%s', (kind, number, valid) => {
  expect(documentProblem(kind as string, number as string) === null).toBe(valid)
})

test('switching passport to DNI revalidates the existing number before saving', () => {
  const draft = createPatientDraft(
    aPatient({ tipo_documento_codigo: 'PAS', numero_documento: 'PASUI000033' }),
  )
  expect(validatePatientDraft(draft, '2026-10-01').numero_documento).toBeUndefined()
  draft.tipo_documento_codigo = 'DNI'
  expect(validatePatientDraft(draft, '2026-10-01').numero_documento).toContain('8 dígitos')
  draft.numero_documento = '00123456'
  expect(validatePatientDraft(draft, '2026-10-01').numero_documento).toBeUndefined()
})

test('SIS family uses the catalog regime; clearing preserves ethnicity', () => {
  expect(isSisInsurance({ codigo: 'SIS_GRATUITO', regimen: 'SIS' })).toBe(true)
  expect(isSisInsurance({ codigo: 'SIS' })).toBe(true)
  expect(isSisInsurance({ codigo: 'ESSALUD', regimen: 'ESSALUD' })).toBe(false)
  expect(isSisInsurance()).toBe(false)
  const draft = {
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '00000001',
    sis_secuencia: '01',
    etnia_codigo: '58',
  }
  clearSisAffiliation(draft)
  expect(draft).toEqual({
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
    sis_secuencia: null,
    etnia_codigo: '58',
  })
})
