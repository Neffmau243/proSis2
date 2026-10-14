import { expect, test } from '@playwright/test'

/**
 * Verifica en un Chromium real lo que Vitest simula: la calibración en
 * milímetros, su persistencia y el documento FUA que se envía a impresión.
 * El arnés usa datos 100 % sintéticos (`PRUEBA-001`) y no llama al backend.
 */
const HARNESS = '/tests/fua-print-harness.html'
const LAYOUT_KEY = 'ipress.fua-layout.v1'

/** Evita el diálogo del sistema y registra el documento que se imprimiría. */
async function stubPrinting(page: import('@playwright/test').Page) {
  // Cada prueba de Playwright abre un contexto nuevo: el localStorage ya parte vacío.
  await page.addInitScript(() => {
    const prints: string[] = []
    ;(window as unknown as { __fuaPrints: string[] }).__fuaPrints = prints
    // Se ejecuta también dentro del iframe de impresión: registra su documento
    // y evita el diálogo del sistema, que en modo headless cerraría el iframe.
    window.print = function () {
      const top = window.top as unknown as { __fuaPrints?: string[] }
      ;(top?.__fuaPrints ?? prints).push(window.document.documentElement.outerHTML)
    }
  })
}

// El input nativo de Element Plus está oculto: se activa desde su etiqueta.
function checkbox(page: import('@playwright/test').Page, text: string) {
  return page.locator('label.el-checkbox', { hasText: text })
}

function prints(page: import('@playwright/test').Page) {
  return page.evaluate(() => (window as unknown as { __fuaPrints: string[] }).__fuaPrints ?? [])
}

async function openCalibration(page: import('@playwright/test').Page) {
  await page.goto(HARNESS)
  await expect(page.getByText('Imprimir FUA · uso local')).toBeVisible()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
}

test('la calibración en milímetros habilita la impresión real y produce el FUA del paciente', async ({
  page,
}) => {
  await stubPrinting(page)
  await openCalibration(page)

  const print = page.getByRole('button', { name: 'Imprimir sobre FUA preimpresa' })
  // Sin calibrar, la impresión real queda bloqueada.
  await expect(print).toBeDisabled()

  // La prueba sin datos imprime solo la retícula de calibración.
  await page.getByRole('button', { name: 'Imprimir prueba sin datos' }).click()
  await expect.poll(() => prints(page).then((d) => d.length)).toBe(1)
  const [testDoc] = await prints(page)
  expect(testDoc).toContain('outline')
  expect(testDoc).not.toContain('PRUEBA-001')

  // El arnés no declara etnia: el profesional debe reconocer el faltante antes
  // de imprimir datos (casilla en la pestaña de datos).
  await page.getByRole('tab', { name: 'Datos de la FUA' }).click()
  await checkbox(page, 'Revisé los faltantes').click()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()

  // Confirmar la prueba física habilita la impresión y se guarda como geometría.
  await checkbox(page, 'Comprobé tamaño y alineación').click()
  await expect(print).toBeEnabled()
  await page.getByRole('button', { name: 'Guardar calibración' }).click()
  const stored = await page.evaluate((key) => window.localStorage.getItem(key), LAYOUT_KEY)
  expect(stored).toBeTruthy()
  expect(stored).not.toContain('PRUEBA-001')
  expect(stored).not.toContain('00000001')
  expect(JSON.parse(stored as string).calibrated).toBe(true)

  // La salida real usa el tamaño de hoja y los datos del paciente.
  await print.click()
  await expect.poll(() => prints(page).then((d) => d.length)).toBe(2)
  const doc = (await prints(page))[1]!
  expect(doc).toContain('PRUEBA-001')
  expect(doc).toContain('@page{size:216mm 356mm;margin:0}')
  expect(doc).toMatch(/left:[\d.]+mm/)
  // El fondo de referencia y los controles nunca se imprimen.
  expect(doc).not.toMatch(/<script|<button|<img|referencia\.webp/)

  // Mover la geometría invalida la calibración hasta revisarla de nuevo...
  await checkbox(page, 'Imprimir este campo').click()
  await expect(print).toBeDisabled()

  // El cambio se guarda automáticamente: al reabrir conserva la geometría
  // pendiente de comprobar en lugar de recuperar una confirmación obsoleta.
  await page.reload()
  await expect(page.getByText('Imprimir FUA · uso local')).toBeVisible()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
  await expect(checkbox(page, 'Comprobé tamaño y alineación').locator('input')).not.toBeChecked()
  // Los faltantes vuelven a confirmarse en cada apertura, como exige el diálogo.
  await page.getByRole('tab', { name: 'Datos de la FUA' }).click()
  await checkbox(page, 'Revisé los faltantes').click()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
  await checkbox(page, 'Comprobé tamaño y alineación').click()
  await expect(page.getByRole('button', { name: 'Imprimir sobre FUA preimpresa' })).toBeEnabled()
})

