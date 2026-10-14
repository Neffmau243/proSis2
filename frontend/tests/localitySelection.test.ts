import { expect, test } from 'vitest'
import { localityOptions, localitySelection } from '@/utils/localitySelection'

const suggestions = [
  {
    id: 12,
    ubigeo_codigo: '040102',
    codigo_catalogo: '0052',
    codigo_sis: '00000001',
    nombre: 'PORTALES DEL MIRADOR',
    activo: true,
  },
]

test('la localidad escrita permanece texto y elegir una sugerencia conserva su ID', () => {
  expect(localitySelection('  ALTO SELVA ALEGRE  ', suggestions)).toEqual({
    localidad_id: null,
    localidad: 'ALTO SELVA ALEGRE',
  })
  expect(localitySelection(12, suggestions)).toEqual({
    localidad_id: 12,
    localidad: 'PORTALES DEL MIRADOR',
  })
  expect(localitySelection('portales del mirador', suggestions).localidad_id).toBe(12)
  expect(localitySelection(null, suggestions)).toEqual({ localidad_id: null, localidad: null })
})

test('el nombre general usado en el legado es una opción de texto, sin duplicar localidades existentes', () => {
  expect(localityOptions(suggestions, 'ALTO SELVA ALEGRE')[0]).toEqual({
    label: 'ALTO SELVA ALEGRE',
    value: 'ALTO SELVA ALEGRE',
  })
  expect(localityOptions(suggestions, 'portales del mirador')).toHaveLength(1)
})
