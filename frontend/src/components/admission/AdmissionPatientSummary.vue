<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import PatientSisCodeFields from '@/components/patients/PatientSisCodeFields.vue'
import PatientInsuranceBrand from '@/components/patients/PatientInsuranceBrand.vue'
import PatientConditionSelect from '@/components/patients/PatientConditionSelect.vue'
import FamilyHistorySelector from '@/components/patients/FamilyHistorySelector.vue'
import AdmissionDocumentTypes from '@/components/admission/AdmissionDocumentTypes.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAdmissionPatientDetails } from '@/composables/useAdmissionPatientDetails'
import { useAdmissionPatientEditor } from '@/composables/useAdmissionPatientEditor'
import AdmissionPatientRelations from '@/components/admission/AdmissionPatientRelations.vue'
import { patientFields, type PatientFieldKey } from '@/utils/patientDraft'
import { localityOptions, localitySelection } from '@/utils/localitySelection'
import { clearSisAffiliation, isSisInsurance } from '@/utils/patientInsurance'
import type { PatientSisContractKey, PatientSisData } from '@/utils/patientSis'
import { pacientes, type Patient } from '@/services/pacientes'
import type { CodeCatalogItem, RiskGroupCatalogItem } from '@/services/catalogos'

const props = defineProps<{
  patient: Patient
  canEdit: boolean
  /** El permiso de baja vive fuera del editor: la admisión solo lo refleja. */
  canDelete?: boolean
  blocked?: boolean
  /** Catálogo cargado por la vista, que también lo usa para el diálogo de responsables. */
  tiposDocumento: CodeCatalogItem[]
  /** Catálogos que alimentan el diálogo de riesgo dentro del panel. */
  gruposRiesgo?: RiskGroupCatalogItem[]
}>()
const emit = defineEmits<{
  saved: [patient: Patient]
  dirtyChange: [dirty: boolean]
  busyChange: [busy: boolean]
  removed: [patient: Patient]
}>()
const { draft, saving, dirty, error, fieldErrors, save, reset } = useAdmissionPatientEditor({
  patient: toRef(props, 'patient'),
  canEdit: () => props.canEdit && props.patient.estado,
  blocked: () => Boolean(props.blocked),
  update: pacientes.update,
  onSaved: (patient) => {
    emit('saved', patient)
    ElMessage.success('Datos del paciente actualizados.')
  },
})
const {
  sexos,
  seguros,
  catalogError,
  loadCatalogs,
  establishments,
  districts,
  familyHistories,
  localities,
  localitiesLoading,
  localitiesError,
  loadLocalities,
} = useAdmissionPatientDetails(toRef(props, 'patient'))
const removing = ref(false)
const selectedInsurance = computed(() => seguros.value.find((item) => item.id === draft.seguro_id))
const hasSisInsurance = computed(() => isSisInsurance(selectedInsurance.value))
function changeInsurance(): void {
  if (!hasSisInsurance.value) {
    const hadAffiliation = Boolean(
      draft.sis_diresa || draft.sis_tipo || draft.sis_numero || draft.sis_secuencia,
    )
    clearSisAffiliation(draft)
    if (hadAffiliation)
      ElMessage.info('Se retiró la afiliación SIS del borrador. Guarde los cambios para confirmar.')
    return
  }
}
function updateSisAffiliation(changes: Partial<Pick<PatientSisData, PatientSisContractKey>>): void {
  Object.assign(draft, changes)
}
const fullName = computed(
  () =>
    [props.patient.apellido_paterno, props.patient.apellido_materno, props.patient.primer_nombre]
      .filter(Boolean)
      .join(' ') || `Paciente #${props.patient.id}`,
)
const disabled = computed(
  () => !props.canEdit || !props.patient.estado || saving.value || props.blocked,
)
const canRemove = computed(
  () => Boolean(props.canDelete) && props.patient.estado && !props.blocked && !saving.value,
)
// La condición se muestra al final, en la fila «Grupo etáreo».
const admissionFields = patientFields.filter(
  (field) => !['fecha_inscripcion', 'condicion', 'sufijo_documento'].includes(field.key),
)
const options = computed<
  Partial<Record<PatientFieldKey, { label: string; value: string | number }[]>>
