<template>
  <div>
    <div class="page-header">
      <div>
        <h2>{{ fullName }}</h2>
        <div class="muted">
          {{ patient?.tipo_documento_codigo }} {{ patient?.numero_documento }} · HC:
          {{ patient?.historia_clinica || '—' }}
          <el-tag class="estado-tag" :type="patient?.estado ? 'success' : 'info'" size="small">
            {{ patient?.estado ? 'Activo' : 'Inactivo' }}
          </el-tag>
        </div>
      </div>
      <div>
        <el-button
          v-if="can('PACIENTE_DAR_BAJA') && patient?.estado"
          type="danger"
          plain
          @click="confirmDeactivate"
        >
          Dar de baja
        </el-button>
        <el-button @click="router.back()">Volver</el-button>
      </div>
    </div>

    <el-card v-loading="loading">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="Datos" name="datos">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="Nacimiento">{{
              patient?.fecha_nacimiento
            }}</el-descriptions-item>
            <el-descriptions-item label="Sexo">{{
              sexLabel(patient?.sexo_codigo)
            }}</el-descriptions-item>
            <el-descriptions-item label="Edad">{{ ageLabel }}</el-descriptions-item>
            <el-descriptions-item label="Apellido paterno">{{
              patient?.apellido_paterno || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Apellido materno">{{
              patient?.apellido_materno || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Nombres">{{
              patient
                ? [patient.primer_nombre, patient.otros_nombres].filter(Boolean).join(' ')
                : '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Inscripción">{{
              patient?.fecha_inscripcion || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Seguro">{{
              seguroLabel(patient?.seguro_id)
            }}</el-descriptions-item>
            <el-descriptions-item label="Establecimiento">{{
              establishmentLabel(patient?.establecimiento_registro_id)
            }}</el-descriptions-item>
            <el-descriptions-item label="Distrito">{{
              patient?.distrito_residencia || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Localidad">{{
              patient?.localidad || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Dirección">{{
              patient?.direccion || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Teléfono">{{
              patient?.telefono_principal || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Condición">{{
              patient?.condicion || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="Historia familiar">{{
              patient?.historia_familiar || '—'
            }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="Responsables" name="responsables">
          <div class="tab-actions">
            <el-button
              v-if="can('PACIENTE_EDITAR')"
              type="primary"
              size="small"
              @click="responsibleDialog = true"
            >
              Agregar responsable
            </el-button>
          </div>
          <el-table :data="patient?.responsables ?? []" empty-text="Sin responsables">
            <el-table-column prop="nombre_completo" label="Nombre" min-width="180" />
            <el-table-column prop="parentesco" label="Parentesco" width="110" />
            <el-table-column label="Documento" width="160">
              <template #default="{ row }">
                {{
                  row.tipo_documento_codigo
                    ? `${row.tipo_documento_codigo} ${row.numero_documento}`
                    : '—'
                }}
              </template>
            </el-table-column>
            <el-table-column prop="telefono" label="Teléfono" width="130" />
            <el-table-column label="Principal" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.es_principal" type="warning" size="small">Sí</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column label="Activo" width="90">
              <template #default="{ row }">
                <el-tag :type="row.activo ? 'success' : 'info'" size="small">
                  {{ row.activo ? 'Activo' : 'Inactivo' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="can('PACIENTE_EDITAR')" label="Acciones" width="90">
              <template #default="{ row }">
                <el-button link type="primary" @click="editResponsible(row)">Editar</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Riesgos" name="riesgos">
          <div class="tab-actions">
            <el-button
              v-if="can('PACIENTE_EDITAR')"
              type="primary"
              size="small"
              @click="riskDialog = true"
            >
              Agregar riesgo
            </el-button>
          </div>
          <el-table :data="patient?.riesgos ?? []" empty-text="Sin periodos de riesgo">
            <el-table-column label="Grupo" min-width="160">
              <template #default="{ row }">
                {{ row.grupo_riesgo_nombre || row.grupo_riesgo_codigo || row.grupo_riesgo_id }}
              </template>
            </el-table-column>
            <el-table-column prop="fecha_inicio" label="Inicio" width="120" />
            <el-table-column label="Fin" width="120">
              <template #default="{ row }">{{ row.fecha_fin || 'Vigente' }}</template>
            </el-table-column>
            <el-table-column prop="observacion" label="Observación" min-width="160" />
            <el-table-column v-if="can('PACIENTE_EDITAR')" label="Acciones" width="90">
              <template #default="{ row }">
                <el-button link type="primary" @click="editRisk(row)">Editar</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Atenciones" name="atenciones">
          <el-table
            :data="atencionesList"
            v-loading="atencionesLoading"
            empty-text="Sin atenciones"
          >
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="fecha_atencion" label="Fecha" width="170" />
            <el-table-column prop="modalidad_atencion_codigo" label="Modalidad" width="130" />
            <el-table-column prop="grupo_etario_codigo" label="Grupo etario" width="130" />
            <el-table-column label="Grupo de atención" min-width="170">
              <template #default="{ row }">
                {{ careGroupLabel(row.grupo_atencion_codigo) }}
              </template>
            </el-table-column>
            <el-table-column label="Estado" width="110">
              <template #default="{ row }">
                <el-tag :type="row.estado === 'ANULADO' ? 'danger' : 'success'">
                  {{ row.estado }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Acciones" width="110">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  @click="router.push({ name: 'atencion-detalle', params: { id: row.id } })"
                >
                  Ver
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <ResponsibleDialog
      v-model="responsibleDialog"
      :patient-id="patientId"
      :responsible="editingResponsible"
      :tipos-documento="tiposDocumento"
      @saved="reload"
    />
    <RiskDialog
      v-model="riskDialog"
      :patient-id="patientId"
      :riesgo="editingRisk"
      :grupos-riesgo="gruposRiesgo"
      @saved="reload"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import ResponsibleDialog from '@/components/patient/ResponsibleDialog.vue'
import RiskDialog from '@/components/patient/RiskDialog.vue'
import { useAuthStore } from '@/stores/auth'
import {
  catalogos,
  type CodeCatalogItem,
  type EstablishmentCatalogItem,
  type IdCatalogItem,
  type RiskGroupCatalogItem,
} from '@/services/catalogos'
import {
  pacientes,
  type Patient,
  type PatientResponsible,
  type PatientRisk,
} from '@/services/pacientes'
import { atenciones, type Attention } from '@/services/atenciones'
import { careGroupLabel } from '@/utils/careGroup'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const patientId = Number(route.params.id)

const patient = ref<Patient | null>(null)
const loading = ref(false)
const activeTab = ref('datos')

const tiposDocumento = ref<CodeCatalogItem[]>([])
const sexos = ref<CodeCatalogItem[]>([])
const seguros = ref<IdCatalogItem[]>([])
const establecimientos = ref<EstablishmentCatalogItem[]>([])
const gruposRiesgo = ref<RiskGroupCatalogItem[]>([])

const atencionesList = ref<Attention[]>([])
const atencionesLoading = ref(false)

const responsibleDialog = ref(false)
const editingResponsible = ref<PatientResponsible | null>(null)
const riskDialog = ref(false)
const editingRisk = ref<PatientRisk | null>(null)

const fullName = computed(() =>
  patient.value
    ? [
        patient.value.apellido_paterno,
        patient.value.apellido_materno,
        patient.value.primer_nombre,
        patient.value.otros_nombres,
      ]
        .filter(Boolean)
        .join(' ')
    : 'Cargando…',
)

const ageLabel = computed(() => {
  if (!patient.value) return '—'
  const born = new Date(patient.value.fecha_nacimiento)
  const now = new Date()
  let years = now.getFullYear() - born.getFullYear()
  const monthDiff = now.getMonth() - born.getMonth()
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < born.getDate())) years -= 1
  return years >= 0 ? `${years} años` : '—'
})

function can(permission: string): boolean {
  return auth.hasPermission(permission)
}

function sexLabel(codigo: string | null | undefined): string {
  return sexos.value.find((sexo) => sexo.codigo === codigo)?.nombre ?? codigo ?? '—'
}

function seguroLabel(id: number | null | undefined): string {
  return seguros.value.find((seguro) => seguro.id === id)?.nombre ?? (id ? `#${id}` : '—')
}

function establishmentLabel(id: number | null | undefined): string {
  return establecimientos.value.find((est) => est.id === id)?.nombre ?? (id ? `#${id}` : '—')
}

function editResponsible(row: PatientResponsible): void {
  editingResponsible.value = row
  responsibleDialog.value = true
}

function editRisk(row: PatientRisk): void {
  editingRisk.value = row
  riskDialog.value = true
}

async function reload(): Promise<void> {
  patient.value = await pacientes.get(patientId)
  loadAtenciones()
}

async function loadAtenciones(): Promise<void> {
  // El ADMIN no tiene ATENCION_LEER: no se debe llamar a un endpoint que
  // el backend rechazará con 403. La pestaña se muestra igualmente vacía.
  if (!can('ATENCION_LEER')) return
  atencionesLoading.value = true
  try {
    atencionesList.value = await atenciones.listByPatient(patientId)
  } catch {
    atencionesList.value = []
  } finally {
    atencionesLoading.value = false
  }
}

async function confirmDeactivate(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `¿Dar de baja a ${fullName.value}? La baja es lógica y el historial se conserva.`,
      'Dar de baja paciente',
      { type: 'warning', confirmButtonText: 'Dar de baja', cancelButtonText: 'Cancelar' },
    )
  } catch {
    return
  }
  try {
    const result = await pacientes.deactivate(patientId)
    ElMessage.success(result.mensaje)
    patient.value = await pacientes.get(patientId)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'No se pudo dar de baja.')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [
      tipos,
      sexosResult,
      segurosResult,
      establecimientosResult,
      riesgosResult,
      patientResult,
    ] = await Promise.all([
      catalogos.tiposDocumento(),
      catalogos.sexos(),
      catalogos.seguros(),
      catalogos.establecimientos(undefined, 25, 0),
      catalogos.gruposRiesgo(),
      pacientes.get(patientId),
    ])
    tiposDocumento.value = tipos
    sexos.value = sexosResult
    seguros.value = segurosResult
    establecimientos.value = establecimientosResult.items
    gruposRiesgo.value = riesgosResult
    patient.value = patientResult
    loadAtenciones()
  } catch (error) {
    ElMessage.error(
      error instanceof Error ? error.message : 'No se pudo cargar la ficha del paciente.',
    )
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}

.page-header h2 {
  margin: 0 0 4px;
}

.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.estado-tag {
  margin-left: 8px;
}

.tab-actions {
  margin-bottom: 12px;
  text-align: right;
}
</style>
