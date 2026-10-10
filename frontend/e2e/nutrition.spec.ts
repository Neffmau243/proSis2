import { expect, test, type Page } from '@playwright/test'
import { readFile, mkdir } from 'node:fs/promises'

// Requires audit_admission.py setup/serve on a new ipress_test_admission_* DB.
// The explicit gate keeps the usual FUA harness suite entirely offline.
test.skip(process.env.NUTRITION_E2E !== '1', 'Requires the isolated nutrition API on port 8001')
const evidence = '../tests/e2e/evidence_nutrition_20261008'
const stamp = Date.now().toString().slice(-7)
const profiles = [
  {
    name: 'infantil',
    birth: '2023-10-09',
    group: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    weight: '12',
    height: '86',
    doc: 'DNI',
    mode: 'AMBULATORIA',
  },
  {
    name: 'gestante',
    birth: '1998-01-01',
    group: 'GESTANTES',
    weight: '65',
    height: '160',
    doc: 'PAS',
    mode: 'AMBULATORIA',
  },
  {
    name: 'puerpera',
    birth: '1996-01-01',
    group: 'PUERPERAS',
    weight: '64',
    height: '160',
    doc: 'OTRO',
    mode: 'EMERGENCIA',
  },
]

function field(page: Page, label: string) {
  return page.locator('.el-form-item').filter({
    has: page.locator('.el-form-item__label', {
      hasText: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`),
    }),
  })
}
async function fill(page: Page, label: string, value: string) {
  const input = field(page, label).locator('input').first()
  await input.fill(value)
  await input.press('Tab')
  await page.keyboard.press('Escape')
}

for (const [index, profile] of profiles.entries()) {
  test(`${profile.name}: UI → API → MySQL → historial → descarga`, async ({ page, request }) => {
    const login = await request.post('http://127.0.0.1:8001/api/v1/auth/login', {
      data: { nombre_usuario: 'auditoria_e2e', password: '12345678' },
    })
    expect(login.ok()).toBe(true)
    const session = await login.json()
    const headers = { Authorization: `Bearer ${session.access_token}` }
    const response = await request.post('http://127.0.0.1:8001/api/v1/patients', {
      headers,
      data: {
        tipo_documento_codigo: profile.doc,
        numero_documento: `${index}${stamp}`,
        fecha_nacimiento: profile.birth,
        apellido_paterno: 'FICTICIO',
        primer_nombre: profile.name.toUpperCase(),
        historia_clinica: `HC-UI-${profile.name}-${stamp}`,
        historia_familiar: `AM-${stamp}`,
        sufijo_documento: '01',
        sexo_codigo: 'F',
        establecimiento_registro_id: 7,
        responsables:
          profile.name === 'infantil'
            ? [{ parentesco: 'MADRE', nombre_completo: 'MADRE FICTICIA' }]
            : [],
      },
    })
    expect(response.status(), await response.text()).toBe(201)
    const patient = await response.json()
    await page.addInitScript(
      (data) => localStorage.setItem('ipress:session', JSON.stringify(data)),
      {
        ...session,
        nombre_usuario: 'auditoria_e2e',
        expires_at: Date.now() + 3600_000,
      },
    )
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto(`/admision?patientId=${patient.id}`)
    await expect(page.getByRole('heading', { name: 'Valoración nutricional' })).toBeVisible({
      timeout: 30_000,
    })
    await expect(page.getByText('Datos complementarios de nutrición')).toHaveCount(0)
    await expect(page.getByText('Códigos del registro legado')).toHaveCount(0)
    await field(page, 'Consultorio').locator('.el-select').click()
    await page.getByRole('option', { name: 'PRUEBA E2E CONSULTORIO', exact: true }).click()
    await field(page, 'Profesional').locator('input').fill('PRUEBA E2E')
    await page.getByRole('option', { name: 'PRUEBA E2E PROFESIONAL', exact: true }).click()
    if (profile.mode === 'EMERGENCIA')
      await page
        .locator('label.el-radio')
        .filter({ has: page.locator('input[value="EMERGENCIA"]') })
        .click()
    if (profile.group !== 'NINOS_ADOLESCENTES_ADULTOS_MAYORES') {
      await page
        .locator('label.el-radio')
        .filter({ has: page.locator(`input[value="${profile.group}"]`) })
        .click()
      await fill(page, 'Peso antes del embarazo (kg)', '55')
    }
    await fill(page, 'Peso actual (kg)', profile.weight)
    await fill(page, 'Talla (cm)', profile.height)
    const table = page.locator('.clinical-section--nutrition .nutrition-table')
    const expectedLabels =
      profile.name === 'infantil'
        ? ['P/E', 'T/E', 'P/T']
        : profile.name === 'gestante'
          ? ['IMC', 'Dx IMC', 'Ganancia de peso']
          : ['IMC', 'Dx IMC']
    await expect(table.locator('th')).toHaveText(expectedLabels)
    if (profile.name === 'infantil') {
      await expect(page.locator('.nutrition-age')).toContainText('3 años')
    }
    if (profile.name === 'gestante') {
      await expect(table.locator('tr').nth(2).locator('td')).toHaveText('10 kg')
    }
    if (profile.name === 'puerpera') {
      await expect(table).not.toContainText('Ganancia de peso')
    }
    const savedResponse = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/atenciones'),
    )
    await page.getByRole('button', { name: 'Guardar atención', exact: true }).click()
    const saved = await savedResponse
    expect(saved.status(), await saved.text()).toBe(201)
    const body = await saved.json()
    await expect(page.getByRole('button', { name: 'Atención guardada', exact: true })).toBeVisible()
    await mkdir(evidence, { recursive: true })
    if (['infantil', 'gestante', 'puerpera'].includes(profile.name)) {
      await page.locator('.clinical-section--nutrition').screenshot({
        path: `${evidence}/${profile.name}-fields-desktop.png`,
        animations: 'disabled',
      })
      await page.locator('main').evaluate((element) => {
        element.scrollTop = 0
      })
      await page.screenshot({
        path: `${evidence}/${profile.name}-desktop.png`,
        fullPage: true,
        animations: 'disabled',
      })
      await page.setViewportSize({ width: 390, height: 844 })
      await page.getByRole('button', { name: 'Abrir menú', exact: true }).click()
      await expect(page.getByRole('navigation')).toBeVisible()
      const historyLink = page.getByRole('link', { name: 'Historial de atenciones', exact: true })
      await historyLink.scrollIntoViewIfNeeded()
      await expect(historyLink).toBeInViewport()
      await historyLink.focus()
      await expect(historyLink).toBeFocused()
      await page.screenshot({
        path: `${evidence}/${profile.name}-menu-mobile.png`,
        animations: 'disabled',
      })
      await page.getByRole('button', { name: 'Cerrar menú', exact: true }).click()
      await page.screenshot({
        path: `${evidence}/${profile.name}-mobile.png`,
        animations: 'disabled',
      })
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true)
      await page
        .locator('.clinical-section--nutrition')
        .evaluate((element) => element.scrollIntoView({ block: 'start' }))
      await page.locator('.clinical-section--nutrition').screenshot({
        path: `${evidence}/${profile.name}-fields-mobile.png`,
        animations: 'disabled',
      })
      await page.setViewportSize({ width: 1440, height: 1100 })
    }
    expect(body.evaluaciones_nutricionales).toHaveLength(1)
    expect(body.contexto_clinico.historia_familiar).toBe(`AM-${stamp}`)
    expect(body.modalidad_atencion_codigo).toBe(profile.mode)
    expect(body.grupo_atencion_codigo).toBe(profile.group)
    expect(body.valoracion_calculada).toBeTruthy()
    expect(body.fua_impresion.grupo_atencion_codigo).toBe(profile.group)
    expect(body.fua_impresion.grupo_referencia).toBe(body.valoracion_calculada.grupo_referencia)
    expect(body.fua_impresion.estado_nutricional).toBe(body.valoracion_calculada.estado)
    if (profile.name === 'infantil') {
      expect(body.valoracion_calculada.grupo_referencia).toBe('INFANTIL')
      expect(body.evaluaciones_nutricionales[0].waz).toBe(body.valoracion_calculada.pe)
      expect(body.evaluaciones_nutricionales[0].haz).toBe(body.valoracion_calculada.te)
      expect(body.evaluaciones_nutricionales[0].whz).toBe(body.valoracion_calculada.pt)
      expect(body.fua_impresion.pe).toBe(body.valoracion_calculada.pe)
      expect(body.fua_impresion.te).toBe(body.valoracion_calculada.te)
      expect(body.fua_impresion.pt).toBe(body.valoracion_calculada.pt)
    } else {
      expect(body.valoracion_calculada.imc_pregestacional).toBe('21.484')
      expect(body.fua_impresion.imc_pregestacional).toBe('21.484')
      expect(body.fua_impresion.diagnostico_imc).toBe(
        body.valoracion_calculada.diagnostico_imc.toUpperCase(),
      )
    }
    await expect(page.getByRole('button', { name: 'Atención guardada', exact: true })).toBeVisible()
    await page.goto(`/atenciones/${body.id}`)
    await expect(page.getByRole('heading', { name: 'Valoración guardada' })).toBeVisible()
    await expect(page.locator('.nutrition-summary .nutrition-table th')).toHaveText(expectedLabels)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Valoración guardada' })).toBeVisible()
    await page.getByRole('button', { name: 'Imprimir S.I.S.' }).click()
    await expect(
      page.getByRole('heading', { name: 'Valoración nutricional conservada' }),
    ).toBeVisible()
    await expect(page.locator('.fua-nutrition .nutrition-table th')).toHaveText(expectedLabels)
    await page.getByRole('button', { name: 'Cerrar', exact: true }).click()
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Descargar para revisión' }).click()
    const download = await downloadEvent
    const path = await download.path()
    const exported = JSON.parse(await readFile(path!, 'utf8'))
    expect(exported.trama_oficial).toBe(false)
    expect(exported.campos_legados.Enviado).toBe(false)
    await expect(page.getByText('Archivo de revisión exportado', { exact: true })).toBeVisible()
    await page
      .getByLabel('Constancia del envío realizado externamente')
      .fill(`CONSTANCIA-FICTICIA-${body.id}`)
    await page.getByRole('button', { name: 'Registrar constancia de envío externo' }).click()
    await expect(
      page.getByText('Envío externo registrado manualmente', { exact: true }),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByText(`Constancia de envío externo: CONSTANCIA-FICTICIA-${body.id}`, {
        exact: true,
      }),
    ).toBeVisible()
    if (profile.name === 'infantil') {
      await page.screenshot({
        path: `${evidence}/historial-desktop.png`,
        fullPage: true,
        animations: 'disabled',
      })
    }
    expect(errors).toEqual([])
  })
}
