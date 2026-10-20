<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import LaboratoryPatientPanel from './LaboratoryPatientPanel.vue'
import LaboratoryHistory from './LaboratoryHistory.vue'
import LaboratoryActions from './LaboratoryActions.vue'
import LaboratoryEncounterHeader from './LaboratoryEncounterHeader.vue'
import LaboratoryReferralContext from './LaboratoryReferralContext.vue'
import LaboratoryEncounterReview from './LaboratoryEncounterReview.vue'
import { useLaboratory } from '@/composables/useLaboratory'
import { useLaboratoryReview } from '@/composables/useLaboratoryReview'
import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import { useAuthStore } from '@/stores/auth'
import { printLaboratoryClinical } from '@/utils/laboratoryPrint'
import type { Patient } from '@/services/pacientes'
import type { Attention } from '@/services/atenciones'
import { officeLabel } from '@/utils/officeHierarchy'

const FuaPrintDialog = defineAsyncComponent(
  () => import('@/components/admission/FuaPrintDialog.vue'),
)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const selectedPatient = usePacienteSeleccionado()
const canRead = computed(() => auth.hasPermission('ATENCION_LEER'))
const {
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
  entries,
  total,
  page,
  historyLoading,
  historyError,
  dailyCount,
  countError,
  disabledReason,
  savedAttention,
  attentionCreated,
  fuaSnapshot,
  fuaDialog,
  initialize,
  searchPatients,
  selectPatient,
  patientSaved,
  changeDocumentType,
  refreshHistory,
  refreshCount,
  save,
  newAttention,
} = useLaboratory(
  () => auth.hasPermission('ATENCION_CREAR'),
  () => canRead.value,
)
const locked = computed(() => saving.value || attentionCreated.value)
const encounterLocked = computed(() => locked.value || patientBusy.value)
const officeOptions = computed(() => {
  const siteNames = new Map(establishments.value.map((item) => [item.id, item.nombre]))
  return offices.value.map((item) => {
    const siteName =
      siteNames.get(item.establecimiento_id) || `Establecimiento #${item.establecimiento_id}`
    return { id: item.id, label: `${officeLabel(item)} — ${siteName}`.toUpperCase() }
  })
})
function updatePatient(value: Patient): void {
  patientSaved(value)
  if (selectedPatient.seleccionado.value?.id === value.id) selectedPatient.seleccionar(value)
  selectedPatient.notificarCambio()
  ElMessage.success('Datos del paciente actualizados.')
}
const printing = shallowRef(false)
function canPrintSis(attention: Attention | null): boolean {
  return Boolean(attention?.fua_impresion?.sis_tipo && attention.fua_impresion.sis_numero)
}
const sisPrintReady = computed(() => canPrintSis(savedAttention.value))
const review = useLaboratoryReview({
  patientId: () => patient.value?.id ?? null,
  officeId: () => form.officeId,
  canRead: () => canRead.value,
})
const {
  opened: reviewOpened,
  attention: reviewedAttention,
  loading: reviewLoading,
  error: reviewError,
} = review
const reviewedSisReady = computed(() => canPrintSis(reviewedAttention.value))
const printAttention = shallowRef<Attention | null>(null)
const printSnapshot = computed(() => printAttention.value?.fua_impresion ?? null)
const additionalCopy = shallowRef(false)
const printError = shallowRef('')
async function submit(): Promise<void> {
  if (attentionCreated.value) {
    newAttention()
    return
  }
  if (await save()) ElMessage.success('Atención de laboratorio guardada.')
}
function openFua(additional = false, attention: Attention | null = savedAttention.value): void {
  if (!attention || !canPrintSis(attention)) return
  printAttention.value = attention
  additionalCopy.value = additional
  fuaDialog.value = true
}
async function printHci(attention: Attention | null = savedAttention.value): Promise<void> {
  if (!attention?.fua_impresion || printing.value) return
  printing.value = true
  printError.value = ''
  try {
    await printLaboratoryClinical(attention)
  } catch (cause) {
    printError.value = cause instanceof Error ? cause.message : 'No se pudo imprimir la HCI.'
  } finally {
    printing.value = false
  }
}
watch(
  [() => patient.value?.id, () => form.officeId],
  () => {
    printAttention.value = null
    fuaDialog.value = false
    printError.value = ''
  },
  { flush: 'sync' },
)
const initialPatientId = Number(route.query.paciente_id) || selectedPatient.seleccionado.value?.id
onMounted(() => void initialize(initialPatientId))
</script>

