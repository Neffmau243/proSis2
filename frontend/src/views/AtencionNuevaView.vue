<template>
  <div class="admission-page" :class="{ 'admission-page--workspace': isAdmission }">
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <el-skeleton v-if="initialLoading" :rows="8" animated />

    <template v-else>
      <el-empty
        v-if="isAdmission && !admissionPatient"
        description="No fue posible cargar el paciente para esta admisión."
      />

      <div
        v-else-if="showForm"
        class="admission-workbench"
        :class="{ 'admission-workbench--standalone': !isAdmission }"
      >
        <aside v-if="isAdmission && admissionPatient" class="admission-workbench__patient">
          <AdmissionPatientSummary
            :patient="admissionPatient"
            :can-edit="auth.hasPermission('PACIENTE_EDITAR')"
            :can-delete="auth.hasPermission('PACIENTE_DAR_BAJA')"
            :blocked="saving || attentionCreated"
            :tipos-documento="tiposDocumento"
            :grupos-riesgo="gruposRiesgo"
            @saved="applyUpdatedPatient"
            @dirty-change="patientContextDirty = $event"
            @busy-change="patientContextSaving = $event"
            @removed="onPatientRemoved"
          />
        </aside>

        <div class="admission-workbench__content">
          <el-card class="encounter-card" shadow="never">
            <el-form
              ref="formRef"
              :model="form"
              :rules="rules"
              :disabled="saving || attentionCreated"
              :label-width="isAdmission ? 'auto' : '200px'"
              :label-position="isAdmission ? 'top' : 'right'"
              class="encounter-form"
              @submit.prevent="submit"
            >
              <AdmissionEncounterHeader v-if="isAdmission" v-model="form.fecha_atencion" />
              <section
                class="clinical-section clinical-section--context"
                aria-labelledby="encounter-context-title"
              >
                <div class="attention-mode-control">
                  <el-form-item label="Modalidad de atención" prop="modalidad_atencion_codigo">
                    <el-radio-group
                      class="attention-mode-selector"
                      v-model="form.modalidad_atencion_codigo"
                      aria-label="Modalidad de atención"
                    >
                      <el-radio value="AMBULATORIA"> Ambulatoria </el-radio>
                      <el-radio value="EMERGENCIA"> Emergencia </el-radio>
                    </el-radio-group>
                  </el-form-item>
                </div>
                <div class="clinical-section__heading">
                  <div>
                    <h3 id="encounter-context-title" class="clinical-section__title">
                      Consultorio
                    </h3>
                    <p v-if="!isAdmission" class="clinical-section__description">
                      {{
                        isAdmission
                          ? 'Seleccione consultorio, especialidad y profesional para la atención.'
                          : 'Defina dónde, cuándo y con quién se registra la atención.'
                      }}
                    </p>
                  </div>
                </div>
                <el-row :gutter="isAdmission ? 12 : 16">
                  <template v-if="isAdmission">
                    <el-col :span="24">
                      <el-form-item
                        class="admission-context-field"
                        label="Consultorio"
                        prop="consultorio_id"
                      >
                        <el-select
                          v-model="form.consultorio_id"
                          filterable
                          :loading="consultoriosLoading"
                          style="width: 100%"
                          placeholder="Seleccione el consultorio"
                        >
                          <el-option
                            v-for="office in consultorios"
                            :key="office.id"
                            :label="office.nombre"
                            :value="office.id"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-form-item class="admission-context-field" label="Especialidad">
                        <el-select v-model="form.especialidad_codigo" clearable style="width: 100%">
                          <el-option
                            v-for="esp in especialidades"
                            :key="esp.codigo"
                            :label="esp.nombre"
                            :value="esp.codigo"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-form-item
                        class="admission-context-field"
                        label="Profesional"
                        prop="profesional_id"
                      >
                        <el-select
                          v-model="form.profesional_id"
                          filterable
                          remote
                          :remote-method="searchProfesionales"
                          :loading="profesionalesLoading"
                          style="width: 100%"
                          placeholder="Seleccione el profesional"
                        >
                          <el-option
                            v-for="prof in profesionales"
                            :key="prof.id"
                            :label="prof.nombre_completo"
                            :value="prof.id"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                  </template>

                  <template v-else>
                    <el-col :span="8">
                      <el-form-item label="Paciente" prop="paciente_id">
                        <el-select
                          v-model="form.paciente_id"
                          filterable
                          remote
                          :remote-method="searchPacientes"
                          :loading="pacientesLoading"
                          style="width: 100%"
                          placeholder="Busque por documento o nombre"
                          :disabled="lockPatientSelection"
                        >
                          <el-option
                            v-for="paciente in pacientesOptions"
                            :key="paciente.id"
                            :label="`${paciente.id} — ${paciente.tipo_documento_codigo} ${paciente.numero_documento}${paciente.primer_nombre ? ' · ' + paciente.primer_nombre : ''}`"
                            :value="paciente.id"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="Establecimiento" prop="establecimiento_id">
                        <el-select
                          v-model="form.establecimiento_id"
                          filterable
                          remote
                          :remote-method="searchEstablecimientos"
                          :loading="establecimientosLoading"
                          style="width: 100%"
                          placeholder="Busque"
                        >
                          <el-option
                            v-for="est in establecimientos"
                            :key="est.id"
                            :label="est.nombre"
                            :value="est.id"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="Consultorio" prop="consultorio_id">
                        <el-select
                          v-model="form.consultorio_id"
                          filterable
                          :loading="consultoriosLoading"
                          style="width: 100%"
                          placeholder="Según establecimiento"
                        >
                          <el-option
                            v-for="office in consultorios"
                            :key="office.id"
                            :label="office.nombre"
                            :value="office.id"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="Profesional" prop="profesional_id">
                        <el-select
                          v-model="form.profesional_id"
                          filterable
                          remote
                          :remote-method="searchProfesionales"
                          :loading="profesionalesLoading"
                          style="width: 100%"
                          placeholder="Busque"
                        >
                          <el-option
                            v-for="prof in profesionales"
                            :key="prof.id"
                            :label="prof.nombre_completo"
                            :value="prof.id"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="Especialidad">
                        <el-select v-model="form.especialidad_codigo" clearable style="width: 100%">
                          <el-option
                            v-for="esp in especialidades"
                            :key="esp.codigo"
                            :label="esp.nombre"
                            :value="esp.codigo"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="Fecha de atención" prop="fecha_atencion">
                        <el-date-picker
                          v-model="form.fecha_atencion"
                          type="datetime"
                          value-format="YYYY-MM-DDTHH:mm:ss"
                          style="width: 100%"
                        />
                      </el-form-item>
                    </el-col>
                  </template>
                </el-row>

                <el-collapse
                  v-if="!isAdmission"
                  v-model="expandedContextDetails"
                  class="clinical-details"
                >
                  <el-collapse-item name="context-details">
                    <template #title>
                      <span class="clinical-details__title"
                        >Datos complementarios de la atención</span
                      >
                    </template>
                    <el-row :gutter="16">
                      <el-col :span="8">
                        <el-form-item label="Fecha efectiva (opcional)">
                          <el-date-picker
                            v-model="form.fecha_atendido"
                            type="datetime"
                            value-format="YYYY-MM-DDTHH:mm:ss"
                            style="width: 100%"
                            clearable
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="8">
                        <el-form-item label="Hora inicio">
                          <el-time-picker
                            v-model="form.hora_inicio"
                            value-format="HH:mm:ss"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="8">
                        <el-form-item label="Hora fin">
                          <el-time-picker
                            v-model="form.hora_fin"
                            value-format="HH:mm:ss"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="8">
                        <el-form-item :label="isAdmission ? 'Motivo de admisión' : 'Admisión'">
                          <el-input
                            v-model="form.admision"
                            :placeholder="
                              isAdmission ? 'Motivo o referencia de ingreso' : undefined
                            "
                          />
                        </el-form-item>
                      </el-col>
                    </el-row>
                  </el-collapse-item>
                </el-collapse>
              </section>

              <section
                class="clinical-section clinical-section--measurements"
                aria-labelledby="measurements-title"
              >
                <div class="clinical-population-selector">
                  <el-form-item label="Grupo de atención">
                    <el-radio-group
                      class="care-group-selector"
                      :model-value="selectedCareGroup"
                      aria-label="Grupo de atención"
                      @update:model-value="selectCareGroup($event as CareGroupCode)"
                    >
                      <el-radio value="NINOS_ADOLESCENTES_ADULTOS_MAYORES">
                        Niños, adolescentes, adultos y adultos mayores
                      </el-radio>
                      <el-radio value="GESTANTES"> Gestantes </el-radio>
                      <el-radio value="PUERPERAS"> Puérperas </el-radio>
                    </el-radio-group>
                  </el-form-item>
                </div>
                <div v-if="!isAdmission" class="clinical-section__heading">
                  <div>
                    <h3 id="measurements-title" class="clinical-section__title">
                      Mediciones clínicas
                    </h3>
                    <p class="clinical-section__description">
                      Registre medidas y signos vitales tomados durante la atención.
                    </p>
                  </div>
                </div>
                <div class="measurement-groups">
                  <div class="measurement-group">
                    <h4
                      :id="isAdmission ? 'measurements-title' : undefined"
                      class="measurement-group__title"
                    >
                      Mediciones clínicas
                    </h4>
                    <el-row :gutter="isAdmission ? 12 : 16">
                      <el-col v-if="isObstetric" :span="24">
                        <el-form-item class="measurement-field" label="Tipo de embarazo">
                          <el-select
                            v-model="form.tipo_embarazo_codigo"
                            clearable
                            placeholder="Seleccione"
                            style="width: 100%"
                          >
                            <el-option
                              v-for="type in PREGNANCY_TYPES"
                              :key="type.value"
                              :label="type.label"
                              :value="type.value"
                            />
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-col v-if="isObstetric" :span="24">
                        <el-form-item
                          class="measurement-field"
                          label="Peso antes del embarazo (kg)"
                        >
                          <el-input-number
                            v-model="form.peso_antes_embarazo_kg"
                            :min="0"
                            :precision="2"
                            :controls="false"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="24">
                        <el-form-item class="measurement-field" label="Peso actual (kg)">
                          <el-input-number
                            v-model="form.peso_kg"
                            :min="0"
                            :precision="2"
                            :controls="false"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="24">
                        <el-form-item class="measurement-field" label="Talla (cm)">
                          <el-input-number
                            v-model="form.talla_cm"
                            :min="0"
                            :precision="2"
                            :controls="false"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col v-if="isPregnant" :span="24">
                        <el-form-item class="measurement-field" label="Fecha probable de parto">
                          <el-date-picker
                            v-model="form.fecha_probable_parto"
                            type="date"
                            value-format="YYYY-MM-DD"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col v-else-if="isPuerperal" :span="24">
                        <el-form-item class="measurement-field" label="Fecha del parto">
                          <el-date-picker
                            v-model="form.fecha_parto"
                            type="date"
                            value-format="YYYY-MM-DD"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col v-else :span="24">
                        <el-form-item class="measurement-field" label="Perímetro abdominal (cm)">
                          <el-input-number
                            v-model="form.perimetro_abdominal_cm"
                            :min="0"
                            :precision="2"
                            :controls="false"
                            style="width: 100%"
                          />
                        </el-form-item>
                      </el-col>
                    </el-row>
                  </div>
                  <div class="measurement-group">
                    <h4 class="measurement-group__title">Presión arterial y temperatura</h4>
                    <div
                      class="vital-signs"
                      role="group"
                      aria-label="Presión arterial y temperatura"
                    >
                      <div class="vital-signs__pressure">
                        <span class="vital-signs__label">Diast.</span>
                        <el-input-number
                          v-model="form.presion_diastolica"
                          class="vital-signs__input"
                          :min="1"
                          :controls="false"
                          aria-label="Presión diastólica"
                        />
                        <span class="vital-signs__separator" aria-hidden="true">/</span>
                        <span class="vital-signs__label">Sist.</span>
                        <el-input-number
                          v-model="form.presion_sistolica"
                          class="vital-signs__input"
                          :min="1"
                          :controls="false"
                          aria-label="Presión sistólica"
                        />
                      </div>
                      <div class="vital-signs__temperature">
                        <span class="vital-signs__label">Temp.</span>
                        <el-input-number
                          v-model="form.temperatura_c"
                          class="vital-signs__input"
                          :min="0"
                          :precision="1"
                          :controls="false"
                          aria-label="Temperatura en grados Celsius"
                        />
                        <span class="vital-signs__unit">°C</span>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section
                class="clinical-section clinical-section--nutrition"
                aria-labelledby="nutrition-title"
              >
                <div class="clinical-section__heading">
                  <h3 id="nutrition-title" class="clinical-section__title">
                    Valoración nutricional
                  </h3>
                </div>
                <div class="nutrition-age" aria-live="polite">
                  <div class="nutrition-age__row">
                    <span class="nutrition-age__label">Edad a la atención</span>
                    <strong class="nutrition-age__value">{{ nutritionalAge }}</strong>
                  </div>
                </div>
                <el-row :gutter="isAdmission ? 12 : 16" class="nutrition-fields">
                  <el-col v-for="item in nutritionRows" :key="item.label" :span="24">
                    <el-form-item class="nutrition-field" :label="item.label">
                      <el-input :model-value="item.value" readonly />
                    </el-form-item>
                  </el-col>
                </el-row>
                <small role="status">{{ nutritionStatus }}</small>
              </section>
            </el-form>
            <AdmissionFinalActions
              :saving="saving"
              :saved="attentionCreated"
              :print-ready="!!fuaSnapshot"
              :disabled="patientContextDirty || patientContextSaving"
              :disabled-reason="
                patientContextSaving
                  ? 'Termine de guardar los datos del paciente.'
                  : patientContextDirty
                    ? 'Guarde o descarte los cambios del paciente antes de guardar la atención.'
                    : attentionCreated
                      ? fuaSnapshot
                        ? 'Atención guardada correctamente. Ya puede imprimir S.I.S.'
                        : 'Atención guardada. La copia para imprimir S.I.S. no está disponible.'
                      : 'Guarde la atención para habilitar Imprimir S.I.S.'
              "
              :primary-label="
                attentionCreated
                  ? 'Atención guardada'
                  : isAdmission
                    ? 'Guardar atención'
                    : 'Registrar atención'
              "
              @submit="submit"
              @exit="cancel"
              @print="fuaDialog = true"
            />
          </el-card>
        </div>

        <div v-if="showHistorial" class="admission-workbench__history">
          <AdmissionHistory
            :compact="isAdmission"
            :entries="historial"
            :loading="historialLoading"
            :error="historialError"
            @refresh="loadHistorial"
          />
        </div>
      </div>
    </template>
    <FuaPrintDialog v-if="fuaSnapshot" v-model="fuaDialog" :snapshot="fuaSnapshot" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import AdmissionHistory from '@/components/admission/AdmissionHistory.vue'
