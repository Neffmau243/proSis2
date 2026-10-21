<template>
  <div>
    <div class="panel-toolbar">
      <el-switch
        :model-value="incluirInactivos"
        active-text="Incluir inactivos"
        @update:model-value="emit('update:incluirInactivos', $event as boolean)"
      />
      <el-button type="primary" @click="openCreate">Nuevo profesional</el-button>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <el-table
      v-loading="loading"
      :data="rows"
      empty-text="Sin profesionales registrados"
      class="professionals-table"
    >
      <el-table-column
        prop="nombre_completo"
        label="Nombre"
        min-width="200"
        show-overflow-tooltip
      />
      <el-table-column label="Documento / Colegiatura" min-width="190">
        <template #default="{ row }">
          <div class="stacked-cell">
            <span class="nowrap">{{ row.numero_documento || '—' }}</span>
            <span class="stacked-cell__muted nowrap">{{
              row.colegiatura || 'Sin colegiatura'
            }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="Profesión" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ profesionNombre(row.profesion_id) }}</template>
      </el-table-column>
      <el-table-column label="Áreas y especialidades" min-width="200">
        <template #default="{ row }">
          <div v-if="row.especialidades.length" class="tags-cell">
            <el-tag
              v-for="specialty in row.especialidades"
              :key="specialty.especialidad_codigo"
              :type="specialty.es_principal ? 'primary' : 'info'"
              size="small"
            >
              {{ especialidadNombre(specialty.especialidad_codigo) }}
              <template v-if="specialty.es_principal"> · principal</template>
            </el-tag>
          </div>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="Estado" min-width="150">
        <template #default="{ row }">
          <div class="tags-cell">
            <el-tag :type="row.activo ? 'success' : 'danger'" size="small">
              {{ row.activo ? 'Activo' : 'Inactivo' }}
            </el-tag>
            <el-tag :type="hasAccount(row.id) ? 'success' : 'info'" size="small" effect="plain">
              {{ hasAccount(row.id) ? 'Con cuenta' : 'Sin cuenta' }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="Acciones" min-width="280">
        <template #default="{ row }">
          <div class="actions-cell">
            <el-button link type="primary" @click="openEdit(row)">Editar</el-button>
            <el-button link type="primary" @click="openSpecialties(row)">Especialidades</el-button>
            <el-button
              v-if="canCreateAccount && !hasAccount(row.id)"
              link
              type="primary"
              @click="emit('create-account', row)"
            >
              Crear cuenta
            </el-button>
            <el-button link type="primary" :disabled="!row.activo" @click="deactivate(row)">
              Dar de baja
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- Alta / edición de la ficha -->
    <el-dialog v-model="formVisible" :title="formTitle" width="min(620px, 94vw)" top="6vh">
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        class="form-alert"
      />
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="Nombre completo" prop="nombre_completo">
          <el-input v-model="form.nombre_completo" maxlength="200" />
        </el-form-item>
        <el-form-item label="Documento" prop="numero_documento">
          <el-input v-model="form.numero_documento" maxlength="30" />
        </el-form-item>
        <el-form-item label="Profesión" prop="profesion_id">
          <el-select
            v-model="form.profesion_id"
            clearable
            filterable
            placeholder="Seleccione una profesión"
            style="width: 100%"
          >
            <el-option
              v-for="profesion in profesiones"
              :key="profesion.id"
              :label="profesion.nombre"
              :value="profesion.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Colegiatura" prop="colegiatura">
          <el-input v-model="form.colegiatura" maxlength="50" />
        </el-form-item>
        <ProfessionalQualificationsFields
          v-if="editingId === null"
          v-model:selected="createQualifications"
          v-model:principal="createPrincipal"
          :options="especialidades"
        />
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">Cancelar</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">Guardar</el-button>
      </template>
    </el-dialog>

    <!-- Reemplazo completo de especialidades (PUT .../especialidades) -->
    <el-dialog v-model="specialtiesVisible" title="Especialidades" width="560px">
      <p class="dialog-hint">
        El guardado reemplaza la lista completa. Si hay especialidades, exactamente una debe
        marcarse como principal.
      </p>
      <el-alert
        v-if="specialtiesError"
        :title="specialtiesError"
        type="error"
        :closable="false"
        class="form-alert"
      />

      <el-radio-group v-model="principalIndex" class="specialty-list">
        <div v-for="(row, index) in specialtyRows" :key="index" class="specialty-row">
          <el-select
            v-model="row.codigo"
            filterable
            clearable
            placeholder="Especialidad"
            class="specialty-row__select"
          >
            <el-option
              v-for="specialty in staffSpecialtyOptions"
              :key="specialty.codigo"
              :label="
                isStaffSpecialty(specialty)
                  ? specialty.nombre
                  : `${specialty.nombre} (registro anterior)`
              "
              :value="specialty.codigo"
              :disabled="isSpecialtyTaken(specialty.codigo, index)"
            />
          </el-select>
          <el-radio :value="index" :disabled="!row.codigo">Principal</el-radio>
          <el-button link type="danger" @click="removeSpecialtyRow(index)">Quitar</el-button>
        </div>
      </el-radio-group>

      <el-button class="specialty-add" @click="addSpecialtyRow">Agregar especialidad</el-button>

      <template #footer>
        <el-button @click="specialtiesVisible = false">Cancelar</el-button>
        <el-button type="primary" :loading="savingSpecialties" @click="submitSpecialties">
          Guardar especialidades
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { catalogos, type IdCatalogItem, type SpecialtyCatalogItem } from '@/services/catalogos'
import { profesionales, type ProfessionalResponse } from '@/services/profesionales'
import { isStaffSpecialty } from '@/utils/staffSpecialties'
import ProfessionalQualificationsFields from './ProfessionalQualificationsFields.vue'

const props = defineProps<{
  rows: ProfessionalResponse[]
  loading: boolean
  incluirInactivos: boolean
  /** Ids de profesionales que ya tienen cuenta de usuario. */
  linkedProfessionalIds: number[]
  canCreateAccount: boolean
  catalogRevision?: number
}>()

const emit = defineEmits<{
  (event: 'refresh'): void
  (event: 'update:incluirInactivos', value: boolean): void
  (event: 'create-account', professional: ProfessionalResponse): void
}>()

const profesiones = ref<IdCatalogItem[]>([])
const especialidades = ref<SpecialtyCatalogItem[]>([])

const formRef = ref<FormInstance>()
const createQualifications = ref<string[]>([])
const createPrincipal = ref<string | null>(null)
const formVisible = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const errorMessage = ref<string | null>(null)

const form = reactive({
  nombre_completo: '',
  numero_documento: '',
  profesion_id: null as number | null,
  colegiatura: '',
})

const rules: FormRules = {
  nombre_completo: [
    { required: true, message: 'Ingrese el nombre completo.', trigger: 'blur' },
    { min: 2, message: 'Mínimo 2 caracteres.', trigger: 'blur' },
  ],
}

const formTitle = computed(() =>
  editingId.value === null ? 'Nuevo profesional' : 'Editar profesional',
)

// --- Edición de especialidades ---
const specialtiesVisible = ref(false)
const savingSpecialties = ref(false)
const specialtiesError = ref<string | null>(null)
const specialtyTargetId = ref<number | null>(null)
const specialtyRows = ref<{ codigo: string | null }[]>([])
const principalIndex = ref<number | null>(null)
// Preserve existing historical assignments while offering staff qualifications.
const staffSpecialtyOptions = computed(() =>
  especialidades.value.filter(
    (item) =>
      isStaffSpecialty(item) || specialtyRows.value.some((row) => row.codigo === item.codigo),
  ),
)

function hasAccount(id: number): boolean {
  return props.linkedProfessionalIds.includes(id)
}

function profesionNombre(id: number | null): string {
  if (id === null) return '—'
  return profesiones.value.find((item) => item.id === id)?.nombre ?? `#${id}`
}

function especialidadNombre(codigo: string): string {
  return especialidades.value.find((item) => item.codigo === codigo)?.nombre ?? codigo
}

function isSpecialtyTaken(codigo: string, ownIndex: number): boolean {
  return specialtyRows.value.some((row, index) => index !== ownIndex && row.codigo === codigo)
}

async function loadCatalogs(): Promise<void> {
  try {
    const [profesionList, specialtyList] = await Promise.all([
      catalogos.profesiones(),
      catalogos.especialidades(),
    ])
    profesiones.value = profesionList
    especialidades.value = specialtyList
  } catch {
    // Los catálogos solo enriquecen la vista; la lista sigue siendo útil sin ellos.
  }
}

watch(() => props.catalogRevision, loadCatalogs)

function openCreate(): void {
  editingId.value = null
  resetForm()
  formVisible.value = true
}

function openEdit(row: ProfessionalResponse): void {
  editingId.value = row.id
  form.nombre_completo = row.nombre_completo
  form.numero_documento = row.numero_documento ?? ''
  form.profesion_id = row.profesion_id
  form.colegiatura = row.colegiatura ?? ''
  formVisible.value = true
}

function resetForm(): void {
  createQualifications.value = []
  createPrincipal.value = null
  form.nombre_completo = ''
  form.numero_documento = ''
  form.profesion_id = null
  form.colegiatura = ''
  formRef.value?.clearValidate()
}

/** Los opcionales vacíos viajan como null: el contrato los acepta sin ambigüedad. */
function buildPayload() {
  const documento = form.numero_documento.trim()
  const colegiatura = form.colegiatura.trim()
  return {
    nombre_completo: form.nombre_completo.trim(),
    numero_documento: documento === '' ? null : documento,
    profesion_id: form.profesion_id,
    colegiatura: colegiatura === '' ? null : colegiatura,
  }
}

async function submitForm(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  errorMessage.value = null
  try {
    if (editingId.value === null) {
      await profesionales.create({
        ...buildPayload(),
        especialidades: createQualifications.value.map((codigo) => ({
          especialidad_codigo: codigo,
          es_principal: codigo === (createPrincipal.value ?? createQualifications.value[0]),
        })),
      })
      ElMessage.success('Profesional creado.')
    } else {
      await profesionales.update(editingId.value, buildPayload())
      ElMessage.success('Profesional actualizado.')
    }
    formVisible.value = false
    emit('refresh')
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo guardar el profesional.'
  } finally {
    saving.value = false
  }
}

function openSpecialties(row: ProfessionalResponse): void {
  specialtyTargetId.value = row.id
  specialtyRows.value = row.especialidades.map((item) => ({ codigo: item.especialidad_codigo }))
  const principal = row.especialidades.findIndex((item) => item.es_principal)
  principalIndex.value = principal >= 0 ? principal : null
  specialtiesError.value = null
  specialtiesVisible.value = true
}

function addSpecialtyRow(): void {
  specialtyRows.value.push({ codigo: null })
}

function removeSpecialtyRow(index: number): void {
  specialtyRows.value.splice(index, 1)
  if (principalIndex.value === index) {
    principalIndex.value = null
  } else if (principalIndex.value !== null && principalIndex.value > index) {
    principalIndex.value -= 1
  }
}

async function submitSpecialties(): Promise<void> {
  const filled = specialtyRows.value.filter((row): row is { codigo: string } => Boolean(row.codigo))
  specialtiesError.value = null

  const principalCode =
    principalIndex.value !== null
      ? (specialtyRows.value[principalIndex.value]?.codigo ?? null)
      : null

  if (filled.length && principalIndex.value === null) {
    specialtiesError.value = 'Marque una especialidad como principal.'
    return
  }
  if (filled.length && principalCode === null) {
    specialtiesError.value = 'La especialidad principal debe tener un código seleccionado.'
    return
  }

  const payload = filled.map((row) => ({
    especialidad_codigo: row.codigo,
    es_principal: row.codigo === principalCode,
  }))
  const distinct = new Set(payload.map((item) => item.especialidad_codigo))
  if (distinct.size !== payload.length) {
    specialtiesError.value = 'No se puede repetir una especialidad.'
    return
  }

  savingSpecialties.value = true
  try {
    await profesionales.replaceSpecialties(specialtyTargetId.value as number, payload)
    ElMessage.success('Especialidades actualizadas.')
    specialtiesVisible.value = false
    emit('refresh')
  } catch (error) {
    specialtiesError.value =
      error instanceof Error ? error.message : 'No se pudieron guardar las especialidades.'
  } finally {
    savingSpecialties.value = false
  }
}

async function deactivate(row: ProfessionalResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Se dará de baja a ${row.nombre_completo}. La baja es lógica: el registro y su historial se conservan.`,
      'Dar de baja profesional',
      { type: 'info', confirmButtonText: 'Dar de baja', cancelButtonText: 'Cancelar' },
    )
  } catch {
    return
  }
  errorMessage.value = null
  try {
    const result = await profesionales.deactivate(row.id)
    ElMessage.success(`${result.nombre_completo} quedó inactivo.`)
    emit('refresh')
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo dar de baja al profesional.'
  }
}

onMounted(loadCatalogs)
</script>

<style scoped>
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.form-alert {
  margin-bottom: 16px;
}

/* Evita que las celdas rompan el layout de la tabla: cada valor se acomoda
   dentro de su columna y los tags envuelven en varias líneas. */
.professionals-table :deep(.cell) {
  word-break: normal;
  overflow-wrap: anywhere;
}

.stacked-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.stacked-cell__muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.tags-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
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

.nowrap {
  white-space: nowrap;
}

.dialog-hint {
  margin-top: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.specialty-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.specialty-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.specialty-row__select {
  flex: 1;
}

.specialty-add {
  margin-top: 12px;
  margin-left: 0 !important;
}
</style>
