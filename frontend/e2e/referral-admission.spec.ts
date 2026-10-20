import { expect, test } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

// Only run through tests/e2e/run_referral_e2e.py: it owns a disposable MySQL
// database and a loopback API serving the production SPA build.
test.skip(!process.env.REFERRAL_E2E_URL, 'Requires the isolated referral API')
test.beforeAll(() => {
  expect(process.env.REFERRAL_E2E_DATABASE).toMatch(/^ipress_test_referral_e2e_[a-f0-9]{10}$/)
  expect(new URL(process.env.REFERRAL_E2E_URL!).hostname).toBe('127.0.0.1')
})
const evidence = process.env.REFERRAL_E2E_EVIDENCE || '../tmp/referral-e2e'
const origin = {
  renipress: '00001234',
  name: 'C.S. ORIGEN DE PRUEBA E2E',
  sheet: 'REF-000042',
}

test('Referencia conserva el tamaño y llega desde admisión hasta las casillas impresas del FUA', async ({
  page,
  request,
  context,
}) => {
  test.setTimeout(120_000)
  await mkdir(evidence, { recursive: true })
  const login = await request.post('/api/v1/auth/login', {
    data: { nombre_usuario: 'referencia.e2e', password: '12345678' },
  })
  expect(login.status(), await login.text()).toBe(200)
  const session = await login.json()
  const headers = { Authorization: `Bearer ${session.access_token}` }
  const createdPatient = await request.post('/api/v1/patients', {
    headers,
    data: {
      tipo_documento_codigo: 'DNI',
      numero_documento: '00000001',
      apellido_paterno: 'PRUEBA',
      apellido_materno: 'FICTICIA',
      primer_nombre: 'ANA',
      sexo_codigo: 'F',
      fecha_nacimiento: '1990-01-02',
      historia_clinica: 'E2E-REF-001',
      establecimiento_registro_id: Number(process.env.REFERRAL_E2E_SITE),
      seguro_id: Number(process.env.REFERRAL_E2E_INSURANCE),
      sis_diresa: '040',
      sis_tipo: '2',
      sis_numero: '00000001',
      etnia_codigo: '58',
    },
  })
  expect(createdPatient.status(), await createdPatient.text()).toBe(201)
  const patient = await createdPatient.json()
  await context.addInitScript(
    (data) => {
      localStorage.setItem('ipress:session', JSON.stringify(data))
      const host = window as unknown as { __referralPrints: string[] }
      host.__referralPrints = []
      window.print = () => {
        const top = window.top as unknown as { __referralPrints?: string[] }
        top.__referralPrints?.push(document.documentElement.outerHTML)
      }
    },
    {
      ...session,
      nombre_usuario: 'referencia.e2e',
      expires_at: Date.now() + session.expires_in * 1000,
    },
  )
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const metrics: unknown[] = []
  const admission = `/admision?patientId=${patient.id}`
  const block = page.locator('.clinical-section--context')
  const measure = () =>
    page.locator('.encounter-card').evaluate((card) => {
      const section = card.querySelector('.clinical-section--context') as HTMLElement
      const measurements = card.querySelector('.clinical-section--measurements') as HTMLElement
      return {
        height: section.getBoundingClientRect().height,
        measurementsTop: measurements.offsetTop,
        columns: getComputedStyle(card.querySelector('.el-card__body')!).gridTemplateColumns,
        overflow: card.scrollWidth > card.clientWidth + 1,
      }
    })
  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 1024, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport)
    await page.goto(admission)
    await expect(page.getByLabel('SIS · Número de afiliación', { exact: true })).toHaveValue(
      '00000001',
    )
    await expect(block.getByRole('heading', { name: 'Consultorio', exact: true })).toBeVisible()
    const before = await measure()
    await page.getByText('Referencia', { exact: true }).click()
    await expect(block.getByRole('heading', { name: 'Referencia realizada por' })).toBeVisible()
    await expect(block.locator('.el-select')).toHaveCount(0)
    await expect(block.locator('.referral-fields input')).toHaveCount(3)
    await page.getByLabel('Código RENIPRESS de origen', { exact: true }).fill(origin.renipress)
    await page
      .getByLabel('Nombre de la IPRESS de origen', { exact: true })
      .fill('CENTRO DE SALUD DE PRUEBA CON UN NOMBRE LARGO PARA COMPROBAR QUE LA VISTA NO CRECE')
    await page.getByLabel('N.º de hoja de referencia', { exact: true }).fill(origin.sheet)
    const after = await measure()
    expect(after.height, `Context height at ${viewport.width}px`).toBeLessThanOrEqual(
      before.height + 1,
    )
    expect(
      after.measurementsTop,
      `Measurement position at ${viewport.width}px`,
    ).toBeLessThanOrEqual(before.measurementsTop + 1)
    expect(after.columns).toBe(before.columns)
    expect(after.overflow).toBe(false)
    metrics.push({ viewport, before, after })
    await block.screenshot({ path: join(evidence, `referencia-${viewport.width}.png`) })
    await page.getByText('Ambulatoria', { exact: true }).click()
    await expect(block.getByRole('heading', { name: 'Consultorio', exact: true })).toBeVisible()
    expect((await measure()).height).toBeCloseTo(before.height, 0)
  }

  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto(admission)
  await page.getByText('Referencia', { exact: true }).click()
  await page.getByLabel('Código RENIPRESS de origen', { exact: true }).fill(origin.renipress)
  await page.getByLabel('Nombre de la IPRESS de origen', { exact: true }).fill(origin.name)
  await page.getByLabel('N.º de hoja de referencia', { exact: true }).fill(origin.sheet)
  const savedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/v1/atenciones'),
  )
  await page.getByRole('button', { name: 'Guardar atención', exact: true }).click()
  const response = await savedResponse
  expect(response.status(), await response.text()).toBe(201)
  const saved = await response.json()
  expect(saved.consultorio_id).toBeNull()
  expect(saved.profesional_id).toBeNull()
  expect(saved.especialidad_codigo).toBeNull()
  expect(saved.fua_impresion).toMatchObject({
    tipo_atencion: 'REFERENCIA',
    referencia_renipress: origin.renipress,
    referencia_nombre: origin.name,
    referencia_hoja: origin.sheet,
    profesional_nombre: null,
  })
  const reloaded = await request.get(`/api/v1/atenciones/${saved.id}`, { headers })
  expect(reloaded.status()).toBe(200)
  expect((await reloaded.json()).fua_impresion).toEqual(saved.fua_impresion)
  await expect(page.getByRole('button', { name: 'Atención guardada', exact: true })).toBeVisible()
  await page.screenshot({
    path: join(evidence, 'admision-referencia-guardada.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Imprimir S.I.S.', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  const pending = page.locator('label.el-checkbox').filter({ hasText: 'Revisé los faltantes' })
  if (await pending.count()) await pending.click()
  await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
  for (const [label, text] of [
    ['X · Referencia', 'X'],
    ['X · Ambulatoria', '·'],
    ['X · Emergencia', '·'],
    ['Referencia · RENIPRESS', origin.renipress],
    ['Referencia · IPRESS origen', origin.name],
    ['Referencia · Hoja', origin.sheet],
  ])
    await expect(page.getByLabel(`Ajustar ${label}`, { exact: true })).toHaveText(text!)

  await page.getByRole('button', { name: 'Ver FUA / guardar PDF', exact: true }).click()
  const prints = () =>
    page.evaluate(() => (window as unknown as { __referralPrints: string[] }).__referralPrints)
  await expect.poll(async () => (await prints()).length).toBe(1)
  const review = (await prints())[0]!
  expect(review).toContain('FUA de referencia')
  for (const value of Object.values(origin)) expect(review).toContain(value)
  expect(review).not.toContain('PROFESIONAL E2E')
  await page
    .locator('label.el-checkbox')
    .filter({ hasText: 'Comprobé tamaño y alineación' })
    .click()
  await page.getByRole('button', { name: 'Imprimir sobre FUA preimpresa', exact: true }).click()
  await expect.poll(async () => (await prints()).length).toBe(2)
  const preprinted = (await prints())[1]!
  expect(preprinted).not.toContain('<img')
  for (const value of Object.values(origin)) expect(preprinted).toContain(value)

  const output = await context.newPage()
  await output.setViewportSize({ width: 820, height: 1350 })
  // Keep the server origin so the review image resolves exactly as in srcdoc.
  await output.goto('/')
  for (const [name, html] of [
    ['fua-referencia-revision', review],
    ['fua-referencia-solo-datos', preprinted],
  ]) {
    await writeFile(join(evidence, `${name}.html`), html!)
    await output.setContent(html!, { waitUntil: 'load' })
    await output.evaluate(() => document.fonts.ready)
    await output.pdf({
      path: join(evidence, `${name}.pdf`),
      preferCSSPageSize: true,
      printBackground: true,
    })
    if (name === 'fua-referencia-revision')
      await output.screenshot({ path: join(evidence, `${name}.png`), fullPage: true })
  }
  await output.close()
  expect(errors).toEqual([])
  await writeFile(
    join(evidence, 'resultado.json'),
    JSON.stringify(
      {
        attentionId: saved.id,
        patientId: patient.id,
        metrics,
        snapshot: saved.fua_impresion,
        errors,
      },
      null,
      2,
    ),
  )
})
