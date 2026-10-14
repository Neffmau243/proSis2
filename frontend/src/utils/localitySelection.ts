import type { LocalidadCatalogItem } from '@/services/catalogos'

export function localityOptions(suggestions: LocalidadCatalogItem[], districtName?: string | null) {
  const options: { label: string; value: string | number }[] = suggestions.map((item) => ({
    label: item.nombre,
    value: item.id,
  }))
  const name = districtName?.trim()
  if (
    name &&
    !options.some((item) => item.label.trim().toLocaleLowerCase() === name.toLocaleLowerCase())
  ) {
    options.unshift({ label: name, value: name })
  }
  return options
}

/** Legacy registration accepts a suggested locality or a name written by staff. */
export function localitySelection(
  value: number | string | null | undefined,
  suggestions: LocalidadCatalogItem[],
): { localidad_id: number | null; localidad: string | null } {
  if (typeof value === 'number') {
    const selected = suggestions.find((item) => item.id === value)
    return { localidad_id: value, localidad: selected?.nombre ?? null }
  }
  const name = value?.trim() || null
  const selected =
    name &&
    suggestions.find((item) => item.nombre.trim().toLocaleLowerCase() === name.toLocaleLowerCase())
  return {
    localidad_id: selected ? selected.id : null,
    localidad: selected ? selected.nombre : name,
  }
}
