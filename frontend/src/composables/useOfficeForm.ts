import { computed, reactive, ref, shallowRef, useTemplateRef, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { consultorios, type OfficeResponse } from '@/services/consultorios'
import type { SpecialtyCatalogItem } from '@/services/catalogos'
import OfficeFormDialog from '@/components/configuracion/OfficeFormDialog.vue'
import type { OfficeForm } from '@/components/configuracion/officeForm'

export function useOfficeForm(
  especialidades: Ref<SpecialtyCatalogItem[]>,
  filtroEstablecimiento: Ref<number | null>,
  load: () => Promise<void>,
  onSaved?: (office: OfficeResponse, created: boolean) => Promise<void>,
) {
  const formRef = useTemplateRef<InstanceType<typeof OfficeFormDialog>>('formRef')
  const formVisible = ref(false)
  const saving = ref(false)
  const editingId = ref<number | null>(null)
  const initialArea = shallowRef<string | null>(null)
  const formError = ref<string | null>(null)
  const form = reactive<OfficeForm>({
    establecimiento_id: null,
    codigo: '',
    nombre: '',
    area_codigo: null,
  })
  const areaOptions = computed(() =>
    especialidades.value.filter(
      (item) => item.es_area || item.codigo === form.area_codigo || item.es_area === undefined,
    ),
  )
  const formTitle = computed(() =>
    editingId.value !== null ? 'Editar consultorio' : 'Nuevo consultorio',
  )

  function changeForm(changes: Partial<OfficeForm>): void {
    Object.assign(form, changes)
  }

  function showForm(): void {
    formError.value = null
    formRef.value?.clearValidate()
    formVisible.value = true
  }

  function openCreate(): void {
    editingId.value = null
    initialArea.value = null
    Object.assign(form, {
      establecimiento_id: filtroEstablecimiento.value,
      codigo: '',
      nombre: '',
      area_codigo: null,
    })
    showForm()
  }

  function openEdit(row: OfficeResponse): void {
    editingId.value = row.id
    initialArea.value = row.area_codigo || row.especialidad_codigo
    Object.assign(form, {
      establecimiento_id: row.establecimiento_id,
      codigo: row.codigo,
      nombre: row.nombre,
      area_codigo: initialArea.value,
    })
    showForm()
  }

  async function submitForm(): Promise<void> {
    if (saving.value) return
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return

    saving.value = true
    formError.value = null
    try {
      const identity = { codigo: form.codigo.trim(), nombre: form.nombre.trim() }
      let result: OfficeResponse
      const created = editingId.value === null
      if (editingId.value === null) {
        result = await consultorios.create({
          ...identity,
          establecimiento_id: form.establecimiento_id as number,
          area_codigo: form.area_codigo,
          consultorio_padre_id: null,
        })
        ElMessage.success('Consultorio creado.')
      } else {
        // Identity edits must not rewrite clinical configuration or legacy relationships.
        result = await consultorios.update(editingId.value, {
          ...identity,
          ...(form.area_codigo !== initialArea.value ? { area_codigo: form.area_codigo } : {}),
        })
        ElMessage.success('Consultorio actualizado.')
      }
      formVisible.value = false
      await load()
      await onSaved?.(result, created)
    } catch (error) {
      formError.value =
        error instanceof Error ? error.message : 'No se pudo guardar el consultorio.'
    } finally {
      saving.value = false
    }
  }

  return {
    formVisible,
    saving,
    editingId,
    formError,
    form,
    formTitle,
    areaOptions,
    changeForm,
    openCreate,
    openEdit,
    submitForm,
  }
}
