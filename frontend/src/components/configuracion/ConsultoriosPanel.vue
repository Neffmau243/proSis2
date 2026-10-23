<script setup lang="ts">
import { computed, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  catalogos,
  type EstablishmentCatalogItem,
  type SpecialtyCatalogItem,
  type CodeCatalogItem,
} from '@/services/catalogos'
import { consultorios, type OfficeResponse } from '@/services/consultorios'

import OfficesTable from './OfficesTable.vue'
import OfficeFormDialog from './OfficeFormDialog.vue'
import OfficeAssignmentsDialog from './OfficeAssignmentsDialog.vue'
import OfficeServicesPanel from './OfficeServicesPanel.vue'
import { useOfficeForm } from '@/composables/useOfficeForm'
import AdminPageHeader from './AdminPageHeader.vue'
import { careDirectoryQuery, type CareNavigationContext } from '@/utils/careNavigation'

const props = defineProps<{ officeId?: number }>()
const emit = defineEmits<{ context: [value: CareNavigationContext] }>()
const router = useRouter()
const route = useRoute()
function establishmentQuery(): number | null {
  const value = Number(route.query.establecimientoId)
  return Number.isSafeInteger(value) && value > 0 ? value : null
}
function areaQuery(): string | null {
  return typeof route.query.areaCodigo === 'string' ? route.query.areaCodigo : null
}

// --- Catálogos de apoyo (nombres y selects) ---
const establishments = ref<EstablishmentCatalogItem[]>([])
const establishmentsLoading = ref(false)
const especialidades = ref<SpecialtyCatalogItem[]>([])
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

const establishmentNames = computed(() =>
  Object.fromEntries(establishments.value.map((item) => [item.id, item.nombre])),
)
const specialtyNames = computed(() =>
  Object.fromEntries(especialidades.value.map((item) => [item.codigo, item.nombre])),
)
// --- Lista de consultorios ---
const rows = ref<OfficeResponse[]>([])
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const incluirInactivos = ref(false)
const filtroEstablecimiento = ref<number | null>(establishmentQuery())
const filtroArea = ref<string | null>(areaQuery())
const search = ref('')
const selectedOffice = computed(() => rows.value.find((item) => item.id === props.officeId))
const navigationContext = computed<CareNavigationContext>(() => {
  const office = selectedOffice.value
  const establishmentId = props.officeId ? office?.establecimiento_id : filtroEstablecimiento.value
  const areaCode = props.officeId
    ? office?.area_codigo || office?.especialidad_codigo
    : filtroArea.value
  return {
    establishmentId: establishmentId || undefined,
    establishmentName:
      office?.establecimiento_nombre ||
      (establishmentId ? establishmentNames.value[establishmentId] : undefined) ||
      rows.value.find((item) => item.establecimiento_id === establishmentId)
        ?.establecimiento_nombre ||
      undefined,
    areaCode: areaCode || undefined,
    areaName: office?.area_nombre || (areaCode ? specialtyNames.value[areaCode] : undefined),
    officeName: office?.nombre,
  }
})
watch(navigationContext, (value) => emit('context', value), { immediate: true })
const backQuery = computed(() =>
  selectedOffice.value
    ? {
        ...route.query,
        establecimientoId: undefined,
        areaCodigo: undefined,
        ...careDirectoryQuery(navigationContext.value),
      }
    : route.query,
)
const directoryRows = computed(() => {
  const known = new Set(rows.value.map((item) => item.id))
  const query = search.value.trim().toLocaleLowerCase('es')
  return rows.value.filter(
    (item) =>
      (item.consultorio_padre_id === null || !known.has(item.consultorio_padre_id)) &&
      (!filtroArea.value || (item.area_codigo || item.especialidad_codigo) === filtroArea.value) &&
      (!query ||
        [
          item.nombre,
          item.codigo,
          item.area_nombre,
          ...(item.servicios_habilitados || []).map((service) => service.nombre),
        ].some((value) => value?.toLocaleLowerCase('es').includes(query))),
  )
})
function updateOffice(office: OfficeResponse): void {
  rows.value = rows.value.map((item) => (item.id === office.id ? office : item))
  void load()
}
function openOffice(office: OfficeResponse): void {
  void router.push({
    name: 'consultorio-servicios',
    params: { officeId: office.id },
    query: route.query,
  })
}

