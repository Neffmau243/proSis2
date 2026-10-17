<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { DocumentChecked, Close } from '@element-plus/icons-vue'

import PatientRegistrationBaseSection from '@/components/patients/PatientRegistrationBaseSection.vue'
import PatientRegistrationFamilySections from '@/components/patients/PatientRegistrationFamilySections.vue'
import type {
  PatientRegistrationDraft,
  PatientRegistrationPatch,
} from '@/components/patients/patientRegistration.types'
import {
  catalogos,
  type CodeCatalogItem,
  type EstablishmentCatalogItem,
  type FamilyHistoryCatalogItem,
  type IdCatalogItem,
  type RiskGroupCatalogItem,
  type UbigeoCatalogItem,
} from '@/services/catalogos'
import { pacientes } from '@/services/pacientes'
import { emptyPatientSis, patientSisErrors } from '@/utils/patientSis'
import { documentProblem } from '@/utils/patientDocument'
import { clearSisAffiliation, isSisInsurance } from '@/utils/patientInsurance'
import { familyHistoryProblem } from '@/utils/familyHistory'
import { useDistrictLocalities } from '@/composables/useDistrictLocalities'
import { useRemoteCatalog } from '@/composables/useRemoteCatalog'
import { allCatalogPages } from '@/services/catalogPages'
import { useSisAffiliationDefaults } from '@/composables/useSisAffiliationDefaults'

const route = useRoute()
const router = useRouter()

// La misma vista sirve al botón destacado "Admisión" y a "Nuevo paciente".
// El título ya lo muestra la barra superior del layout: aquí no se repite.
const esAdmision = computed(() => route.name === 'admision')

/** Fecha de hoy en hora local (YYYY-MM-DD); el backend la espera sin zona horaria. */
function todayIso(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

// Un paciente que se registra hoy se inscribe hoy: la fecha arranca en hoy y se
// puede corregir cuando se digita a alguien que ya estaba inscrito.

const formRef = ref<FormInstance>()
const saving = ref(false)
const errorMessage = ref<string | null>(null)

const tiposDocumento = ref<CodeCatalogItem[]>([])
const sexos = ref<CodeCatalogItem[]>([])
const seguros = ref<IdCatalogItem[]>([])
const gruposRiesgo = ref<RiskGroupCatalogItem[]>([])
const siteCatalog = useRemoteCatalog<EstablishmentCatalogItem>({
  fetch: async (query) => ({
    items: await allCatalogPages((offset) => catalogos.establecimientos(query, 100, offset)),
  }),
  key: (item) => item.id,
})
const {
  items: establecimientos,
  loading: establecimientosLoading,
  error: establecimientosError,
} = siteCatalog
const districtCatalog = useRemoteCatalog<UbigeoCatalogItem>({
  fetch: async (query) => ({
    items: await allCatalogPages((offset) => catalogos.ubigeos(query, 100, offset)),
  }),
  key: (item) => item.codigo,
})
const { items: ubigeos, loading: ubigeosLoading, error: ubigeosError } = districtCatalog
const {
  items: localidades,
  loading: localidadesLoading,
  error: localidadesError,
  load: loadDistrictLocalities,
} = useDistrictLocalities()
const historiasFamiliares = ref<FamilyHistoryCatalogItem[]>([])
const historiasFamiliaresLoading = ref(false)

const form = reactive<PatientRegistrationDraft>({
  sufijo_documento: '',
  ...emptyPatientSis(),
  tipo_documento_codigo: '',
  numero_documento: '',
  historia_clinica: '',
  historia_familiar: '',
  apellido_paterno: '',
  apellido_materno: '',
  primer_nombre: '',
  otros_nombres: '',
  fecha_nacimiento: '',
  sexo_codigo: null,
  fecha_inscripcion: todayIso(),
  seguro_id: null,
  establecimiento_registro_id: null,
  ubigeo_residencia_codigo: null,
  localidad: '',
  localidad_id: null,
  direccion: '',
  telefono_principal: '',
  condicion: '',
  responsables: [],
  riesgos: [],
})

const rules: FormRules = {
  tipo_documento_codigo: [
    { required: true, message: 'Seleccione el tipo de documento.', trigger: 'change' },
  ],
  numero_documento: [
    { required: true, message: 'Ingrese el número de documento.', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        const problem = documentProblem(form.tipo_documento_codigo, value)
        callback(problem ? new Error(problem) : undefined)
      },
      trigger: ['blur', 'change'],
    },
  ],
  primer_nombre: [{ required: true, message: 'Ingrese al menos un nombre.', trigger: 'blur' }],
  fecha_nacimiento: [
    { required: true, message: 'Indique la fecha de nacimiento.', trigger: 'change' },
  ],
  fecha_inscripcion: [
    {
      validator: (_rule, value: string, callback) => {
        if (!value) return callback()
        if (value > todayIso()) {
          return callback(new Error('La fecha de inscripción no puede estar en el futuro.'))
        }
        if (form.fecha_nacimiento && form.fecha_nacimiento > value) {
          return callback(new Error('No puede ser anterior a la fecha de nacimiento.'))
        }
        callback()
      },
      trigger: 'change',
    },
  ],
  historia_familiar: [
    {
      validator: (_rule, value: string, callback) => {
        const problem = familyHistoryProblem(value)
        callback(problem ? new Error(problem) : undefined)
      },
      trigger: ['blur', 'change'],
    },
  ],
}