import AdmissionEncounterHeader from '@/components/admission/AdmissionEncounterHeader.vue'
import AdmissionFinalActions from '@/components/admission/AdmissionFinalActions.vue'
import FuaPrintDialog from '@/components/admission/FuaPrintDialog.vue'
import { useSavedAdmission } from '@/composables/useSavedAdmission'
import AdmissionPatientSummary from '@/components/admission/AdmissionPatientSummary.vue'
import {
  catalogos,
  type CodeCatalogItem,
  type EstablishmentCatalogItem,
  type OfficeCatalogItem,
  type ProfessionalCatalogItem,
  type RiskGroupCatalogItem,
  type SpecialtyCatalogItem,
} from '@/services/catalogos'
import { pacientes, type Patient } from '@/services/pacientes'
import { useAuthStore } from '@/stores/auth'
import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import {
  atenciones,
  type Attention,
  type AttentionCreatePayload,
  type CareGroupCode,
  type NutritionalSnapshotPayload,
  type PregnancyTypeCode,
} from '@/services/atenciones'
import { formatCalendarAge } from '@/utils/calendarAge'
import { useNutritionalIndicatorsPreview } from '@/composables/useNutritionalIndicatorsPreview'
import { nutritionalRows, nutritionalBmiSummary } from '@/utils/nutritionalDisplay'
import { PREGNANCY_TYPES } from '@/utils/pregnancy'