let listRequest = 0
async function load(): Promise<void> {
  const request = ++listRequest
  loading.value = true
  errorMessage.value = null
  try {
    const items = await consultorios.list({
      establecimientoId: props.officeId ? undefined : (filtroEstablecimiento.value ?? undefined),
      incluirInactivos: !!props.officeId || incluirInactivos.value,
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
watch([filtroEstablecimiento, filtroArea], () => {
  void router.replace({
    query: {
      ...route.query,
      establecimientoId: filtroEstablecimiento.value || undefined,
      areaCodigo: filtroArea.value || undefined,
    },
  })
})
watch(
  () => route.query,
  () => {
    filtroEstablecimiento.value = establishmentQuery()
    filtroArea.value = areaQuery()
  },
)
watch(
  () => props.officeId,
  () => {
    formVisible.value = false
    assignmentsRef.value?.close()
    void load()
  },
)

const {
  formVisible,
  saving,
  editingId,
  formError,
  form,
  formTitle,
  areaOptions,
  changeForm,
  openCreate,
  openEdit,
  submitForm,
} = useOfficeForm(especialidades, filtroEstablecimiento, load, async (office, created) => {
  if (created) {
    await router.push({
      name: 'consultorio-servicios',
      params: { officeId: office.id },
      query: careDirectoryQuery({
        establishmentId: office.establecimiento_id,
        areaCode: office.area_codigo || office.especialidad_codigo || undefined,
      }),
    })
  } else if (!props.officeId && filtroArea.value) {
    filtroArea.value = office.area_codigo || office.especialidad_codigo || null
  }
})
async function deactivate(row: OfficeResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Se dará de baja el consultorio ${row.nombre}. Se conservará el historial.`,
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

async function reactivate(row: OfficeResponse): Promise<void> {
  errorMessage.value = null
  try {
    await consultorios.reactivate(row.id)
    ElMessage.success('Consultorio reactivado.')
    await load()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo reactivar el consultorio.'
  }
}

const assignmentsRef =
  useTemplateRef<InstanceType<typeof OfficeAssignmentsDialog>>('assignmentsRef')
function openAssignments(row: OfficeResponse, service?: CodeCatalogItem): void {
  assignmentsRef.value?.open(row, service)
}
function startCreate(): void {
  openCreate()
  if (filtroArea.value && areaOptions.value.some((item) => item.codigo === filtroArea.value))
    changeForm({ area_codigo: filtroArea.value })
}
let ready = false
function createFromContext(): void {
  if (!ready || route.query.nuevo !== '1' || props.officeId) return
  startCreate()
  const query = { ...route.query }
  delete query.nuevo
  void router.replace({ query })
}
watch(() => route.query.nuevo, createFromContext)

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
  ])
  ready = true
  createFromContext()
})
</script>

<template>
  <div>
    <AdminPageHeader
      :title="officeId ? selectedOffice?.nombre || 'Detalle del consultorio' : 'Consultorios'"
      :description="
        officeId
          ? 'Gestiona sus servicios y los profesionales que atienden en ellos.'
          : 'Crea consultorios y administra sus servicios y profesionales.'
      "
    >
      <el-button v-if="officeId" @click="router.push({ name: 'consultorios', query: backQuery })"
        >Volver a consultorios</el-button
      >
      <el-button v-else @click="router.push({ name: 'establecimientos' })"
        >Ver establecimientos</el-button
      >
      <el-button v-if="!officeId" type="primary" @click="startCreate">Nuevo consultorio</el-button>
    </AdminPageHeader>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <template v-if="officeId">
      <el-button v-if="errorMessage" :loading="loading" @click="load">Reintentar</el-button>
      <section v-if="selectedOffice" class="office-detail" aria-label="Servicios del consultorio">
        <div class="detail-context">
          <div>
            <p>
              {{
                selectedOffice.establecimiento_nombre ||
                establishmentNames[selectedOffice.establecimiento_id] ||
                `Sede #${selectedOffice.establecimiento_id}`
              }}
            </p>
            <p>
              {{ selectedOffice.codigo }} ·
              {{
                selectedOffice.area_nombre ||
                specialtyNames[
                  selectedOffice.area_codigo || selectedOffice.especialidad_codigo || ''
                ] ||
                'Sin área'
              }}
            </p>
          </div>
          <el-tag
            :type="
              selectedOffice.activo && selectedOffice.activo_efectivo !== false ? 'success' : 'info'
            "
          >
            {{
              !selectedOffice.activo
                ? 'Inactivo'
                : selectedOffice.activo_efectivo === false
                  ? 'Padre inactivo'
                  : 'Activo'
            }}
          </el-tag>
        </div>
        <div class="detail-actions">
          <el-button @click="openEdit(selectedOffice)">Editar consultorio</el-button>
          <el-button @click="openAssignments(selectedOffice)">Asignaciones</el-button>
          <el-button v-if="selectedOffice.activo" @click="deactivate(selectedOffice)"
            >Dar de baja</el-button
          >
          <el-button v-else type="primary" @click="reactivate(selectedOffice)"
            >Reactivar consultorio</el-button
          >
        </div>
        <OfficeServicesPanel
          :key="selectedOffice.id"
          :office="selectedOffice"
          @updated="updateOffice"
          @assignments="openAssignments(selectedOffice, $event)"
        />
      </section>
      <div v-if="!selectedOffice && !loading && !errorMessage">
        <p role="status">No se encontró este consultorio.</p>
        <el-button @click="router.push({ name: 'consultorios', query: route.query })"
          >Ver consultorios</el-button
        >
      </div>
      <p v-if="loading && !selectedOffice" role="status">Cargando consultorio…</p>
    </template>
    <section v-else aria-label="Directorio de consultorios">
      <div>
        <div class="toolbar">
          <div class="toolbar-filters">
            <el-input
              v-model="search"
              clearable
              placeholder="Buscar consultorio o servicio"
              aria-label="Buscar consultorio o servicio"
              class="establishment-filter"
            />
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
            <el-select
              v-model="filtroArea"
              clearable
              filterable
              aria-label="Filtrar por área"
              placeholder="Filtrar por área"
              class="establishment-filter"
            >
              <el-option
                v-for="item in areaOptions"
                :key="item.codigo"
                :label="item.nombre"
                :value="item.codigo"
              />
            </el-select>
            <el-switch v-model="incluirInactivos" active-text="Incluir inactivos" />
          </div>
        </div>

        <OfficesTable
          :rows="directoryRows"
          directory
          :loading="loading"
          :establishment-names="establishmentNames"
          :specialty-names="specialtyNames"
          @edit="openEdit"
          @assignments="openAssignments"
          @deactivate="deactivate"
          @reactivate="reactivate"
          @open="openOffice"
        />
        <p v-if="!loading && search && !directoryRows.length" role="status">
          No hay coincidencias. Prueba con otro nombre, código o servicio.
        </p>
        <el-button v-if="errorMessage" :loading="loading" @click="load">Reintentar</el-button>
      </div>
    </section>

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
      @change="changeForm"
      @search="searchEstablishments"
      @save="submitForm"
    />

    <OfficeAssignmentsDialog
      ref="assignmentsRef"
      :specialty-names="specialtyNames"
      @changed="load"
    />
  </div>
</template>

<style scoped>
.office-detail {
  margin-bottom: 24px;
}
.detail-context {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  overflow-wrap: anywhere;
}
.detail-context p {
  margin: 0 0 8px;
  color: var(--el-text-color-regular);
}
.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-block: 16px 28px;
}
.detail-actions :deep(.el-button) {
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
  margin-bottom: 24px;
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
</style>
