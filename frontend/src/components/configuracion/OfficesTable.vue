<script setup lang="ts">
import { computed } from 'vue'
import type { OfficeResponse } from '@/services/consultorios'
import { officeTree, type OfficeTreeRow } from '@/utils/officeHierarchy'
import OfficeActions from './OfficeActions.vue'

const props = defineProps<{
  rows: OfficeResponse[]
  loading: boolean
  establishmentNames: Record<number, string>
  specialtyNames: Record<string, string>
  directory?: boolean
}>()
const emit = defineEmits<{
  edit: [row: OfficeResponse]
  assignments: [row: OfficeResponse]
  deactivate: [row: OfficeResponse]
  reactivate: [row: OfficeResponse]
  open: [row: OfficeResponse]
}>()
function serviceNames(row: OfficeResponse): string {
  if (row.servicios_habilitados)
    return (
      row.servicios_habilitados.map((item) => item.nombre).join(', ') || 'Sin servicios habilitados'
    )
  return props.specialtyNames[row.especialidad_codigo || ''] || 'Sin servicios habilitados'
}
function serviceSummary(row: OfficeResponse): string {
  const count =
    row.servicios_habilitados?.length ??
    (props.specialtyNames[row.especialidad_codigo || ''] ? 1 : 0)
  return count === 0
    ? 'Sin servicios habilitados'
    : `${count} ${count === 1 ? 'servicio' : 'servicios'}`
}
const tree = computed(() => officeTree(props.rows))
function flattenTree(nodes: OfficeTreeRow[]): OfficeResponse[] {
  return nodes.flatMap((node) => [node, ...flattenTree(node.children)])
}
const mobileRows = computed(() => flattenTree(tree.value))
function establishmentName(row: OfficeResponse): string {
  return (
    row.establecimiento_nombre ||
    props.establishmentNames[row.establecimiento_id] ||
    `Sede #${row.establecimiento_id}`
  )
}
function areaName(row: OfficeResponse): string {
  return (
    row.area_nombre ||
    props.specialtyNames[row.area_codigo || row.especialidad_codigo || ''] ||
    'Sin área'
  )
}
function statusLabel(row: OfficeResponse): string {
  return !row.activo ? 'Inactivo' : row.activo_efectivo === false ? 'Padre inactivo' : 'Activo'
}
function parentName(row: OfficeResponse): string {
  if (row.consultorio_padre_id === null) return 'Principal'
  return (
    row.consultorio_padre_nombre ||
    props.rows.find((item) => item.id === row.consultorio_padre_id)?.nombre ||
    `Consultorio #${row.consultorio_padre_id}`
  )
}
</script>

<template>
  <div class="offices-table-container">
    <el-table
      v-loading="loading"
      :data="tree"
      row-key="id"
      default-expand-all
      :tree-props="{ children: 'children' }"
      empty-text="Sin consultorios registrados"
      class="offices-table desktop-table-content"
    >
      <el-table-column prop="nombre" label="Consultorio" min-width="220">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            class="office-name office-open"
            :aria-label="`Ver servicios de ${row.nombre}`"
            @click="emit('open', row)"
            >{{ row.nombre }}</el-button
          >
          <div class="office-meta">
            <span>{{ row.codigo }}</span>
            <span
              class="office-status"
              :class="{ 'office-status-inactive': !row.activo || row.activo_efectivo === false }"
              >{{ statusLabel(row) }}</span
            >
          </div>
          <p v-if="row.consultorio_padre_id !== null" class="office-parent">
            Subconsultorio de {{ parentName(row) }}
          </p>
        </template>
      </el-table-column>
      <el-table-column label="Establecimiento" min-width="200">
        <template #default="{ row }">{{ establishmentName(row) }}</template>
      </el-table-column>
      <el-table-column :label="directory ? 'Servicio / especialidad' : 'Área'" min-width="180">
        <template #default="{ row }">
          <span>{{ areaName(row) }}</span>
          <p v-if="directory" class="office-service-names">{{ serviceNames(row) }}</p>
          <details v-else class="office-services">
            <summary
              class="office-services-toggle"
              :aria-label="`Servicios de ${row.nombre}: ${serviceSummary(row)}`"
            >
              {{ serviceSummary(row) }}
            </summary>
            <p class="office-service-names">{{ serviceNames(row) }}</p>
          </details>
        </template>
      </el-table-column>
      <el-table-column label="Acciones" width="224">
        <template #default="{ row }">
          <OfficeActions
            :row="row"
            @open="emit('open', $event)"
            @edit="emit('edit', $event)"
            @assignments="emit('assignments', $event)"
            @deactivate="emit('deactivate', $event)"
            @reactivate="emit('reactivate', $event)"
          />
        </template>
      </el-table-column>
    </el-table>
    <div v-loading="loading" class="office-mobile-list" :aria-busy="loading">
      <p v-if="!mobileRows.length" class="mobile-empty">Sin consultorios registrados</p>
      <article v-for="row in mobileRows" :key="row.id" class="office-mobile-row">
        <div class="mobile-heading">
          <h3 class="mobile-name">
            <el-button
              link
              type="primary"
              class="office-open"
              :aria-label="`Ver servicios de ${row.nombre}`"
              @click="emit('open', row)"
              >{{ row.nombre }}</el-button
            >
          </h3>
          <el-tag
            :type="row.activo && row.activo_efectivo !== false ? 'success' : 'danger'"
            size="small"
          >
            {{ statusLabel(row) }}
          </el-tag>
        </div>
        <p class="mobile-context">{{ row.codigo }} · {{ establishmentName(row) }}</p>
        <p v-if="directory" class="mobile-context">{{ serviceNames(row) }}</p>
        <p v-if="row.consultorio_padre_id !== null" class="mobile-parent">
          Subconsultorio de {{ parentName(row) }}
        </p>
        <OfficeActions
          :row="row"
          @open="emit('open', $event)"
          @edit="emit('edit', $event)"
          @assignments="emit('assignments', $event)"
          @deactivate="emit('deactivate', $event)"
          @reactivate="emit('reactivate', $event)"
        />
        <details class="mobile-details">
          <summary class="mobile-details-toggle">Ver detalles</summary>
          <dl class="mobile-detail-list">
            <dt class="mobile-detail-label">Área</dt>
            <dd class="mobile-detail-value">{{ areaName(row) }}</dd>
            <dt class="mobile-detail-label">Servicios de atención</dt>
            <dd class="mobile-detail-value">{{ serviceNames(row) }}</dd>
            <dt class="mobile-detail-label">Consultorio padre</dt>
            <dd class="mobile-detail-value">{{ parentName(row) }}</dd>
          </dl>
        </details>
      </article>
    </div>
  </div>