>(() => ({
  tipo_documento_codigo: props.tiposDocumento.map((item) => ({
    label: item.nombre,
    value: item.codigo,
  })),
  sexo_codigo: sexos.value.map((item) => ({ label: item.nombre, value: item.codigo })),
  seguro_id: seguros.value.map((item) => ({ label: item.nombre, value: item.id })),
  establecimiento_registro_id: establishments.items.value.map((item) => ({
    label: item.nombre,
    value: item.id,
  })),
  ubigeo_residencia_codigo: districts.items.value.map((item) => ({
    label: `${item.distrito} · ${item.provincia} · ${item.departamento}`,
    value: item.codigo,
  })),
  localidad_id: localityOptions(
    localities.value,
    districts.items.value.find((item) => item.codigo === draft.ubigeo_residencia_codigo)
      ?.distrito ??
      (draft.ubigeo_residencia_codigo === props.patient.ubigeo_residencia_codigo
        ? props.patient.distrito_residencia
        : null),
  ),
}))
function fieldOptions(key: PatientFieldKey) {
  const list = options.value[key] ?? []
  const value = draft[key]
  if (
    key === 'localidad_id' &&
    value == null &&
    draft.localidad &&
    !list.some((item) => item.value === draft.localidad)
  ) {
    return [{ value: draft.localidad, label: draft.localidad }, ...list]
  }
  if (value && !list.some((item) => item.value === value)) {
    let label = String(value)
    if (key === 'ubigeo_residencia_codigo' && value === props.patient.ubigeo_residencia_codigo) {
      label = props.patient.distrito_residencia || label
    } else if (key === 'localidad_id' && typeof draft.localidad === 'string') {
      label = draft.localidad
    }
    return [{ value, label }, ...list]
  }
  return list
}

// La localidad pertenece a un distrito: al cambiarlo se limpia la selección y
// se recarga el catálogo SIS de ese distrito.
let currentDistrict: string | null = props.patient.ubigeo_residencia_codigo
watch(
  () => draft.ubigeo_residencia_codigo,
  (code) => {
    if (code !== currentDistrict) {
      // Resetting or switching the patient restores its saved locality together
      // with the district. Only a new district selection invalidates that pair.
      const restored =
        code === props.patient.ubigeo_residencia_codigo &&
        draft.localidad_id === props.patient.localidad_id
      if (!restored) {
        draft.localidad_id = null
        draft.localidad = null
      }
      currentDistrict = code
    }
    void loadLocalities(code || null)
  },
  { immediate: true },
)

function onLocalityChange(value: number | string | null): void {
  if (
    typeof value === 'number' &&
    value === draft.localidad_id &&
    !localities.value.some((item) => item.id === value)
  )
    return
  Object.assign(draft, localitySelection(value, localities.value))
}
function searchDistricts(query: string) {
  districts.search(
    query,
    districts.items.value.filter((item) => item.codigo === draft.ubigeo_residencia_codigo),
  )
}
function searchEstablishments(query: string) {
  establishments.search(
    query,
    establishments.items.value.filter((item) => item.id === draft.establecimiento_registro_id),
  )
}
function onRelationsSaved(updated: Patient): void {
  emit('saved', updated)
}

function onRelationsBusy(busy: boolean): void {
  emit('busyChange', busy)
}

async function removePatient(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `¿Dar de baja a ${fullName.value}? La baja es lógica: el historial se conserva.`,
      'Eliminar paciente',
      { type: 'warning', confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar' },
    )
  } catch {
    return
  }
  removing.value = true
  try {
    const result = await pacientes.deactivate(props.patient.id)
    ElMessage.success(result.mensaje)
    emit('removed', props.patient)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'No se pudo eliminar el paciente.')
  } finally {
    removing.value = false
  }
}

watch(dirty, (value) => emit('dirtyChange', value), { immediate: true, flush: 'sync' })
watch(saving, (value) => emit('busyChange', value), { flush: 'sync' })
</script>

