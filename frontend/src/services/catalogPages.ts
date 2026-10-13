import type { PageResponse } from '@/types/api'

export async function allCatalogPages<T>(
  fetch: (offset: number) => Promise<PageResponse<T>>,
): Promise<T[]> {
  const items: T[] = []
  let offset = 0
  for (;;) {
    const page = await fetch(offset)
    items.push(...page.items)
    if (!page.has_more || page.items.length === 0) return items
    offset += page.limit
  }
}
