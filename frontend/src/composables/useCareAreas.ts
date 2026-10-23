import { computed, onMounted, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { areasAtencion, type CareArea } from '@/services/configuracionAtencion'
export function useCareAreas() {
  const items = shallowRef<CareArea[]>([]),
    search = shallowRef(''),
    includeInactive = shallowRef(false)
  const loading = shallowRef(false),
    saving = shallowRef(false),
    error = shallowRef<string | null>(null)
  const visible = shallowRef(false),
    editing = shallowRef<CareArea | null>(null),
    name = shallowRef(''),
    formError = shallowRef<string | null>(null)
  const filtered = computed(() =>
    items.value.filter((item) =>
      item.nombre.toLocaleLowerCase('es').includes(search.value.trim().toLocaleLowerCase('es')),
    ),
  )
  let request = 0
  async function load() {
    const current = ++request
    loading.value = true
    error.value = null
    try {
      const result = await areasAtencion.list(includeInactive.value)
      if (current === request) items.value = result
    } catch (cause) {
      if (current === request)
        error.value = cause instanceof Error ? cause.message : 'No se pudieron cargar las áreas.'
    } finally {
      if (current === request) loading.value = false
    }
  }
  function open(item: CareArea | null = null) {
    editing.value = item
    name.value = item?.nombre || ''
    formError.value = null
    visible.value = true
  }
  async function save() {
    if (saving.value) return
    if (name.value.trim().length < 2) {
      formError.value = 'Ingrese un nombre de al menos 2 caracteres.'
      return
    }
    saving.value = true
    formError.value = null
    try {
      await areasAtencion.save(name.value.trim(), editing.value?.codigo)
      visible.value = false
      ElMessage.success('Área guardada.')
      await load()
    } catch (cause) {
      formError.value = cause instanceof Error ? cause.message : 'No se pudo guardar el área.'
    } finally {
      saving.value = false
    }
  }
  async function toggle(item: CareArea) {
    try {
      await ElMessageBox.confirm(
        `Se ${item.activo ? 'dará de baja' : 'reactivará'} «${item.nombre}». Se conservarán sus vínculos e historial.`,
        item.activo ? 'Dar de baja área' : 'Reactivar área',
        {
          confirmButtonText: item.activo ? 'Dar de baja' : 'Reactivar',
          cancelButtonText: 'Cancelar',
          type: 'info',
        },
      )
    } catch {
      return
    }
    if (saving.value) return
    saving.value = true
    error.value = null
    try {
      await areasAtencion.setActive(item.codigo, !item.activo)
      await load()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : 'No se pudo cambiar el estado.'
    } finally {
      saving.value = false
    }
  }
  watch(includeInactive, load)
  onMounted(load)
  return {
    filtered,
    search,
    includeInactive,
    loading,
    saving,
    error,
    load,
    visible,
    editing,
    name,
    formError,
    open,
    save,
    toggle,
  }
}
