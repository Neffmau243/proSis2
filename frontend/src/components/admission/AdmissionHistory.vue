<script setup lang="ts">
import type { Attention } from '@/services/atenciones'
import { nutritionalRows, nutritionalStatus, nutritionalHistoryValue } from '@/utils/nutritionalDisplay'

function nutritionSummary(row: Attention): string {
  return row.valoracion_calculada
    ? [nutritionalStatus(row.valoracion_calculada), ...nutritionalRows(row.valoracion_calculada).map(item => `${item.label}: ${item.value}`)].filter(Boolean).join('; ')
    : row.imc != null ? `IMC: ${row.imc}. Sin clasificación histórica guardada` : 'Sin valoración histórica calculada'
}

defineProps<{
  entries: Attention[]
  loading: boolean
  error?: string | null
  compact?: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

function formatDate(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('es-PE')
}
</script>

<template>
  <el-card
    class="admission-history"
    :class="{ 'admission-history--compact': compact }"
    shadow="never"
  >
    <header class="admission-history__header">
      <div>
        <h3 class="admission-history__title">Historial de atenciones del paciente</h3>
      </div>
      <el-button size="small" :loading="loading" @click="emit('refresh')">Refrescar</el-button>
    </header>

    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-else class="admission-history__table-wrap">
      <el-table
        :data="entries"
        :height="compact ? '100%' : undefined"
        :max-height="compact ? 300 : 180"
        table-layout="fixed"
        :show-overflow-tooltip="compact"
        v-loading="loading"
        size="small"
        class="admission-history__table"
        empty-text="Sin atenciones registradas"
      >
        <el-table-column label="N.° historia" width="108">
          <template #default="{ row }">{{ row.historia_clinica_snapshot || '—' }}</template>
        </el-table-column>
        <el-table-column label="Fecha atención" width="82">
          <template #default="{ row }">{{ formatDate(row.fecha_atencion) }}</template>
        </el-table-column>
        <el-table-column label="Edad del paciente" width="118">
          <template #default="{ row }">
            {{ row.edad_detallada ?? (row.edad_anios !== null ? `${row.edad_anios} años` : '—') }}
          </template>
        </el-table-column>
        <el-table-column label="Peso" width="46" align="center">
          <template #default="{ row }">{{ row.peso_kg ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="Talla" width="46" align="center">
          <template #default="{ row }">{{ row.talla_cm ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="Diast." width="50" align="center">
          <template #default="{ row }">{{ row.presion_diastolica ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="Sist." width="47" align="center">
          <template #default="{ row }">{{ row.presion_sistolica ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="IMC" :width="compact ? 66 : 50" align="center">
          <template #default="{ row }">
            <el-tooltip :content="nutritionSummary(row)" placement="top">
              <span tabindex="0" :aria-label="nutritionSummary(row)">{{ row.imc ?? '—' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="P/E" :width="compact ? 70 : 42" align="center">
          <template #default="{ row }">{{ nutritionalHistoryValue(row, 'pe') }}</template>
        </el-table-column>
        <el-table-column label="T/E" :width="compact ? 70 : 42" align="center">
          <template #default="{ row }">{{ nutritionalHistoryValue(row, 'te') }}</template>
        </el-table-column>
        <el-table-column label="P/T" :width="compact ? 70 : 42" align="center">
          <template #default="{ row }">{{ nutritionalHistoryValue(row, 'pt') }}</template>
        </el-table-column>
        <el-table-column label="Consultorio" min-width="124">
          <template #default="{ row }">
            <span>{{ row.consultorio_ruta || row.consultorio_nombre || '—' }}</span>
            <div v-if="row.establecimiento_nombre || row.especialidad_nombre">
              {{ [row.establecimiento_nombre, row.especialidad_nombre].filter(Boolean).join(' · ') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Estado" width="82" align="center">
          <template #default="{ row }">
            <el-tag :type="row.estado === 'ANULADO' ? 'danger' : 'success'" size="small">
              {{ row.estado }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="entries.length" class="admission-history__description">
        P/E: peso/edad · T/E: talla/edad · P/T: peso/talla.
        «No aplica»: fuera de la referencia por edad o grupo de atención; no es un fallo del cálculo.
        «—»: sin resultado guardado. En IMC puede consultar el detalle de la valoración.
      </p>
    </div>
  </el-card>
</template>

<style scoped>
.admission-history {
  min-width: 0;
  border-color: var(--admission-border, #b9cbdf);
  border-radius: 4px;
}

.admission-history :deep(.el-card__body) {
  padding: 8px;
}

.admission-history__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.admission-history__title {
  margin: 0;
  color: var(--admission-ink, #304f6d);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
}

.admission-history__description {
  margin: 2px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.admission-history__table-wrap {
  overflow: hidden;
}

.admission-history__table {
  width: 100%;
  min-width: 0;
}

.admission-history__table :deep(.el-table__header-wrapper th.el-table__cell) {
  color: var(--admission-ink, #304f6d);
  background-color: var(--admission-heading, #d4e1ef);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
}

.admission-history__table :deep(.el-table__cell) {
  padding: 4px 0;
  font-size: 12px;
}

.admission-history__table :deep(.el-table__cell .cell) {
  line-height: 1.25;
  overflow-wrap: anywhere;
  white-space: normal;
}

.admission-history--compact {
  display: flex;
  flex-direction: column;
  flex: 1;
  background: var(--admission-panel, #e8eff7);
}
.admission-history--compact :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
  padding: 6px;
}
.admission-history--compact .admission-history__table-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.admission-history--compact .admission-history__table {
  flex: 1;
  min-height: 80px;
}
.admission-history--compact .admission-history__header {
  align-items: center;
  margin: -6px -6px 6px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--admission-border, #b9cbdf);
  background: var(--admission-heading, #d4e1ef);
}
.admission-history--compact .admission-history__title {
  font-size: 13px;
}
.admission-history--compact :deep(.el-table__body .cell) {
  padding-inline: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.admission-history--compact .admission-history__description {
  margin-top: 6px;
  color: var(--admission-ink, #304f6d);
  font-size: 11px;
}

@media (max-width: 680px) {
  .admission-history:not(.admission-history--compact) :deep(.el-card__body) {
    padding: 12px;
  }

  .admission-history:not(.admission-history--compact) .admission-history__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
