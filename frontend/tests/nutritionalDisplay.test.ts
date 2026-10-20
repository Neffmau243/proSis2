import { expect, test } from 'vitest'
import {
  nutritionalBmiSummary,
  nutritionalHistoryValue,
  nutritionalRows,
  nutritionalTableRows,
  nutritionalLimits,
  nutritionalStatus,
} from '@/utils/nutritionalDisplay'
import type { NutritionalIndicatorsPreview } from '@/services/atenciones'

const result: NutritionalIndicatorsPreview = {
  imc: '23.438',
  pe: null,
  te: null,
  pt: null,
  estado: 'CALCULADO',
  mensaje: '',
  referencia: '',
  grupo_referencia: 'ADULTO',
  diagnostico_imc: 'Normal',
}

test('la explicación de resultados conserva los límites y distingue falta de datos', () => {
  expect(nutritionalLimits(null)).toBe('')
  expect(nutritionalStatus(null)).toContain('Ingrese peso y talla')
  for (const [group, text] of [
    ['ADULTO', 'fuera de las tablas'],
    ['ADULTO_MAYOR', 'fuera de las tablas'],
    ['GESTANTE', 'Gestantes'],
    ['PUERPERA', 'Puérperas'],
    ['ESCOLAR', 'Desde los 5 años'],
    ['INFANTIL', 'Menores de 5 años'],
  ] as const) {
    expect(nutritionalLimits({ ...result, grupo_referencia: group })).toContain(text)
  }
  expect(nutritionalStatus({ ...result, mensaje: 'Aviso del servidor' })).toContain(
    'Aviso del servidor',
  )
  expect(nutritionalStatus({ ...result, imc: null, diagnostico_imc: null })).not.toContain(
    'Resultado disponible',
  )
})

test.each(['INFANTIL', 'ESCOLAR', 'ADULTO', 'ADULTO_MAYOR', 'GESTANTE', 'PUERPERA'] as const)(
  'los campos P/E, T/E y P/T permanecen fijos para %s',
  (group) => {
    const rows = nutritionalRows({ ...result, grupo_referencia: group })
    expect(rows.map((row) => row.label)).toEqual([
      'Diagnóstico P/E',
      'Diagnóstico T/E',
      'Diagnóstico P/T',
    ])
    expect(rows).toHaveLength(3)
  },
)

test('el resumen muestra el IMC adulto y diferencia IMC/edad e IMC pregestacional', () => {
  expect(nutritionalBmiSummary(result)).toBe('IMC: 23.438 · Normal')
  expect(nutritionalBmiSummary({ ...result, grupo_referencia: 'ESCOLAR', imc_edad: '0.500' })).toBe(
    'IMC: 23.438 · IMC/edad: Z 0.500 · Normal',
  )
  expect(
    nutritionalBmiSummary({
      ...result,
      grupo_referencia: 'GESTANTE',
      imc_pregestacional: '21.500',
      ganancia_peso_kg: '5',
    }),
  ).toBe('IMC: 23.438 · IMC pregestacional: 21.500 · Normal · Cambio de peso: 5 kg')
  expect(nutritionalBmiSummary(null)).toBe('')
})

test('el historial explica los indicadores no aplicables de adultos sin snapshot', () => {
  const row = {
    pe: null,
    te: null,
    pt: null,
    edad_anios: 32,
    grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES' as const,
  }
  for (const indicator of ['pe', 'te', 'pt'] as const) {
    expect(nutritionalHistoryValue(row, indicator)).toBe('No aplica')
    expect(nutritionalHistoryValue({ ...row, edad_anios: 1 }, indicator)).toBe('—')
    expect(nutritionalHistoryValue({ ...row, [indicator]: '0.000' }, indicator)).toBe('0.000')
  }
  expect(nutritionalHistoryValue({ ...row, edad_anios: 8 }, 'pe')).toBe('—')
  expect(nutritionalHistoryValue({ ...row, edad_anios: 8 }, 'pt')).toBe('No aplica')
  expect(nutritionalHistoryValue({ ...row, edad_anios: 14 }, 'pe')).toBe('No aplica')
  expect(nutritionalHistoryValue({ ...row, edad_anios: 14 }, 'te')).toBe('—')
  expect(nutritionalHistoryValue({ ...row, edad_anios: null }, 'te')).toBe('—')
})