const props = withDefaults(
  defineProps<{
    admission?: boolean
  }>(),
  { admission: false },
)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { seleccionado, seleccionar, notificarCambio } = usePacienteSeleccionado()
const isAdmission = computed(() => props.admission)
// `patientId` es el parámetro canónico de la ruta de admisión. Conservamos
// `pacienteId` para que los accesos creados antes de este cambio no se rompan.
const preselectedPatientId = patientIdFromQuery(route.query.patientId ?? route.query.pacienteId)

const formRef = ref<FormInstance>()
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const initialLoading = ref(false)
const expandedContextDetails = shallowRef<string[]>([])

const pacientesOptions = ref<Patient[]>([])
const pacientesLoading = ref(false)
const admissionPatient = ref<Patient | null>(null)
const patientContextSaving = ref(false)
const patientContextDirty = shallowRef(false)
const lockPatientSelection = ref(false)
const establecimientos = ref<EstablishmentCatalogItem[]>([])
const establecimientosLoading = ref(false)
const consultorios = ref<OfficeCatalogItem[]>([])
const consultoriosLoading = ref(false)
const profesionales = ref<ProfessionalCatalogItem[]>([])
const profesionalesLoading = ref(false)
const especialidades = ref<SpecialtyCatalogItem[]>([])
const tiposDocumento = ref<CodeCatalogItem[]>([])
const gruposRiesgo = ref<RiskGroupCatalogItem[]>([])
const historial = ref<Attention[]>([])
const historialLoading = ref(false)
const historialError = shallowRef<string | null>(null)
let historyRequest = 0

