import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, shallowRef } from 'vue'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { useCareAreas } from '@/composables/useCareAreas'
import { useOfficeForm } from '@/composables/useOfficeForm'
import { useEstablishmentsAdmin } from '@/composables/useEstablishmentsAdmin'
import type { CareArea, EstablishmentAdmin } from '@/services/configuracionAtencion'
import type { SpecialtyCatalogItem } from '@/services/catalogos'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  save: vi.fn(),
  setActive: vi.fn(),
  confirm: vi.fn(),
  success: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  validate: vi.fn(),
  clearValidate: vi.fn(),
}))
vi.mock('@/services/configuracionAtencion', () => ({
  areasAtencion: api,
  establecimientosAdmin: api,
}))
vi.mock('@/services/consultorios', () => ({ consultorios: api }))
vi.mock('element-plus', () => ({
  ElMessage: { success: api.success },
  ElMessageBox: { confirm: api.confirm },
}))

const mounted: { unmount: () => void }[] = []
const area: CareArea = {
  codigo: 'MED',
  nombre: 'Medicina',
  activo: true,
  es_area_base: false,
  consultorios: [],
}
beforeEach(() => {
  vi.resetAllMocks()
  api.list.mockResolvedValue([area])
  api.save.mockResolvedValue(area)
  api.setActive.mockResolvedValue(area)
  api.confirm.mockResolvedValue('confirm')
  api.validate.mockResolvedValue(true)
})
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
})

async function careAreas() {
  let state!: ReturnType<typeof useCareAreas>
  mounted.push(
    mount(
      defineComponent({
        setup() {
          state = useCareAreas()
          return () => null
        },
      }),
    ),
  )
  await flushPromises()
  return state
}

test('las áreas ignoran respuestas y errores anteriores a la búsqueda vigente', async () => {
  const state = await careAreas()
  let rejectOld!: (reason: Error) => void
  api.list.mockImplementationOnce(
    () =>
      new Promise((_, reject) => {
        rejectOld = reject
      }),
  )
  const old = state.load()
  api.list.mockResolvedValueOnce([{ ...area, nombre: 'Obstetricia' }])
  await state.load()
  rejectOld(new Error('respuesta antigua'))
  await old
  expect(state.filtered.value[0]?.nombre).toBe('Obstetricia')
  expect(state.error.value).toBeNull()
  expect(state.loading.value).toBe(false)
  state.search.value = ' OBSTE '
  expect(state.filtered.value).toHaveLength(1)
})

test('cargar áreas muestra errores y permite volver a intentar', async () => {
  api.list.mockRejectedValueOnce('sin conexión')
  const state = await careAreas()
  expect(state.error.value).toBe('No se pudieron cargar las áreas.')
  api.list.mockRejectedValueOnce(new Error('Servidor ocupado'))
  await state.load()
  expect(state.error.value).toBe('Servidor ocupado')
  state.includeInactive.value = true
  await flushPromises()
  expect(api.list).toHaveBeenLastCalledWith(true)
  expect(state.error.value).toBeNull()
})

test('crear y editar áreas valida el nombre y conserva datos ante rechazo', async () => {
  const state = await careAreas()
  state.open()
  state.name.value = ' '
  await state.save()
  expect(api.save).not.toHaveBeenCalled()
  expect(state.formError.value).toContain('al menos 2')
  state.name.value = '  Área nueva  '
  await state.save()
  expect(api.save).toHaveBeenCalledWith('Área nueva', undefined)
  expect(state.visible.value).toBe(false)
  state.open(area)
  api.save.mockRejectedValueOnce(new Error('Nombre duplicado'))
  await state.save()
  expect(state.formError.value).toBe('Nombre duplicado')
  expect(state.visible.value).toBe(true)
  api.save.mockRejectedValueOnce('error')
  await state.save()
  expect(state.formError.value).toBe('No se pudo guardar el área.')
  state.saving.value = true
  await state.save()
  expect(api.save).toHaveBeenCalledTimes(3)
})

test('dar de baja o reactivar áreas requiere confirmación y conserva el historial', async () => {
  const state = await careAreas()
  api.confirm.mockRejectedValueOnce('cancel')
  await state.toggle(area)
  expect(api.setActive).not.toHaveBeenCalled()
  await state.toggle(area)
  expect(api.setActive).toHaveBeenLastCalledWith('MED', false)
  await state.toggle({ ...area, activo: false })
  expect(api.setActive).toHaveBeenLastCalledWith('MED', true)
  expect(api.confirm).toHaveBeenLastCalledWith(
    expect.stringContaining('conservarán'),
    'Reactivar área',
    expect.any(Object),
  )
  state.saving.value = true
  await state.toggle(area)
  expect(api.setActive).toHaveBeenCalledTimes(2)
})

