import { effectScope, nextTick, reactive, ref } from 'vue'
import { expect, test } from 'vitest'
import {
  sisFormatDefault,
  useSisAffiliationDefaults,
} from '@/composables/useSisAffiliationDefaults'

const plans = [
  { id: 72, codigo: 'SIS_GRATUITO', regimen: 'SIS', nombre: 'Gratuito', activo: true },
  { id: 73, codigo: 'SIS_AFILIACION_TEMPORAL', regimen: 'SIS', nombre: 'Temporal', activo: true },
  { id: 74, codigo: 'SIS_NRUS', regimen: 'SIS', nombre: 'NRUS', activo: true },
  { id: 75, codigo: 'SIS_SEMI_SUBSIDIADO', regimen: 'SIS', nombre: 'Semi', activo: true },
]
const sites = [
  {
    id: 41,
    disa_codigo: '040',
    nombre: 'Arequipa',
    codigo_renaes: '1291',
    codigo_ideess: null,
    abreviatura: null,
    activo: true,
  },
  {
    id: 42,
    disa_codigo: '210',
    nombre: 'Puno',
    codigo_renaes: '9991',
    codigo_ideess: null,
    abreviatura: null,
    activo: true,
  },
]
function setup(initialize = true, stored = {}) {
  const draft = reactive({
    seguro_id: null as number | null,
    establecimiento_registro_id: null as number | null,
    tipo_documento_codigo: 'DNI',
    numero_documento: '12345678',
    sis_diresa: null as string | null,
    sis_tipo: null as string | null,
    sis_numero: null as string | null,
    sis_secuencia: null,
    etnia_codigo: null,
    ubigeo_residencia_codigo: '040102',
    localidad_id: 12,
    ...stored,
  })
  const resetKey = ref(0)
  const scope = effectScope()
  const controls = scope.run(() =>
    useSisAffiliationDefaults({
      draft,
      initialize,
      resetKey,
      insurance: () => plans.find((p) => p.id === draft.seguro_id),
      establishment: () => sites.find((s) => s.id === draft.establecimiento_registro_id),
    }),
  )!
  return { draft, controls, scope, resetKey }
}
test('el formato pertenece al plan/documento; no recorta códigos técnicos ni IDs', () => {
  expect(sisFormatDefault(plans[0], 'DNI')).toBe('2')
  expect(sisFormatDefault(plans[0], 'CE')).toBe('3')
  expect(sisFormatDefault(plans[0], 'OTRO')).toBeNull()
  expect(sisFormatDefault(plans[1], 'OTRO')).toBe('E')
  expect(sisFormatDefault(plans[2], 'DNI')).toBe('R')
  expect(sisFormatDefault(plans[3], 'DNI')).toBeNull()
})

test('dos establecimientos de la misma DISA conservan 040 aunque su RENAES cambie', async () => {
  const draft = reactive({
    seguro_id: 72,
    establecimiento_registro_id: 41,
    tipo_documento_codigo: 'DNI',
    numero_documento: '12345678',
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '12345678',
    sis_secuencia: null,
    etnia_codigo: null,
  })
  const localSites = [sites[0]!, { ...sites[0]!, id: 43, codigo_renaes: '1300' }]
  const scope = effectScope()
  scope.run(() =>
    useSisAffiliationDefaults({
      draft,
      initialize: false,
      insurance: () => plans[0],
      establishment: () => localSites.find((site) => site.id === draft.establecimiento_registro_id),
    }),
  )
  draft.establecimiento_registro_id = 43
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: '040', sis_tipo: '2', sis_numero: '12345678' })
  scope.stop()
})
test('sugiere DIRESA, formato y documento sin cambiar el contrato por domicilio', async () => {
  const { draft, scope } = setup()
  draft.seguro_id = 72
  draft.establecimiento_registro_id = 41
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: '040', sis_tipo: '2', sis_numero: '12345678' })
  draft.ubigeo_residencia_codigo = '210101'
  draft.localidad_id = 23
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: '040', sis_tipo: '2' })
  draft.seguro_id = 73
  draft.establecimiento_registro_id = 42
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: '210', sis_tipo: 'E', sis_numero: null })
  scope.stop()
})
test('una corrección manual, incluso dejar vacío, se conserva al cambiar las selecciones', async () => {
  const { draft, controls, scope } = setup()
  draft.seguro_id = 72
  draft.establecimiento_registro_id = 41
  await nextTick()
  controls.markManual({ sis_diresa: '080', sis_tipo: null })
  Object.assign(draft, { sis_diresa: '080', sis_tipo: null })
  draft.seguro_id = 73
  draft.establecimiento_registro_id = 42
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: '080', sis_tipo: null })
  scope.stop()
})
test('abrir una ficha no rellena vacíos ni reemplaza un contrato de otra región', async () => {
  const { draft, scope } = setup(false, {
    seguro_id: 72,
    establecimiento_registro_id: 41,
    sis_diresa: '080',
    sis_tipo: '2',
    sis_numero: '00112233',
  })
  await nextTick()
  expect(draft.sis_diresa).toBe('080')
  draft.seguro_id = 73
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: '080', sis_tipo: 'E', sis_numero: '00112233' })
  scope.stop()
})
test('descartar restaura los códigos confirmados y permite nuevas sugerencias', async () => {
  const { draft, controls, scope, resetKey } = setup(false, {
    seguro_id: 72,
    establecimiento_registro_id: 41,
    sis_diresa: '040',
    sis_tipo: '2',
  })
  controls.markManual({ sis_tipo: 'R' })
  draft.sis_tipo = 'R'
  resetKey.value++
  draft.sis_tipo = '2'
  await nextTick()
  draft.seguro_id = 73
  await nextTick()
  expect(draft.sis_tipo).toBe('E')
  scope.stop()
})

