import { expect, test } from 'vitest'

import { calculateCalendarAge, formatCalendarAge } from '../src/utils/calendarAge'
import { CARE_GROUP_LABELS, careGroupLabel } from '../src/utils/careGroup'
import { buildFuaDraft } from '../src/utils/fuaDraft'
import { normalizeNumericPassword, passwordPattern } from '../src/utils/password'
import { emptyPatientSis, patientSisContractFields } from '../src/utils/patientSis'
import { PREGNANCY_TYPES, pregnancyTypeLabel } from '../src/utils/pregnancy'
import { emptyFuaInput } from '../src/utils/fuaPrint'
import type { Patient } from '../src/services/pacientes'
import type { FuaPrintInput } from '../src/types/fua'

test('la edad se calcula por calendario y no por diferencias de milisegundos', () => {
  expect(calculateCalendarAge('1990-05-10', '2026-09-20')).toEqual({
    years: 36,
    months: 4,
    days: 10,
  })
  // Mismo día: edad exacta sin días negativos.
  expect(calculateCalendarAge('2026-09-20', '2026-09-20')).toEqual({
    years: 0,
    months: 0,
    days: 0,
  })
  // El día del mes aún no llegó: se descuenta un mes y se cuentan los días.
  expect(calculateCalendarAge('1990-05-20', '2026-09-10')).toEqual({
    years: 36,
    months: 3,
    days: 21,
  })
  // Un formato ISO con hora no debe desplazar el día por zona horaria.
  expect(calculateCalendarAge('1990-05-10T23:30:00', '2026-05-10T00:10:00Z')).toEqual({
    years: 36,
    months: 0,
    days: 0,
  })
})

test('quien nace a fin de mes envejece al último día disponible del mes', () => {
  // 31 de enero -> 1 de marzo: un mes cumplido (28 de febrero) y un día.
  expect(calculateCalendarAge('2000-01-31', '2026-03-01')).toEqual({
    years: 26,
    months: 1,
    days: 1,
  })
  // 29 de febrero en un año no bisiesto cumple años el 28 de febrero.
  expect(calculateCalendarAge('2000-02-29', '2026-02-28')).toEqual({
    years: 26,
    months: 0,
    days: 0,
  })
  // Y el día siguiente ya es un día más.
  expect(calculateCalendarAge('2000-02-29', '2026-03-01')).toEqual({
    years: 26,
    months: 0,
    days: 1,
  })
})

test('fechas inválidas, futuras o incompletas no producen una edad', () => {
  expect(calculateCalendarAge('', '2026-09-20')).toBeNull()
  expect(calculateCalendarAge('1990-13-01', '2026-09-20')).toBeNull()
  expect(calculateCalendarAge('2026-02-30', '2026-09-20')).toBeNull()
  expect(calculateCalendarAge('2027-01-01', '2026-09-20')).toBeNull()
  expect(calculateCalendarAge('1990-05-10', 'no-es-fecha')).toBeNull()
  expect(calculateCalendarAge('1990-05-10', new Date('invalid'))).toBeNull()
  expect(formatCalendarAge('2027-01-01', '2026-09-20')).toBeNull()
})

test('la edad legible usa años, meses y días en ese orden', () => {
  expect(formatCalendarAge('1990-05-10', '2026-09-20')).toBe('36 años, 4 meses y 10 días')
  expect(formatCalendarAge('2026-09-19', '2026-09-20')).toBe('0 años, 0 meses y 1 días')
  expect(formatCalendarAge('1990-05-10', new Date(2026, 8, 20))).toBe(
    '36 años, 4 meses y 10 días',
  )
})

