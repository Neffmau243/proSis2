<script setup lang="ts">
import { computed, toRef, shallowRef, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import PatientSisCodeFields from '@/components/patients/PatientSisCodeFields.vue'
import PatientInsuranceBrand from '@/components/patients/PatientInsuranceBrand.vue'
import { useAdmissionPatientEditor } from '@/composables/useAdmissionPatientEditor'
import { clearSisAffiliation, isSisInsurance } from '@/utils/patientInsurance'
import { calculateCalendarAge } from '@/utils/calendarAge'
import { pacientes, type Patient } from '@/services/pacientes'
import type {
  CodeCatalogItem,
  EstablishmentCatalogItem,
  InsuranceCatalogItem,
} from '@/services/catalogos'

const props = defineProps<{
  patient: Patient | null
  options: Patient[]
  documentType: string | null
  documents: CodeCatalogItem[]
  sexes: CodeCatalogItem[]
  insurances: InsuranceCatalogItem[]
  establishments: EstablishmentCatalogItem[]
  date: string
  loading: boolean
  disabled: boolean
  canEdit?: boolean
  error: string
  searchHint: string
  reference?: string
  counterReference?: string
}>()
const emit = defineEmits<{
  search: [query: string]
  select: [patient: Patient | null]
  reference: [value: string]
  counterReference: [value: string]
  saved: [patient: Patient]
  dirtyChange: [dirty: boolean]
  busyChange: [busy: boolean]
}>()
const {
  draft,
  dirty,
  saving,
  error: editError,
  fieldErrors,
  save,
  reset,
} = useAdmissionPatientEditor({
  patient: toRef(props, 'patient'),
  canEdit: () => Boolean(props.canEdit && props.patient?.estado),
  blocked: () => props.disabled,
  update: pacientes.update,
  onSaved: (patient) => emit('saved', patient),
})
const readonly = computed(
  () => !props.canEdit || !props.patient?.estado || props.disabled || saving.value,
)
const selectionLocked = computed(() => props.disabled || saving.value || dirty.value)
watch(dirty, (value) => emit('dirtyChange', value), { immediate: true, flush: 'sync' })
watch(saving, (value) => emit('busyChange', value), { flush: 'sync' })
const query = shallowRef('')
const selectedInsurance = computed(() =>
  props.insurances.find((item) => item.id === draft.seguro_id),
)
const hasSisInsurance = computed(() => isSisInsurance(selectedInsurance.value))
const insuranceHint = computed(() => {
  if (draft.seguro_id == null) return 'Seguro sin registrar. No corresponde afiliación SIS.'
  if (
    selectedInsurance.value?.regimen === 'NINGUNO' ||
    selectedInsurance.value?.codigo === 'SIN_SEGURO'
  )
    return 'Sin seguro. No corresponde afiliación SIS.'
  return 'No corresponde afiliación SIS para este seguro.'
})
const establishmentName = computed(
  () => props.establishments.find((item) => item.id === draft.establecimiento_registro_id)?.nombre,
)
const fields = [
  { key: 'apellido_paterno', label: 'Apellido paterno', max: 100 },
  { key: 'apellido_materno', label: 'Apellido materno', max: 100 },
  { key: 'primer_nombre', label: 'Primer nombre', max: 100 },
  { key: 'otros_nombres', label: 'Otros nombres', max: 150 },
] as const
const age = computed(() =>
  props.patient ? calculateCalendarAge(draft.fecha_nacimiento || '', props.date) : null,
)
function changeInsurance(value: number | undefined): void {
  draft.seguro_id = value ?? null
  if (!isSisInsurance(props.insurances.find((item) => item.id === draft.seguro_id)))
    clearSisAffiliation(draft)
}
function name(patient: Patient): string {
  return [
    patient.apellido_paterno,
    patient.apellido_materno,
    patient.primer_nombre,
    patient.otros_nombres,
  ]
    .filter(Boolean)
    .join(' ')
}
function search(value: string): void {
  query.value = value
  emit('search', value)
}
</script>

<template>
  <section class="lab-panel lab-patient" aria-labelledby="lab-patient-title">
    <header class="lab-panel__header">
      <h2 id="lab-patient-title" class="lab-panel__title">Base de datos</h2>
    </header>
    <div class="lab-panel__body">
      <div class="lab-patient__field lab-patient__document">
        <label for="lab-patient-search">Buscar paciente</label>
        <el-select
          id="lab-patient-search"
          :model-value="patient?.id"
          filterable
          remote
          clearable
          :remote-method="search"
          :loading="loading"
          :disabled="selectionLocked"
          :no-data-text="searchHint"
          placeholder="Buscar documento"
          aria-label="Buscar paciente"
          @update:model-value="emit('select', options.find((item) => item.id === $event) ?? null)"
        >
          <el-option
            v-for="item in options"
            :key="item.id"
            :value="item.id"
            :label="item.numero_documento"
          >
            {{ item.numero_documento }} · {{ name(item) }}
          </el-option>
        </el-select>
        <el-button
          :icon="Search"
          :disabled="selectionLocked"
          aria-label="Buscar por documento"
          @click="search(query || patient?.numero_documento || '')"
        />
      </div>
      <p v-if="error" class="lab-patient__error" role="alert">{{ error }}</p>
      <el-form :model="draft" class="lab-patient__form" @submit.prevent="save">
        <div class="lab-patient__field">
          <span>Tipo documento</span>
          <el-select
            v-model="draft.tipo_documento_codigo"
            :disabled="readonly"
            aria-label="Tipo de documento del paciente"
          >
            <el-option
              v-for="item in documents"
              :key="item.codigo"
              :value="item.codigo"
              :label="item.nombre"
            />
          </el-select>
          <p v-if="fieldErrors.tipo_documento_codigo" class="lab-patient__error" role="alert">
            {{ fieldErrors.tipo_documento_codigo }}
          </p>
        </div>
        <div class="lab-patient__field">
          <label for="lab-document-number">N.° documento</label>
          <el-input
            id="lab-document-number"
            v-model="draft.numero_documento"
            :readonly="readonly"
            maxlength="30"
            aria-label="N.° documento del paciente"
            :aria-invalid="Boolean(fieldErrors.numero_documento)"
          />
          <p v-if="fieldErrors.numero_documento" class="lab-patient__error" role="alert">
            {{ fieldErrors.numero_documento }}
          </p>
        </div>
        <div class="lab-patient__field">
          <label for="lab-history-number">N.° H. clínica</label>
          <el-input
            id="lab-history-number"
            v-model="draft.historia_clinica"
            :readonly="readonly"
            maxlength="255"
            aria-label="N.° historia clínica"
          />
          <p v-if="fieldErrors.historia_clinica" class="lab-patient__error" role="alert">
            {{ fieldErrors.historia_clinica }}
          </p>
        </div>
        <div class="lab-patient__field">
          <label for="lab-reference-number">N.° referencia</label>
          <el-input
            id="lab-reference-number"
            :model-value="reference"
            :readonly="disabled || saving || !patient"
            maxlength="50"
            aria-label="N.° de referencia"
            @update:model-value="emit('reference', $event)"
          />
        </div>
        <div class="lab-patient__field">
          <label for="lab-counter-reference">N.° contrarreferencia</label>
          <el-input
            id="lab-counter-reference"
            :model-value="counterReference"
            :readonly="disabled || saving || !patient"
            maxlength="50"
            aria-label="N.° de contrarreferencia"
            @update:model-value="emit('counterReference', $event)"
          />
        </div>
        <div class="lab-patient__field">
          <span>Fecha nacimiento</span>
          <el-date-picker
            v-model="draft.fecha_nacimiento"
            type="date"
            format="DD/MM/YYYY"
            value-format="YYYY-MM-DD"
            :disabled="readonly"
            :clearable="false"
            aria-label="Fecha nacimiento"
            :aria-invalid="Boolean(fieldErrors.fecha_nacimiento)"
          />
          <p v-if="fieldErrors.fecha_nacimiento" class="lab-patient__error" role="alert">
            {{ fieldErrors.fecha_nacimiento }}
          </p>
        </div>
        <div v-for="field in fields" :key="field.key" class="lab-patient__field">
          <label :for="`lab-field-${field.key}`">{{ field.label }}</label>
          <el-input
            :id="`lab-field-${field.key}`"
            v-model="draft[field.key]"
            :readonly="readonly"
            :maxlength="field.max"
            :aria-label="field.label"
            :aria-invalid="Boolean(fieldErrors[field.key])"
          />
          <p v-if="fieldErrors[field.key]" class="lab-patient__error" role="alert">
            {{ fieldErrors[field.key] }}
          </p>
        </div>
        <div class="lab-patient__field">
          <span>Sexo</span>
          <el-select v-model="draft.sexo_codigo" :disabled="readonly" clearable aria-label="Sexo">
            <el-option
              v-for="item in sexes"
              :key="item.codigo"
              :value="item.codigo"
              :label="item.nombre"
            />
          </el-select>
        </div>
        <div class="lab-patient__field">
          <span>Establecimiento</span>
          <el-select
            v-model="draft.establecimiento_registro_id"
            :disabled="readonly"
            filterable
            clearable
            aria-label="Establecimiento de registro"
          >
            <el-option
              v-for="site in establishments"
              :key="site.id"
              :value="site.id"
              :label="site.nombre"
            />
            <el-option
              v-if="draft.establecimiento_registro_id && !establishmentName"
              :value="draft.establecimiento_registro_id"
              :label="`Establecimiento #${draft.establecimiento_registro_id}`"
            />
          </el-select>
        </div>
        <div class="lab-patient__field">
          <span>Seguro de salud</span>
          <el-select
            :model-value="draft.seguro_id"
            :disabled="readonly"
            clearable
            placeholder="Sin seguro registrado"
            aria-label="Seguro registrado"
            @update:model-value="changeInsurance"
          >
            <el-option
              v-for="insurance in insurances"
              :key="insurance.id"
              :value="insurance.id"
              :label="insurance.nombre"
            />
            <el-option
              v-if="draft.seguro_id && !selectedInsurance"
              :value="draft.seguro_id"
              :label="`Seguro #${draft.seguro_id}`"
            />
          </el-select>
        </div>
        <div class="lab-patient__sis" :class="{ 'lab-patient__sis--other': !hasSisInsurance }">
          <PatientInsuranceBrand
            class="lab-patient__sis-brand"
            :insurance="selectedInsurance"
            :insurance-id="draft.seguro_id"
          />
          <div v-if="hasSisInsurance" class="lab-patient__sis-code">
            <span>Código de N.° SIS</span>
            <PatientSisCodeFields
              :value="draft"
              compact
              :disabled="readonly"
              :errors="fieldErrors"
              @update="Object.assign(draft, $event)"
            />
          </div>
          <div v-if="hasSisInsurance" class="lab-patient__sequence">
            <label for="lab-sis-sequence">N.° hijo</label>
            <el-input
              id="lab-sis-sequence"
              v-model="draft.sis_secuencia"
              :readonly="readonly"
              maxlength="2"
              inputmode="numeric"
              aria-label="Secuencia SIS / N.º de hijo"
              :aria-invalid="Boolean(fieldErrors.sis_secuencia)"
            />
          </div>
          <p v-else class="lab-patient__insurance-hint">{{ insuranceHint }}</p>
        </div>
        <p v-if="fieldErrors.sis_secuencia" class="lab-patient__error" role="alert">
          {{ fieldErrors.sis_secuencia }}
        </p>
        <div class="lab-patient__age">
          <span>Edad</span
          ><strong>{{
            age ? `${age.years} años, ${age.months} meses, ${age.days} días` : '—'
          }}</strong>
        </div>
        <p v-if="editError" class="lab-patient__error" role="alert">{{ editError }}</p>
        <p class="lab-patient__hint" role="status">
          {{
            !patient
              ? 'Seleccione un paciente para cargar sus datos.'
              : dirty
                ? 'Tiene cambios del paciente sin guardar.'
                : !canEdit
                  ? 'No tiene permiso para editar los datos del paciente.'
                  : disabled
                    ? 'Atención guardada · datos del paciente confirmados.'
                    : 'Datos del paciente guardados.'
          }}
        </p>
        <div v-if="dirty" class="lab-patient__actions">
          <el-button type="primary" native-type="submit" :disabled="readonly" :loading="saving"
            >Guardar cambios</el-button
          >
          <el-button :disabled="saving || disabled" @click="reset">Descartar</el-button>
        </div>
      </el-form>
    </div>
  </section>
</template>

<style scoped>
.lab-patient__field {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}
.lab-patient__field > label,
.lab-patient__field > span {
  color: var(--admission-ink);
  font-size: 12px;
  line-height: 1.3;
  text-align: right;
}
.lab-patient__document {
  grid-template-columns: 148px minmax(0, 1fr) 28px;
}
.lab-patient__document :deep(.el-button) {
  width: 28px;
  height: var(--el-component-size);
  padding: 0;
  margin: 0;
}
.lab-patient__sis {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr) 48px;
  align-items: center;
  gap: 6px;
  margin: 8px 0 4px;
  min-height: 52px;
}
.lab-patient__sis--other {
  grid-template-columns: 90px minmax(0, 1fr);
}
.lab-patient__sis-code > span,
.lab-patient__sequence > span {
  display: block;
  text-align: center;
  color: var(--admission-ink);
  font-size: 12px;
  margin-bottom: 3px;
}
.lab-patient__sequence > label {
  display: block;
  text-align: center;
  color: var(--admission-ink);
  font-size: 12px;
  margin-bottom: 3px;
}
.lab-patient__field :deep(.el-date-editor) {
  width: 100%;
}
.lab-patient__field > .lab-patient__error {
  grid-column: 2;
}
.lab-patient__insurance-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--admission-ink);
}
.lab-patient__actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.lab-patient__actions :deep(.el-button) {
  margin: 0;
  font-size: 12px;
}
.lab-patient__sequence :deep(.el-select__wrapper) {
  padding-inline: 4px;
  gap: 4px;
}
.lab-patient__age {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 5px;
  border-top: 1px solid var(--admission-border);
  color: var(--admission-ink);
  font-size: 12px;
}
.lab-patient__hint {
  margin: 4px 0 0;
  color: var(--admission-ink);
  font-size: 12px;
  line-height: 1.4;
}
.lab-patient__error {
  color: var(--el-color-danger);
  font-size: 12px;
  margin: 4px 0;
}
@media (max-width: 560px) {
  .lab-patient__field {
    grid-template-columns: 122px minmax(0, 1fr);
  }
  .lab-patient__document {
    grid-template-columns: 122px minmax(0, 1fr) 36px;
  }
  .lab-patient__document :deep(.el-button) {
    width: 36px;
  }
  .lab-patient__sis {
    grid-template-columns: 90px minmax(0, 1fr);
    min-height: 102px;
  }
  .lab-patient__sequence {
    grid-column: 2;
  }
}
</style>
