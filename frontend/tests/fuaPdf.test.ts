import { readFileSync } from 'node:fs'
import { inflateSync } from 'node:zlib'
import { URL as NodeURL } from 'node:url'
import { expect, test, vi } from 'vitest'
import { createFuaPdf, prepareFuaPdf } from '@/utils/fuaPdf'
import { defaultFuaLayout } from '@/utils/fuaPrint'

const background = new Uint8Array(
  readFileSync(new NodeURL('../src/assets/fua-v02-referencia.png', import.meta.url)),
)
const values = {
  primer_nombre: 'ANA',
  apellido_paterno: 'PRUEBA',
  numero_documento: '98032888',
  referencia_renipress: '00001234',
  referencia_hoja: 'E2E-LAB-01',
  fecha_atencion: '2026-10-18',
}

test('genera un PDF real de una página con formulario, texto y nombre de la atención guardada', async () => {
  const file = await createFuaPdf(defaultFuaLayout(), values, background, 'REF.Lab')
  expect(file.filename).toBe('REF.Lab-ANA PRUEBA-2026-10-18.pdf')
  const raw = Buffer.from(file.data).toString('latin1')
  expect(raw.startsWith('%PDF-')).toBe(true)
  expect(raw).toMatch(/\/Count 1\b/)
  expect(raw).toContain('/Subtype /Image')
  expect(raw).toContain('/Title (REF.Lab-ANA PRUEBA-2026-10-18)')
  const stream = raw.match(/stream\r?\n([\s\S]*?)\r?\nendstream/)![1]!
  const text = inflateSync(Buffer.from(stream, 'latin1')).toString('latin1')
  for (const token of [
    'ANA',
    'PRUEBA',
    '98032888',
    '00001234',
    'E2E-LAB-01',
    'PRELLENADO PARCIAL',
  ]) {
    expect(text).toContain(token)
  }
})

test('conserva la geometría y las casillas deshabilitadas en el PDF', async () => {
  const layout = defaultFuaLayout()
  layout.fields.find((field) => field.id === 'primer_nombre')!.enabled = false
  layout.fields.find((field) => field.id === 'historia_clinica')!.x = 120
  const file = await createFuaPdf(
    layout,
    { ...values, historia_clinica: 'HISTORIA-PRUEBA' },
    background,
  )
  const raw = Buffer.from(file.data).toString('latin1')
  const stream = raw.match(/stream\r?\n([\s\S]*?)\r?\nendstream/)![1]!
  const text = inflateSync(Buffer.from(stream, 'latin1')).toString('latin1')
  expect(text).not.toContain('(ANA) Tj')
  expect(text).toContain('(HISTORIA-PRUEBA) Tj')
  expect(text).toMatch(/340\.15748\d* [\d.]+ Td\n\(HISTORIA-PRUEBA\)/)
})

test('un error de carga o imagen inválida rechaza la generación en lugar de devolver un archivo vacío', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
  await expect(prepareFuaPdf(defaultFuaLayout(), values, '/fua.png')).rejects.toThrow(
    'formulario FUA',
  )
  vi.unstubAllGlobals()
  await expect(createFuaPdf(defaultFuaLayout(), values, new Uint8Array())).rejects.toThrow()
})

test('preparar la descarga carga el formulario y respeta los dígitos en casillas individuales', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, arrayBuffer: async () => background.buffer }),
  )
  try {
    const layout = defaultFuaLayout()
    layout.fields.find((field) => field.id === 'numero_documento')!.step = 3
    const file = await prepareFuaPdf(layout, values, '/formulario.png')
    const raw = Buffer.from(file.data).toString('latin1')
    const stream = raw.match(/stream\r?\n([\s\S]*?)\r?\nendstream/)![1]!
    const text = inflateSync(Buffer.from(stream, 'latin1')).toString('latin1')
    expect(text).toContain('(9) Tj')
    expect(text).toContain('(8) Tj')
    expect(file.filename).toContain('ANA PRUEBA')
  } finally {
    vi.unstubAllGlobals()
  }
})
