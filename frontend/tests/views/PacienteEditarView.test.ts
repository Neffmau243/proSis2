import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import PacienteEditarView from '@/views/PacienteEditarView.vue'
import AdmissionPatientSummary from '@/components/admission/AdmissionPatientSummary.vue'
import { pacientes } from '@/services/pacientes'
import { catalogos } from '@/services/catalogos'
import { useAuthStore } from '@/stores/auth'
import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import { aPatient } from '../fixtures/patient'
vi.mock('@/services/pacientes', () => ({ pacientes: { get: vi.fn() } }))
vi.mock('@/services/catalogos', () => ({
  catalogos: { tiposDocumento: vi.fn(), gruposRiesgo: vi.fn() },
}))
vi.mock('@/components/admission/AdmissionPatientSummary.vue', () => ({
  default: {
    name: 'AdmissionPatientSummary',
    props: ['patient', 'canEdit', 'tiposDocumento', 'gruposRiesgo'],
    emits: ['saved', 'dirtyChange', 'busyChange'],
    template: '<section>Editor compartido</section>',
  },
}))
const mounted: VueWrapper[] = []
async function render() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permisos = ['PACIENTE_LEER', 'PACIENTE_EDITAR']
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/pacientes/:id/editar',
        component: PacienteEditarView,
        props: (route) => ({ patientId: Number(route.params.id) }),
      },
      {
        path: '/pacientes/:id',
        name: 'paciente-detalle',
        component: { template: '<div>Ficha</div>' },
      },
    ],
  })
  await router.push('/pacientes/7/editar')
  const wrapper = mount(
    { template: '<router-view />' },
    { global: { plugins: [pinia, router, ElementPlus] } },
  )
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.resetAllMocks()
  usePacienteSeleccionado().seleccionar(null)
  vi.mocked(pacientes.get).mockResolvedValue(aPatient({ id: 7 }))
  vi.mocked(catalogos.tiposDocumento).mockResolvedValue([])
  vi.mocked(catalogos.gruposRiesgo).mockResolvedValue([])
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
})
afterEach(() => {
  mounted.splice(0).forEach((item) => item.unmount())
  vi.restoreAllMocks()
})

test('admin reutiliza el editor de pacientes sin requerir permisos clínicos', async () => {
  const { wrapper } = await render()
  expect(pacientes.get).toHaveBeenCalledWith(7)
  const panel = wrapper.findComponent(AdmissionPatientSummary)
  expect(panel.props('canEdit')).toBe(true)
  expect(panel.props('patient').id).toBe(7)
  expect(wrapper.text()).toContain('Editar paciente')
  expect(useAuthStore().hasPermission('ATENCION_CREAR')).toBe(false)
})

test('guardar actualiza el paciente seleccionado y avisa al listado', async () => {
  const selected = usePacienteSeleccionado()
  selected.seleccionar(aPatient({ id: 7 }))
  const version = selected.dataVersion.value
  const { wrapper } = await render()
  selected.seleccionar(aPatient({ id: 7 }))
  const changed = aPatient({ id: 7, primer_nombre: 'Nombre corregido' })
  wrapper.findComponent(AdmissionPatientSummary).vm.$emit('saved', changed)
  await flushPromises()
  expect(selected.seleccionado.value?.primer_nombre).toBe('Nombre corregido')
  expect(selected.dataVersion.value).toBe(version + 1)
  expect(wrapper.findComponent(AdmissionPatientSummary).props('patient')).toEqual(changed)
})

test('cancelar la salida conserva los cambios y una operación en curso impide navegar', async () => {
  const { wrapper, router } = await render()
  const panel = wrapper.findComponent(AdmissionPatientSummary)
  panel.vm.$emit('dirtyChange', true)
  vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('cancel')
  await router.push('/pacientes/7')
  expect(router.currentRoute.value.path).toBe('/pacientes/7/editar')
  panel.vm.$emit('busyChange', true)
  await router.push('/pacientes/7')
  expect(router.currentRoute.value.path).toBe('/pacientes/7/editar')
  panel.vm.$emit('busyChange', false)
  panel.vm.$emit('dirtyChange', false)
  await router.push('/pacientes/7')
  expect(router.currentRoute.value.path).toBe('/pacientes/7')
})