const form = reactive({
  paciente_id: null as number | null,
  establecimiento_id: null as number | null,
  consultorio_id: null as number | null,
  profesional_id: null as number | null,
  especialidad_codigo: null as string | null,
  modalidad_atencion_codigo: 'AMBULATORIA' as 'AMBULATORIA' | 'EMERGENCIA',
  fecha_atencion: '',
  fecha_atendido: null as string | null,
  tipo_embarazo_codigo: null as PregnancyTypeCode | null,
  peso_antes_embarazo_kg: null as number | null,
  fecha_probable_parto: null as string | null,
  fecha_parto: null as string | null,
  peso_kg: null as number | null,
  talla_cm: null as number | null,
  perimetro_abdominal_cm: null as number | null,
  temperatura_c: null as number | null,
  presion_sistolica: null as number | null,
  presion_diastolica: null as number | null,
  hora_inicio: null as string | null,
  hora_fin: null as string | null,
  admision: '',
})

const { fuaDialog, fuaSnapshot, attentionCreated, remember } = useSavedAdmission(
  () => form.paciente_id,
)
/** Población clínica declarada; se persiste en la atención. */
const selectedCareGroup = ref<CareGroupCode>('NINOS_ADOLESCENTES_ADULTOS_MAYORES')

/** Los campos obstétricos solo aplican a los grupos Gestantes y Puérperas. */
const isPregnant = computed(() => selectedCareGroup.value === 'GESTANTES')
const isPuerperal = computed(() => selectedCareGroup.value === 'PUERPERAS')
/** Tipo de embarazo y peso antes del embarazo son comunes a ambos grupos. */
const isObstetric = computed(() => isPregnant.value || isPuerperal.value)

const rules: FormRules = {
  paciente_id: [{ required: true, message: 'Seleccione el paciente.', trigger: 'change' }],
  establecimiento_id: [
    { required: true, message: 'Seleccione el establecimiento.', trigger: 'change' },
  ],
  consultorio_id: [{ required: true, message: 'Seleccione el consultorio.', trigger: 'change' }],
  profesional_id: [{ required: true, message: 'Seleccione el profesional.', trigger: 'change' }],
  modalidad_atencion_codigo: [
    { required: true, message: 'Seleccione la modalidad.', trigger: 'change' },
  ],
  fecha_atencion: [{ required: true, message: 'Indique la fecha de atención.', trigger: 'change' }],
}