test('espera la sede pendiente y actualiza al llegar el catálogo sin borrar antes el código', async () => {
  const draft = reactive({
    seguro_id: 72,
    establecimiento_registro_id: 41,
    tipo_documento_codigo: 'DNI',
    numero_documento: '12345678',
    sis_diresa: '040',
    sis_tipo: '2',
    sis_numero: '00112233',
    sis_secuencia: null,
    etnia_codigo: null,
  })
  const loaded = ref([sites[0]!])
  const scope = effectScope()
  scope.run(() =>
    useSisAffiliationDefaults({
      draft,
      initialize: false,
      insurance: () => plans[0],
      establishment: () => loaded.value.find((s) => s.id === draft.establecimiento_registro_id),
    }),
  )
  draft.establecimiento_registro_id = 42
  await nextTick()
  expect(draft.sis_diresa).toBe('040')
  loaded.value = sites
  await nextTick()
  expect(draft.sis_diresa).toBe('210')
  scope.stop()
})

test('el número sigue el documento válido, conserva ceros y cambia entre DNI y CE', async () => {
  const { draft, scope } = setup()
  draft.seguro_id = 72
  draft.numero_documento = '00112233'
  await nextTick()
  expect(draft.sis_numero).toBe('00112233')
  draft.numero_documento = '001122'
  await nextTick()
  expect(draft.sis_numero).toBeNull()
  draft.tipo_documento_codigo = 'CE'
  draft.numero_documento = '001122334'
  await nextTick()
  expect(draft).toMatchObject({ sis_tipo: '3', sis_numero: '001122334' })
  draft.seguro_id = 73
  await nextTick()
  expect(draft).toMatchObject({ sis_tipo: 'E', sis_numero: null })
  scope.stop()
})

test('un número de afiliación corregido manualmente no se sobrescribe con el DNI', async () => {
  const { draft, controls, scope } = setup()
  draft.seguro_id = 72
  await nextTick()
  controls.markManual({ sis_numero: '00998877' })
  draft.sis_numero = '00998877'
  draft.numero_documento = '00112233'
  await nextTick()
  expect(draft.sis_numero).toBe('00998877')
  scope.stop()
})

test('en admisión el número confirmado sigue al DNI en el borrador y descartar lo restaura', async () => {
  const { draft, scope, resetKey } = setup(false, {
    seguro_id: 72,
    sis_tipo: '2',
    sis_numero: '12345678',
  })
  await nextTick()
  expect(draft.sis_numero).toBe('12345678')
  draft.numero_documento = '00112233'
  await nextTick()
  expect(draft.sis_numero).toBe('00112233')
  resetKey.value++
  draft.numero_documento = '12345678'
  draft.sis_numero = '12345678'
  await nextTick()
  expect(draft.sis_numero).toBe('12345678')
  scope.stop()
})

test('cargar catálogos de una ficha sin afiliación no autocompleta sus vacíos guardados', async () => {
  const draft = reactive({
    seguro_id: 72,
    establecimiento_registro_id: null,
    tipo_documento_codigo: 'DNI',
    numero_documento: '12345678',
    sis_diresa: null,
    sis_tipo: null,
    sis_numero: null,
    sis_secuencia: null,
    etnia_codigo: null,
  })
  const loaded = ref<typeof plans>([])
  const scope = effectScope()
  scope.run(() =>
    useSisAffiliationDefaults({
      draft,
      initialize: false,
      insurance: () => loaded.value.find((p) => p.id === draft.seguro_id),
      establishment: () => undefined,
    }),
  )
  loaded.value = plans
  await nextTick()
  expect(draft).toMatchObject({ sis_diresa: null, sis_tipo: null, sis_numero: null })
  scope.stop()
})