<template>
  <section class="patient-context" aria-labelledby="patient-context-title">
    <header class="patient-context__header">
      <h3 id="patient-context-title" class="patient-context__title">Base de datos</h3>
    </header>
    <div class="patient-context__body">
      <el-alert v-if="catalogError" :title="catalogError" type="warning" :closable="false">
        <el-button link type="primary" @click="loadCatalogs">Reintentar catálogos</el-button>
      </el-alert>
      <p v-if="!canEdit" class="patient-context__hint">No tiene permiso para editar estos datos.</p>
      <el-form
        class="patient-context__form"
        :model="draft"
        label-position="left"
        label-width="110px"
        @submit.prevent="save"
      >
        <template v-for="field in admissionFields" :key="field.key">
          <AdmissionDocumentTypes
            v-if="field.key === 'tipo_documento_codigo'"
            v-model="draft.tipo_documento_codigo"
            :options="tiposDocumento"
            :disabled="disabled"
            :error="fieldErrors.tipo_documento_codigo"
          />
          <div v-else-if="field.key === 'seguro_id'" class="patient-context__sis">
            <PatientInsuranceBrand
              class="patient-context__sis-brand"
              :insurance="selectedInsurance"
              :insurance-id="draft.seguro_id"
            />
            <div class="patient-context__sis-fields">
              <el-form-item
                class="patient-context__insurance-selector"
                label-width="0"
                :error="fieldErrors.seguro_id"
              >
                <el-select
                  v-model="draft.seguro_id"
                  @change="changeInsurance"
                  filterable
                  clearable
                  :value-on-clear="null"
                  :disabled="disabled"
                  aria-label="Seguro de salud"
                  placeholder="Sin seguro registrado"
                >
                  <el-option
                    v-for="option in fieldOptions('seguro_id')"
                    :key="`${option.value}:${option.label}`"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <PatientSisCodeFields
                v-if="hasSisInsurance"
                compact
                :value="draft"
                :disabled="disabled"
                :errors="fieldErrors"
                @update="updateSisAffiliation"
              />
            </div>
          </div>
          <el-form-item
            v-else
            :class="{ 'patient-context__contact': field.key === 'telefono_principal' }"
            :label="field.label"
            :error="fieldErrors[field.key]"
            :required="'required' in field && field.required"
          >
            <el-input
              v-if="field.kind === 'text' && field.key !== 'historia_familiar'"
              v-model="draft[field.key]"
              :maxlength="'max' in field ? field.max : undefined"
              :disabled="disabled"
              :aria-label="field.label"
              :inputmode="field.key === 'telefono_principal' ? 'tel' : 'text'"
            />
            <FamilyHistorySelector
              v-else-if="field.key === 'historia_familiar'"
              v-model="draft.historia_familiar"
              :disabled="disabled"
              :options="familyHistories.items.value"
              :loading="familyHistories.loading.value"
            />
            <el-input
              v-else-if="field.kind === 'date'"
              v-model="draft[field.key]"
              type="date"
              :disabled="disabled"
              :aria-label="field.label"
            />
            <el-select
              v-else-if="field.key === 'localidad_id'"
              :model-value="draft.localidad_id ?? draft.localidad"
              filterable
              clearable
              allow-create
              default-first-option
              :disabled="disabled || !draft.ubigeo_residencia_codigo"
              :loading="localitiesLoading"
              :aria-label="field.label"
              :placeholder="
                draft.ubigeo_residencia_codigo
                  ? 'Seleccione o escriba la localidad'
                  : 'Elija el distrito primero'
              "
              @update:model-value="onLocalityChange"
            >
              <el-option
                v-for="option in fieldOptions('localidad_id')"
                :key="`${option.value}:${option.label}`"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-select
              v-else
              v-model="draft[field.key]"
              filterable
              :clearable="!('required' in field && field.required)"
              :disabled="disabled"
              :aria-label="field.label"
              placeholder="Seleccione"
              :remote="
                field.key === 'ubigeo_residencia_codigo' ||
                field.key === 'establecimiento_registro_id'
              "
              :remote-method="
                field.key === 'ubigeo_residencia_codigo' ? searchDistricts : searchEstablishments
              "
              :loading="
                field.key === 'ubigeo_residencia_codigo'
                  ? districts.loading.value
                  : field.key === 'establecimiento_registro_id' && establishments.loading.value
              "
            >
              <el-option
                v-for="option in fieldOptions(field.key)"
                :key="`${option.value}:${option.label}`"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <p
              v-if="field.key === 'ubigeo_residencia_codigo' && districts.error.value"
              class="patient-context__field-error"
              role="alert"
            >
              {{ districts.error.value }}
              <el-button
                link
                type="primary"
                @click="districts.load(draft.ubigeo_residencia_codigo || undefined)"
                >Reintentar</el-button
              >
            </p>
            <p
              v-if="field.key === 'establecimiento_registro_id' && establishments.error.value"
              class="patient-context__field-error"
              role="alert"
            >
              {{ establishments.error.value }}
              <el-button link type="primary" @click="establishments.load()">Reintentar</el-button>
            </p>
            <p
              v-if="field.key === 'localidad_id' && localitiesError"
              class="patient-context__field-error"
              role="alert"
            >
              {{ localitiesError }}
              <el-button
                link
                type="primary"
                @click="loadLocalities(draft.ubigeo_residencia_codigo || null)"
                >Reintentar</el-button
              >
            </p>
          </el-form-item>
        </template>
        <div class="patient-context__relations">
          <AdmissionPatientRelations
            :patient="patient"
            :disabled="disabled"
            :can-edit="canEdit"
            :tipos-documento="tiposDocumento"
            :grupos-riesgo="gruposRiesgo ?? []"
            @saved="onRelationsSaved"
            @busy-change="onRelationsBusy"
          >
            <template #condition>
              <el-form-item label="Grupo etáreo" :error="fieldErrors.condicion">
                <PatientConditionSelect
                  v-model="draft.condicion"
                  :disabled="disabled"
                  aria-label="Grupo etáreo"
                  title="Condición registrada del paciente; independiente de la edad calculada en la atención"
                />
              </el-form-item>
            </template>
          </AdmissionPatientRelations>
        </div>
        <div v-if="canEdit" class="patient-context__actions">
          <el-alert v-if="error" :title="error" type="error" :closable="false" />
          <p class="patient-context__hint" role="status">
            {{ dirty ? 'Tiene cambios sin guardar.' : 'Datos del paciente guardados.' }}
          </p>
          <el-button
            v-if="dirty"
            type="primary"
            native-type="submit"
            :loading="saving"
            :disabled="!dirty || disabled"
            >Guardar cambios</el-button
          >
          <el-button v-if="dirty" :disabled="disabled" @click="reset">Descartar cambios</el-button>
          <details v-if="canRemove" class="patient-context__more-actions">
            <summary>Más acciones del paciente</summary>
            <el-button
              class="patient-context__remove"
              type="danger"
              :loading="removing"
              @click="removePatient"
              >Eliminar paciente</el-button
            >
          </details>
        </div>
      </el-form>
    </div>
  </section>