<template>
  <div class="laboratory-workspace" v-loading="loading">
    <el-alert v-if="catalogError" :title="catalogError" type="error" :closable="false">
      <el-button link type="primary" @click="initialize(initialPatientId)"
        >Reintentar carga</el-button
      >
    </el-alert>
    <el-alert
      v-if="error || printError"
      :title="error || printError"
      type="error"
      :closable="false"
    />
    <LaboratoryEncounterHeader v-model="form.date" :disabled="encounterLocked || loading" />
    <div class="lab-grid">
      <LaboratoryPatientPanel
        class="lab-grid__patient"
        :patient="patient"
        :options="patients"
        :document-type="documentType"
        :documents="documents"
        :sexes="sexes"
        :insurances="insurances"
        :establishments="establishments"
        :date="form.date"
        :loading="searching"
        :disabled="locked"
        :can-edit="auth.hasPermission('PACIENTE_EDITAR')"
        :error="searchError"
        :search-hint="searchHint"
        :reference="form.reference"
        :counter-reference="form.counterReference"
        @search="searchPatients"
        @select="selectPatient"
        @document-type-change="changeDocumentType"
        @saved="updatePatient"
        @dirty-change="patientDirty = $event"
        @busy-change="patientBusy = $event"
        @reference="form.reference = $event"
        @counter-reference="form.counterReference = $event"
      />
      <div class="lab-grid__content">
        <el-form
          :model="form"
          :disabled="encounterLocked"
          label-position="left"
          label-width="100px"
          @submit.prevent="submit"
        >
          <section class="lab-panel lab-office" aria-labelledby="lab-office-title">
            <LaboratoryReferralContext
              v-model:mode="form.mode"
              v-model:renipress="form.originRenipress"
              v-model:name="form.originName"
              v-model:sheet="form.reference"
              :disabled="encounterLocked"
            />
            <header class="lab-panel__header">
              <h2 id="lab-office-title" class="lab-panel__title">Consultorio</h2>
            </header>
            <div class="lab-panel__body">
              <el-form-item label="Consultorio:">
                <el-select
                  v-model="form.officeId"
                  filterable
                  aria-label="Consultorio de laboratorio"
                  placeholder="Seleccione"
                  :disabled="encounterLocked || loading"
                >
                  <el-option
                    v-for="item in officeOptions"
                    :key="item.id"
                    :value="item.id"
                    :label="item.label"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-if="services.length" label="Servicio / especialidad">
                <el-select
                  v-model="form.serviceCode"
                  :disabled="encounterLocked || !office"
                  aria-label="Servicio de laboratorio"
                >
                  <el-option
                    v-for="item in services"
                    :key="item.codigo"
                    :label="item.nombre"
                    :value="item.codigo"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="Profesional:">
                <el-select
                  v-model="form.professionalId"
                  filterable
                  :loading="professionalsLoading"
                  aria-label="Profesional responsable"
                  placeholder="Seleccione"
                  :disabled="encounterLocked || loading || professionalsLoading || !office"
                >
                  <el-option
                    v-for="item in professionals"
                    :key="item.id"
                    :value="item.id"
                    :label="item.nombre_completo.toUpperCase()"
                  />
                </el-select>
              </el-form-item>
              <p
                class="lab-count"
                role="status"
                :title="
                  shift
                    ? `${shift.name}: ${shift.start.slice(11, 16)}–${shift.end.slice(11, 16)}`
                    : 'La hora elegida está fuera de los turnos configurados'
                "
              >
                Atenciones realizadas por el profesional por turno
                <strong>{{ dailyCount ?? '—' }}</strong>
              </p>
              <p v-if="countError" class="lab-count-error" role="alert">
                {{ countError }} <el-button link @click="refreshCount">Reintentar conteo</el-button>
              </p>
              <el-alert
                v-if="!loading && !catalogError && !offices.length"
                title="No hay un consultorio de laboratorio activo."
                type="warning"
                :closable="false"
              />
              <details class="lab-observations">
                <summary>Observaciones</summary>
                <el-input
                  v-model="form.notes"
                  type="textarea"
                  :rows="2"
                  maxlength="2000"
                  aria-label="Observaciones"
                />
              </details>
            </div>
          </section>
        </el-form>
        <p v-if="attentionCreated" class="lab-saved" role="status">
          Atención #{{ savedAttention?.id }} guardada correctamente.
        </p>
        <LaboratoryActions
          :saving="saving || printing || patientBusy"
          :saved="attentionCreated"
          :disabled="Boolean(disabledReason)"
          :print-ready="sisPrintReady"
          :print-reason="
            !sisPrintReady && patient
              ? 'La impresión SIS corresponde a pacientes con seguro SIS y una atención guardada.'
              : ''
          "
          :hci-ready="Boolean(savedAttention && fuaSnapshot)"
          :reason="disabledReason"
          @save="submit"
          @print="openFua()"
          @additional="openFua(true)"
          @hci="printHci()"
          @exit="router.push({ name: 'inicio' })"
        />
        <LaboratoryHistory
          :entries="entries"
          :patient="patient"
          :loading="historyLoading"
          :error="historyError"
          :total="total"
          :page="page"
          :can-read="canRead"
          :has-office="Boolean(office)"
          @refresh="refreshHistory"
          @page="page = $event"
          @open="review.open"
        />
      </div>
    </div>
    <LaboratoryEncounterReview
      v-model="reviewOpened"
      :attention="reviewedAttention"
      :loading="reviewLoading"
      :error="reviewError"
      :printing="printing"
      :sis-ready="reviewedSisReady"
      @print="openFua(false, reviewedAttention)"
      @additional="openFua(true, reviewedAttention)"
      @hci="printHci(reviewedAttention)"
    />
    <FuaPrintDialog
      v-if="printSnapshot && fuaDialog"
      v-model="fuaDialog"
      :snapshot="printSnapshot"
      :additional-copy="additionalCopy"
      document-kind="REF.Lab"
    />
  </div>
