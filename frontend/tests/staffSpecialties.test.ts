import { expect, test } from 'vitest'
import { isStaffSpecialty } from '@/utils/staffSpecialties'

test.each([
  ['ESP_NUTRICION:002', false, false],
  ['Esp_Nutricion:002', false, false],
  ['ESP_MEDICINA:003', false, false],
  ['CERTIFICADO:001', false, false],
  ['ESPECIALIDADES3:004', false, false],
  ['ESPECIALIDADES:005', true, true],
  ['ESPECIALIDADES:009', true, true],
  ['ESP-1234567890ABCDEF', false, true],
  ['CARD', false, true],
] as const)(
  'separa %s del selector de personal sin cambiar el catálogo',
  (codigo, es_area, expected) => {
    const item = { codigo, es_area, nombre: 'Registro', activo: true, grupo: null }
    expect(isStaffSpecialty(item)).toBe(expected)
    expect(item.codigo).toBe(codigo)
  },
)
