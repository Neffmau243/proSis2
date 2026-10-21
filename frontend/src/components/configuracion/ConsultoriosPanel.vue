<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  catalogos,
  type EstablishmentCatalogItem,
  type ProfessionalCatalogItem,
  type SpecialtyCatalogItem,
} from '@/services/catalogos'
import {
  consultorios,
  type OfficeAssignmentResponse,
  type OfficeResponse,
  type OfficeAssignmentCreatePayload,
} from '@/services/consultorios'

import OfficesTable from './OfficesTable.vue'
import OfficeFormDialog from './OfficeFormDialog.vue'
import OfficeAssignmentDialog from './OfficeAssignmentDialog.vue'
import StaffCatalogsPanel from './StaffCatalogsPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { descendantIds } from '@/utils/officeHierarchy'
import type { OfficeForm } from './officeForm'
import { isStaffSpecialty } from '@/utils/staffSpecialties'

const router = useRouter()
const auth = useAuthStore()
const activeTab = shallowRef('consultorios')
const canManageStaffCatalogs = computed(() => auth.hasPermission('PROFESIONAL_GESTIONAR'))

// --- Catálogos de apoyo (nombres y selects) ---
const establishments = ref<EstablishmentCatalogItem[]>([])
const establishmentsLoading = ref(false)
const especialidades = ref<SpecialtyCatalogItem[]>([])
const parentOptions = ref<OfficeResponse[]>([])
const professionalOptions = ref<ProfessionalCatalogItem[]>([])
const professionalsLoading = ref(false)
const professionalSearchError = ref<string | null>(null)
/** Nombres conocidos de profesionales, para resolver las asignaciones listadas. */
const professionalDirectory = ref<Record<number, string>>({})

function mergeEstablishments(items: EstablishmentCatalogItem[]): void {
  const known = new Map(establishments.value.map((item) => [item.id, item]))
  for (const item of items) known.set(item.id, item)
  establishments.value = [...known.values()]
}

