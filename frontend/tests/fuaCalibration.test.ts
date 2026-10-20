import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, expect, test, vi } from 'vitest'
import { useFuaCalibration } from '@/composables/useFuaCalibration'
import { defaultFuaLayout, FUA_LAYOUT_KEY } from '@/utils/fuaPrint'

const wrappers: ReturnType<typeof mount>[] = []
function setup() {
  let state!: ReturnType<typeof useFuaCalibration>
  wrappers.push(
    mount(
      defineComponent({
        setup() {
          state = useFuaCalibration(() => true)
          return () => h('div')
        },
      }),
    ),
  )
  return state
}
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  localStorage.clear()
})

test('una cuota de almacenamiento agotada conserva un error y permite reintentar', () => {
  const state = setup()
  const write = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
    throw new Error('Quota')
  })
  expect(state.save()).toBe(false)
  expect(state.saved.value).toBe(false)
  expect(state.storageError.value).toContain('No se pudo guardar')
  write.mockRestore()
  expect(state.save()).toBe(true)
  expect(state.storageError.value).toBe('')
  expect(JSON.parse(localStorage.getItem(FUA_LAYOUT_KEY)!)).toMatchObject({
    width: defaultFuaLayout().width,
  })
})

test('importar conserva posiciones y requiere volver a confirmar la calibración física', async () => {
  const state = setup()
  const geometry = { ...defaultFuaLayout(), offsetX: 4, calibrated: true }
  await state.importLayout(new File([JSON.stringify(geometry)], 'calibracion.json'))
  expect(state.layout.value.offsetX).toBe(4)
  expect(state.layout.value.calibrated).toBe(false)
  state.layout.value.calibrated = true
  state.changed()
  expect(state.layout.value.calibrated).toBe(false)
  await state.importLayout(new File(['{'], 'invalido.json'))
  expect(state.storageError.value).toContain('No se pudo importar')
  expect(state.layout.value.offsetX).toBe(4)
  await state.importLayout(new File(['x'.repeat(100001)], 'excesivo.json'))
  expect(state.storageError.value).toContain('No se pudo importar')
})

test('otras pestañas actualizan la geometría y exportar descarga únicamente la calibración', async () => {
  vi.useFakeTimers()
  const state = setup()
  localStorage.setItem(FUA_LAYOUT_KEY, JSON.stringify({ ...defaultFuaLayout(), offsetY: 3 }))
  window.dispatchEvent(new StorageEvent('storage', { key: FUA_LAYOUT_KEY }))
  await nextTick()
  expect(state.layout.value.offsetY).toBe(3)
  window.dispatchEvent(new StorageEvent('storage', { key: 'otra-clave' }))
  expect(state.layout.value.offsetY).toBe(3)
  const revoke = vi.fn()
  const create = vi.fn().mockReturnValue('blob:geometria')
  vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  state.exportLayout()
  expect(click).toHaveBeenCalledOnce()
  expect(create.mock.calls[0]![0]).toBeInstanceOf(Blob)
  await vi.runAllTimersAsync()
  expect(revoke).toHaveBeenCalledWith('blob:geometria')
  localStorage.clear()
  window.dispatchEvent(new StorageEvent('storage', { key: null }))
  expect(state.layout.value.offsetY).toBe(0)
})
