import type { PregnancyTypeCode } from '@/services/atenciones'

/** Opciones de pluralidad de la gestación, en el orden que muestra el formulario. */
export const PREGNANCY_TYPES: { value: PregnancyTypeCode; label: string }[] = [
  { value: 'UNICO', label: 'Embarazo único' },
  { value: 'MULTIPLE', label: 'Embarazo múltiple' },
]

/** Muestra la etiqueta del tipo cuando se conoce y el código crudo si no. */
export function pregnancyTypeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PREGNANCY_TYPES.find((type) => type.value === code)?.label ?? code
}

/** Calendar dates only; local encounter dates must not shift with browser timezone. */
export function gestationalAgeFromDueDate(attendedAt: string, dueOn: string | null | undefined):
  { weeks: number; days: number } | null {
  const calendarDay = (value: string) => {
    const text = value.slice(0, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return NaN
    const stamp = Date.parse(`${text}T00:00:00Z`)
    return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0, 10) === text
      ? stamp / 86_400_000 : NaN
  }
  if (!dueOn) return null
  const elapsed = 280 - (calendarDay(dueOn) - calendarDay(attendedAt))
  if (!Number.isInteger(elapsed) || elapsed < 0 || elapsed >= 46 * 7) return null
  return { weeks: Math.floor(elapsed / 7), days: elapsed % 7 }
}