</template>

<style scoped>
.offices-table-container {
  container-type: inline-size;
}
.offices-table :deep(.cell) {
  word-break: normal;
  overflow-wrap: anywhere;
}
.offices-table :deep(.el-table__cell) {
  padding-block: 12px;
  vertical-align: top;
}
.office-name {
  font-weight: 500;
}
.office-open {
  color: color-mix(in srgb, var(--el-color-primary) 65%, var(--el-text-color-primary));
  height: auto;
  white-space: normal;
  text-align: left;
  line-height: 1.5;
  font-size: inherit;
  font-weight: 600;
}
.office-open :deep(span) {
  overflow-wrap: anywhere;
}
.office-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  margin-top: 2px;
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.office-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.office-status::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--el-color-success-dark-2);
}
.office-status-inactive::before {
  background: var(--el-color-danger-dark-2);
}
.office-parent {
  margin: 2px 0 0;
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.office-services {
  margin-top: 2px;
  font-size: 12px;
}
.office-services-toggle {
  width: fit-content;
  min-height: 24px;
  color: var(--el-text-color-regular);
  cursor: pointer;
}
.office-services-toggle:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.office-service-names {
  margin: 4px 0 0;
  line-height: 1.6;
}
.office-mobile-list {
  display: none;
}
@container (max-width: 784px) {
  .desktop-table-content {
    display: none;
  }
  .office-mobile-list {
    display: block;
    min-height: 80px;
  }
}
.office-mobile-row :deep(.office-actions .el-button) {
  min-height: 44px;
}
.office-mobile-row {
  padding-block: 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  overflow-wrap: anywhere;
}
.office-mobile-row:first-child {
  padding-top: 8px;
}
.mobile-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.mobile-name {
  margin: 0;
  font-size: 16px;
  line-height: 1.5;
}
.mobile-heading :deep(.el-tag) {
  flex-shrink: 0;
  margin-top: 3px;
}
.mobile-context,
.mobile-parent {
  margin: 4px 0 12px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.mobile-parent {
  margin-top: -4px;
}
.mobile-details {
  margin-top: 8px;
}
.mobile-details-toggle {
  display: list-item;
  width: fit-content;
  min-height: 44px;
  align-content: center;
  cursor: pointer;
  color: var(--el-text-color-regular);
}
.mobile-details-toggle:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.mobile-detail-list {
  margin: 4px 0 0;
}
.mobile-detail-label {
  margin-top: 12px;
  font-weight: 600;
  font-size: 13px;
}
.mobile-detail-value {
  margin: 4px 0 0;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.mobile-empty {
  margin: 0;
  padding-block: 24px;
  text-align: center;
  color: var(--el-text-color-regular);
}
</style>
