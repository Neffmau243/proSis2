export const FAMILY_HISTORY_PATTERN = /^([A-Z0-9]{2,4})-(\d{1,24})$/

export function normalizeFamilyHistory(value: string | null | undefined): string | null {
  const normalized = value?.trim().toUpperCase() ?? ''
  return normalized || null
}

export function splitFamilyHistory(
  value: string | null | undefined,
): { prefix: string; number: string } | null {
  const normalized = normalizeFamilyHistory(value)
  if (!normalized) return null
  const match = normalized.match(FAMILY_HISTORY_PATTERN)
  return match ? { prefix: match[1]!, number: match[2]! } : null
}

export function familyHistoryProblem(value: string | null | undefined): string | null {
  if (!normalizeFamilyHistory(value)) return null
  return splitFamilyHistory(value)
    ? null
    : 'Seleccione un color o sector e ingrese de 1 a 24 dígitos.'
}
