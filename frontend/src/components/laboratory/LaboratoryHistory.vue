<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import type { Attention } from '@/services/atenciones'
import type { Patient } from '@/services/pacientes'

const props = defineProps<{
  entries: Attention[]
  patient: Patient | null
  loading: boolean
  error: string
  total: number
  page: number
  canRead: boolean
  hasOffice: boolean
}>()
const emit = defineEmits<{ refresh: []; page: [value: number]; open: [attention: Attention] }>()
const selectedId = shallowRef<number | null>(null)
const selected = computed(
  () => props.entries.find((row) => row.id === selectedId.value) ?? props.entries[0],
)
function date(value: string): string {
  return value.slice(0, 10).split('-').reverse().join('/')
}
function rowClass({ row }: { row: Attention }): string {
  return row.id === selected.value?.id ? 'lab-history__selected' : ''
}
</script>

<template>
  <section class="lab-panel lab-history" aria-labelledby="lab-history-title">
    <header class="lab-history__header">
      <h2 id="lab-history-title" class="lab-panel__title">Registro de atenciones</h2>
      <el-button
        :icon="Refresh"
        size="small"
        :loading="loading"
        :disabled="!patient || !hasOffice || !canRead"
        title="Actualizar registro"
        aria-label="Actualizar registro"
        @click="emit('refresh')"
      />
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table
      v-else
      v-loading="loading"
      :data="entries"
      row-key="id"
      :row-class-name="rowClass"
      size="small"
      border
      height="100%"
      :max-height="300"
      show-overflow-tooltip
      @row-click="(row: Attention) => (selectedId = row.id)"
      :empty-text="
        !canRead
          ? 'No tiene permiso para consultar atenciones.'
          : !patient
            ? 'Seleccione un paciente para consultar su registro.'
            : !hasOffice
              ? 'Seleccione el consultorio de laboratorio.'
              : 'Sin atenciones de laboratorio registradas.'
      "
    >
      <el-table-column label="N° historia" min-width="84">
        <template #default="{ row }">{{
          row.historia_clinica_snapshot || patient?.historia_clinica || '—'
        }}</template>
      </el-table-column>
      <el-table-column label="N° DNI" min-width="82">
        <template #default="{ row }">{{
          row.fua_impresion?.numero_documento || patient?.numero_documento || '—'
        }}</template>
      </el-table-column>
      <el-table-column label="F. atención" min-width="88">
        <template #default="{ row }"
          ><span :title="row.fecha_atencion">{{ date(row.fecha_atencion) }}</span></template
        >
      </el-table-column>
      <el-table-column label="Apellido pat." min-width="75">
        <template #default="{ row }">{{
          row.fua_impresion?.apellido_paterno ?? patient?.apellido_paterno ?? '—'
        }}</template>
      </el-table-column>
      <el-table-column label="Apellido mat." min-width="75">
        <template #default="{ row }">{{
          row.fua_impresion?.apellido_materno ?? patient?.apellido_materno ?? '—'
        }}</template>
      </el-table-column>
      <el-table-column label="Primer nombre" min-width="75">
        <template #default="{ row }">{{
          row.fua_impresion?.primer_nombre ?? patient?.primer_nombre ?? '—'
        }}</template>
      </el-table-column>
      <el-table-column label="Otros nombres" min-width="75">
        <template #default="{ row }">{{
          row.fua_impresion?.otros_nombres ?? patient?.otros_nombres ?? '—'
        }}</template>
      </el-table-column>
      <el-table-column label="Ref. recibida" min-width="100">
        <template #default="{ row }">{{
          row.numero_referencia_ingreso || row.fua_impresion?.referencia_hoja || '—'
        }}</template>
      </el-table-column>
      <el-table-column label="Contrarref. recibida" min-width="110">
        <template #default="{ row }">{{ row.numero_contrarreferencia_ingreso || '—' }}</template>
      </el-table-column>
    </el-table>
    <footer class="lab-history__footer">
      <span v-if="selected" class="lab-history__status"
        >{{ selected.estado }} ·
        <RouterLink
          :to="{ name: 'atencion-detalle', params: { id: selected.id } }"
          :aria-label="`Ver atención ${selected.id}`"
          >Ver #{{ selected.id }}</RouterLink
        ></span
      >
      <el-button
        v-if="selected"
        size="small"
        :disabled="loading || !canRead"
        @click="emit('open', selected)"
      >
        Consultar / reimprimir #{{ selected.id }}
      </el-button>
      <el-pagination
        v-if="total > 10"
        size="small"
        layout="prev, pager, next"
        :page-size="10"
        :total="total"
        :current-page="page"
        @update:current-page="emit('page', $event)"
      />
    </footer>
  </section>
</template>

<style scoped>
.lab-history {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 160px;
}
.lab-history__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--admission-border);
  background: var(--admission-heading);
}
.lab-history__header :deep(.el-button) {
  padding: 2px 5px;
  height: 24px;
}
.lab-history :deep(.el-table) {
  flex: 1;
  min-height: 80px;
  --el-table-border-color: var(--admission-border);
  --el-table-header-bg-color: var(--admission-heading);
}
.lab-history :deep(.el-table__header-wrapper th.el-table__cell) {
  color: var(--admission-ink);
  font-weight: 700;
}
.lab-history :deep(.el-table .cell) {
  padding-inline: 5px;
  font-size: 12px;
  line-height: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
}
.lab-history :deep(.el-table__header-wrapper .cell) {
  font-size: 11px;
  line-height: 1.2;
  white-space: normal;
}
.lab-history :deep(.el-table__cell) {
  padding-block: 3px;
}
.lab-history :deep(tr.lab-history__selected > td) {
  background: var(--el-color-primary-light-9);
}
.lab-history__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 24px;
  padding: 4px 8px;
}
.lab-history__status {
  font-size: 12px;
  color: var(--admission-ink);
}
.lab-history :deep(a) {
  color: var(--el-color-primary-dark-2);
  text-underline-offset: 2px;
}
.lab-history :deep(.el-table__empty-text) {
  line-height: 1.4;
  padding: 6px;
}
</style>
