<script setup lang="ts">
import { computed } from 'vue'
import type { CareService } from '@/services/serviciosAsistenciales'
import CareServiceOfficeList from './CareServiceOfficeList.vue'

const props = defineProps<{
  items: CareService[]
  areaNames: Record<string, string>
  loading: boolean
  saving: boolean
}>()
const emit = defineEmits<{ edit: [item: CareService]; toggle: [item: CareService] }>()
const rows = computed(() =>
  props.items.map((item) => {
    const areaNames = item.area_codigos.map((code) => props.areaNames[code] || code)
    const isGeneralService = areaNames.some(
      (name) => name.localeCompare(item.nombre, 'es', { sensitivity: 'base' }) === 0,
    )
    return {
      ...item,
      areaLabel: isGeneralService ? 'Servicio general del área' : `Área: ${areaNames.join(', ')}`,
      usageLabel:
        item.consultorios.length === 1
          ? 'Habilitado en 1 consultorio'
          : `Habilitado en ${item.consultorios.length} consultorios`,
    }
  }),
)
</script>

<template>
  <div v-loading="loading" class="catalog-list" :aria-busy="loading">
    <p v-if="!items.length && !loading" class="catalog-empty" role="status">
      No hay servicios para estos filtros.
    </p>
    <article v-for="item in rows" :key="item.codigo" class="catalog-row">
      <div class="catalog-identity">
        <h3 class="catalog-name">{{ item.nombre }}</h3>
        <p class="catalog-context">
          {{ item.areaLabel }}
        </p>
        <el-tag :type="item.activo ? 'success' : 'info'" size="small">{{
          item.activo ? 'Activo' : 'Inactivo'
        }}</el-tag>
      </div>
      <div class="catalog-usage">
        <details v-if="item.consultorios.length" class="catalog-usage-detail">
          <summary class="catalog-usage-toggle">{{ item.usageLabel }}</summary>
          <CareServiceOfficeList :offices="item.consultorios" />
        </details>
        <p v-if="!item.consultorios.length" class="catalog-context">Sin consultorios vinculados</p>
        <details class="catalog-code">
          <summary class="catalog-code-toggle">Ver código</summary>
          <p class="catalog-context">{{ item.codigo }}</p>
        </details>
      </div>
      <div class="catalog-actions">
        <el-button
          :disabled="saving"
          :aria-label="`Editar servicio ${item.nombre}`"
          @click="emit('edit', item)"
          >Editar</el-button
        >
        <el-button
          :disabled="saving"
          :aria-label="`${item.activo ? 'Dar de baja' : 'Reactivar'} servicio ${item.nombre}`"
          @click="emit('toggle', item)"
          >{{ item.activo ? 'Dar de baja' : 'Reactivar' }}</el-button
        >
      </div>
    </article>
  </div>
</template>

<style scoped>
.catalog-list {
  min-height: 100px;
}
.catalog-row {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(180px, 1fr) auto;
  gap: 20px;
  align-items: start;
  padding-block: 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  overflow-wrap: anywhere;
}
.catalog-name {
  font-size: 18px;
  line-height: 1.4;
  margin: 0;
}
.catalog-identity :deep(.el-tag) {
  color: var(--el-text-color-regular);
}
.catalog-identity :deep(.el-tag--success) {
  color: color-mix(in srgb, var(--el-color-success) 45%, var(--el-text-color-primary));
}
.catalog-context {
  margin: 4px 0 8px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.6;
}
.catalog-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.catalog-actions :deep(.el-button) {
  margin: 0;
}
.catalog-usage-toggle {
  cursor: pointer;
  min-height: 32px;
  line-height: 1.6;
}
.catalog-usage-toggle:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 3px;
}
.catalog-code {
  margin-top: 4px;
}
.catalog-code-toggle {
  cursor: pointer;
  min-height: 28px;
  line-height: 1.6;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.catalog-code-toggle:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 3px;
}
.catalog-empty {
  color: var(--el-text-color-regular);
  padding-block: 24px;
  text-align: center;
}
@media (max-width: 900px) {
  .catalog-row {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .catalog-actions :deep(.el-button),
  .catalog-usage-toggle,
  .catalog-code-toggle {
    min-height: 44px;
  }
}
</style>
