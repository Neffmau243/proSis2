import { computed, reactive, ref, shallowRef, type ComputedRef } from 'vue'
import { ElMessage } from 'element-plus'
import { catalogos, type ProfessionalCatalogItem, type CodeCatalogItem } from '@/services/catalogos'
import {
  consultorios,
  type OfficeAssignmentResponse,
  type OfficeResponse,
  type OfficeAssignmentCreatePayload,
} from '@/services/consultorios'

export function useOfficeAssignments(
  canManageStaffCatalogs: ComputedRef<boolean>,
  specialtyNames: ComputedRef<Record<string, string>>,
) {
  const professionalOptions = ref<ProfessionalCatalogItem[]>([])
  const professionalsLoading = shallowRef(false)
  const professionalSearchError = shallowRef<string | null>(null)
  const professionalDirectory = ref<Record<number, string>>({})
  const selectedService = shallowRef<CodeCatalogItem | null>(null)
  function profesionalNombre(id: number): string {
    return professionalDirectory.value[id] ?? `Profesional #${id}`
  }
  let professionalSearchRequest = 0
  async function searchProfesionales(query: string): Promise<void> {
    const request = ++professionalSearchRequest
    professionalsLoading.value = true
    professionalSearchError.value = null
    try {
      const page = await catalogos.profesionales(query || undefined, 25, 0)
      if (request !== professionalSearchRequest) return
      professionalOptions.value = page.items
      for (const item of page.items) {
        professionalDirectory.value[item.id] = item.nombre_completo
      }
    } catch (error) {
      if (request === professionalSearchRequest)
        professionalSearchError.value =
          error instanceof Error
            ? error.message
            : 'No se pudieron buscar profesionales. Intente escribir de nuevo.'
    } finally {
      if (request === professionalSearchRequest) professionalsLoading.value = false
    }
  }

  // --- Asignaciones de profesionales ---
  const today = new Date().toLocaleDateString('sv-SE')
  const assignmentsVisible = ref(false)
  const officeTarget = ref<OfficeResponse | null>(null)
  const assignments = ref<OfficeAssignmentResponse[]>([])
  const assignmentsLoading = ref(false)
  const assignmentsError = ref<string | null>(null)
  const assignFormVisible = ref(false)
  const savingAssignment = ref(false)
  const assignError = ref<string | null>(null)
  const assignmentSearch = ref('')
  const filteredAssignments = computed(() => {
    const query = assignmentSearch.value.trim().toLocaleLowerCase('es')
    return assignments.value.filter((item) =>
      profesionalNombre(item.profesional_id).toLocaleLowerCase('es').includes(query),
    )
  })

  const assignmentsTitle = computed(() =>
    officeTarget.value
      ? `Profesionales · ${officeTarget.value.nombre}${selectedService.value ? ` / ${selectedService.value.nombre}` : ''}`
      : 'Profesionales',
  )
  const assignmentRequirementName = computed(() => {
    const office = officeTarget.value
    const required = office?.especialidad_requerida_codigo ?? office?.especialidad_codigo
    return required && required !== office?.area_codigo
      ? specialtyNames.value[required] || required
      : ''
  })

  function openAssignments(row: OfficeResponse, service?: CodeCatalogItem): void {
    selectedService.value = service ?? null
    officeTarget.value = row
    assignmentsError.value = null
    assignmentSearch.value = ''
    assignFormVisible.value = false
    assignmentsVisible.value = true
    loadAssignments()
  }

  let assignmentsRequest = 0
  async function loadAssignments(): Promise<void> {
    const request = ++assignmentsRequest
    const office = officeTarget.value
    if (!office) return
    assignmentsLoading.value = true
    assignmentsError.value = null
    try {
      const items = await consultorios.listAssignments(office.id, {
        includeInherited: true,
        serviceCode: selectedService.value?.codigo,
      })
      if (request !== assignmentsRequest) return
      assignments.value = items
      for (const item of items) {
        if (item.profesional_nombre)
          professionalDirectory.value[item.profesional_id] = item.profesional_nombre
      }
      if (items.some((item) => !item.profesional_nombre)) await searchProfesionales('')
    } catch (error) {
      if (request !== assignmentsRequest) return
      assignmentsError.value =
        error instanceof Error ? error.message : 'No se pudieron cargar las asignaciones.'
    } finally {
      if (request === assignmentsRequest) assignmentsLoading.value = false
    }
  }

  function openAssignForm(): void {
    assignError.value = null
    professionalSearchError.value = null
    assignFormVisible.value = true
  }

  async function submitAssignment(payload: OfficeAssignmentCreatePayload): Promise<void> {
    if (!officeTarget.value || savingAssignment.value) return
    savingAssignment.value = true
    assignError.value = null
    try {
      await consultorios.assign(officeTarget.value.id, {
        ...payload,
        vincular_area: canManageStaffCatalogs.value,
      })
      ElMessage.success('Profesional asignado.')
      assignFormVisible.value = false
      await loadAssignments()
    } catch (error) {
      assignError.value =
        error instanceof Error ? error.message : 'No se pudo asignar el profesional.'
    } finally {
      savingAssignment.value = false
    }
  }

  const closeVisible = ref(false)
  const closeTarget = ref<OfficeAssignmentResponse | null>(null)
  const closeError = ref<string | null>(null)
  const savingClose = ref(false)
  const closeForm = reactive({ fecha_fin: '' })

  function openClose(row: OfficeAssignmentResponse): void {
    closeTarget.value = row
    closeForm.fecha_fin = ''
    closeError.value = null
    closeVisible.value = true
  }

  async function submitClose(): Promise<void> {
    const office = officeTarget.value
    const target = closeTarget.value
    if (!office || !target) return
    if (!closeForm.fecha_fin) {
      closeError.value = 'Indique la fecha de fin.'
      return
    }
    if (closeForm.fecha_fin < target.fecha_inicio) {
      closeError.value = 'La fecha de fin no puede ser anterior a la fecha de inicio.'
      return
    }

    savingClose.value = true
    closeError.value = null
    try {
      await consultorios.closeAssignment(
        target.consultorio_id,
        target.profesional_id,
        target.fecha_inicio,
        closeForm.fecha_fin,
      )
      ElMessage.success('Asignación cerrada.')
      closeVisible.value = false
      await loadAssignments()
    } catch (error) {
      closeError.value = error instanceof Error ? error.message : 'No se pudo cerrar la asignación.'
    } finally {
      savingClose.value = false
    }
  }

  return {
    professionalOptions,
    professionalsLoading,
    professionalSearchError,
    selectedService,
    profesionalNombre,
    searchProfesionales,
    today,
    assignmentsVisible,
    officeTarget,
    assignments,
    assignmentsLoading,
    assignmentsError,
    assignFormVisible,
    savingAssignment,
    assignError,
    assignmentSearch,
    filteredAssignments,
    assignmentsTitle,
    assignmentRequirementName,
    openAssignments,
    loadAssignments,
    openAssignForm,
    submitAssignment,
    closeVisible,
    closeTarget,
    closeError,
    savingClose,
    closeForm,
    openClose,
    submitClose,
  }
}
