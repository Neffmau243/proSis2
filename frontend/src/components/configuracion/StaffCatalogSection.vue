<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import type { StaffCatalogKind, StaffCatalogEntry } from '@/composables/useStaffCatalogs'
import type { StaffCatalogPayload } from '@/services/catalogosPersonal'
import StaffCatalogForm from './StaffCatalogForm.vue'

const props = defineProps<{
  kind: StaffCatalogKind
  areasOnly?: boolean
  items: StaffCatalogEntry[]
  loading: boolean
  saving: boolean
  creating: boolean
  editing: StaffCatalogEntry | null
  error: string | null
}>()
const emit = defineEmits<{
  open: []
  edit: [item: StaffCatalogEntry]
  delete: [item: StaffCatalogEntry]
  cancel: []
  submit: [payload: StaffCatalogPayload]
}>()
const search = shallowRef('')
const showPrevious = shallowRef(false)
const title = computed(() =>
  props.kind === 'profesion' ? 'Profesiones' : props.areasOnly ? 'Áreas de atención' : 'Áreas y especialidades',
)
const createLabel = computed(() =>
  props.kind === 'profesion' ? 'Nueva profesión' : props.areasOnly ? 'Nueva área' : 'Nueva área o especialidad',
)
const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('es')
  return props.items.filter((item) =>
    (!props.areasOnly || showPrevious.value || ('es_area' in item && item.es_area)) &&
    item.nombre.toLocaleLowerCase('es').includes(query),
  )
})

watch(
  () => props.items,
  () => {
    search.value = ''
  },
)
</script>

<template>
  <section :aria-label="title">
    <p class="catalog-description">
      {{
        kind === 'profesion'
          ? 'Profesiones disponibles al registrar o editar al personal.'
          : areasOnly
            ? 'Crea un área y úsala en los consultorios de cada establecimiento. Luego asigna sus profesionales.'
            : 'Áreas de atención y especialidades disponibles para consultorios y profesionales.'
      }}
    </p>
    <div class="panel-toolbar">
      <el-input
        v-model="search"
        :aria-label="`Buscar en ${title.toLowerCase()}`"
        :placeholder="
          kind === 'profesion' ? 'Buscar profesión por nombre' : areasOnly ? 'Buscar área' : 'Buscar área o especialidad'
        "
        clearable
        class="catalog-search"
      />
      <el-button type="primary" :disabled="saving || loading || creating" @click="emit('open')">{{
        createLabel
      }}</el-button>
    </div>
    <el-checkbox v-if="areasOnly" v-model="showPrevious">
      Mostrar también especialidades anteriores
    </el-checkbox>
    <el-table
      v-loading="loading"
      :data="filtered"
      row-key="nombre"
      :empty-text="search ? 'Sin coincidencias para esta búsqueda' : 'Sin registros'"
      max-height="420"
      class="catalog-table"
    >
      <el-table-column prop="nombre" label="Nombre" min-width="200" show-overflow-tooltip />
      <el-table-column v-if="kind === 'especialidad' && (!areasOnly || showPrevious)" label="Tipo" width="150">
        <template #default="{ row }">
          <el-tag :type="row.es_area ? 'info' : 'primary'" size="small" effect="plain">{{
            row.es_area ? 'Área' : 'Especialidad'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Estado" width="110">
        <template #default="{ row }">
          <el-tag :type="row.activo ? 'success' : 'danger'" size="small">{{
            row.activo ? 'Activo' : 'Inactivo'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Acciones" width="180">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            :disabled="saving || creating"
            :aria-label="`Editar ${row.nombre}`"
            @click="emit('edit', row)"
            >Editar</el-button
          >
          <el-button
            link
            type="danger"
            :disabled="saving || creating || row.es_area_base"
            :title="
              row.es_area_base
                ? 'Las áreas base organizan los servicios y no se pueden eliminar'
                : undefined
            "
            :aria-label="`Eliminar ${row.nombre}`"
            @click="emit('delete', row)"
            >Eliminar</el-button
          >
        </template>
      </el-table-column>
    </el-table>
    <p class="catalog-count" role="status">
      {{ filtered.length }} {{ search ? 'resultados' : 'registros' }}
    </p>
    <StaffCatalogForm
      v-if="creating"
      :kind="kind"
      :areas-only="areasOnly"
      :record="editing"
      :saving="saving"
      :error="error"
      @submit="emit('submit', $event)"
      @cancel="emit('cancel')"
    />
  </section>
</template>

<style scoped>
.catalog-description {
  margin: 0 0 16px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.catalog-search {
  max-width: 360px;
}
.catalog-count {
  margin: 12px 0 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
@media (max-width: 600px) {
  .panel-toolbar {
    flex-wrap: wrap;
  }
  .catalog-search {
    max-width: none;
    flex-basis: 100%;
  }
}
</style>
