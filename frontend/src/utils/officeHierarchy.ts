import type { OfficeCatalogItem } from '@/services/catalogos'
import type { OfficeResponse } from '@/services/consultorios'

export function officeLabel(office: OfficeCatalogItem): string {
  return `${office.codigo} · ${office.ruta || office.nombre}`
}

export function descendantIds(
  items: { id: number; consultorio_padre_id?: number | null }[],
  id: number,
): Set<number> {
  const result = new Set<number>([id])
  let changed = true
  while (changed) {
    changed = false
    for (const item of items) {
      if (
        item.consultorio_padre_id != null &&
        result.has(item.consultorio_padre_id) &&
        !result.has(item.id)
      ) {
        result.add(item.id)
        changed = true
      }
    }
  }
  return result
}

export type OfficeTreeRow = OfficeResponse & { children: OfficeTreeRow[] }
export function officeTree(items: OfficeResponse[]): OfficeTreeRow[] {
  const nodes = new Map(items.map((item) => [item.id, { ...item, children: [] } as OfficeTreeRow]))
  const roots: OfficeTreeRow[] = []
  for (const item of nodes.values()) {
    const parent =
      item.consultorio_padre_id == null ? undefined : nodes.get(item.consultorio_padre_id)
    if (parent && !descendantIds(items, item.id).has(parent.id)) parent.children.push(item)
    else roots.push(item)
  }
  return roots
}