/** El paciente de la admisión nunca debe quedar fuera del formulario. */
const showForm = computed(() => !isAdmission.value || admissionPatient.value !== null)

/** El historial necesita un paciente conocido (admisión o selección manual). */
const historialPatientId = computed(() =>
  isAdmission.value ? (admissionPatient.value?.id ?? null) : form.paciente_id,
)
const showHistorial = computed(() => !initialLoading.value && historialPatientId.value !== null)

const nutritionalPatient = computed<Patient | null>(() =>
  isAdmission.value
    ? admissionPatient.value
    : (pacientesOptions.value.find((patient) => patient.id === form.paciente_id) ?? null),
)
const nutritionalAge = computed(() => {
  const birthDate = nutritionalPatient.value?.fecha_nacimiento
  if (!birthDate) return '—'

  return formatCalendarAge(birthDate, form.fecha_atencion || new Date()) ?? '—'
})

const { indicators: nutritionIndicators, loading: nutritionLoading, error: nutritionError } = useNutritionalIndicatorsPreview({
  patientId: () => nutritionalPatient.value?.id ?? null,
  attendedAt: () => form.fecha_atencion,
  weightKg: () => form.peso_kg,
  heightCm: () => form.talla_cm,
  patientRevision: () => `${nutritionalPatient.value?.fecha_nacimiento}|${nutritionalPatient.value?.sexo_codigo}`,
  careGroup: () => selectedCareGroup.value,
  pregestationalWeightKg: () => form.peso_antes_embarazo_kg,
})

const nutritionRows = computed(() => nutritionLoading.value || nutritionError.value
  ? nutritionalRows(null).map(item => ({ ...item, value: nutritionLoading.value ? 'Calculando…' : 'No disponible' }))
  : nutritionalRows(nutritionIndicators.value))

const nutritionStatus = computed(() => {
  if (nutritionLoading.value) return 'Calculando…'
  if (nutritionError.value) return nutritionError.value
  return nutritionalBmiSummary(nutritionIndicators.value) || nutritionIndicators.value?.mensaje || ''
})

function patientIdFromQuery(value: unknown): number | null {
  const rawValue = Array.isArray(value) ? value[0] : value
  if (typeof rawValue !== 'string') return null

  const patientId = Number(rawValue)
  return Number.isSafeInteger(patientId) && patientId > 0 ? patientId : null
}

function formatCurrentDateTime(): string {
  const current = new Date()
  const local = new Date(current.getTime() - current.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 19)
}

/**
 * Precarga los datos del paciente en el formulario: el paciente queda fijado y,
 * cuando tiene establecimiento de registro, la atención se abre en esa sede.
 * Si no lo tiene, el consultorio elegido determina la sede requerida por el
 * backend. Consultorio, especialidad y profesional siguen siendo elecciones
 * explícitas de la admisión.
 */
function applyPatientContext(patient: Patient): void {
  form.paciente_id = patient.id
  if (patient.establecimiento_registro_id) {
    form.establecimiento_id = patient.establecimiento_registro_id
  }
}

/** Consume a confirmed patient save; the editor owns its PATCH lifecycle. */
function applyUpdatedPatient(updated: Patient): void {
  const previous = admissionPatient.value
  admissionPatient.value = updated
  pacientesOptions.value = [updated]
  if (seleccionado.value?.id === updated.id) seleccionar(updated)
  notificarCambio()
  if (
    previous?.establecimiento_registro_id !== updated.establecimiento_registro_id &&
    form.consultorio_id === null
  ) {
    form.establecimiento_id = updated.establecimiento_registro_id
  }
}

/**
 * El paciente se dio de baja desde el panel de admisión: se limpia la
 * selección compartida y se vuelve al listado para no admitir a un inactivo.
 */
function onPatientRemoved(removed: Patient): void {
  if (seleccionado.value?.id === removed.id) seleccionar(null)
  pacientesOptions.value = []
  notificarCambio()
  // El paciente ya no existe: no hay ediciones que conservar y la guarda de
  // salida no debe bloquear la vuelta al listado.
  patientContextDirty.value = false
  void router.push({ name: 'inicio' })
}

/** Convierte el bloque en el payload del backend; `null` si no se registró nada. */
function buildNutritionalPayload(): NutritionalSnapshotPayload | null {
  // The server recalculates and persists the classifications atomically.
  return null
}

function selectCareGroup(group: CareGroupCode): void {
  selectedCareGroup.value = group
  // El perímetro abdominal solo corresponde al grupo general.
  form.perimetro_abdominal_cm = null
  // Cada grupo conserva únicamente sus fechas: FPP para gestantes, fecha real
  // del parto para puérperas, ninguna de las dos para el grupo general.
  if (group !== 'GESTANTES') form.fecha_probable_parto = null
  if (group !== 'PUERPERAS') form.fecha_parto = null
  if (group === 'GESTANTES' || group === 'PUERPERAS') return
  // Tipo de embarazo y peso previo tampoco viajan fuera de los grupos maternos.
  form.tipo_embarazo_codigo = null
  form.peso_antes_embarazo_kg = null
}

