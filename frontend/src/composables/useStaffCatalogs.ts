import { onMounted, ref, shallowRef } from 'vue'

import { catalogos, type IdCatalogItem, type SpecialtyCatalogItem } from '@/services/catalogos'
import { catalogosPersonal, type StaffCatalogPayload } from '@/services/catalogosPersonal'

export type StaffCatalogKind = 'profesion' | 'especialidad'
export type StaffCatalogEntry = IdCatalogItem | SpecialtyCatalogItem

export function useStaffCatalogs(
  onSaved: (action: 'created' | 'updated' | 'deleted') => void,
  kind: StaffCatalogKind,
) {
  const professions = ref<IdCatalogItem[]>([])
  const specialties = ref<SpecialtyCatalogItem[]>([])
  const loading = shallowRef(false)
  const saving = shallowRef(false)
  const error = shallowRef<string | null>(null)
  const formError = shallowRef<string | null>(null)
  const creating = shallowRef<StaffCatalogKind | null>(null)
  const editing = shallowRef<StaffCatalogEntry | null>(null)
  const deleting = shallowRef<StaffCatalogEntry | null>(null)
  const deleteError = shallowRef<string | null>(null)

  function openDelete(item: StaffCatalogEntry): void {
    deleting.value = item
    deleteError.value = null
  }

  function cancelDelete(): void {
    if (saving.value) return
    deleting.value = null
    deleteError.value = null
  }

  async function remove(): Promise<void> {
    const item = deleting.value
    if (!item || saving.value) return
    saving.value = true
    deleteError.value = null
    try {
      if ('id' in item) {
        await catalogosPersonal.deleteProfession(item.id)
        professions.value = professions.value.filter((existing) => existing.id !== item.id)
      } else {
        await catalogosPersonal.deleteSpecialty(item.codigo)
        specialties.value = specialties.value.filter((existing) => existing.codigo !== item.codigo)
      }
      deleting.value = null
    } catch (cause) {
      deleteError.value =
        cause instanceof Error ? cause.message : 'No se pudo eliminar. Intente otra vez.'
      return
    } finally {
      saving.value = false
    }
    onSaved('deleted')
  }

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      if (kind === 'profesion') professions.value = await catalogos.profesiones()
      else specialties.value = await catalogos.especialidades()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : 'No se pudieron cargar los catálogos.'
    } finally {
      loading.value = false
    }
  }

  function open(kind: StaffCatalogKind): void {
    editing.value = null
    creating.value = kind
    formError.value = null
  }

  function openEdit(kind: StaffCatalogKind, item: StaffCatalogEntry): void {
    editing.value = item
    creating.value = kind
    formError.value = null
  }

  function cancel(): void {
    if (saving.value) return
    creating.value = null
    editing.value = null
    formError.value = null
  }

  async function save(kind: StaffCatalogKind, payload: StaffCatalogPayload): Promise<void> {
    if (saving.value) return
    saving.value = true
    formError.value = null
    const updated = editing.value !== null
    try {
      if (kind === 'profesion') {
        const item =
          editing.value && 'id' in editing.value
            ? await catalogosPersonal.updateProfession(editing.value.id, payload.nombre)
            : await catalogosPersonal.createProfession(payload.nombre)
        professions.value = [
          ...professions.value.filter((existing) => existing.id !== item.id),
          item,
        ].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
      } else {
        const item = editing.value
          ? await catalogosPersonal.updateSpecialty(
              editing.value.codigo,
              payload.nombre,
              payload.es_area,
            )
          : await catalogosPersonal.createSpecialty(payload)
        specialties.value = [
          ...specialties.value.filter((existing) => existing.codigo !== item.codigo),
          item,
        ].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
      }
      creating.value = null
      editing.value = null
      onSaved(updated ? 'updated' : 'created')
    } catch (cause) {
      formError.value =
        cause instanceof Error ? cause.message : 'No se pudo guardar. Intente otra vez.'
    } finally {
      saving.value = false
    }
  }

  onMounted(load)
  return {
    professions,
    specialties,
    loading,
    saving,
    error,
    formError,
    creating,
    editing,
    deleting,
    deleteError,
    openDelete,
    cancelDelete,
    remove,
    load,
    open,
    openEdit,
    cancel,
    save,
  }
}
