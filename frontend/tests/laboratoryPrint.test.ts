import { expect, test } from 'vitest'
import { laboratoryClinicalHtml } from '@/utils/laboratoryPrint'
import type { Attention } from '@/services/atenciones'
test('HCI conserva la identidad de la atención guardada y escapa texto clínico', () => {
  const html = laboratoryClinicalHtml({
    id: 99,
    numero_referencia_ingreso: '001565',
    numero_contrarreferencia_ingreso: '00007',
    fua_impresion: {
      historia_clinica: 'HC-ORIGINAL',
      tipo_documento: 'DNI',
      numero_documento: '00112233',
      apellido_paterno: '<script>alert(1)</script>',
    },
    observaciones: 'A & B',
  } as Attention)
  expect(html).toContain('HC-ORIGINAL')
  expect(html).toContain('001565')
  expect(html).toContain('00007')
  expect(html).toContain('&lt;script&gt;')
  expect(html).not.toContain('<script>')
  expect(html).toContain('A &amp; B')
  expect(() => laboratoryClinicalHtml({ fua_impresion: null } as Attention)).toThrow()
})
