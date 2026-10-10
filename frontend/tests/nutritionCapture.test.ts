import { expect, test } from 'vitest'
import { nutritionErrors, nutritionPayload } from '@/utils/nutritionCapture'

test('conserva cero y No, y distingue vacíos de resultados', () => {
  expect(nutritionPayload({ nro_sachets: 0, juntos: false, pin: null, grado: '' }, 'NINO')).toEqual(
    { nro_sachets: 0, juntos: false },
  )
  expect(nutritionPayload({}, 'ADULTO')).toBeNull()
})

test('descarta datos incompatibles al cambiar de grupo o edad', () => {
  const mixed = {
    hemoglobina: 12,
    nro_sachets: 0,
    juntos: false,
    p65: 1,
    edad_gestacional_semanas: 24,
    estado_ganancia_peso: 'EVALUADO',
  }
  expect(nutritionPayload(mixed, 'ADULTO')).toEqual({ hemoglobina: 12, p65: 1 })
  expect(nutritionPayload(mixed, 'PUERPERA')).toEqual({ hemoglobina: 12 })
  expect(nutritionPayload(mixed, 'GESTANTE')).toEqual({
    hemoglobina: 12,
    edad_gestacional_semanas: 24,
    estado_ganancia_peso: 'EVALUADO',
  })
})

test('exige fecha de Hb, método y altitud para corregida', () => {
  expect(nutritionErrors({ hemoglobina: 12 }, '2020-01-01', '2026-10-01')).toHaveLength(1)
  expect(nutritionErrors({ hemoglobina_corregida: 11 }, '2020-01-01', '2026-10-01')).toHaveLength(1)
  expect(
    nutritionErrors(
      { hemoglobina: 12, fecha_hemoglobina: '2019-12-31' },
      '2020-01-01',
      '2026-10-01',
    ),
  ).toHaveLength(1)
  expect(
    nutritionErrors(
      { hemoglobina: 12, fecha_hemoglobina: '2026-10-02' },
      '2020-01-01',
      '2026-10-01',
    ),
  ).toHaveLength(1)
  expect(
    nutritionErrors(
      {
        hemoglobina: 12,
        fecha_hemoglobina: '2026-10-01',
        hemoglobina_corregida: 11,
        metodo_correccion_hb: 'Laboratorio',
        altitud_msnm: 0,
      },
      '2020-01-01',
      '2026-10-01',
    ),
  ).toEqual([])
})