test('el PDF de revisión contiene la referencia oficial y datos, sin exigir prueba física', async ({
  page,
}) => {
  await stubPrinting(page)
  await openCalibration(page)
  await page.getByRole('tab', { name: 'Datos de la FUA' }).click()
  await checkbox(page, 'Revisé los faltantes').click()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
  await expect(page.getByRole('button', { name: 'Imprimir sobre FUA preimpresa' })).toBeDisabled()
  await page.getByRole('button', { name: 'Ver FUA / guardar PDF' }).click()
  await expect.poll(() => prints(page).then((docs) => docs.length)).toBe(1)
  const [doc] = await prints(page)
  expect(doc).toContain('fua-v02-referencia.png')
  expect(doc).toContain('PRUEBA-001')
  expect(doc).toContain('PRELLENADO PARCIAL')
  expect(doc).toContain('00000001')
  const previewSrc = await page.locator('.fua-background').getAttribute('src')
  expect(doc).toContain(`src="${previewSrc}"`)
  await expect(page.getByRole('button', { name: 'Ver FUA / guardar PDF' })).toHaveClass(
    /el-button--primary/,
  )
  // Image loading is part of the print path, and desktop/mobile use the same sheet.
  await expect(page.locator('.fua-background')).toBeVisible()
  await page.screenshot({ path: '../docs/audits/fua-v02-desktop-20261014.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: 'Ver FUA / guardar PDF' })).toBeVisible()
  await page.screenshot({ path: '../docs/audits/fua-v02-mobile-20261014.png', fullPage: true })
  // The form is an image element: it must print even with background graphics off.
  await page.setViewportSize({ width: 1000, height: 1400 })
  await page.setContent(doc!)
  await expect
    .poll(() =>
      page.locator('img').evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0),
    )
    .toBe(true)
  await page.pdf({
    path: '../docs/audits/fua-v02-revision-sintetica-20261014.pdf',
    preferCSSPageSize: true,
    printBackground: false,
  })
  await page.screenshot({ path: '../docs/audits/fua-v02-hoja-20261014.png', fullPage: true })
})

test('un perfil histórico usa la misma referencia en vista previa y PDF conservando sus posiciones', async ({
  page,
}) => {
  await stubPrinting(page)
  await openCalibration(page)
  await checkbox(page, 'Comprobé tamaño y alineación').click()
  const legacy = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)!), LAYOUT_KEY)
  legacy.template = 'historica'
  const history = legacy.fields.find((field: { id: string }) => field.id === 'historia_clinica')
  history.x = 120
  await page.evaluate(({ key, raw }) => localStorage.setItem(key, raw), {
    key: LAYOUT_KEY,
    raw: JSON.stringify(legacy),
  })
  await page.reload()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
  await expect(page.locator('.fua-background')).toHaveAttribute('src', /fua-v02-referencia\.png$/)
  await expect(page.locator('#fua-scan')).toHaveCount(0)
  const normalized = await page.evaluate(
    (key) => JSON.parse(localStorage.getItem(key)!),
    LAYOUT_KEY,
  )
  expect(normalized.template).toBe('sis-v02')
  expect(normalized.calibrated).toBe(false)
  expect(normalized.fields).toEqual(legacy.fields)
  await page.getByRole('tab', { name: 'Datos de la FUA' }).click()
  await checkbox(page, 'Revisé los faltantes').click()
  await page.getByRole('button', { name: 'Ver FUA / guardar PDF' }).click()
  await expect.poll(() => prints(page).then((docs) => docs.length)).toBe(1)
  const [doc] = await prints(page)
  expect(doc).toContain('fua-v02-referencia.png')
  expect(doc).not.toContain('fua-referencia.webp')
  expect(doc).toContain('left:120mm')
})

test('importar posiciones conserva la geometría y exige comprobar la impresora de destino', async ({
  page,
}) => {
  await openCalibration(page)
  await checkbox(page, 'Comprobé tamaño y alineación').click()
  const raw = await page.evaluate((key) => localStorage.getItem(key)!, LAYOUT_KEY)
  const imported = JSON.parse(raw)
  imported.offsetX = 1.5
  await page.locator('#fua-layout-import').setInputFiles({
    name: 'calibracion.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(imported)),
  })
  await expect
    .poll(() => page.evaluate((key) => JSON.parse(localStorage.getItem(key)!).offsetX, LAYOUT_KEY))
    .toBe(1.5)
  await expect(checkbox(page, 'Comprobé tamaño y alineación').locator('input')).not.toBeChecked()
})