async function searchPacientes(query: string): Promise<void> {
  pacientesLoading.value = true
  try {
    const page = await pacientes.search({
      q: query && query.trim().length >= 2 ? query.trim() : undefined,
      limit: 10,
      offset: 0,
    })
    pacientesOptions.value = page.items
  } finally {
    pacientesLoading.value = false
  }
}

async function searchEstablecimientos(query: string): Promise<void> {
  establecimientosLoading.value = true
  try {
    const page = await catalogos.establecimientos(query || undefined, 25, 0)
    establecimientos.value = page.items
  } finally {
    establecimientosLoading.value = false
  }
}

async function searchProfesionales(query: string): Promise<void> {
  profesionalesLoading.value = true
  try {
    const page = await catalogos.profesionales(query || undefined, 25, 0)
    profesionales.value = page.items
  } finally {
    profesionalesLoading.value = false
  }
}

async function loadConsultorios(): Promise<void> {
  consultoriosLoading.value = true
  try {
    const page = await catalogos.consultorios(
      form.establecimiento_id ?? undefined,
      undefined,
      50,
      0,
    )
    consultorios.value = page.items
  } finally {
    consultoriosLoading.value = false
  }
}

async function loadHistorial(): Promise<void> {
  const request = ++historyRequest
  const patientId = historialPatientId.value
  historialError.value = null
  if (!patientId) {
    historial.value = []
    historialLoading.value = false
    return
  }
  historialLoading.value = true
  try {
    const entries = await atenciones.listByPatient(patientId)
    if (request === historyRequest) historial.value = entries
  } catch (error) {
    if (request === historyRequest) {
      historialError.value =
        error instanceof Error
          ? error.message
          : 'No se pudo cargar el historial. Pulse Refrescar para reintentar.'
    }
  } finally {
    if (request === historyRequest) historialLoading.value = false
  }
}

// Al cambiar el establecimiento, se recargan los consultorios de esa sede.
// Conservamos el seleccionado si justamente fue él quien definió la sede.
watch(
  () => form.establecimiento_id,
  (establishmentId) => {
    const selectedOffice = consultorios.value.find((office) => office.id === form.consultorio_id)
    if (!selectedOffice || selectedOffice.establecimiento_id !== establishmentId) {
      form.consultorio_id = null
    }
    void loadConsultorios()
  },
)

// En "Nueva atención" el paciente se elige a mano: su historial se recarga y,
// si aún no hay sede, se precarga la de registro del paciente.
watch(
  () => form.paciente_id,
  (id) => {
    const selected = pacientesOptions.value.find((item) => item.id === id)
    if (selected && !isAdmission.value && !form.establecimiento_id) {
      applyPatientContext(selected)
    }
    void loadHistorial()
  },
)

// El consultorio define la sede y la especialidad cuando las trae asignadas.
watch(
  () => form.consultorio_id,
  (id) => {
    if (id === null) return
    const office = consultorios.value.find((item) => item.id === id)
    if (office && form.establecimiento_id !== office.establecimiento_id) {
      form.establecimiento_id = office.establecimiento_id
    }
    if (office?.especialidad_codigo) {
      form.especialidad_codigo = office.especialidad_codigo
    }
  },
)

async function submit(): Promise<void> {
  if (
    saving.value ||
    attentionCreated.value ||
    patientContextSaving.value ||
    patientContextDirty.value
  )
    return
  saving.value = true
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    saving.value = false
    return
  }

  const valoracion = buildNutritionalPayload()
  errorMessage.value = null
  try {
    const payload: AttentionCreatePayload = {
      paciente_id: form.paciente_id!,
      establecimiento_id: form.establecimiento_id!,
      consultorio_id: form.consultorio_id!,
      profesional_id: form.profesional_id!,
      especialidad_codigo: form.especialidad_codigo,
      modalidad_atencion_codigo: form.modalidad_atencion_codigo,
      grupo_atencion_codigo: selectedCareGroup.value,
      fecha_atencion: form.fecha_atencion,
      fecha_atendido: form.fecha_atendido,
      tipo_embarazo_codigo: form.tipo_embarazo_codigo,
      peso_antes_embarazo_kg: form.peso_antes_embarazo_kg,
      fecha_probable_parto: form.fecha_probable_parto,
      fecha_parto: form.fecha_parto,
      peso_kg: form.peso_kg,
      talla_cm: form.talla_cm,
      perimetro_abdominal_cm: form.perimetro_abdominal_cm,
      temperatura_c: form.temperatura_c,
      presion_sistolica: form.presion_sistolica,
      presion_diastolica: form.presion_diastolica,
      hora_inicio: form.hora_inicio,
      hora_fin: form.hora_fin,
      admision: form.admision || null,
      valoracion_nutricional: valoracion,
    }
    const created = await atenciones.create(payload)
    remember(created)
    ElMessage.success('Atención guardada correctamente.')
    void loadHistorial()
    // Refresh from the committed patient, never infer a successful update from
    // the selected radio. A refresh failure must not invite a duplicate POST.
    try {
      applyUpdatedPatient(await pacientes.get(created.paciente_id))
    } catch {
      ElMessage.warning(
        'La atención está guardada, pero no se pudo refrescar la ficha. Recargue para ver la condición actualizada.',
      )
    }
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo registrar la atención.'
  } finally {
    saving.value = false
  }
}