test('el grupo de atención muestra su etiqueta y cae al código si es desconocido', () => {
  expect(careGroupLabel('GESTANTES')).toBe('Gestantes')
  expect(careGroupLabel('PUERPERAS')).toBe('Puérperas')
  expect(careGroupLabel('NINOS_ADOLESCENTES_ADULTOS_MAYORES')).toBe(
    'Niños, adolescentes, adultos y adultos mayores',
  )
  // Un código nuevo del backend debe verse tal cual, nunca vacío.
  expect(careGroupLabel('ADOLESCENTES')).toBe('ADOLESCENTES')
  expect(careGroupLabel(null)).toBe('—')
  expect(careGroupLabel(undefined)).toBe('—')
  expect(careGroupLabel('')).toBe('—')
  expect(Object.keys(CARE_GROUP_LABELS)).toEqual([
    'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    'GESTANTES',
    'PUERPERAS',
  ])
})

test('el tipo de embarazo solo se muestra para códigos conocidos', () => {
  expect(pregnancyTypeLabel('UNICO')).toBe('Embarazo único')
  expect(pregnancyTypeLabel('MULTIPLE')).toBe('Embarazo múltiple')
  expect(pregnancyTypeLabel('TRIPLE')).toBe('TRIPLE')
  expect(pregnancyTypeLabel(null)).toBe('—')
  expect(PREGNANCY_TYPES.map((type) => type.value)).toEqual(['UNICO', 'MULTIPLE'])
})

test('la contraseña se limita a ocho dígitos descartando cualquier otro carácter', () => {
  expect(normalizeNumericPassword('12ab34')).toBe('1234')
  expect(normalizeNumericPassword('12345678901')).toBe('12345678')
  expect(normalizeNumericPassword(' - 1 2 ')).toBe('12')
  expect(normalizeNumericPassword('')).toBe('')
  expect(passwordPattern.test('12345678')).toBe(true)
  expect(passwordPattern.test('1234567')).toBe(false)
  expect(passwordPattern.test('1234567a')).toBe(false)
})

const patient: Patient = {
  id: 1,
  codclie_legacy: null,
  historia_clinica: 'HC-1',
  historia_familiar: null,
  tipo_documento_codigo: 'DNI',
  numero_documento: '12345678',
  fecha_inscripcion: null,
  fecha_nacimiento: '1990-05-10',
  apellido_paterno: 'Quispe',
  apellido_materno: 'Mamani',
  primer_nombre: 'Ana',
  otros_nombres: null,
  sexo_codigo: 'F',
  ubigeo_residencia_codigo: '040101',
  distrito_residencia: 'Arequipa',
  localidad: null,
  localidad_id: null,
  direccion: null,
  establecimiento_registro_id: null,
  seguro_id: null,
  telefono_principal: null,
  condicion: null,
  estado: true,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  responsables: [],
  riesgos: [],
}

const encounter = {
  fecha_atencion: '2026-09-19T09:05:00',
  modalidad_atencion_codigo: 'AMBULATORIA' as const,
  peso_kg: 60,
  talla_cm: 160,
  presion_sistolica: 120,
  presion_diastolica: 80,
  perimetro_abdominal_cm: 80,
  grupo_atencion_codigo: 'GESTANTES' as const,
  fecha_probable_parto: '2027-01-15',
}

test('el borrador del FUA copia el paciente y calcula solo lo que puede calcular', () => {
  const draft = buildFuaDraft(patient, encounter, emptyFuaInput(), undefined, undefined)

  expect(draft.version).toBe(1)
  expect(draft.tipo_documento).toBe('DNI')
  expect(draft.tdi).toBe('2')
  expect(draft.numero_documento).toBe('12345678')
  expect(draft.apellido_paterno).toBe('Quispe')
  expect(draft.fecha_atencion).toBe('2026-09-19')
  expect(draft.hora_atencion).toBe('09:05:00')
  expect(draft.imc).toBe('23.438')
  expect(draft.grupo_atencion_codigo).toBe('GESTANTES')
  expect(draft.fecha_probable_parto).toBe('2027-01-15')
  // Sin establecimiento ni profesional no se inventa ningún identificador.
  expect(draft.ipress_nombre).toBe('')
  expect(draft.profesional_nombre).toBe('')
  expect(draft.profesional_colegiatura).toBeNull()
  expect(draft.profesional_documento).toBeNull()
  expect(draft.codigo_renipress).toBeNull()
})

