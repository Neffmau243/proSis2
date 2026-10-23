import type { SpecialtyCatalogItem } from '@/services/catalogos'

/** Separate legacy office services from qualifications in the staff UI only. */
export function isStaffSpecialty(item: SpecialtyCatalogItem): boolean {
  if (item.es_area) return true
  const code = item.codigo.toUpperCase()
  return ![
    'SRV-',
    'ESP_',
    'CERTIFICADO:',
    'ESPECIALIDADES:',
    'ESPECIALIDADES2:',
    'ESPECIALIDADES3:',
  ].some((prefix) => code.startsWith(prefix))
}