test('un rechazo al cambiar estado de área se muestra y no bloquea otro intento', async () => {
  const state = await careAreas()
  api.setActive.mockRejectedValueOnce(new Error('Área en uso'))
  await state.toggle(area)
  expect(state.error.value).toBe('Área en uso')
  expect(state.saving.value).toBe(false)
  api.setActive.mockRejectedValueOnce('error')
  await state.toggle(area)
  expect(state.error.value).toBe('No se pudo cambiar el estado.')
})

function officeForm(withCallback = true, withForm = true) {
  let state!: ReturnType<typeof useOfficeForm>
  const load = vi.fn().mockResolvedValue(undefined)
  const onSaved = vi.fn().mockResolvedValue(undefined)
  const Form = defineComponent({
    setup(_, { expose }) {
      expose({ validate: api.validate, clearValidate: api.clearValidate })
      return () => h('div')
    },
  })
  mounted.push(
    mount(
      defineComponent({
        setup() {
          const options = shallowRef<SpecialtyCatalogItem[]>([
            { codigo: 'MED', nombre: 'Medicina', es_area: true, activo: true, grupo: null },
            { codigo: 'GEN', nombre: 'General', es_area: false, activo: true, grupo: null },
            { codigo: 'LEG', nombre: 'Legacy', activo: true, grupo: null },
          ])
          state = useOfficeForm(options, shallowRef(7), load, withCallback ? onSaved : undefined)
          return () => (withForm ? h(Form, { ref: 'formRef' }) : null)
        },
      }),
    ),
  )
  return { state, load, onSaved }
}

test('el alta de consultorio valida antes de enviar y conserva el contexto de sede', async () => {
  const { state, load, onSaved } = officeForm()
  state.openCreate()
  expect(state.form.establecimiento_id).toBe(7)
  expect(state.formTitle.value).toBe('Nuevo consultorio')
  expect(state.areaOptions.value.map((option) => option.codigo)).toEqual(['MED', 'LEG'])
  state.changeForm({ codigo: '  MED-1 ', nombre: ' Medicina  ', area_codigo: 'MED' })
  api.validate.mockRejectedValueOnce(new Error('inválido'))
  await state.submitForm()
  expect(api.create).not.toHaveBeenCalled()
  api.create.mockResolvedValueOnce({ id: 4 })
  await state.submitForm()
  expect(api.create).toHaveBeenCalledWith({
    codigo: 'MED-1',
    nombre: 'Medicina',
    establecimiento_id: 7,
    area_codigo: 'MED',
    consultorio_padre_id: null,
  })
  expect(load).toHaveBeenCalledOnce()
  expect(onSaved).toHaveBeenCalledWith({ id: 4 }, true)
  state.saving.value = true
  await state.submitForm()
  expect(api.create).toHaveBeenCalledOnce()
})

test('editar conserva servicios y vínculos; solo envía el área si cambió', async () => {
  const { state } = officeForm()
  state.openEdit({
    id: 4,
    establecimiento_id: 7,
    codigo: 'MED-1',
    nombre: 'Medicina',
    area_codigo: null,
    consultorio_padre_id: null,
    especialidad_codigo: 'GEN',
    activo: true,
  })
  expect(state.formTitle.value).toBe('Editar consultorio')
  expect(state.areaOptions.value.some((option) => option.codigo === 'GEN')).toBe(true)
  api.update.mockResolvedValue({ id: 4 })
  await state.submitForm()
  expect(api.update).toHaveBeenLastCalledWith(4, { codigo: 'MED-1', nombre: 'Medicina' })
  state.changeForm({ area_codigo: 'MED' })
  await state.submitForm()
  expect(api.update).toHaveBeenLastCalledWith(4, {
    codigo: 'MED-1',
    nombre: 'Medicina',
    area_codigo: 'MED',
  })
})

test('un rechazo de consultorio deja el formulario abierto y evita duplicados', async () => {
  const { state } = officeForm()
  state.openCreate()
  api.create.mockRejectedValueOnce('sin conexión')
  await state.submitForm()
  expect(state.formError.value).toBe('No se pudo guardar el consultorio.')
  expect(state.formVisible.value).toBe(true)
  api.create.mockRejectedValueOnce(new Error('Código duplicado'))
  await state.submitForm()
  expect(state.formError.value).toBe('Código duplicado')
  expect(state.saving.value).toBe(false)
})