function cancel(): void {
  void router.push({ name: 'inicio' })
}

function canLeavePatientEditor(): boolean {
  if (
    !patientContextDirty.value &&
    !patientContextSaving.value &&
    (!saving.value || attentionCreated.value)
  )
    return true
  ElMessage.warning(
    'Guarde o descarte los cambios del paciente y termine las operaciones en curso antes de salir.',
  )
  return false
}
onBeforeRouteLeave((to) => to.name === 'login' || canLeavePatientEditor())
onBeforeRouteUpdate(() => canLeavePatientEditor())
function beforeUnload(event: BeforeUnloadEvent): void {
  if (!patientContextDirty.value && !patientContextSaving.value && !saving.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))

onMounted(async () => {
  initialLoading.value = true
  errorMessage.value = null
  try {
    if (isAdmission.value && preselectedPatientId === null) {
      errorMessage.value =
        'Seleccione un paciente desde la Base de datos antes de iniciar una admisión.'
      return
    }

    const [
      especialidadesResult,
      estResult,
      profesionalesResult,
      tiposDocumentoResult,
      gruposRiesgoResult,
      patient,
    ] = await Promise.all([
      catalogos.especialidades(),
      catalogos.establecimientos(undefined, 25, 0),
      catalogos.profesionales(undefined, 50, 0),
      catalogos.tiposDocumento(),
      catalogos.gruposRiesgo(),
      preselectedPatientId === null ? Promise.resolve(null) : pacientes.get(preselectedPatientId),
    ])
    especialidades.value = especialidadesResult
    establecimientos.value = estResult.items
    profesionales.value = profesionalesResult.items
    tiposDocumento.value = tiposDocumentoResult
    gruposRiesgo.value = gruposRiesgoResult

    if (patient) {
      pacientesOptions.value = [patient]
      lockPatientSelection.value = true
      applyPatientContext(patient)
      if (isAdmission.value) {
        admissionPatient.value = patient
        form.fecha_atencion = formatCurrentDateTime()
        if (!form.establecimiento_id) await loadConsultorios()
      }
    }
  } catch (error) {
    form.paciente_id = null
    lockPatientSelection.value = false
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo preparar la admisión del paciente.'
  } finally {
    initialLoading.value = false
  }
})
</script>

<style scoped>
.admission-page {
  --admission-space-tight: 6px;
  --admission-space: 12px;
  --admission-space-wide: 16px;
}

.form-alert {
  margin-bottom: var(--admission-space);
}

.admission-workbench {
  display: grid;
  grid-template-areas:
    'patient content'
    'history history';
  grid-template-columns: minmax(280px, 320px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.admission-workbench--standalone {
  grid-template-areas:
    'content'
    'history';
  grid-template-columns: minmax(0, 1fr);
}

.admission-workbench__patient {
  grid-area: patient;
  display: flex;
  min-width: 0;
}

.admission-workbench__patient :deep(.patient-context) {
  flex: 1 1 auto;
}

.admission-workbench__content {
  grid-area: content;
  display: grid;
  min-width: 0;
  gap: 12px;
}

.admission-workbench__history {
  grid-area: history;
  min-width: 0;
}

.encounter-card {
  min-width: 0;
  border-color: var(--el-border-color-lighter);
  border-radius: 12px;
  container-type: inline-size;
}

.encounter-card :deep(.el-card__body) {
  padding: 14px;
}

.encounter-form {
  display: grid;
  grid-template-areas:
    'context nutrition'
    'measurements nutrition';
  grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
  gap: var(--admission-space-wide) 16px;
}

.clinical-section {
  min-width: 0;
}

.clinical-section--context {
  grid-area: context;
}

.clinical-section--measurements {
  grid-area: measurements;
  padding-top: var(--admission-space-wide);
  border-top: 1px solid var(--el-border-color-lighter);
}

.clinical-section--nutrition {
  grid-area: nutrition;
  display: flex;
  flex-direction: column;
  padding-left: 16px;
  border-left: 1px solid var(--el-border-color-lighter);
}

.clinical-section__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--admission-space);
  margin-bottom: 10px;
}

.clinical-section__title,
.measurement-group__title {
  margin: 0;
  color: var(--el-text-color-primary);
}

.clinical-section__title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.3;
}

.clinical-section__description {
  margin: 2px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.35;
}

.measurement-groups {
  display: grid;
  gap: var(--admission-space);
}

.measurement-group + .measurement-group {
  padding-top: var(--admission-space);
  border-top: 1px solid var(--el-border-color-lighter);
}

.measurement-group__title {
  font-size: 13px;
  font-weight: 650;
  line-height: 1.35;
}