const sisDefaults = useSisAffiliationDefaults({
  draft: form,
  insurance: () => seguros.value.find((item) => item.id === form.seguro_id),
  establishment: () =>
    establecimientos.value.find((item) => item.id === form.establecimiento_registro_id),
  initialize: true,
})

function updatePatientForm(changes: PatientRegistrationPatch): void {
  sisDefaults.markManual(changes)
  Object.assign(form, changes)
  if (
    'seguro_id' in changes &&
    !isSisInsurance(seguros.value.find((item) => item.id === form.seguro_id))
  ) {
    clearSisAffiliation(form)
  }
  if ('tipo_documento_codigo' in changes && form.numero_documento) {
    void formRef.value?.validateField('numero_documento').catch(() => undefined)
  }
}

async function searchEstablecimientos(query: string): Promise<void> {
  await siteCatalog.load(
    query || undefined,
    establecimientos.value.filter((item) => item.id === form.establecimiento_registro_id),
  )
}

async function searchUbigeos(query: string): Promise<void> {
  await districtCatalog.load(
    query || undefined,
    ubigeos.value.filter((item) => item.codigo === form.ubigeo_residencia_codigo),
  )
}

// La localidad pertenece al distrito: al cambiarlo se limpia la selección y se
// recarga el catálogo SIS.
async function loadLocalidades(ubigeoCodigo: string | null): Promise<void> {
  form.localidad_id = null
  form.localidad = ''
  await loadDistrictLocalities(ubigeoCodigo)
}

watch(
  () => form.ubigeo_residencia_codigo,
  (code) => {
    void loadLocalidades(code)
  },
)

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const sisErrors = Object.values(patientSisErrors(form))
  if (sisErrors.length) {
    errorMessage.value = sisErrors.join(' ')
    return
  }

  saving.value = true
  errorMessage.value = null
  try {
    const created = await pacientes.create({
      tipo_documento_codigo: form.tipo_documento_codigo,
      numero_documento: form.numero_documento,
      sufijo_documento: form.sufijo_documento?.trim() || null,
      historia_clinica: form.historia_clinica || null,
      historia_familiar: form.historia_familiar || null,
      fecha_nacimiento: form.fecha_nacimiento,
      fecha_inscripcion: form.fecha_inscripcion || null,
      apellido_paterno: form.apellido_paterno || null,
      apellido_materno: form.apellido_materno || null,
      primer_nombre: form.primer_nombre || null,
      otros_nombres: form.otros_nombres || null,
      sexo_codigo: form.sexo_codigo,
      ubigeo_residencia_codigo: form.ubigeo_residencia_codigo,
      localidad: form.localidad || null,
      localidad_id: form.localidad_id,
      direccion: form.direccion || null,
      establecimiento_registro_id: form.establecimiento_registro_id,
      seguro_id: form.seguro_id,
      sis_diresa: form.sis_diresa,
      sis_tipo: form.sis_tipo,
      sis_numero: form.sis_numero,
      sis_secuencia: form.sis_secuencia,
      etnia_codigo: form.etnia_codigo,
      telefono_principal: form.telefono_principal || null,
      condicion: form.condicion || null,
      responsables: form.responsables.map((responsable) => ({
        parentesco: responsable.parentesco,
        nombre_completo: responsable.nombre_completo,
        tipo_documento_codigo: responsable.tipo_documento_codigo,
        numero_documento: responsable.numero_documento,
        telefono: responsable.telefono,
        es_principal: responsable.es_principal,
        activo: true,
      })),
      riesgos: form.riesgos.map((riesgo) => ({
        grupo_riesgo_id: riesgo.grupo_riesgo_id!,
        fecha_inicio: riesgo.fecha_inicio,
        fecha_fin: riesgo.fecha_fin,
        observacion: riesgo.observacion || null,
      })),
    })
    router.push({ name: 'paciente-detalle', params: { id: created.id } })
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo registrar el paciente.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  void searchUbigeos('')
  void searchEstablecimientos('')
  historiasFamiliaresLoading.value = true
  try {
    const [tipos, sexosResult, segurosResult, riesgosResult, historiasResult] = await Promise.all([
      catalogos.tiposDocumento(),
      catalogos.sexos(),
      catalogos.seguros(),
      catalogos.gruposRiesgo(),
      catalogos.historiasFamiliares(undefined, 50, 0),
    ])
    tiposDocumento.value = tipos
    sexos.value = sexosResult
    seguros.value = segurosResult
    gruposRiesgo.value = riesgosResult
    historiasFamiliares.value = historiasResult.items
  } finally {
    historiasFamiliaresLoading.value = false
  }
})
</script>

