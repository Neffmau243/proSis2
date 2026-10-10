<script setup lang="ts">
import type { NutritionalTableRow } from '@/utils/nutritionalDisplay'

defineProps<{
  rows: NutritionalTableRow[]
  label?: string
}>()
</script>

<template>
  <div class="nutrition-table-wrap">
    <table class="nutrition-table" :aria-label="label || 'Indicadores nutricionales'">
      <tbody>
        <tr v-for="row in rows" :key="row.key">
          <th scope="row">{{ row.label }}</th>
          <td>{{ row.value }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.nutrition-table-wrap {
  overflow-x: auto;
}

.nutrition-table {
  width: 100%;
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}

.nutrition-table th,
.nutrition-table td {
  padding: 5px 7px;
  border-top: 1px solid #c1d1df;
  text-align: left;
  line-height: 1.25;
}

.nutrition-table th {
  width: 42%;
  color: #0757a6;
  font-weight: 500;
}

.nutrition-table td {
  color: #111827;
  font-weight: 700;
}

@media (max-width: 480px) {
  .nutrition-table th,
  .nutrition-table td {
    padding-inline: 4px;
  }
}
</style>
