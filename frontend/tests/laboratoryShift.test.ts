import { expect, test } from 'vitest'
import { laboratoryShift } from '@/utils/laboratoryShift'
test('los límites del turno no cuentan dos veces la atención de las 13:00', () => {
  expect(laboratoryShift('2026-10-12T06:59:59')).toBeNull()
  expect(laboratoryShift('2026-10-12T07:00:00')?.name).toBe('Mañana')
  expect(laboratoryShift('2026-10-12T12:59:59')?.end).toBe('2026-10-12T13:00:00')
  expect(laboratoryShift('2026-10-12T13:00:00')?.name).toBe('Tarde')
  expect(laboratoryShift('2026-10-12T13:00')?.name).toBe('Tarde')
  expect(laboratoryShift('2026-10-12T19:00:00')).toBeNull()
})
