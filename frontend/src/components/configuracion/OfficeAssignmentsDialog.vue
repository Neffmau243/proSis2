<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  consultorios,
  type OfficeAssignmentResponse,
  type OfficeAssignmentCreatePayload,
} from '@/services/consultorios'
import { useAuthStore } from '@/stores/auth'
import { useOfficeAssignments } from '@/composables/useOfficeAssignments'
import OfficeAssignmentDialog from './OfficeAssignmentDialog.vue'
import OfficeAssignmentActions from './OfficeAssignmentActions.vue'
const props = defineProps<{ specialtyNames: Record<string, string> }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const router = useRouter()
const canManageStaffCatalogs = computed(() => auth.hasPermission('PROFESIONAL_GESTIONAR'))
const {
  professionalOptions,
  professionalsLoading,
  professionalSearchError,
  selectedService,
  profesionalNombre,
  searchProfesionales,
  today,
  assignmentsVisible,
  officeTarget,
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
} = useOfficeAssignments(
  canManageStaffCatalogs,
  computed(() => props.specialtyNames),
)
defineExpose({
  open: openAssignments,
  close: () => {
    assignmentsVisible.value = false
  },
})
async function saveAssignment(payload: Parameters<typeof submitAssignment>[0]) {
  await submitAssignment(payload)
  emit('changed')
}
async function closeAssignment() {
  await submitClose()
  emit('changed')
}
const editTarget = shallowRef<OfficeAssignmentResponse | null>(null)
const editVisible = shallowRef(false)
const editSaving = shallowRef(false)
const editError = shallowRef<string | null>(null)
function closeForms() {
  assignFormVisible.value = false
  editVisible.value = false
}
function scopeLabel(row: OfficeAssignmentResponse): string {
  if (row.servicios_codigos == null) return 'Todos los servicios del consultorio'
  return row.servicios_codigos
    .map(
      (code) =>
        officeTarget.value?.servicios_habilitados?.find((service) => service.codigo === code)
          ?.nombre ||
        props.specialtyNames[code] ||
        code,
    )
    .join(', ')
}
function assignmentStatus(row: OfficeAssignmentResponse): string {
  if (row.profesional_activo === false) return 'Profesional inactivo'
  return row.fecha_inicio > today
    ? 'Programada'
    : row.fecha_fin && row.fecha_fin < today
      ? 'Finalizada'
      : 'Vigente'
}
function openEdit(row: OfficeAssignmentResponse) {
  editTarget.value = row
  editError.value = null
  editVisible.value = true
}
async function saveEdit(payload: OfficeAssignmentCreatePayload) {
  if (!editTarget.value || editSaving.value) return
  editSaving.value = true
  editError.value = null
  try {
    await consultorios.updateAssignment(editTarget.value, {
      fecha_inicio: payload.fecha_inicio,
      fecha_fin: payload.fecha_fin || null,
      es_responsable: payload.es_responsable,
      servicios_codigos: payload.servicios_codigos ?? null,
    })
    editVisible.value = false
    ElMessage.success('Asignación actualizada.')
    await loadAssignments()
    emit('changed')
  } catch (cause) {
    editError.value =
      cause instanceof Error ? cause.message : 'No se pudo actualizar la asignación.'
  } finally {
    editSaving.value = false
  }
}
function viewOrigin(row: OfficeAssignmentResponse) {
  assignmentsVisible.value = false
  void router.push({ name: 'consultorio-servicios', params: { officeId: row.consultorio_id } })
}
</script>
<template>
  <!-- Asignaciones del consultorio -->
  <el-dialog
    v-model="assignmentsVisible"
    class="care-config"
    modal-class="care-config-overlay"
    :title="assignmentsTitle"
    width="min(1080px, 94vw)"
    top="6vh"
    :close-on-click-modal="!assignFormVisible && !editVisible"
    :close-on-press-escape="!assignFormVisible && !editVisible"
    :show-close="!assignFormVisible && !editVisible"
    @closed="closeForms"
  >
    <el-alert
      v-if="assignmentsError"
      :title="assignmentsError"
      type="error"
      :closable="false"
      class="form-alert"
    />
    <p class="dialog-hint">
      {{
        selectedService
          ? `Profesionales que atienden ${selectedService.nombre}.`
          : 'Profesionales del consultorio y sus servicios.'
      }}
      Las asignaciones heredadas se gestionan desde su consultorio de origen.
    </p>

    <div class="toolbar">
      <el-input
        v-model="assignmentSearch"
        placeholder="Buscar profesional asignado"
        aria-label="Buscar profesional asignado"
        clearable
        class="assignment-search"
      />
      <div class="assignment-actions">
        <el-button
          type="primary"
          :disabled="!officeTarget?.activo || officeTarget?.activo_efectivo === false"
          @click="openAssignForm"
          >Asignar profesional</el-button
        >
        <el-button :loading="assignmentsLoading" @click="loadAssignments">Recargar</el-button>
      </div>
    </div>

    <el-table
      class="assignment-table"
      v-loading="assignmentsLoading"
      :data="filteredAssignments"
      :empty-text="
        assignmentSearch ? 'Sin coincidencias para esta búsqueda' : 'Sin asignaciones registradas'
      "
      max-height="45vh"
    >
      <el-table-column label="Profesional" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ profesionalNombre(row.profesional_id) }}</template>
      </el-table-column>
      <el-table-column prop="fecha_inicio" label="Inicio" width="120" />
      <el-table-column label="Fin" width="130">
        <template #default="{ row }">
          <span>{{ row.fecha_fin || 'Sin fecha de fin' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Servicios y origen" min-width="220">
        <template #default="{ row }">
          <span>{{ scopeLabel(row) }}</span>
          <p class="assignment-origin">
            {{
              row.heredada
                ? `Heredada de ${row.consultorio_nombre || 'consultorio padre'}`
                : 'Asignación directa'
            }}
            · {{ assignmentStatus(row) }}
          </p>
        </template>
      </el-table-column>
      <el-table-column label="Responsable" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.es_responsable" type="primary" size="small">Sí</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="Acciones" width="150">
        <template #default="{ row }">
          <OfficeAssignmentActions
            :assignment="row"
            :professional-name="profesionalNombre(row.profesional_id)"
            :today="today"
            :inactive="!officeTarget?.activo"
            @origin="viewOrigin"
            @edit="openEdit"
            @close="openClose"
          />
        </template>
      </el-table-column>
    </el-table>
    <div v-loading="assignmentsLoading" class="assignment-mobile-list">
      <p v-if="!filteredAssignments.length" role="status">
        {{
          assignmentSearch ? 'Sin coincidencias para esta búsqueda' : 'Sin asignaciones registradas'
        }}
      </p>
      <article
        v-for="row in filteredAssignments"
        :key="`${row.consultorio_id}-${row.profesional_id}-${row.fecha_inicio}`"
        class="assignment-mobile-row"
      >
        <h3 class="assignment-name">{{ profesionalNombre(row.profesional_id) }}</h3>
        <p class="assignment-origin">
          {{ assignmentStatus(row) }}{{ row.es_responsable ? ' · Responsable' : '' }}
        </p>
        <p class="assignment-dates">
          {{ row.fecha_inicio }} → {{ row.fecha_fin || 'Sin fecha de fin' }}
        </p>
        <p class="assignment-services">{{ scopeLabel(row) }}</p>
        <p class="assignment-origin">
          {{
            row.heredada
              ? `Heredada de ${row.consultorio_nombre || 'consultorio padre'}`
              : 'Asignación directa'
          }}
        </p>
        <OfficeAssignmentActions
          :assignment="row"
          :professional-name="profesionalNombre(row.profesional_id)"
          :today="today"
          :inactive="!officeTarget?.activo"
          @origin="viewOrigin"
          @edit="openEdit"
          @close="openClose"
        />
      </article>
    </div>

    <OfficeAssignmentDialog
      v-model="assignFormVisible"
      :office-name="officeTarget?.nombre || ''"
      :area-name="
        officeTarget?.area_nombre || specialtyNames[officeTarget?.area_codigo || ''] || ''
      "
      :requirement-name="assignmentRequirementName"
      :link-area="canManageStaffCatalogs"
      :professionals="professionalOptions"
      :loading="professionalsLoading"
      :saving="savingAssignment"
      :error="assignError || professionalSearchError"
      :services="officeTarget?.servicios_habilitados || []"
      :initial-service="selectedService?.codigo"
      @search="searchProfesionales"
      @submit="saveAssignment"
    />
  </el-dialog>

  <OfficeAssignmentDialog
    v-model="editVisible"
    :office-name="officeTarget?.nombre || ''"
    :editing-assignment="editTarget"
    :professionals="[]"
    :loading="false"
    :saving="editSaving"
    :error="editError"
    :services="officeTarget?.servicios_habilitados || []"
    @submit="saveEdit"
  />

  <!-- Cierre de asignación -->
  <el-dialog
    v-model="closeVisible"
    class="care-config"
    modal-class="care-config-overlay"
    title="Cerrar asignación"
    width="min(460px, 94vw)"
    :close-on-click-modal="!savingClose"
    :close-on-press-escape="!savingClose"
    :show-close="!savingClose"
  >
    <el-alert
      v-if="closeError"
      :title="closeError"
      type="error"
      :closable="false"
      class="form-alert"
    />
    <p class="dialog-hint">
      Se cierra la asignación de
      <strong>{{ closeTarget ? profesionalNombre(closeTarget.profesional_id) : '' }}</strong>
      (inicio {{ closeTarget?.fecha_inicio }}). El cierre no puede ampliar una vigencia ya definida.
    </p>
    <el-form label-width="130px" :disabled="savingClose">
      <el-form-item label="Fecha de fin" required>
        <el-date-picker
          v-model="closeForm.fecha_fin"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="savingClose" @click="closeVisible = false">Cancelar</el-button>
      <el-button type="primary" :loading="savingClose" @click="closeAssignment">
        Cerrar asignación
      </el-button>
    </template>
  </el-dialog>
</template>
<style scoped>
.toolbar,
.assignment-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-block: 16px;
}
.toolbar {
  justify-content: space-between;
}
.assignment-search {
  max-width: 320px;
}
.dialog-hint {
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.form-alert {
  margin-bottom: 16px;
}
.assignment-origin {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
.assignment-mobile-list {
  display: none;
}
.assignment-mobile-row {
  padding-block: 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  overflow-wrap: anywhere;
}
.assignment-name {
  margin: 0;
  font-size: 16px;
  line-height: 1.5;
}
.assignment-dates,
.assignment-services {
  margin: 8px 0;
  line-height: 1.6;
}
@media (max-width: 700px) {
  .assignment-table {
    display: none;
  }
  .assignment-mobile-list {
    display: block;
    max-height: 48dvh;
    overflow-y: auto;
  }
}
@media (max-width: 600px) {
  .assignment-search {
    max-width: none;
  }
}
</style>