test('el borrador de la puérpera lleva la fecha real del parto y no la FPP', () => {
  const draft = buildFuaDraft(patient, {
    ...encounter, grupo_atencion_codigo: 'PUERPERAS', fecha_probable_parto: null, fecha_parto: '2026-09-20',
  }, emptyFuaInput(), undefined, undefined)

  expect(draft.fecha_parto).toBe('2026-09-20')
  expect(draft.fecha_probable_parto).toBeNull()
})

test('el RENIPRESS solo se toma de un código RENAES de ocho dígitos', () => {
  const establishment = {
    id: 5,
    codigo_renaes: '00001234',
    codigo_ideess: null,
    disa_codigo: null,
    nombre: 'CS Prueba',
    abreviatura: null,
    activo: true,
  }
  const withRenaes = buildFuaDraft(
    patient,
    encounter,
    emptyFuaInput(),
    establishment,
    {
      id: 9,
      nombre_completo: 'Dra. Prueba',
      colegiatura: 'CMP-1',
      activo: true,
    },
  )
  expect(withRenaes.codigo_renipress).toBe('00001234')
  expect(withRenaes.ipress_nombre).toBe('CS Prueba')
  expect(withRenaes.profesional_colegiatura).toBe('CMP-1')

  const shortRenaes = buildFuaDraft(
    patient,
    encounter,
    emptyFuaInput(),
    { ...establishment, codigo_renaes: '123' },
    undefined,
  )
  expect(shortRenaes.codigo_renipress).toBeNull()
})

test('lo que el formulario escribe en el FUA gana sobre lo deducido', () => {
  const supplement: FuaPrintInput = {
    ...emptyFuaInput(),
    tipo_atencion: 'REFERENCIA',
    codigo_renipress: '99999999',
  }
  const draft = buildFuaDraft(
    patient,
    encounter,
    supplement,
    {
      id: 5,
      codigo_renaes: '00001234',
      codigo_ideess: null,
      disa_codigo: null,
      nombre: 'CS Prueba',
      abreviatura: null,
      activo: true,
    },
    undefined,
  )

  expect(draft.tipo_atencion).toBe('REFERENCIA')
  expect(draft.codigo_renipress).toBe('99999999')
})

test('sin medidas no hay IMC y sin grupo declarado se asume la población general', () => {
  const draft = buildFuaDraft(
    { ...patient, tipo_documento_codigo: 'CE' },
    { ...encounter, peso_kg: null, talla_cm: null, grupo_atencion_codigo: undefined },
    emptyFuaInput(),
  )

  expect(draft.imc).toBeNull()
  expect(draft.peso_kg).toBeNull()
  expect(draft.tdi).toBe('3')
  expect(draft.grupo_atencion_codigo).toBe('NINOS_ADOLESCENTES_ADULTOS_MAYORES')

  const otherDocument = buildFuaDraft(
    { ...patient, tipo_documento_codigo: 'PASAPORTE' },
    encounter,
    emptyFuaInput(),
  )
  expect(otherDocument.tdi).toBeNull()
})

test('el contrato SIS declarado coincide con los campos que el formulario envía', () => {
  expect(patientSisContractFields.map((field) => field.key)).toEqual([
    'sis_diresa',
    'sis_tipo',
    'sis_numero',
    'sis_secuencia',
  ])
  expect(Object.keys(emptyPatientSis())).toEqual([
    'sis_diresa',
    'sis_tipo',
    'sis_numero',
    'sis_secuencia',
    'etnia_codigo',
  ])
  expect(Object.values(emptyPatientSis()).every((value) => value === null)).toBe(true)
})
