import { expect, test } from 'vitest'
import { descendantIds, officeLabel, officeTree } from '@/utils/officeHierarchy'
import type { OfficeResponse } from '@/services/consultorios'

test('los descendientes incluyen nietos aunque el catálogo llegue desordenado y toleran ciclos', () => {
  const items = [
    { id: 3, consultorio_padre_id: 2 },
    { id: 2, consultorio_padre_id: 1 },
    { id: 1 },
    { id: 4, consultorio_padre_id: 5 },
    { id: 5, consultorio_padre_id: 4 },
  ]
  expect([...descendantIds(items, 1)].sort()).toEqual([1, 2, 3])
  expect([...descendantIds(items, 4)].sort()).toEqual([4, 5])
  expect(
    officeLabel({ codigo: 'LAB', ruta: 'Sede / Laboratorio', nombre: 'Laboratorio' } as never),
  ).toBe('LAB · Sede / Laboratorio')
  expect(officeLabel({ codigo: 'LAB', nombre: 'Laboratorio' } as never)).toBe('LAB · Laboratorio')
})

test('el árbol conserva huérfanos y ciclos como raíces sin crear referencias recursivas', () => {
  const rows = [
    { id: 3, consultorio_padre_id: 2 },
    { id: 2, consultorio_padre_id: 1 },
    { id: 1 },
    { id: 4, consultorio_padre_id: 99 },
    { id: 5, consultorio_padre_id: 6 },
    { id: 6, consultorio_padre_id: 5 },
  ] as OfficeResponse[]
  const roots = officeTree(rows)
  expect(roots.map((item) => item.id)).toEqual([1, 4, 5, 6])
  expect(roots[0]!.children[0]!.children[0]!.id).toBe(3)
  expect(() => JSON.stringify(roots)).not.toThrow()
})