async function searchEstablishments(query: string): Promise<void> {
  establishmentsLoading.value = true
  try {
    const page = await catalogos.establecimientos(query || undefined, 100, 0)
    mergeEstablishments(page.items)
  } catch {
    // El catálogo solo enriquece los selects; la vista sigue siendo útil sin él.
  } finally {
    establishmentsLoading.value = false
  }
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

const establishmentNames = computed(() =>
  Object.fromEntries(establishments.value.map((item) => [item.id, item.nombre])),
)
const specialtyNames = computed(() =>
  Object.fromEntries(especialidades.value.map((item) => [item.codigo, item.nombre])),
)
const areaOptions = computed(() =>
  especialidades.value.filter(
    (item) => item.es_area || item.codigo === form.area_codigo || item.es_area === undefined,
  ),
)
const qualificationOptions = computed(() =>
  especialidades.value.filter(
    (item) => (!item.es_area && isStaffSpecialty(item)) || item.codigo === form.especialidad_codigo,
  ),
)
const availableParents = computed(() => {
  const excluded =
    editingId.value === null
      ? new Set<number>()
      : descendantIds(parentOptions.value, editingId.value)
  return parentOptions.value.filter(
    (item) =>
      !excluded.has(item.id) &&
      item.activo &&
      item.activo_efectivo !== false &&
      (!form.area_codigo || (item.area_codigo || item.especialidad_codigo) === form.area_codigo),
  )
})
const availableServices = computed(() => {
  const parent = parentOptions.value.find((item) => item.id === form.consultorio_padre_id)
  if (parent?.servicios_habilitados) return parent.servicios_habilitados
  return especialidades.value.filter(
    (item) =>
      item.area_codigos?.includes(form.area_codigo || '') || item.codigo === form.area_codigo,
  )
})
function changeForm(changes: Partial<OfficeForm>): void {
  Object.assign(form, changes)
}

function profesionalNombre(id: number): string {
  return professionalDirectory.value[id] ?? `Profesional #${id}`
}

// --- Lista de consultorios ---
const rows = ref<OfficeResponse[]>([])
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const incluirInactivos = ref(false)
const filtroEstablecimiento = ref<number | null>(null)

let listRequest = 0
async function load(): Promise<void> {
  const request = ++listRequest
  loading.value = true
  errorMessage.value = null
  try {
    const items = await consultorios.list({
      establecimientoId: filtroEstablecimiento.value ?? undefined,
      incluirInactivos: incluirInactivos.value,
    })
    if (request === listRequest) rows.value = items
  } catch (error) {
    if (request === listRequest)
      errorMessage.value =
        error instanceof Error ? error.message : 'No se pudo cargar la lista de consultorios.'
  } finally {
    if (request === listRequest) loading.value = false
  }
}

watch([incluirInactivos, filtroEstablecimiento], load)

// --- Alta / edición ---
const formRef = ref<InstanceType<typeof OfficeFormDialog>>()
const formVisible = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const formError = ref<string | null>(null)
const form = reactive<OfficeForm>({
  establecimiento_id: null as number | null,
  codigo: '',
  nombre: '',
  especialidad_codigo: null as string | null,
  area_codigo: null,
  servicios_codigos: null,
  consultorio_padre_id: null as number | null,
})

const formTitle = computed(() =>
  editingId.value === null ? 'Nuevo consultorio' : 'Editar consultorio',
)

let parentRequest = 0
async function loadParentOptions(): Promise<void> {
  const request = ++parentRequest
  const establishmentId = form.establecimiento_id
  parentOptions.value = []
  if (establishmentId === null) return
  try {
    const items = await consultorios.list({
      establecimientoId: establishmentId,
      incluirInactivos: true,
    })
    if (request === parentRequest) parentOptions.value = items
  } catch {
    if (request === parentRequest)
      formError.value =
        'No se pudieron cargar los consultorios padre. Reabra el formulario para reintentar.'
  }
}

watch(() => form.establecimiento_id, loadParentOptions)

function openCreate(): void {
  editingId.value = null
  form.establecimiento_id = filtroEstablecimiento.value ?? null
  form.codigo = ''
  form.nombre = ''
  form.especialidad_codigo = null
  form.area_codigo = null
  form.servicios_codigos = null
  form.consultorio_padre_id = null
  formError.value = null
  formRef.value?.clearValidate()
  formVisible.value = true
  loadParentOptions()
}

function openCreateChild(parent: OfficeResponse): void {
  openCreate()
  form.establecimiento_id = parent.establecimiento_id
  form.area_codigo = parent.area_codigo || parent.especialidad_codigo
  form.consultorio_padre_id = parent.id
  loadParentOptions()
}

function openEdit(row: OfficeResponse): void {
  editingId.value = row.id
  form.establecimiento_id = row.establecimiento_id
  form.codigo = row.codigo
  form.nombre = row.nombre
  form.especialidad_codigo = row.especialidad_codigo
  form.area_codigo = row.area_codigo || row.especialidad_codigo
  form.servicios_codigos = row.servicios_codigos ?? null
  form.consultorio_padre_id = row.consultorio_padre_id
  formError.value = null
  formRef.value?.clearValidate()
  formVisible.value = true
  loadParentOptions()
}

async function submitForm(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  formError.value = null
  try {
    if (editingId.value === null) {
      await consultorios.create({
        establecimiento_id: form.establecimiento_id as number,
        codigo: form.codigo.trim(),
        nombre: form.nombre.trim(),
        consultorio_padre_id: form.consultorio_padre_id,
        especialidad_codigo: form.especialidad_codigo,
        area_codigo: form.area_codigo,
        servicios_codigos: form.servicios_codigos,
      })
      ElMessage.success('Consultorio creado.')
      formVisible.value = false
    } else {
      await consultorios.update(editingId.value, {
        codigo: form.codigo.trim(),
        nombre: form.nombre.trim(),
        consultorio_padre_id: form.consultorio_padre_id,
        especialidad_codigo: form.especialidad_codigo,
        area_codigo: form.area_codigo,
        servicios_codigos: form.servicios_codigos,
      })
      ElMessage.success('Consultorio actualizado.')
      formVisible.value = false
    }
    await load()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : 'No se pudo guardar el consultorio.'
  } finally {
    saving.value = false
  }
}

async function deactivate(row: OfficeResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Se dará de baja el consultorio ${row.nombre}. Primero debe dar de baja sus subconsultorios activos. Se conservará el historial.`,
      'Dar de baja consultorio',
      { type: 'info', confirmButtonText: 'Dar de baja', cancelButtonText: 'Cancelar' },
    )
  } catch {
    return
  }
  errorMessage.value = null
  try {
    await consultorios.deactivate(row.id)
    ElMessage.success('Consultorio dado de baja.')
    await load()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo dar de baja el consultorio.'
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
  officeTarget.value ? `Profesionales · ${officeTarget.value.nombre}` : 'Profesionales',
)
const assignmentRequirementName = computed(() => {
  const office = officeTarget.value
  const required = office?.especialidad_requerida_codigo ?? office?.especialidad_codigo
  return required && required !== office?.area_codigo ? specialtyNames.value[required] || required : ''
})

function openAssignments(row: OfficeResponse): void {
  officeTarget.value = row
  assignmentsError.value = null
  assignmentSearch.value = ''
  assignFormVisible.value = false
  assignmentsVisible.value = true
  loadAssignments()
}

async function loadAssignments(): Promise<void> {
  const office = officeTarget.value
  if (!office) return
  assignmentsLoading.value = true
  assignmentsError.value = null
  try {
    assignments.value = await consultorios.listAssignments(office.id)
  } catch (error) {
    assignmentsError.value =
      error instanceof Error ? error.message : 'No se pudieron cargar las asignaciones.'
  } finally {
    assignmentsLoading.value = false
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
    await consultorios.assign(officeTarget.value.id, { ...payload, vincular_area: true })
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
      office.id,
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

async function refreshSpecialtyCatalog(): Promise<void> {
  try {
    especialidades.value = await catalogos.especialidades()
    await load()
  } catch {
    errorMessage.value =
      'Los cambios se guardaron. Recargue la página para actualizar los selectores.'
  }
}

onMounted(async () => {
  await Promise.all([
    load(),
    searchEstablishments(''),
    catalogos
      .especialidades()
      .then((items) => {
        especialidades.value = items
      })
      .catch(() => undefined),
    catalogos
      .profesionales(undefined, 100, 0)
      .then((page) => {
        for (const item of page.items) {
          professionalDirectory.value[item.id] = item.nombre_completo
        }
      })
      .catch(() => undefined),
  ])
})
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Consultorios</h2>
      <el-button @click="router.back()">Volver</el-button>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Consultorios" name="consultorios">
        <el-card>
          <div class="toolbar">
            <div class="toolbar-filters">
              <el-select
                v-model="filtroEstablecimiento"
                clearable
                filterable
                remote
                :remote-method="searchEstablishments"
                :loading="establishmentsLoading"
                placeholder="Filtrar por establecimiento"
                aria-label="Filtrar por establecimiento"
                class="establishment-filter"
              >
                <el-option
                  v-for="item in establishments"
                  :key="item.id"
                  :label="item.nombre"
                  :value="item.id"
                />
              </el-select>
              <el-switch v-model="incluirInactivos" active-text="Incluir inactivos" />
            </div>
            <el-button type="primary" @click="openCreate">Nuevo consultorio</el-button>
          </div>

          <OfficesTable
            :rows="rows"
            :loading="loading"
            :establishment-names="establishmentNames"
            :specialty-names="specialtyNames"
            @edit="openEdit"
            @assignments="openAssignments"
            @deactivate="deactivate"
            @create-child="openCreateChild"
          />
        </el-card>
      </el-tab-pane>
      <el-tab-pane
        v-if="canManageStaffCatalogs"
        label="Áreas de atención"
        name="catalogos"
        lazy
      >
        <el-card>
          <StaffCatalogsPanel kind="especialidad" areas-only @created="refreshSpecialtyCatalog" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <OfficeFormDialog
      ref="formRef"
      v-model="formVisible"
      :form="form"
      :title="formTitle"
      :error="formError"
      :saving="saving"
      :editing="editingId !== null"
      :establishments="establishments"
      :loading="establishmentsLoading"
      :areas="areaOptions"
      :specialties="qualificationOptions"
      :parents="availableParents"
      :services="availableServices"
      @change="changeForm"
      @search="searchEstablishments"
      @save="submitForm"
    />

    <!-- Asignaciones del consultorio -->
    <el-dialog
      v-model="assignmentsVisible"
      :title="assignmentsTitle"
      width="min(820px, 94vw)"
      top="6vh"
      :close-on-click-modal="!assignFormVisible"
      :close-on-press-escape="!assignFormVisible"
      :show-close="!assignFormVisible"
      @closed="assignFormVisible = false"
    >
      <el-alert
        v-if="assignmentsError"
        :title="assignmentsError"
        type="error"
        :closable="false"
        class="form-alert"
      />
      <p class="dialog-hint">Consulta los profesionales asignados y sus fechas de vigencia.</p>

      <div class="toolbar">
        <el-input
          v-model="assignmentSearch"
          placeholder="Buscar profesional asignado"
          aria-label="Buscar profesional asignado"
          clearable
          class="assignment-search"
        />
        <div class="assignment-actions">
          <el-button type="primary" @click="openAssignForm">Asignar profesional</el-button>
          <el-button :loading="assignmentsLoading" @click="loadAssignments">Recargar</el-button>
        </div>
      </div>

      <el-table
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
        <el-table-column label="Responsable" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.es_responsable" type="primary" size="small">Sí</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="Acciones" width="110">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="row.fecha_fin !== null && row.fecha_fin < today"
              @click="openClose(row)"
            >
              Cerrar
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <OfficeAssignmentDialog
        v-model="assignFormVisible"
        :office-name="officeTarget?.nombre || ''"
        :area-name="officeTarget?.area_nombre || specialtyNames[officeTarget?.area_codigo || ''] || ''"
        :requirement-name="assignmentRequirementName"
        :professionals="professionalOptions"
        :loading="professionalsLoading"
        :saving="savingAssignment"
        :error="assignError || professionalSearchError"
        @search="searchProfesionales"
        @submit="submitAssignment"
      />
    </el-dialog>

    <!-- Cierre de asignación -->
    <el-dialog v-model="closeVisible" title="Cerrar asignación" width="min(460px, 94vw)">
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
        (inicio {{ closeTarget?.fecha_inicio }}). El cierre no puede ampliar una vigencia ya
        definida.
      </p>
      <el-form label-width="130px">
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
        <el-button @click="closeVisible = false">Cancelar</el-button>
        <el-button type="primary" :loading="savingClose" @click="submitClose">
          Cerrar asignación
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
}

.form-alert {
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.toolbar-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  min-width: 0;
  max-width: 100%;
}

.establishment-filter {
  width: 280px;
  max-width: 100%;
}

/* Las celdas contienen los valores sin desbordar la columna. */
.offices-table :deep(.cell) {
  word-break: normal;
  overflow-wrap: anywhere;
}

.actions-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 10px;
}

.actions-cell :deep(.el-button + .el-button) {
  margin-left: 0;
}

.dialog-hint {
  margin-top: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.assignment-search {
  max-width: 320px;
}
.assignment-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.assignment-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
@media (max-width: 600px) {
  .assignment-search {
    max-width: none;
  }
}
</style>
