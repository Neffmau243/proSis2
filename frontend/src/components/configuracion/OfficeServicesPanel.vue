<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { CodeCatalogItem } from '@/services/catalogos'
import {
  consultorios,
  type OfficeResponse,
  type OfficeServiceAdd,
  type OfficeAssignmentResponse,
} from '@/services/consultorios'
import AddOfficeServiceForm from './AddOfficeServiceForm.vue'
import OfficeServiceEditor from './OfficeServiceEditor.vue'

const props = defineProps<{ office: OfficeResponse }>()
const emit = defineEmits<{
  updated: [office: OfficeResponse]
  assignments: [service: CodeCatalogItem]
}>()
const assignments = shallowRef<OfficeAssignmentResponse[]>([])
const assignmentsError = shallowRef(false)
let assignmentsRequest = 0
async function loadAssignments() {
  const current = ++assignmentsRequest
  assignmentsError.value = false
  try {
    const result = await consultorios.listAssignments(props.office.id, { includeInherited: true })
    if (current === assignmentsRequest) assignments.value = result
  } catch {
    if (current === assignmentsRequest) assignmentsError.value = true
  }
}
watch(() => props.office, loadAssignments, { immediate: true })
const professionalCounts = computed(() => {
  const today = new Date().toLocaleDateString('sv-SE')
  return Object.fromEntries(
    (props.office.servicios_habilitados || []).map((service) => [
      service.codigo,
      new Set(
        assignments.value
          .filter(
            (item) =>
              item.profesional_activo !== false &&
              item.fecha_inicio <= today &&
              (!item.fecha_fin || item.fecha_fin >= today) &&
              (item.servicios_codigos == null || item.servicios_codigos.includes(service.codigo)),
          )
          .map((item) => item.profesional_id),
      ).size,
    ]),
  )
})
const adding = shallowRef(false)
const options = shallowRef<CodeCatalogItem[]>([])
const loading = shallowRef(false)
const saving = shallowRef(false)
const error = shallowRef<string | null>(null)
const canManage = computed(() => props.office.activo && props.office.activo_efectivo !== false)
const available = computed(() => {
  const enabled = new Set(props.office.servicios_habilitados?.map((item) => item.codigo))
  return options.value.filter((item) => item.activo && !enabled.has(item.codigo))
})
let request = 0
watch(
  () => props.office.id,
  () => {
    request++
    adding.value = false
    error.value = null
    options.value = []
  },
)

async function loadCatalog(): Promise<void> {
  const current = ++request
  const officeId = props.office.id
  loading.value = true
  error.value = null
  try {
    const items = await consultorios.listServices(officeId)
    if (current === request) options.value = items
  } catch (cause) {
    if (current === request)
      error.value = cause instanceof Error ? cause.message : 'No se pudo cargar el catálogo.'
  } finally {
    if (current === request) loading.value = false
  }
}

function openAdd(): void {
  if (props.office.consultorio_padre_id !== null || !canManage.value) return
  adding.value = true
  void loadCatalog()
}

async function add(payload: OfficeServiceAdd): Promise<void> {
  if (saving.value || loading.value || !canManage.value) return
  const officeId = props.office.id
  saving.value = true
  error.value = null
  try {
    const result = await consultorios.addService(officeId, payload)
    emit('updated', result.consultorio)
    if (props.office.id === officeId) adding.value = false
    ElMessage.success('Servicio agregado al consultorio.')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'No se pudo agregar el servicio.'
  } finally {
    saving.value = false
  }
}

