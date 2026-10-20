import { afterEach, expect, test, vi } from 'vitest'
import { laboratoryClinicalHtml, printLaboratoryClinical } from '@/utils/laboratoryPrint'
import type { Attention } from '@/services/atenciones'

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
  document.body.innerHTML = ''
})

test('la impresión espera la carga, abre el diálogo y retira el iframe al terminar', async () => {
  vi.useFakeTimers()
  const append = document.body.appendChild.bind(document.body)
  const focus = vi.fn()
  const print = vi.fn()
  let afterPrint!: () => void
  vi.spyOn(document.body, 'appendChild').mockImplementation((node) => {
    const result = append(node)
    Object.defineProperty(node, 'contentDocument', {
      value: { fonts: { ready: Promise.resolve() } },
    })
    Object.defineProperty(node, 'contentWindow', {
      value: {
        focus,
        print,
        addEventListener: (_: string, listener: () => void) => {
          afterPrint = listener
        },
      },
    })
    queueMicrotask(() => node.dispatchEvent(new Event('load')))
    return result
  })
  await printLaboratoryClinical({ id: 1, fua_impresion: {} } as Attention)
  expect(print).toHaveBeenCalledOnce()
  expect(focus).toHaveBeenCalledOnce()
  expect(document.querySelector('iframe')).not.toBeNull()
  afterPrint()
  expect(document.querySelector('iframe')).toBeNull()
  await vi.runAllTimersAsync()
})

test('una carga fallida retira el iframe y permite informar el error', async () => {
  const append = document.body.appendChild.bind(document.body)
  vi.spyOn(document.body, 'appendChild').mockImplementation((node) => {
    const result = append(node)
    queueMicrotask(() => node.dispatchEvent(new Event('error')))
    return result
  })
  await expect(printLaboratoryClinical({ id: 1, fua_impresion: {} } as Attention)).rejects.toThrow(
    'No se pudo preparar',
  )
  expect(document.querySelector('iframe')).toBeNull()
})
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