test('un formulario todavía no montado no envía; un consumidor sin callback puede guardar', async () => {
  const pending = officeForm(false, false)
  pending.state.openCreate()
  await pending.state.submitForm()
  expect(api.create).not.toHaveBeenCalled()

  const ready = officeForm(false)
  ready.state.openEdit({
    id: 4,
    establecimiento_id: 7,
    codigo: 'MED',
    nombre: 'Medicina',
    area_codigo: 'MED',
    consultorio_padre_id: null,
    especialidad_codigo: 'GEN',
    activo: true,
  })
  api.update.mockResolvedValueOnce({ id: 4 })
  await ready.state.submitForm()
  expect(ready.state.formError.value).toBeNull()
  expect(ready.onSaved).not.toHaveBeenCalled()
  expect(ready.load).toHaveBeenCalledOnce()
})

const site: EstablishmentAdmin = {
  id: 7,
  nombre: 'Sede de prueba',
  abreviatura: null,
  codigo_renaes: '1291',
  codigo_ideess: null,
  ubigeo_codigo: '040102',
  activo: true,
  ubicacion: null,
  consultorios_total: 0,
  fua_personal_atiende: 'IPRESS',
  fua_lugar_atencion: 'INTRAMURAL',
  fua_codigo_aisped: null,
  fua_renipress_preimpreso: true,
}

function establishments(onChanged?: () => Promise<void>) {
  let state!: ReturnType<typeof useEstablishmentsAdmin>
  api.list.mockResolvedValue({ items: [site], total: 1 })
  mounted.push(
    mount(
      defineComponent({
        setup() {
          state = useEstablishmentsAdmin({ autoLoad: false, onChanged })
          return () => null
        },
      }),
    ),
  )
  return state
}

test('el buscador de sedes vuelve a la primera página y consulta las bajas solo al pedirlas', async () => {
  const state = establishments()
  expect(api.list).not.toHaveBeenCalled()
  state.page.value = 2
  await flushPromises()
  expect(api.list).toHaveBeenLastCalledWith('', false, 25)
  state.search.value = 'Sede'
  state.applySearch()
  await flushPromises()
  expect(api.list).toHaveBeenLastCalledWith('Sede', false, 0)
  state.includeInactive.value = true
  await flushPromises()
  expect(api.list).toHaveBeenLastCalledWith('Sede', true, 0)
})

test('las sedes conservan la respuesta vigente frente a rechazos antiguos y permiten reintentar', async () => {
  const state = establishments()
  let rejectOld!: (reason: Error) => void
  api.list.mockImplementationOnce(
    () =>
      new Promise((_, reject) => {
        rejectOld = reject
      }),
  )
  const old = state.load()
  await state.load()
  rejectOld(new Error('rechazo antiguo'))
  await old
  expect(state.error.value).toBeNull()
  expect(state.items.value).toEqual([site])
  api.list.mockRejectedValueOnce('sin conexión')
  await state.load()
  expect(state.error.value).toBe('No se pudieron cargar los establecimientos.')
  expect(state.loading.value).toBe(false)
})

test('guardar una sede rechazada conserva sus datos; un envío duplicado no llega al servidor', async () => {
  const onChanged = vi.fn().mockResolvedValue(undefined)
  const state = establishments(onChanged)
  state.open()
  state.draft.nombre = ' '
  await state.save()
  expect(api.save).not.toHaveBeenCalled()
  state.open(site)
  api.save.mockRejectedValueOnce('sin conexión')
  await state.save()
  expect(state.formError.value).toBe('No se pudo guardar el establecimiento.')
  expect(state.formVisible.value).toBe(true)
  expect(state.draft.nombre).toBe(site.nombre)
  state.saving.value = true
  await state.save()
  expect(api.save).toHaveBeenCalledOnce()
  state.saving.value = false
  await state.save()
  expect(onChanged).toHaveBeenCalledOnce()
  expect(state.formVisible.value).toBe(false)
})

test('la baja o reactivación de sedes respeta cancelación, errores y guardado en curso', async () => {
  const state = establishments()
  api.confirm.mockRejectedValueOnce('cancel')
  await state.toggle(site)
  expect(api.setActive).not.toHaveBeenCalled()
  state.saving.value = true
  await state.toggle(site)
  expect(api.setActive).not.toHaveBeenCalled()
  state.saving.value = false
  api.setActive.mockRejectedValueOnce('sin conexión')
  await state.toggle(site)
  expect(state.error.value).toBe('No se pudo cambiar el estado.')
  await state.toggle({ ...site, activo: false })
  expect(api.setActive).toHaveBeenLastCalledWith(7, true)
  expect(api.list).toHaveBeenCalledOnce()
  expect(state.saving.value).toBe(false)
})
