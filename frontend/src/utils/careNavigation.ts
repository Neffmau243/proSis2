import type { LocationQuery, RouteLocationRaw } from 'vue-router'

export interface CareNavigationContext {
  establishmentId?: number
  establishmentName?: string
  areaCode?: string
  areaName?: string
  officeName?: string
}

export interface CareBreadcrumb {
  label: string
  to?: RouteLocationRaw
}

/** Derive the location from the displayed records, including direct detail links. */
export function careBreadcrumbs(
  routeName: unknown,
  context: CareNavigationContext = {},
): CareBreadcrumb[] {
  const items: CareBreadcrumb[] = [{ label: 'Administración' }]
  const site = context.establishmentId
    ? {
        label: context.establishmentName || `Establecimiento #${context.establishmentId}`,
        to: {
          name: 'establecimiento-detalle',
          params: { establishmentId: context.establishmentId },
        },
      }
    : undefined
  if (routeName === 'establecimiento-detalle') {
    items.push({ label: 'Establecimientos', to: { name: 'establecimientos' } })
    items.push({ label: site?.label || 'Establecimiento' })
    return items
  }
  if (routeName === 'consultorios' || routeName === 'consultorio-servicios') {
    if (site) {
      items.push({ label: 'Establecimientos', to: { name: 'establecimientos' } }, site)
    }
    if (context.areaCode) {
      items.push({ label: `Área: ${context.areaName || context.areaCode}` })
    }
    items.push({
      label: 'Consultorios',
      ...(routeName === 'consultorio-servicios'
        ? { to: { name: 'consultorios', query: careDirectoryQuery(context) } }
        : {}),
    })
    if (routeName === 'consultorio-servicios') {
      items.push({ label: context.officeName || 'Consultorio' })
    }
    return items
  }
  const titles: Record<string, string> = {
    establecimientos: 'Establecimientos',
    'areas-atencion': 'Áreas de atención',
    'servicios-asistenciales': 'Servicios / especialidades',
    personal: 'Personal y cuentas',
  }
  items.push({ label: titles[String(routeName)] || 'Configuración' })
  return items
}

export function careDirectoryQuery(context: CareNavigationContext): LocationQuery {
  return {
    ...(context.establishmentId ? { establecimientoId: String(context.establishmentId) } : {}),
    ...(context.areaCode ? { areaCodigo: context.areaCode } : {}),
  }
}
