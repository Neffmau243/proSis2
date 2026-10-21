import { expect, test } from 'vitest'
import { gestationalAgeFromDueDate } from '../src/utils/pregnancy'

test('fecha de atención y FPP producen semanas completas y días, incluso al pasar la FPP', () => {
  expect(gestationalAgeFromDueDate('2026-10-20T23:30:00', '2026-12-27')).toEqual({ weeks: 30, days: 2 })
  expect(gestationalAgeFromDueDate('2026-12-27', '2026-12-27')).toEqual({ weeks: 40, days: 0 })
  expect(gestationalAgeFromDueDate('2026-12-28', '2026-12-27')).toEqual({ weeks: 40, days: 1 })
})

test.each([
  ['', '2026-12-27'], ['2026-10-20', null], ['2026-10-20', '2026-02-30'],
  ['2026-02-30', '2026-12-27'], ['2026-10-20', '2027-12-27'], ['2026-10-20', '2026-01-01'],
])('fechas ausentes o incoherentes no inventan edad (%s, %s)', (attention, dueDate) => {
  expect(gestationalAgeFromDueDate(attention!, dueDate)).toBeNull()
})