.measurement-group__description {
  margin: 2px 0 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.nutrition-age {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  margin-bottom: 10px;
  padding: 8px 10px;
  color: var(--el-color-primary-dark-2);
  background-color: var(--el-color-primary-light-9);
  border-top: 1px solid var(--el-color-primary-light-7);
  border-bottom: 1px solid var(--el-color-primary-light-7);
}

.nutrition-age__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--admission-space);
}

.nutrition-age__label {
  color: inherit;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.35;
}

.nutrition-age__value {
  min-width: 0;
  color: var(--el-text-color-primary);
  font-size: clamp(15px, 1.2vw, 18px);
  font-weight: 700;
  line-height: 1.3;
  overflow-wrap: anywhere;
  text-align: end;
}

.nutrition-fields {
  display: grid;
  gap: 2px;
}

.vital-signs,
.vital-signs__pressure,
.vital-signs__temperature {
  display: flex;
  align-items: center;
}

.vital-signs {
  flex-wrap: nowrap;
  gap: 8px;
  margin-top: 4px;
}

.vital-signs__pressure,
.vital-signs__temperature {
  flex: 0 0 auto;
  gap: 4px;
}

.vital-signs__label,
.vital-signs__unit,
.vital-signs__separator {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}

.vital-signs__separator {
  color: var(--el-text-color-regular);
}

.vital-signs :deep(.vital-signs__input) {
  width: clamp(46px, 6vw, 64px);
}

.clinical-details {
  margin-top: 4px;
  border-top: 1px solid var(--el-border-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.clinical-details :deep(.el-collapse-item__header) {
  height: 34px;
  color: var(--el-text-color-secondary);
  background-color: transparent;
  border-bottom: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
}

.clinical-details :deep(.el-collapse-item__wrap) {
  background-color: transparent;
  border-bottom: 0;
}

.clinical-details :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.clinical-details__title {
  line-height: 1.35;
}

:deep(.encounter-form .el-form-item) {
  margin-bottom: 8px;
}

:deep(.encounter-form .el-form-item__label) {
  height: auto;
  padding: 0 0 3px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
}

:deep(.admission-context-field) {
  display: flex;
  align-items: center;
  gap: var(--admission-space);
}

:deep(.admission-context-field .el-form-item__label) {
  flex: 0 0 116px;
  justify-content: flex-start;
  padding: 0;
}

:deep(.admission-context-field .el-form-item__content) {
  flex: 1 1 auto;
  min-width: 0;
  margin-left: 0 !important;
}

:deep(.measurement-field),
:deep(.nutrition-field) {
  display: flex;
  align-items: center;
  gap: var(--admission-space);
}

.nutrition-fields :deep(.nutrition-field) {
  margin-bottom: 0;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.nutrition-fields :deep(.el-col:last-child .nutrition-field) {
  border-bottom: 0;
}

:deep(.measurement-field .el-form-item__label),
:deep(.nutrition-field .el-form-item__label) {
  flex: 0 1 170px;
  min-width: 124px;
  justify-content: flex-start;
  padding: 0;
}

:deep(.measurement-field .el-form-item__content),
:deep(.nutrition-field .el-form-item__content) {
  flex: 1 1 auto;
  min-width: 0;
  margin-left: 0 !important;
}

:deep(.encounter-form .el-radio-group),
:deep(.encounter-form .el-checkbox-group),
.attention-mode-selector,
.care-group-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 10px;
}

:deep(.encounter-form .el-radio),
:deep(.encounter-form .el-checkbox) {
  margin-right: 0;
}

@container (max-width: 700px) {
  .encounter-form {
    grid-template-areas:
      'context'
      'measurements'
      'nutrition'
      'actions';
    grid-template-columns: minmax(0, 1fr);
  }

  .clinical-section--nutrition {
    padding-top: var(--admission-space-wide);
    padding-left: 0;
    border-top: 1px solid var(--el-border-color-lighter);
    border-left: 0;
  }
}

@media (max-width: 900px) {
  .admission-workbench {
    grid-template-areas:
      'patient'
      'content'
      'history';
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
  }

  .admission-workbench--standalone {
    grid-template-areas:
      'content'
      'history';
  }
}

@media (max-width: 680px) {
  .nutrition-age__row {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }

  .nutrition-age__value {
    text-align: start;
  }

  :deep(.admission-context-field) {
    flex-direction: column;
    align-items: stretch;
    gap: 0;
  }

  :deep(.admission-context-field .el-form-item__label) {
    flex-basis: auto;
    padding-bottom: 5px;
  }

  :deep(.measurement-field),
  :deep(.nutrition-field) {
    flex-direction: column;
    align-items: stretch;
    gap: 0;
  }

  :deep(.measurement-field .el-form-item__label),
  :deep(.nutrition-field .el-form-item__label) {
    flex-basis: auto;
    min-width: 0;
    padding-bottom: 5px;
  }

  .encounter-card :deep(.el-card__body) {
    padding: var(--admission-space);
  }

  .clinical-section--nutrition :deep(.el-col),
  .clinical-section :deep(.el-col) {
    flex: 0 0 100%;
    max-width: 100%;
  }
}
</style>

<style scoped src="@/assets/admission-workspace.css"></style>
