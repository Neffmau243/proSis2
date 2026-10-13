<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

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
} from '@/services/consultorios'

import OfficesTable from './OfficesTable.vue'
import OfficeFormDialog from './OfficeFormDialog.vue'
import { descendantIds } from '@/utils/officeHierarchy'
import type { OfficeForm } from './officeForm'

const router = useRouter()

// --- Catálogos de apoyo (nombres y selects) ---
const establishments = ref<EstablishmentCatalogItem[]>([])
const establishmentsLoading = ref(false)
const especialidades = ref<SpecialtyCatalogItem[]>([])
const parentOptions = ref<OfficeResponse[]>([])
const professionalOptions = ref<ProfessionalCatalogItem[]>([])
const professionalsLoading = ref(false)
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

async function searchProfesionales(query: string): Promise<void> {
  professionalsLoading.value = true
  try {
    const page = await catalogos.profesionales(query || undefined, 25, 0)
    professionalOptions.value = page.items
    for (const item of page.items) {
      professionalDirectory.value[item.id] = item.nombre_completo
    }
  } finally {
    professionalsLoading.value = false
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
const assignRef = ref<FormInstance>()
const assignForm = reactive({
  profesional_id: null as number | null,
  fecha_inicio: '',
  fecha_fin: '',
  es_responsable: false,
})

const assignRules: FormRules = {
  profesional_id: [{ required: true, message: 'Seleccione el profesional.', trigger: 'change' }],
  fecha_inicio: [{ required: true, message: 'Indique la fecha de inicio.', trigger: 'change' }],
}

const assignmentsTitle = computed(() =>
  officeTarget.value ? `Profesionales · ${officeTarget.value.nombre}` : 'Profesionales',
)

function openAssignments(row: OfficeResponse): void {
  officeTarget.value = row
  assignmentsError.value = null
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
  assignForm.profesional_id = null
  assignForm.fecha_inicio = ''
  assignForm.fecha_fin = ''
  assignForm.es_responsable = false
  assignRef.value?.clearValidate()
  assignFormVisible.value = true
}

async function submitAssignment(): Promise<void> {
  if (!officeTarget.value) return
  const valid = await assignRef.value?.validate().catch(() => false)
  if (!valid) return

  const professionalId = assignForm.profesional_id
  const fechaInicio = assignForm.fecha_inicio
  if (professionalId === null || !fechaInicio) return
  if (assignForm.fecha_fin && assignForm.fecha_fin < fechaInicio) {
    assignmentsError.value = 'La fecha de fin no puede ser anterior a la fecha de inicio.'
    return
  }

  savingAssignment.value = true
  assignmentsError.value = null
  try {
    await consultorios.assign(officeTarget.value.id, {
      profesional_id: professionalId,
      fecha_inicio: fechaInicio,
      fecha_fin: assignForm.fecha_fin === '' ? null : assignForm.fecha_fin,
      es_responsable: assignForm.es_responsable,
    })
    ElMessage.success('Profesional asignado.')
    assignFormVisible.value = false
    await loadAssignments()
  } catch (error) {
    assignmentsError.value =
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
      />
    </el-card>

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
      :parents="availableParents"
      :services="availableServices"
      @change="changeForm"
      @search="searchEstablishments"
      @save="submitForm"
    />

    <!-- Asignaciones del consultorio -->
    <el-dialog v-model="assignmentsVisible" :title="assignmentsTitle" width="min(820px, 94vw)">
      <el-alert
        v-if="assignmentsError"
        :title="assignmentsError"
        type="error"
        :closable="false"
        class="form-alert"
      />
      <p class="dialog-hint">
        La asignación vincula al profesional con el consultorio para la atención clínica. La tabla
        se muestra aunque esté vacía: significa que todavía no hay asignaciones históricas, no un
        error.
      </p>

      <div class="toolbar">
        <el-button type="primary" @click="openAssignForm">Asignar profesional</el-button>
        <el-button @click="loadAssignments">Recargar</el-button>
      </div>

      <el-table
        v-loading="assignmentsLoading"
        :data="assignments"
        empty-text="Sin asignaciones registradas"
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

      <el-form
        v-if="assignFormVisible"
        ref="assignRef"
        :model="assignForm"
        :rules="assignRules"
        label-width="150px"
        class="assign-form"
      >
        <el-form-item label="Profesional" prop="profesional_id">
          <el-select
            v-model="assignForm.profesional_id"
            filterable
            remote
            :remote-method="searchProfesionales"
            :loading="professionalsLoading"
            placeholder="Busque por nombre o colegiatura"
            style="width: 100%"
          >
            <el-option
              v-for="item in professionalOptions"
              :key="item.id"
              :label="item.nombre_completo"
              :value="item.id"
            />
          </el-select>
          <div class="hint">El consultorio exige que el profesional tenga su especialidad.</div>
        </el-form-item>
        <el-form-item label="Fecha de inicio" prop="fecha_inicio">
          <el-date-picker
            v-model="assignForm.fecha_inicio"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Fecha de fin" prop="fecha_fin">
          <el-date-picker
            v-model="assignForm.fecha_fin"
            type="date"
            value-format="YYYY-MM-DD"
            clearable
            placeholder="Opcional"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Responsable">
          <el-checkbox v-model="assignForm.es_responsable">
            Es responsable del consultorio
          </el-checkbox>
        </el-form-item>
        <div class="form-actions">
          <el-button type="primary" :loading="savingAssignment" @click="submitAssignment">
            Guardar asignación
          </el-button>
          <el-button @click="assignFormVisible = false">Cancelar</el-button>
        </div>
      </el-form>
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

.assign-form {
  margin-top: 16px;
}

.form-actions {
  display: flex;
  gap: 8px;
  margin-left: 150px;
}

@media (max-width: 600px) {
  .form-actions {
    margin-left: 0;
    flex-wrap: wrap;
  }
}
</style>