<template>
  <div class="patient-registration">
    <el-alert
      v-if="esAdmision"
      type="info"
      :closable="false"
      class="form-alert"
      title="Admisión: registre al paciente y su inscripción en el establecimiento."
    />

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <el-card class="patient-registration__card" shadow="never">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="patient-registration__layout">
          <PatientRegistrationBaseSection
            :form="form"
            :tipos-documento="tiposDocumento"
            :sexos="sexos"
            :seguros="seguros"
            :establecimientos="establecimientos"
            :establecimientos-loading="establecimientosLoading"
            :establecimientos-error="establecimientosError"
            :ubigeos="ubigeos"
            :ubigeos-loading="ubigeosLoading"
            :ubigeos-error="ubigeosError"
            :localidades="localidades"
            :localidades-loading="localidadesLoading"
            :localidades-error="localidadesError"
            :historias-familiares="historiasFamiliares"
            :historias-familiares-loading="historiasFamiliaresLoading"
            @update="updatePatientForm"
            @search-establecimientos="searchEstablecimientos"
            @search-ubigeos="searchUbigeos"
          />

          <div class="patient-registration__sidebar">
            <PatientRegistrationFamilySections
              v-model:responsables="form.responsables"
              v-model:riesgos="form.riesgos"
              v-model:telefono-principal="form.telefono_principal"
              :grupos-riesgo="gruposRiesgo"
            />

            <footer class="form-actions">
              <el-form-item
                class="form-actions__date"
                label="Fecha de inscripción"
                prop="fecha_inscripcion"
              >
                <el-date-picker
                  v-model="form.fecha_inscripcion"
                  type="date"
                  value-format="YYYY-MM-DD"
                  :clearable="false"
                  :disabled-date="(date: Date) => date.getTime() > Date.now()"
                />
              </el-form-item>
              <div class="form-actions__buttons">
                <el-button type="primary" :icon="DocumentChecked" :loading="saving" @click="submit">
                  Registrar paciente
                </el-button>
                <el-button :icon="Close" @click="router.back()">Salir</el-button>
              </div>
            </footer>
          </div>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.patient-registration {
  min-width: 0;
  max-width: 1040px;
  container-type: inline-size;
  --registration-panel: #e8eff7;
  --registration-heading: #d4e1ef;
  --registration-border: #b9cbdf;
  --registration-ink: #304f6d;
  --registration-control-size: 24px;
  --el-component-size: var(--registration-control-size);
}

.form-alert {
  margin-bottom: 10px;
}

.patient-registration__card {
  min-width: 0;
  border: 0;
  background: transparent;
}

.patient-registration__card :deep(.el-card__body) {
  padding: 0;
}

.patient-registration__layout {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(280px, 2fr);
  align-items: stretch;
  gap: 8px;
}

.patient-registration__sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.patient-registration__sidebar :deep(.family-sections) {
  flex: 1;
  align-content: stretch;
}

.form-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  margin-top: auto;
  border: 1px solid var(--registration-border);
  border-radius: 4px;
  background: var(--registration-panel);
}

/* La fecha de inscripción es el único dato de fecha del alta y vive junto a los
   botones: etiqueta arriba y el error en todo el ancho del pie. */
.form-actions__date {
  margin: 0;
}

.form-actions__date :deep(.el-form-item__label) {
  display: block;
  height: auto;
  margin: 0 0 2px;
  padding: 0;
  color: var(--registration-ink);
  font-size: 12px;
  line-height: 1.2;
}

.form-actions__date :deep(.el-form-item__content) {
  min-width: 0;
  margin-left: 0 !important;
}

.form-actions__date :deep(.el-form-item__error) {
  position: static;
  padding-top: 2px;
}

.form-actions__date :deep(.el-date-editor) {
  width: 100%;
}

.form-actions__buttons {
  display: flex;
  gap: 8px;
}

.form-actions__buttons :deep(.el-button) {
  min-height: 28px;
  margin: 0;
  padding-inline: 8px;
  flex: 1 1 auto;
  font-size: 12px;
}

@container (max-width: 720px) {
  .patient-registration__layout {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .patient-registration {
    --registration-control-size: 36px;
  }
  .patient-registration :deep(.el-input__inner),
  .patient-registration :deep(.el-select__input) {
    font-size: 16px;
  }
  .form-actions__buttons :deep(.el-button) {
    min-height: 44px;
  }
}
@media (pointer: coarse) {
  .patient-registration {
    --registration-control-size: 36px;
  }
  .form-actions__buttons :deep(.el-button) {
    min-height: 44px;
  }
}
</style>
