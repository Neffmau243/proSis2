import { expect, test } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { downloadFuaPdf } from './fuaPdfDownload'

// Run with run_referral_e2e.py --spec gestante-fua.spec.ts. The runner owns
// an empty disposable database; this never creates a patient in the user's DB.
test.skip(!process.env.REFERRAL_E2E_URL, 'Requires the isolated API and MySQL database')
test.beforeAll(() => {
  expect(process.env.REFERRAL_E2E_DATABASE).toMatch(/^ipress_test_referral_e2e_[a-f0-9]{10}$/)
  expect(new URL(process.env.REFERRAL_E2E_URL!).hostname).toBe('127.0.0.1')
})

test('gestante: FPP y edad valorada llegan desde admisión hasta el PDF y la copia histórica', async ({
  page, request, context,
}) => {
  test.setTimeout(180_000)
  page.setDefaultTimeout(15_000)
  const evidence = process.env.REFERRAL_E2E_EVIDENCE!
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
      tipo_documento_codigo: 'DNI', numero_documento: '00000002',
      apellido_paterno: 'PRUEBA', apellido_materno: 'FICTICIA', primer_nombre: 'ANA',
      sexo_codigo: 'F', fecha_nacimiento: '1995-01-02', historia_clinica: 'E2E-GESTANTE-002',
      establecimiento_registro_id: Number(process.env.REFERRAL_E2E_SITE),
      seguro_id: Number(process.env.REFERRAL_E2E_INSURANCE),
      sis_diresa: '040', sis_tipo: '2', sis_numero: '00000002', etnia_codigo: '58',
    },
  })
  expect(createdPatient.status(), await createdPatient.text()).toBe(201)
  const patient = await createdPatient.json()
  await context.addInitScript(data => {
    localStorage.setItem('ipress:session', JSON.stringify(data))
    const host = window as unknown as { __pregnancyPrints: string[] }
    host.__pregnancyPrints = []
    window.print = () => {
      const top = window.top as unknown as { __pregnancyPrints?: string[] }
      top.__pregnancyPrints?.push(document.documentElement.outerHTML)
    }
  }, { ...session, nombre_usuario: 'referencia.e2e', expires_at: Date.now() + session.expires_in * 1000 })
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const encounters: { attentionId: number; snapshot: Record<string, unknown> }[] = []
  const measurements = page.locator('.clinical-section--measurements')
  const age = page.getByRole('spinbutton', { name: 'Edad gestacional en semanas', exact: true })
  const fillMeasurement = async (label: string, value: string) => {
    await page.getByLabel(label, { exact: true }).fill(value)
    await page.getByLabel(label, { exact: true }).press('Tab')
  }
  const prepare = async (captureEmpty = false) => {
    await page.setViewportSize({ width: 1280, height: 1000 })
    await page.goto(`/admision?patientId=${patient.id}`)
    await expect(page.getByLabel('SIS · Número de afiliación', { exact: true })).toHaveValue('00000002')
    const date = page.locator('input[aria-label="Fecha y hora de atención"]')
    await date.fill('20/10/2026 10:30')
    await date.press('Enter')
    await page.getByText('Gestantes', { exact: true }).click()
    await expect(age).toHaveValue('')
    await expect(page.getByText('Registre la edad valorada o revise la fecha probable de parto para calcularla.',
      { exact: true })).toHaveCount(0)
    await expect(measurements.locator('.gestational-age-help')).toHaveCount(0)
    if (captureEmpty) {
      for (const width of [1280, 390]) {
        await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
        await age.scrollIntoViewIfNeeded()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
        await measurements.screenshot({ path: join(evidence, `gestante-sin-mensaje-${width}.png`) })
      }
      await page.setViewportSize({ width: 1280, height: 1000 })
    }
    const office = page.locator('.admission-context-field').filter({ hasText: /^Consultorio/ })
    await office.getByRole('combobox').click()
    await page.getByRole('option', { name: /CONSULTORIO E2E/ }).click()
    const professional = page.locator('.admission-context-field').filter({ hasText: /^Profesional/ })
    await expect(professional.getByRole('combobox')).toBeEnabled()
    await professional.getByRole('combobox').click()
    await page.getByRole('option', { name: 'PROFESIONAL E2E', exact: true }).click()
    await measurements.locator('.measurement-field').filter({ hasText: 'Tipo de embarazo' })
      .locator('.el-select').click()
    await page.getByRole('option', { name: 'Embarazo único', exact: true }).click()
    await fillMeasurement('Peso antes del embarazo (kg)', '55')
    await fillMeasurement('Peso actual (kg)', '62')
    await fillMeasurement('Talla (cm)', '160')
    await fillMeasurement('Presión sistólica', '110')
    await fillMeasurement('Presión diastólica', '70')
    const due = page.getByLabel('Fecha probable de parto', { exact: true })
    await due.fill('2026-12-27')
    await due.press('Enter')
    await expect(age).toHaveValue('30')
    await expect(measurements.getByText(/Según FPP: 30 semanas y 2 días/)).toBeVisible()
    await expect(page.getByLabel('Perímetro abdominal (cm)', { exact: true })).toHaveCount(0)
  }
  const saveAndReview = async (name: string, weeks: number, source: string) => {
    const pending = page.waitForResponse(r => r.request().method() === 'POST' &&
      r.url().endsWith('/api/v1/atenciones'))
    await page.getByRole('button', { name: 'Guardar atención', exact: true }).click()
    const response = await pending
    expect(response.status(), await response.text()).toBe(201)
    const saved = await response.json()
    expect(saved.fua_impresion).toMatchObject({
      grupo_atencion_codigo: 'GESTANTES', fecha_atencion: '2026-10-20',
      fecha_probable_parto: '2026-12-27', edad_gestacional_semanas: weeks,
      edad_gestacional_fuente: source,
      edad_gestacional_dias: source === 'FPP' ? 2 : null,
    })
    const reloaded = await request.get(`/api/v1/atenciones/${saved.id}`, { headers })
    expect((await reloaded.json()).fua_impresion).toEqual(saved.fua_impresion)
    encounters.push({ attentionId: saved.id, snapshot: saved.fua_impresion })
    await page.getByRole('button', { name: 'Imprimir S.I.S.', exact: true }).click()
    const pendingFields = page.locator('label.el-checkbox').filter({ hasText: 'Revisé los faltantes' })
    if (await pendingFields.count()) await pendingFields.click()
    await expect(page.locator('dd').filter({ hasText: new RegExp(`^${weeks} semanas`) })).toBeVisible()
    await page.getByRole('tab', { name: 'Vista previa y calibración' }).click()
    await expect(page.getByLabel('Ajustar Edad gestacional (semanas)', { exact: true })).toHaveText(String(weeks))
    await expect(page.getByLabel('Ajustar X · Gestante', { exact: true })).toHaveText('X')
    await expect(page.getByLabel('Ajustar X · Puérpera', { exact: true })).toHaveText('·')
    const { download, content } = await downloadFuaPdf(page)
    expect(content).toContain(`(${weeks}) Tj`)
    expect(content).toContain('E2E-GESTANTE-002')
    await download.saveAs(join(evidence, `${name}.pdf`))
    const calibrated = page.locator('label.el-checkbox').filter({ hasText: 'Comprobé tamaño y alineación' })
    if (!await calibrated.locator('input').isChecked()) await calibrated.click()
    await page.getByRole('button', { name: 'Imprimir sobre FUA preimpresa', exact: true }).click()
    const prints = () => page.evaluate(() => (window as unknown as { __pregnancyPrints: string[] }).__pregnancyPrints)
    await expect.poll(async () => (await prints()).length).toBe(1)
    const html = (await prints())[0]!
    expect(html).not.toContain('<img')
    const agePosition = await page.evaluate(() => {
      const fields = JSON.parse(localStorage.getItem('ipress.fua-layout.v1')!).fields as
        { id: string; x: number; y: number }[]
      return fields.find(f => f.id === 'edad_gestacional_semanas')!
    })
    expect(html).toContain(`left:${agePosition.x}mm;top:${agePosition.y}mm`)
    const paper = await context.newPage()
    await paper.setContent(html)
    const printedAge = paper.locator(`body > div[style*="left:${agePosition.x}mm;top:${agePosition.y}mm"]`)
    await expect(printedAge).toHaveText(String(weeks))
    await paper.pdf({ path: join(evidence, `${name}-solo-datos.pdf`), preferCSSPageSize: true })
    await paper.close()
    return saved
  }

  await prepare(true)
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await age.scrollIntoViewIfNeeded()
    await expect(age).toHaveValue('30')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await measurements.screenshot({ path: join(evidence, `gestante-mediciones-${width}.png`) })
  }
  await page.setViewportSize({ width: 1280, height: 1000 })
  const automatic = await saveAndReview('fua-gestante-fpp', 30, 'FPP')
  await prepare()
  await age.fill('29')
  await age.press('Tab')
  await expect(measurements.getByText('Se imprimirá la edad valorada por el profesional.')).toBeVisible()
  // Reset is explicit; the professional's assessment can override the suggestion.
  await page.getByRole('button', { name: 'Usar cálculo por FPP' }).click()
  await expect(age).toHaveValue('30')
  await age.fill('29')
  await age.press('Tab')
  await saveAndReview('fua-gestante-valorada', 29, 'VALORACION')
  const historical = await request.get(`/api/v1/atenciones/${automatic.id}`, { headers })
  expect((await historical.json()).fua_impresion).toEqual(automatic.fua_impresion)
  expect(errors).toEqual([])
  await writeFile(join(evidence, 'resultado.json'), JSON.stringify({
    patientId: patient.id, encounters, historical_snapshot_unchanged: true, errors,
  }, null, 2))
})