</template>

<style scoped>
.laboratory-workspace {
  --admission-panel: #e8eff7;
  --admission-heading: #d4e1ef;
  --admission-border: #b9cbdf;
  --admission-ink: #304f6d;
  --el-component-size: 24px;
  --el-text-color-placeholder: #61758b;
  display: grid;
  gap: 8px;
  min-width: 0;
}
.lab-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.95fr) minmax(0, 2fr);
  align-items: stretch;
  gap: 8px;
  min-width: 0;
}
.lab-attention-mode {
  display: grid;
  gap: 2px;
  padding: 6px 6px 4px;
  color: var(--admission-ink);
  font-size: 12px;
  line-height: 1.4;
}
.lab-saved {
  margin: 0;
  text-align: right;
  font-size: 12px;
  color: var(--el-color-success-dark-2);
}
.lab-modes {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 10px;
}
.lab-modes :deep(.el-radio) {
  margin: 0;
  height: auto;
  min-height: var(--el-component-size);
  white-space: normal;
}
.lab-modes :deep(.el-radio__label) {
  font-size: 12px;
  line-height: 1.35;
  white-space: normal;
}
.lab-grid__content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  min-height: 0;
}
.laboratory-workspace :deep(.lab-panel) {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 1px solid var(--admission-border);
  border-radius: 4px;
  background: var(--admission-panel);
  overflow: hidden;
}
.laboratory-workspace :deep(.lab-panel__header) {
  padding: 4px 8px;
  border-bottom: 1px solid var(--admission-border);
  background: var(--admission-heading);
}
.laboratory-workspace :deep(.lab-panel__title) {
  margin: 0;
  color: var(--admission-ink);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
}
.laboratory-workspace :deep(.lab-panel__body) {
  padding: 6px 8px;
}
.laboratory-workspace :deep(.el-form-item) {
  margin: 0 0 4px;
  min-width: 0;
}
.laboratory-workspace :deep(.el-form-item__label) {
  height: auto;
  padding: 0 8px 0 0;
  line-height: 26px;
  font-size: 12px;
  color: var(--admission-ink);
}
.laboratory-workspace :deep(.el-select) {
  width: 100%;
}
.laboratory-workspace :deep(.el-select__wrapper),
.laboratory-workspace :deep(.el-input__wrapper) {
  min-height: var(--el-component-size);
  padding-block: 0;
}
.laboratory-workspace :deep(.el-input__inner),
.laboratory-workspace :deep(.el-select__selected-item) {
  font-size: 12px;
  height: var(--el-component-size);
  line-height: var(--el-component-size);
}
/* Los datos maestros son legibles aunque no se editen desde Laboratorio. */
.laboratory-workspace :deep(.lab-patient .el-select__wrapper.is-disabled),
.laboratory-workspace :deep(.lab-patient .el-input.is-disabled .el-input__wrapper) {
  background: var(--el-fill-color-blank);
}
.laboratory-workspace :deep(.lab-patient .el-select__wrapper.is-disabled .el-select__selected-item),
.laboratory-workspace :deep(.lab-patient .el-input.is-disabled .el-input__inner) {
  color: var(--el-text-color-regular);
  -webkit-text-fill-color: var(--el-text-color-regular);
}
.lab-count {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 6px 0;
  padding-block: 6px;
  border-top: 1px solid var(--admission-border);
  color: var(--admission-ink);
  font-size: 12px;
  line-height: 1.4;
}
.lab-count strong {
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}
.lab-count-error {
  margin: 4px 0;
  color: var(--el-color-danger);
  font-size: 12px;
}
.lab-observations {
  font-size: 12px;
  color: var(--admission-ink);
}
.lab-observations summary {
  cursor: pointer;
  padding-block: 3px;
}
.lab-observations :deep(.el-textarea__inner) {
  margin-top: 4px;
  font-size: 12px;
}
@media (max-width: 820px) {
  .lab-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .lab-grid__content :deep(.lab-history) {
    flex: 0 1 auto;
  }
}
@media (max-width: 560px), (pointer: coarse) {
  .laboratory-workspace {
    --el-component-size: 36px;
  }
  .laboratory-workspace :deep(.el-form-item__label) {
    line-height: 36px;
  }
  .laboratory-workspace :deep(.el-input__inner) {
    font-size: 16px;
  }
}
</style>
