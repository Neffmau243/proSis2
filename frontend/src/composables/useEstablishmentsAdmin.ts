import { onMounted, reactive, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  establecimientosAdmin,
  type EstablishmentAdmin,
  type EstablishmentDraft,
} from '@/services/configuracionAtencion'

export function useEstablishmentsAdmin(
  options: { autoLoad?: boolean; onChanged?: () => Promise<void> } = {},
) {
  const items = shallowRef<EstablishmentAdmin[]>([])
  const total = shallowRef(0)
  const page = shallowRef(1)
  const search = shallowRef('')
  const includeInactive = shallowRef(false)
  const loading = shallowRef(false)
  const error = shallowRef<string | null>(null)
  const formVisible = shallowRef(false)
  const editing = shallowRef<EstablishmentAdmin | null>(null)
  const saving = shallowRef(false)
  const formError = shallowRef<string | null>(null)
  const draft = reactive<EstablishmentDraft>({
    nombre: '',
    abreviatura: null,
    codigo_renaes: null,
    codigo_ideess: null,
    ubigeo_codigo: null,
  })
  let request = 0
  async function load() {
    const current = ++request
    loading.value = true
    error.value = null
    try {
      const result = await establecimientosAdmin.list(
        search.value,
        includeInactive.value,
        (page.value - 1) * 25,
      )
      if (current === request) {
        items.value = result.items
        total.value = result.total
      }
    } catch (cause) {
      if (current === request)
        error.value =
          cause instanceof Error ? cause.message : 'No se pudieron cargar los establecimientos.'
    } finally {
      if (current === request) loading.value = false
    }
  }
  function applySearch() {
    if (page.value !== 1) page.value = 1
    else void load()
  }
  watch(includeInactive, applySearch)
  watch(page, load)
  function open(item: EstablishmentAdmin | null = null) {
    editing.value = item
    Object.assign(
      draft,
      item
        ? {
            nombre: item.nombre,
            abreviatura: item.abreviatura,
            codigo_renaes: item.codigo_renaes,
            codigo_ideess: item.codigo_ideess,
            ubigeo_codigo: item.ubigeo_codigo,
          }
        : {
            nombre: '',
            abreviatura: null,
            codigo_renaes: null,
            codigo_ideess: null,
            ubigeo_codigo: null,
          },
    )
    formError.value = null
    formVisible.value = true
  }
  async function save() {
    if (saving.value) return
    if (draft.nombre.trim().length < 2) {
      formError.value = 'Ingrese un nombre de al menos 2 caracteres.'
      return
    }
    saving.value = true
    formError.value = null
    try {
      await establecimientosAdmin.save({ ...draft, nombre: draft.nombre.trim() }, editing.value?.id)
      formVisible.value = false
      ElMessage.success('Establecimiento guardado.')
      await (options.onChanged ?? load)()
    } catch (cause) {
      formError.value =
        cause instanceof Error ? cause.message : 'No se pudo guardar el establecimiento.'
    } finally {
      saving.value = false
    }
  }
  async function toggle(item: EstablishmentAdmin) {
    try {
      await ElMessageBox.confirm(
        item.activo
          ? `Se dará de baja «${item.nombre}». Sus consultorios deben estar inactivos; se conservará el historial.`
          : `Se reactivará «${item.nombre}». Sus consultorios conservarán su estado actual.`,
        item.activo ? 'Dar de baja establecimiento' : 'Reactivar establecimiento',
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
      await establecimientosAdmin.setActive(item.id, !item.activo)
      await (options.onChanged ?? load)()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : 'No se pudo cambiar el estado.'
    } finally {
      saving.value = false
    }
  }
  onMounted(() => {
    if (options.autoLoad !== false) void load()
  })
  return {
    items,
    total,
    page,
    search,
    includeInactive,
    loading,
    error,
    load,
    applySearch,
    formVisible,
    editing,
    saving,
    formError,
    draft,
    open,
    save,
    toggle,
  }
}