test('el historial usa la valoración guardada cuando existe', () => {
  const row = {
    pe: null,
    te: null,
    pt: null,
    edad_anios: 8,
    grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES' as const,
    valoracion_calculada: {
      ...result,
      grupo_referencia: 'ESCOLAR' as const,
      pe: '0.000',
      te: '-0.500',
    },
  }
  expect(nutritionalHistoryValue(row, 'pe')).toBe('0.000')
  expect(nutritionalHistoryValue(row, 'te')).toBe('-0.500')
  expect(nutritionalHistoryValue(row, 'pt')).toBe('No aplica')
})

test('adultos conservan los tres indicadores originales sin sustituirlos por IMC', () => {
  expect(nutritionalRows(result)).toHaveLength(3)
  expect(nutritionalRows(result).map((row) => row.label)).toEqual([
    'Diagnóstico P/E',
    'Diagnóstico T/E',
    'Diagnóstico P/T',
  ])
  expect(nutritionalRows(result).map((row) => row.value)).toEqual([
    'No aplica',
    'No aplica',
    'No aplica',
  ])
  expect(nutritionalRows({ ...result, grupo_referencia: 'ADULTO_MAYOR' })[1]?.value).toBe(
    'No aplica',
  )
})

test('escolares conservan las etiquetas y muestran solo puntajes aplicables', () => {
  const rows = nutritionalRows({
    ...result,
    grupo_referencia: 'ESCOLAR',
    imc_edad: '1.8',
    te: '-0.5',
  })
  expect(rows.map((row) => row.label)).toEqual([
    'Diagnóstico P/E',
    'Diagnóstico T/E',
    'Diagnóstico P/T',
  ])
  expect(rows.map((row) => row.value)).toEqual(['No aplica', 'Z: -0.5', 'No aplica'])
  expect(
    nutritionalRows({ ...result, grupo_referencia: 'ESCOLAR', pe: '0.1' }).map((row) => row.label),
  ).toContain('Diagnóstico P/E')
})

test('embarazo y puerperio mantienen los tres campos como No aplica', () => {
  const rows = nutritionalRows({
    ...result,
    grupo_referencia: 'GESTANTE',
    imc_pregestacional: '21.5',
    ganancia_peso_kg: '5',
  })
  expect(rows.map((row) => row.value)).toEqual(['No aplica', 'No aplica', 'No aplica'])
  expect(nutritionalRows({ ...result, grupo_referencia: 'PUERPERA' })).toHaveLength(3)
  expect(nutritionalRows({ ...result, grupo_referencia: 'PUERPERA' })[0]).toEqual({
    label: 'Diagnóstico P/E',
    value: 'No aplica',
  })
})

test('las tablas compactas cambian exactamente según el grupo de atención', () => {
  const child = nutritionalTableRows({
    ...result,
    grupo_referencia: 'INFANTIL',
    pe: '0.1',
    te: '-0.2',
    pt: '0.3',
  })
  expect(child.map((row) => row.label)).toEqual(['P/E', 'T/E', 'P/T'])

  const pregnant = nutritionalTableRows({
    ...result,
    grupo_referencia: 'GESTANTE',
    imc_pregestacional: '21.484',
    diagnostico_imc: 'Normal',
    ganancia_peso_kg: '10',
  })
  expect(pregnant).toEqual([
    { key: 'imc', label: 'IMC', value: '21.484' },
    { key: 'diagnostico_imc', label: 'Dx IMC', value: 'Normal' },
    { key: 'ganancia_peso', label: 'Ganancia de peso', value: '10 kg' },
  ])

  const puerperal = nutritionalTableRows({ ...pregnant[0], ...result }, 'PUERPERA')
  expect(puerperal.map((row) => row.label)).toEqual(['IMC', 'Dx IMC'])
})