</template>

<style scoped>
.patient-context {
  min-width: 0;
  border: 1px solid var(--admission-border, #b9cbdf);
  border-radius: 4px;
  background: var(--admission-panel, #e8eff7);
  --el-component-size: var(--admission-control-size, 26px);
}
.patient-context__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--admission-border, #b9cbdf);
  background: var(--admission-heading, #d4e1ef);
}
.patient-context__title {
  margin: 0;
  font-size: 13px;
  color: var(--admission-ink, #304f6d);
}
.patient-context__body {
  padding: 6px 8px;
}
.patient-context__form {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 2px;
}
.patient-context__form :deep(.el-form-item) {
  margin-bottom: 0;
  min-width: 0;
}
.patient-context__form :deep(.el-form-item__label) {
  height: auto;
  line-height: 1.4;
  padding: 2px 8px 0 0;
  margin-bottom: 0;
  font-size: 12px;
  color: var(--admission-ink, #304f6d);
  justify-content: flex-end;
  text-align: right;
}
.patient-context__form :deep(.el-form-item__error) {
  position: static;
  flex-basis: 100%;
  line-height: 1.4;
}
.patient-context__form :deep(.el-form-item__content) {
  display: flex;
  flex-wrap: wrap;
  min-width: 0;
  line-height: var(--el-component-size);
}
.patient-context__form :deep(.el-input),
.patient-context__form :deep(.el-select) {
  width: 100%;
}
.patient-context__form :deep(.el-select__wrapper) {
  min-height: var(--el-component-size);
  padding-block: 0;
}
.patient-context__form :deep(.el-input__inner),
.patient-context__form :deep(.el-select__selected-item) {
  font-size: 12px;
}
.patient-context__more-actions summary {
  cursor: pointer;
  font-size: 12px;
  padding-block: 4px;
}
.patient-context__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-top: 4px;
  grid-column: 1 / -1;
}
.patient-context__actions > .patient-context__hint,
.patient-context__actions > .patient-context__more-actions,
.patient-context__actions > .el-alert {
  flex-basis: 100%;
}
.patient-context__actions > .el-button {
  flex: 1 1 auto;
}
.patient-context__sis {
  display: grid;
  grid-template-columns: 102px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  min-width: 0;
  min-height: calc(var(--el-component-size, 26px) * 2 + 2px);
}
.patient-context__sis-brand {
  justify-self: end;
}
.patient-context__sis-fields {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.patient-context__contact :deep(.el-input__wrapper) {
  background: #fff0dd;
}
.patient-context__relations {
  grid-column: 1 / -1;
}
.patient-context__actions :deep(.el-button) {
  margin: 0;
}
/* La baja es una acción destructiva: se separa del guardado habitual. */
.patient-context__remove {
  margin-top: 8px !important;
  border-style: dashed;
}
.patient-context__hint {
  margin: 2px 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
}
.patient-context__field-error {
  color: var(--el-color-danger);
  font-size: 12px;
  margin: 4px 0 0;
}
@media (max-width: 560px) {
  .patient-context {
    --el-component-size: 36px;
  }
  .patient-context__form :deep(.el-input__inner),
  .patient-context__form :deep(.el-select__input) {
    font-size: 16px;
  }
  .patient-context__form :deep(.el-form-item) {
    flex-direction: column;
  }
  .patient-context__form :deep(.el-form-item__label) {
    width: auto !important;
    justify-content: flex-start;
    text-align: left;
  }
  .patient-context__form :deep(.el-form-item__content) {
    width: 100%;
    margin-left: 0 !important;
  }
}
@media (pointer: coarse) {
  .patient-context {
    --el-component-size: 36px;
  }
}
</style>
