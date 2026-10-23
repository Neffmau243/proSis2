import { computed, reactive, ref, shallowRef, watch } from 'vue'
import { atenciones, type Attention, type AttentionCreatePayload } from '@/services/atenciones'
import { pacientes, type Patient } from '@/services/pacientes'
import {
  catalogos,
  type CodeCatalogItem,
  type EstablishmentCatalogItem,
  type InsuranceCatalogItem,
  type OfficeCatalogItem,
  type ProfessionalCatalogItem,
} from '@/services/catalogos'
import { useSavedAdmission } from '@/composables/useSavedAdmission'
import type { PageResponse } from '@/types/api'
import { laboratoryShift } from '@/utils/laboratoryShift'
import { emptyFuaInput } from '@/utils/fuaPrint'

async function allPages<T>(fetchPage: (offset: number) => Promise<PageResponse<T>>): Promise<T[]> {
  const items: T[] = []
  let more = true
  while (more) {
    const result = await fetchPage(items.length)
    items.push(...result.items)
    more = result.has_more && result.items.length > 0
  }
  return items
}

function localDateTime(): string {
  const parts = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Lima',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).format(new Date())
  return parts.replace(' ', 'T')
}
function message(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'No se pudo completar la consulta. Intente nuevamente.'
}

/** Laboratorio registra atenciones en el mismo flujo clínico que admisión. */
export function useLaboratory(canCreate: () => boolean, canRead: () => boolean) {
  const patient = shallowRef<Patient | null>(null)
  const patientDirty = shallowRef(false)
  const patientBusy = shallowRef(false)
  const patients = ref<Patient[]>([])
  const documentType = shallowRef<string | null>('DNI')
  const searching = shallowRef(false)
  const searchError = shallowRef('')
  const searchHint = shallowRef('Escriba al menos 2 caracteres para buscar.')
  const loading = shallowRef(false)
  const catalogError = shallowRef('')
  const error = shallowRef('')
  const saving = shallowRef(false)
  const documents = ref<CodeCatalogItem[]>([])
  const sexes = ref<CodeCatalogItem[]>([])
  const insurances = ref<InsuranceCatalogItem[]>([])
  const establishments = ref<EstablishmentCatalogItem[]>([])
  const offices = ref<OfficeCatalogItem[]>([])
  const professionals = ref<ProfessionalCatalogItem[]>([])
  const form = reactive({
    officeId: null as number | null,
    professionalId: null as number | null,
    serviceCode: null as string | null,
    date: localDateTime(),
    mode: 'AMBULATORIA' as AttentionCreatePayload['modalidad_atencion_codigo'],
    originRenipress: '',
    originName: '',
    notes: '',
    reference: '',
    counterReference: '',
  })
  const office = computed(() => offices.value.find((item) => item.id === form.officeId))
  const services = computed(() => office.value?.servicios_habilitados ?? [])
  const professionalsLoading = shallowRef(false)
  let staffRequest = 0
  const shift = computed(() => laboratoryShift(form.date))
  const establishment = computed(() =>
    establishments.value.find((item) => item.id === office.value?.establecimiento_id),
  )
  const saved = useSavedAdmission(() => patient.value?.id ?? null)
  const entries = ref<Attention[]>([])
  const total = shallowRef(0)
  const page = shallowRef(1)
  const historyLoading = shallowRef(false)
  const historyError = shallowRef('')
  const dailyCount = shallowRef<number | null>(null)
  const countError = shallowRef('')
  let searchVersion = 0
  let historyVersion = 0
  let countVersion = 0

  async function initialize(initialPatientId?: number): Promise<void> {
    loading.value = true
    catalogError.value = ''
    try {
      const [types, sex, insurance, sites, rooms, staff] = await Promise.all([
        catalogos.tiposDocumento(),
        catalogos.sexos(),
        catalogos.seguros(),
        allPages((offset) => catalogos.establecimientos(undefined, 100, offset)),
        allPages((offset) => catalogos.consultorios(undefined, undefined, 100, offset)),
        Promise.resolve([] as ProfessionalCatalogItem[]),
      ])
      documents.value = types
      sexes.value = sex
      insurances.value = insurance
      establishments.value = sites
      offices.value = rooms.filter(
        (item) =>
          item.activo &&
          item.activo_efectivo !== false &&
          (item.area_codigo === 'ESPECIALIDADES:002' ||
            (!item.area_codigo && (item.codigo === 'LAB' || /laboratorio/i.test(item.nombre)))),
      )
      professionals.value = staff
      if (offices.value.length === 1) form.officeId = offices.value[0]!.id
      if (initialPatientId) selectPatient(await pacientes.get(initialPatientId))
    } catch (cause) {
      catalogError.value = message(cause)
    } finally {
      loading.value = false
    }
  }

  async function searchPatients(query: string): Promise<void> {
    const version = ++searchVersion
    searchError.value = ''
    patients.value = patient.value ? [patient.value] : []
    const term = query.trim()
    if (term.length < 2) {
      searching.value = false
      searchHint.value = 'Escriba al menos 2 caracteres para buscar.'
      return
    }
    searching.value = true
    try {
      const result = await pacientes.search({
        q: term,
        tipo_documento_codigo: documentType.value || undefined,
        limit: 25,
        offset: 0,
      })
      if (version !== searchVersion) return
      patients.value = result.items
      searchHint.value = result.has_more
        ? 'Hay más coincidencias. Precise el documento o los nombres.'
        : 'No se encontraron pacientes.'
    } catch (cause) {
      if (version === searchVersion) searchError.value = message(cause)
    } finally {
      if (version === searchVersion) searching.value = false
    }
  }

  function selectPatient(value: Patient | null): void {
    if (saving.value || patientBusy.value || patientDirty.value) return
    ++searchVersion
    searching.value = false
    searchError.value = ''
    error.value = ''
    if (patient.value?.id !== value?.id) {
      form.notes = ''
      form.reference = ''
      form.counterReference = ''
      form.originRenipress = ''
      form.originName = ''
      form.mode = 'AMBULATORIA'
    }
    patient.value = value
    patients.value = value ? [value] : []
    if (value) {
      documentType.value = value.tipo_documento_codigo
      const room = offices.value.find(
        (item) => item.establecimiento_id === value.establecimiento_registro_id,
      )
      if (room) form.officeId = room.id
    }
  }

  function changeDocumentType(value: string | null): void {
    if (saving.value || patientBusy.value || patientDirty.value) return
    selectPatient(null)
    documentType.value = value
  }

  function patientSaved(value: Patient): void {
    if (value.id !== patient.value?.id) return
    patient.value = value
    patients.value = [value, ...patients.value.filter((item) => item.id !== value.id)]
    documentType.value = value.tipo_documento_codigo
  }

  async function refreshHistory(): Promise<void> {
    const version = ++historyVersion
    entries.value = []
    total.value = 0
    historyError.value = ''
    if (!patient.value || !office.value || !canRead()) {
      historyLoading.value = false
      return
    }
    historyLoading.value = true
    try {
      const result = await atenciones.search({
        paciente_id: patient.value.id,
        consultorio_id: office.value.id,
        limit: 10,
        offset: (page.value - 1) * 10,
      })
      if (version !== historyVersion) return
      entries.value = result.items
      total.value = result.total
    } catch (cause) {
      if (version === historyVersion) historyError.value = message(cause)
    } finally {
      if (version === historyVersion) historyLoading.value = false
    }
  }

  async function refreshCount(): Promise<void> {
    const version = ++countVersion
    dailyCount.value = null
    countError.value = ''
    if (!office.value || !form.professionalId || !shift.value || !canRead()) return
    try {
      const result = await atenciones.search({
        consultorio_id: office.value.id,
        profesional_id: form.professionalId,
        fecha_hora_desde: shift.value.start,
        fecha_hora_hasta: shift.value.end,
        estado: 'ATENDIDO',
        limit: 1,
        offset: 0,
      })
      if (version === countVersion) dailyCount.value = result.total
    } catch (cause) {
      if (version === countVersion) countError.value = message(cause)
    }
  }

  const disabledReason = computed(() => {
    if (!canCreate()) return 'No tiene permiso para registrar atenciones.'
    if (catalogError.value || loading.value)
      return 'Complete la carga de los catálogos para continuar.'
    if (!patient.value) return 'Busque y seleccione un paciente para registrar su atención.'
    if (!patient.value.estado) return 'El paciente está dado de baja.'
    if (patientBusy.value) return 'Espere a que se guarden los datos del paciente.'
    if (patientDirty.value)
      return 'Guarde o descarte los cambios del paciente antes de registrar la atención.'
    if (!office.value) return 'Seleccione un consultorio de laboratorio.'
    if (!form.professionalId) return 'Seleccione al profesional responsable.'
    if (!form.date || Number.isNaN(new Date(form.date).getTime()))
      return 'Indique una fecha y hora válidas.'
    if (form.date.slice(0, 10) < patient.value.fecha_nacimiento)
      return 'La atención no puede ser anterior al nacimiento.'
    if (form.mode === 'REFERENCIA') {
      if (!/^[0-9]{8}$/.test(form.originRenipress.trim()))
        return 'Indique los 8 dígitos del RENIPRESS de la IPRESS de origen.'
      if (!form.originName.trim()) return 'Indique el nombre de la IPRESS de origen.'
      if (!form.reference.trim()) return 'Indique el N.º de referencia recibida.'
    }
    return ''
  })

  async function save(): Promise<boolean> {
    if (saving.value || saved.attentionCreated.value) return false
    error.value = disabledReason.value
    if (error.value || !patient.value || !office.value || !form.professionalId) return false
    saving.value = true
    try {
      const result = await atenciones.create({
        paciente_id: patient.value.id,
        establecimiento_id: office.value.establecimiento_id,
        consultorio_id: office.value.id,
        especialidad_codigo: form.serviceCode ?? office.value.especialidad_codigo,
        profesional_id: form.professionalId,
        modalidad_atencion_codigo: form.mode,
        fecha_atencion: form.date,
        observaciones: form.notes.trim() || null,
        numero_referencia_ingreso: form.reference.trim() || null,
        numero_contrarreferencia_ingreso: form.counterReference.trim() || null,
        fua_datos:
          form.mode === 'REFERENCIA'
            ? {
                ...emptyFuaInput(),
                tipo_atencion: 'REFERENCIA',
                referencia_renipress: form.originRenipress.trim(),
                referencia_nombre: form.originName.trim(),
                referencia_hoja: form.reference.trim(),
              }
            : null,
      })
      // Bloquear un segundo POST incluso si falla la actualización del historial.
      saved.remember(result)
      page.value = 1
      await Promise.all([refreshHistory(), refreshCount()])
      return true
    } catch (cause) {
      error.value = message(cause)
      return false
    } finally {
      saving.value = false
    }
  }

  function newAttention(): void {
    if (saving.value) return
    saved.savedAttention.value = null
    saved.fuaDialog.value = false
    form.date = localDateTime()
    form.notes = ''
    form.reference = ''
    form.counterReference = ''
    form.originRenipress = ''
    form.originName = ''
    form.mode = 'AMBULATORIA'
    error.value = ''
  }

  async function refreshProfessionals(): Promise<void> {
    const request = ++staffRequest
    if (!form.officeId) {
      professionals.value = []
      form.professionalId = null
      return
    }
    professionalsLoading.value = true
    try {
      const staff = await allPages((offset) =>
        catalogos.profesionales(
          undefined,
          100,
          offset,
          form.officeId!,
          form.date.slice(0, 10),
          form.serviceCode || undefined,
        ),
      )
      if (request === staffRequest) {
        professionals.value = staff
        if (!staff.some((item) => item.id === form.professionalId)) form.professionalId = null
      }
    } catch (cause) {
      if (request === staffRequest) {
        professionals.value = []
        catalogError.value = message(cause)
      }
    } finally {
      if (request === staffRequest) professionalsLoading.value = false
    }
  }
  watch(
    () => form.officeId,
    () => {
      form.serviceCode = services.value[0]?.codigo ?? office.value?.especialidad_codigo ?? null
    },
  )
  watch(
    [() => form.officeId, () => form.serviceCode, () => form.date.slice(0, 10)],
    () => void refreshProfessionals(),
  )

  watch([() => patient.value?.id, () => form.officeId], () => {
    page.value = 1
    void refreshHistory()
  })
  watch(page, () => void refreshHistory())
  watch(
    [() => form.officeId, () => form.professionalId, () => shift.value?.start],
    () => void refreshCount(),
  )

  return {
    patient,
    patientDirty,
    patientBusy,
    patients,
    documentType,
    searching,
    searchError,
    searchHint,
    loading,
    catalogError,
    error,
    saving,
    documents,
    sexes,
    insurances,
    establishments,
    offices,
    professionals,
    professionalsLoading,
    services,
    form,
    office,
    shift,
    establishment,
    entries,
    total,
    page,
    historyLoading,
    historyError,
    dailyCount,
    countError,
    disabledReason,
    ...saved,
    initialize,
    searchPatients,
    selectPatient,
    patientSaved,
    changeDocumentType,
    refreshHistory,
    refreshCount,
    save,
    newAttention,
  }
}
