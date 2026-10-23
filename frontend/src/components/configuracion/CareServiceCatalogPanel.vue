<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { catalogos, type SpecialtyCatalogItem } from '@/services/catalogos'
import { useCareServiceCatalog } from '@/composables/useCareServiceCatalog'
import CareServiceFormDialog from './CareServiceFormDialog.vue'
import CareServiceTable from './CareServiceTable.vue'
import AdminPageHeader from './AdminPageHeader.vue'

const props = defineProps<{ areaCode?: string }>()
const areas = shallowRef<SpecialtyCatalogItem[]>([])
const areaError = shallowRef<string | null>(null)
const areaNames = computed(() =>
  Object.fromEntries(areas.value.map((item) => [item.codigo, item.nombre])),
)
const {
  visibleItems,
  loading,
  saving,
  error,
  formError,
  search,
  includeInactive,
  areaFilter,
  editing,
  formVisible,
  load,
  open,
  save,
  toggle,
} = useCareServiceCatalog()
watch(
  () => props.areaCode,
  (code) => {
    areaFilter.value = code || null
  },
  { immediate: true },
)
async function loadAreas() {
  areaError.value = null
  try {
    areas.value = (await catalogos.especialidades()).filter((item) => item.es_area)
  } catch {
    areaError.value = 'No se pudieron cargar las áreas. Reintenta antes de registrar un servicio.'
  }
}
onMounted(loadAreas)
async function reloadAll() {
  await Promise.all([load(), loadAreas()])
}
</script>

<template>
  <section aria-labelledby="care-catalog-heading">
    <AdminPageHeader
      title-id="care-catalog-heading"
      title="Catálogo de servicios / especialidades"
      description="Consulta y administra los servicios disponibles. Abre sus consultorios para habilitarlos y gestionar profesionales."
    >
      <el-button type="primary" :disabled="!areas.length" @click="open()"
        >Registrar servicio</el-button
      >
    </AdminPageHeader>
    <el-alert
      v-if="error || areaError"
      :title="error || areaError || ''"
      type="error"
      :closable="false"
      role="alert"
    />
    <div class="catalog-toolbar">
      <el-input
        v-model="search"
        placeholder="Buscar servicio por nombre o código"
        aria-label="Buscar servicio"
        clearable
        class="catalog-filter"
      />
      <el-select
        v-model="areaFilter"
        clearable
        filterable
        placeholder="Todas las áreas"
        aria-label="Filtrar servicios por área"
        class="catalog-filter"
      >
        <el-option
          v-for="area in areas"
          :key="area.codigo"
          :label="area.nombre"
          :value="area.codigo"
        />
      </el-select>
      <el-switch v-model="includeInactive" active-text="Incluir inactivos" />
      <el-button v-if="error || areaError" :loading="loading" @click="reloadAll"
        >Reintentar</el-button
      >
    </div>
    <CareServiceTable
      :items="visibleItems"
      :area-names="areaNames"
      :loading="loading"
      :saving="saving"
      @edit="open"
      @toggle="toggle"
    />
    <CareServiceFormDialog
      v-model="formVisible"
      :service="editing"
      :areas="areas"
      :saving="saving"
      :error="formError"
      @save="save"
    />
  </section>
</template>

<style scoped>
.catalog-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.catalog-filter {
  --el-text-color-placeholder: var(--el-text-color-regular);
  width: 280px;
  max-width: 100%;
}
@media (max-width: 600px) {
  .catalog-filter {
    width: 100%;
  }
}
</style>
