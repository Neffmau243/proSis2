import { computed, ref, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { serviciosAsistenciales, type CareService } from '@/services/serviciosAsistenciales'

export function useCareServiceCatalog() {
  const items = ref<CareService[]>([])
  const loading = shallowRef(false)
  const saving = shallowRef(false)
  const error = shallowRef<string | null>(null)
  const formError = shallowRef<string | null>(null)
  const search = shallowRef('')
  const includeInactive = shallowRef(false)
  const areaFilter = shallowRef<string | null>(null)
  const editing = shallowRef<CareService | null>(null)
  const formVisible = shallowRef(false)
  const visibleItems = computed(() => {
    const query = search.value.trim().toLocaleLowerCase('es')
    return items.value.filter(
      (item) =>
        (!areaFilter.value || item.area_codigos.includes(areaFilter.value)) &&
        (!query || `${item.nombre} ${item.codigo}`.toLocaleLowerCase('es').includes(query)),
    )
  })
  let request = 0
  async function load() {
    const current = ++request
    loading.value = true
    error.value = null
    try {
      const result = await serviciosAsistenciales.list(includeInactive.value)
      if (current === request) items.value = result
    } catch (cause) {
      if (current === request)
        error.value = cause instanceof Error ? cause.message : 'No se pudo cargar el catálogo.'
    } finally {
      if (current === request) loading.value = false
    }
  }
  watch(includeInactive, load, { immediate: true })
  function open(service: CareService | null = null) {
    editing.value = service
    formError.value = null
    formVisible.value = true
  }
  async function save(payload: { nombre: string; area_codigo: string }) {
    if (saving.value) return
    saving.value = true
    formError.value = null
    try {
      if (editing.value) await serviciosAsistenciales.update(editing.value.codigo, payload.nombre)
      else await serviciosAsistenciales.create(payload)
      formVisible.value = false
      ElMessage.success(
        editing.value
          ? 'Servicio actualizado en el catálogo.'
          : 'Servicio registrado. Ya puedes habilitarlo en un consultorio.',
      )
      await load()
    } catch (cause) {
      formError.value = cause instanceof Error ? cause.message : 'No se pudo guardar el servicio.'
    } finally {
      saving.value = false
    }
  }
  async function toggle(service: CareService) {
    if (saving.value) return
    try {
      await ElMessageBox.confirm(
        service.activo
          ? `Se dará de baja «${service.nombre}» del catálogo general. Se conservará su historial. Si está habilitado en consultorios activos, primero debes quitarlo de ellos.`
          : `«${service.nombre}» volverá a estar disponible para habilitarlo en consultorios.`,
        service.activo ? 'Dar de baja servicio' : 'Reactivar servicio',
        {
          confirmButtonText: service.activo ? 'Dar de baja' : 'Reactivar',
          cancelButtonText: 'Cancelar',
          type: 'warning',
        },
      )
    } catch {
      return
    }
    saving.value = true
    error.value = null
    try {
      await serviciosAsistenciales.setActive(service)
      ElMessage.success(service.activo ? 'Servicio dado de baja.' : 'Servicio reactivado.')
      await load()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : 'No se pudo cambiar el estado.'
    } finally {
      saving.value = false
    }
  }
  return {
    items,
    visibleItems,
    loading,
    saving,
    error,
    formError,
    search,
    includeInactive,
    areaFilter,
    editing,
    formVisible,
    load,
    open,
    save,
    toggle,
  }
}