async function remove(service: CodeCatalogItem): Promise<void> {
  if (saving.value || !canManage.value) return
  const office = props.office
  try {
    await ElMessageBox.confirm(
      `Se quitará «${service.nombre}» de ${office.nombre}. El servicio seguirá en el catálogo y se conservarán las atenciones anteriores.`,
      'Quitar servicio del consultorio',
      { confirmButtonText: 'Quitar servicio', cancelButtonText: 'Cancelar', type: 'warning' },
    )
  } catch {
    return
  }
  if (saving.value || props.office.id !== office.id) return
  saving.value = true
  error.value = null
  try {
    const updated = await consultorios.update(office.id, {
      servicios_codigos: (office.servicios_habilitados || [])
        .filter((item) => item.codigo !== service.codigo)
        .map((item) => item.codigo),
    })
    emit('updated', updated)
    ElMessage.success('Servicio quitado del consultorio.')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'No se pudo quitar el servicio.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section
    class="office-services-panel"
    aria-labelledby="office-services-heading"
    :aria-busy="saving"
  >
    <div class="services-heading">
      <div>
        <h3 id="office-services-heading">Servicios / especialidades</h3>
        <p>Gestiona los servicios que se atienden en este consultorio.</p>
      </div>
      <el-button
        v-if="!adding && office.consultorio_padre_id === null"
        type="primary"
        :disabled="!canManage || saving"
        @click="openAdd"
      >
        Agregar servicio
      </el-button>
    </div>
    <p v-if="office.consultorio_padre_id !== null" class="services-empty">
      Usa «Editar consultorio» para seleccionar los servicios heredados. Los nuevos servicios se
      agregan desde el consultorio principal.
    </p>
    <p v-if="assignmentsError" class="services-empty" role="status">
      No se pudo cargar la cantidad de profesionales.
      <el-button link type="primary" @click="loadAssignments">Reintentar</el-button>
    </p>
    <el-alert v-if="error && !adding" :title="error" type="error" :closable="false" role="alert" />
    <AddOfficeServiceForm
      v-if="adding"
      :options="available"
      :loading="loading"
      :saving="saving"
      :error="error"
      @add="add"
      @cancel="adding = false"
      @retry="loadCatalog"
    />
    <ul v-if="office.servicios_habilitados?.length" class="services-list">
      <li v-for="service in office.servicios_habilitados" :key="service.codigo" class="service-row">
        <div>
          <strong>{{ service.nombre }}</strong>
          <span class="service-code"
            >{{ service.codigo }} · {{ service.activo ? 'Activo' : 'Inactivo' }}</span
          >
          <span v-if="!assignmentsError" class="service-code"
            >{{ professionalCounts[service.codigo] || 0 }}
            {{
              professionalCounts[service.codigo] === 1
                ? 'profesional vigente'
                : 'profesionales vigentes'
            }}</span
          >
        </div>
        <div class="service-actions">
          <OfficeServiceEditor
            :office-id="office.id"
            :service="service"
            :disabled="!canManage || saving"
            @updated="emit('updated', $event)"
          />
          <el-button
            type="primary"
            :aria-label="`Ver profesionales de ${service.nombre}`"
            @click="emit('assignments', service)"
          >
            Profesionales
          </el-button>
          <el-button
            :disabled="!canManage || saving"
            :aria-label="`Quitar ${service.nombre}`"
            @click="remove(service)"
          >
            Quitar
          </el-button>
        </div>
      </li>
    </ul>
    <p v-else class="services-empty">Este consultorio no tiene servicios habilitados.</p>
  </section>
</template>

<style scoped>
.services-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
}
.services-heading h3 {
  margin: 0 0 8px;
  font-size: 18px;
}
.services-heading p,
.services-empty {
  margin: 0;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.services-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.service-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-block: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.service-row > div {
  min-width: 0;
  overflow-wrap: anywhere;
}
.service-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.service-actions :deep(.el-button) {
  margin: 0;
}
@media (max-width: 600px) {
  .service-row {
    align-items: stretch;
    flex-direction: column;
  }
}
.service-code {
  display: block;
  margin-top: 6px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
@media (max-width: 600px) {
  .service-row :deep(.el-button),
  .services-heading :deep(.el-button),
  .office-services-panel :deep(.add-service .el-button) {
    min-height: 44px;
  }
}
</style>
