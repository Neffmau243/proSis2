import { expect, test, type Locator, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { randomInt, randomUUID } from 'node:crypto'
import { downloadFuaPdf } from './fuaPdfDownload'

// Mutations are allowed only in a new Compose project owned by the Docker runner.
test.skip(!process.env.DOCKER_E2E_URL, 'Requires the isolated Docker E2E stack')

function field(page: Page, scope: Locator, label: string) {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return scope.locator('.el-form-item').filter({
    has: page.locator('.el-form-item__label').filter({ hasText: new RegExp(`^${escaped}$`) }),
  })
}

async function selectOption(page: Page, control: Locator, label: string, search = false) {
  await control.press('ArrowDown')
  if (search) await control.fill(label)
  await page.getByRole('option', { name: label, exact: true }).click()
}

async function login(page: Page, username: string, password: string) {
  await page.goto('/login')
  await selectOption(page, page.getByLabel('Usuario', { exact: true }), username, true)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  const pending = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
  const response = await pending
  expect(response.status(), await response.text()).toBe(200)
  await expect(page).not.toHaveURL(/\/login(?:\?|$)/)
  return response.json()
}

test('Docker: admin crea médico y cuenta; el médico atiende y emite un FUA con PDF', async ({ page, request, context }) => {
  page.setDefaultTimeout(15_000)
  expect(process.env.DOCKER_E2E_PROJECT).toMatch(/^ipress_docker_e2e_[a-f0-9]{10}$/)
  expect(new URL(process.env.DOCKER_E2E_URL!).hostname).toBe('127.0.0.1')
  const evidence = process.env.DOCKER_E2E_EVIDENCE!
  await mkdir(evidence, { recursive: true })
  const suffix = randomUUID().replaceAll('-', '').slice(0, 6)
  const doctorName = `PRUEBA E2E DOCKER MIGUEL ANDRES SALAZAR ${suffix.toUpperCase()}`
  const doctorDocument = String(randomInt(90_000_000, 99_999_999))
  const patientDocument = String(randomInt(80_000_000, 89_999_999))
  const username = `medico.docker.e2e.${suffix}`
  const password = String(randomInt(10_000_000, 99_999_999))
  const colegiatura = String(randomInt(100_000, 999_999))
  const testDate = process.env.DOCKER_E2E_DATE || '2026-10-23'
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const progress: Record<string, unknown> = {
    project: process.env.DOCKER_E2E_PROJECT,
    url: process.env.DOCKER_E2E_URL,
    doctorName, doctorDocument, colegiatura, username, password,
    synthetic_data_only: true,
  }
  const saveProgress = async (stage: string) => {
    progress.stage = stage
    await writeFile(join(evidence, 'resultado.json'), JSON.stringify(progress, null, 2))
  }
  await saveProgress('starting')

  const admin = await login(page, process.env.DOCKER_E2E_ADMIN_USERNAME || 'admin', process.env.DOCKER_E2E_ADMIN_PASSWORD!)
  expect(admin.roles).toContain('ADMIN')
  const adminHeaders = { Authorization: `Bearer ${admin.access_token}` }
  const officesResponse = await request.get('/api/v1/configuracion/consultorios', { headers: adminHeaders })
  expect(officesResponse.status()).toBe(200)
  const offices = await officesResponse.json()
  const office = offices.find((item: { codigo: string; establecimiento_nombre: string }) =>
    item.codigo === 'MED' && item.establecimiento_nombre.includes('ALTO SELVA ALEGRE'))
  expect(office).toBeTruthy()
  progress.officeId = office.id
  progress.siteId = office.establecimiento_id

  // Every mutation in this administrative phase is performed using the actual SPA.
  await page.goto('/configuracion/personal')
  await page.getByRole('button', { name: 'Nuevo profesional', exact: true }).click()
  const professionalDialog = page.getByRole('dialog', { name: 'Nuevo profesional', exact: true })
  await professionalDialog.getByLabel('Nombre completo', { exact: true }).fill(doctorName)
  await professionalDialog.getByLabel('Documento', { exact: true }).fill(doctorDocument)
  await selectOption(page, professionalDialog.getByLabel('Profesión', { exact: true }), 'MEDICO', true)
  await professionalDialog.getByLabel('Colegiatura', { exact: true }).fill(colegiatura)
  await selectOption(page, field(page, professionalDialog, 'Áreas y especialidades').getByRole('combobox'), 'MEDICINA')
  await page.keyboard.press('Escape')
  await professionalDialog.screenshot({ path: join(evidence, '01-medico-datos-completos.png') })
  const professionalPending = page.waitForResponse(r => r.url().endsWith('/api/v1/configuracion/profesionales') && r.request().method() === 'POST')
  await professionalDialog.getByRole('button', { name: 'Guardar', exact: true }).click()
  const professionalResponse = await professionalPending
  expect(professionalResponse.status(), await professionalResponse.text()).toBe(201)
  const professional = await professionalResponse.json()
  expect(professional).toMatchObject({ nombre_completo: doctorName, numero_documento: doctorDocument, colegiatura })
  expect(professional.profesion_id).toBeGreaterThan(0)
  expect(professional.especialidades).toEqual([{ especialidad_codigo: 'ESPECIALIDADES:003', es_principal: true }])
  progress.professionalId = professional.id
  await saveProgress('professional_created')

  const doctorRow = page.locator('.professionals-table .el-table__row').filter({ hasText: doctorName })
  await doctorRow.getByRole('button', { name: 'Crear cuenta', exact: true }).click()
  const userDialog = page.getByRole('dialog', { name: 'Nuevo usuario', exact: true })
  await userDialog.getByLabel('Nombre de usuario', { exact: true }).fill(username)
  await userDialog.getByLabel('Contraseña', { exact: true }).fill(password)
  await userDialog.getByLabel('Confirmar contraseña', { exact: true }).fill(password)
  await expect(userDialog.getByRole('checkbox', { name: 'PROFESIONAL — atención clínica' })).toBeChecked()
  await expect(userDialog.getByRole('checkbox', { name: 'ADMIN — gestión administrativa' })).not.toBeChecked()
  const userPending = page.waitForResponse(r => r.url().endsWith('/api/v1/usuarios') && r.request().method() === 'POST')
  await userDialog.getByRole('button', { name: 'Crear usuario', exact: true }).click()
  const userResponse = await userPending
  expect(userResponse.status(), await userResponse.text()).toBe(201)
  const user = await userResponse.json()
  expect(user).toMatchObject({ nombre_usuario: username, profesional_id: professional.id, roles: ['PROFESIONAL'] })
  progress.userId = user.id
  await saveProgress('account_created')

  await page.goto(`/configuracion/consultorios/${office.id}`)
  await page.getByRole('button', { name: 'Ver profesionales de MEDICINA GENERAL', exact: true }).click()
  await page.getByRole('button', { name: 'Asignar profesional', exact: true }).click()
  const assignmentDialog = page.getByRole('dialog', { name: 'Asignar profesional', exact: true })
  await selectOption(page, assignmentDialog.getByLabel('Profesional', { exact: true }), doctorName, true)
  const start = field(page, assignmentDialog, 'Fecha de inicio').getByRole('combobox')
  await start.fill(testDate)
  await start.press('Enter')
  const allServices = assignmentDialog.getByRole('checkbox', { name: 'Todos los servicios del consultorio' })
  await expect(allServices).not.toBeChecked()
  await expect(assignmentDialog.getByRole('combobox', { name: 'Servicios del profesional' })).toBeVisible()
  await assignmentDialog.screenshot({ path: join(evidence, '02-asignacion-medicina-general.png') })
  const assignmentPending = page.waitForResponse(r => r.url().endsWith(`/consultorios/${office.id}/profesionales`) && r.request().method() === 'POST')
  await assignmentDialog.getByRole('button', { name: 'Guardar asignación', exact: true }).click()
  const assignmentResponse = await assignmentPending
  expect(assignmentResponse.status(), await assignmentResponse.text()).toBe(201)
  const assignment = await assignmentResponse.json()
  expect(assignment).toMatchObject({ profesional_id: professional.id, fecha_inicio: testDate, servicios_codigos: ['ESP_MEDICINA:001'] })
  progress.assignment = assignment
  await saveProgress('assigned_to_general_medicine')

  // A new browser context proves that the new credentials work through the login screen.
  const clinicalContext = await context.browser()!.newContext({ baseURL: process.env.DOCKER_E2E_URL, viewport: { width: 1440, height: 1100 } })
  const clinicalPage = await clinicalContext.newPage()
  clinicalPage.setDefaultTimeout(15_000)
  clinicalPage.on('pageerror', error => errors.push(error.message))
  const clinician = await login(clinicalPage, username, password)
  expect(clinician.roles).toEqual(['PROFESIONAL'])
  const clinicalHeaders = { Authorization: `Bearer ${clinician.access_token}` }
  const adminDenied = await request.get('/api/v1/usuarios', { headers: clinicalHeaders })
  expect(adminDenied.status()).toBe(403)
  const insuranceResponse = await request.get('/api/v1/catalogos/seguros', { headers: clinicalHeaders })
  const insurances = await insuranceResponse.json()
  const insurance = insurances.find((item: { codigo: string }) => item.codigo === 'SIS_GRATUITO')
  expect(insurance).toBeTruthy()
  const localitiesResponse = await request.get('/api/v1/catalogos/localidades?ubigeo_codigo=040102&limit=1', { headers: clinicalHeaders })
  expect(localitiesResponse.status()).toBe(200)
  const locality = (await localitiesResponse.json()).items[0]
  expect(locality).toBeTruthy()
  // The patient is a synthetic fixture created through the container API as the new clinician.
  const patientResponse = await request.post('/api/v1/patients', {
    headers: clinicalHeaders,
    data: {
      tipo_documento_codigo: 'DNI', numero_documento: patientDocument,
      apellido_paterno: 'PRUEBA', apellido_materno: 'DOCKER', primer_nombre: 'PACIENTE',
      otros_nombres: suffix.toUpperCase(), sexo_codigo: 'M', fecha_nacimiento: '1990-01-02',
      fecha_inscripcion: testDate, historia_clinica: `E2E-DOCKER-${suffix.toUpperCase()}`,
      ubigeo_residencia_codigo: '040102', direccion: 'DOMICILIO FICTICIO DE PRUEBA',
      localidad_id: locality.id, localidad: locality.nombre,
      establecimiento_registro_id: office.establecimiento_id, seguro_id: insurance.id,
      sis_diresa: '040', sis_tipo: '2', sis_numero: patientDocument, etnia_codigo: '58',
    },
  })
  expect(patientResponse.status(), await patientResponse.text()).toBe(201)
  const patient = await patientResponse.json()
  progress.patientId = patient.id
  await saveProgress('synthetic_patient_created')
  await clinicalPage.goto(`/admision?patientId=${patient.id}`)
  const date = clinicalPage.locator('input[aria-label="Fecha y hora de atención"]')
  await date.fill(`${testDate.split('-').reverse().join('/')} 10:30`)
  await date.press('Enter')
  const officeControl = field(clinicalPage, clinicalPage.locator('form.encounter-form'), 'Consultorio').getByRole('combobox')
  await officeControl.press('ArrowDown')
  await clinicalPage.getByRole('option', { name: `${office.codigo} · ${office.ruta || office.nombre}`, exact: true }).click()
  await selectOption(clinicalPage, field(clinicalPage, clinicalPage.locator('form.encounter-form'), 'Servicio / especialidad').getByRole('combobox'), 'MEDICINA GENERAL')
  const professionalControl = field(clinicalPage, clinicalPage.locator('form.encounter-form'), 'Profesional').getByRole('combobox')
  await selectOption(clinicalPage, professionalControl, doctorName, true)
  for (const [label, value] of [['Peso actual (kg)', '72'], ['Talla (cm)', '175'], ['Presión sistólica', '120'], ['Presión diastólica', '80']]) {
    await clinicalPage.getByLabel(label!, { exact: true }).fill(value!)
    await clinicalPage.getByLabel(label!, { exact: true }).press('Tab')
  }
  await clinicalPage.screenshot({ path: join(evidence, '03-admision-medico-nuevo.png'), fullPage: true })
  const attentionPending = clinicalPage.waitForResponse(r => r.url().endsWith('/api/v1/atenciones') && r.request().method() === 'POST')
  await clinicalPage.getByRole('button', { name: 'Guardar atención', exact: true }).click()
  const attentionResponse = await attentionPending
  expect(attentionResponse.status(), await attentionResponse.text()).toBe(201)
  const attention = await attentionResponse.json()
  expect(attention).toMatchObject({ profesional_id: professional.id, consultorio_id: office.id, especialidad_codigo: 'ESP_MEDICINA:001', estado: 'ATENDIDO' })
  expect(attention.fua_impresion).toMatchObject({ profesional_nombre: doctorName, profesional_documento: doctorDocument, profesional_colegiatura: colegiatura })
  progress.attentionId = attention.id
  await saveProgress('attention_saved')

  await clinicalPage.goto(`/atenciones/${attention.id}`)
  await clinicalPage.getByRole('button', { name: 'Registrar FUA', exact: true }).click()
  const fuaDialog = clinicalPage.getByRole('dialog', { name: 'Registrar FUA', exact: true })
  await fuaDialog.getByRole('textbox', { name: 'Observaciones', exact: true }).fill('PRUEBA E2E DOCKER — DOCUMENTO FICTICIO')
  const fuaPending = clinicalPage.waitForResponse(r => r.url().endsWith('/api/v1/documentos/fua') && r.request().method() === 'POST')
  await fuaDialog.getByRole('button', { name: 'Emitir', exact: true }).click()
  const fuaResponse = await fuaPending
  expect(fuaResponse.status(), await fuaResponse.text()).toBe(201)
  const fua = await fuaResponse.json()
  expect(fua).toMatchObject({ atencion_id: attention.id, estado: 'EMITIDO', codigo_renipress: '00001291' })
  expect(fua.numero_fua).toMatch(new RegExp(`^00001291-${testDate.slice(2, 4)}-\\d{8}$`))
  await clinicalPage.getByRole('dialog', { name: 'Documento emitido' }).screenshot({ path: join(evidence, '04-fua-emitido.png') })
  await clinicalPage.getByRole('button', { name: 'Entendido', exact: true }).click()
  await clinicalPage.getByRole('button', { name: 'Imprimir S.I.S.', exact: true }).click()
  const missing = clinicalPage.locator('label.el-checkbox').filter({ hasText: 'Revisé los faltantes' })
  if (await missing.count()) await missing.click()
  const { download, content } = await downloadFuaPdf(clinicalPage)
  expect(content).toContain(doctorDocument)
  expect(content).toContain(patientDocument)
  expect(content).toContain(`E2E-DOCKER-${suffix.toUpperCase()}`)
  await download.saveAs(join(evidence, 'fua-medico-docker.pdf'))
  const persisted = await request.get(`/api/v1/atenciones/${attention.id}`, { headers: clinicalHeaders })
  expect((await persisted.json()).fua_impresion).toEqual(attention.fua_impresion)
  expect(errors).toEqual([])
  progress.fua = fua
  progress.pdf = join(evidence, 'fua-medico-docker.pdf')
  progress.errors = errors
  progress.status = 'passed'
  await saveProgress('completed')
  await clinicalContext.close()
})
