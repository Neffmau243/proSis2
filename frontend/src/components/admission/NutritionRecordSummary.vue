<script setup lang="ts">
import { computed } from 'vue'
import type { NutritionRecord } from '@/types/nutritionRecord'
import { nutritionSections } from '@/utils/nutritionCapture'
import type { NutritionalTableRow } from '@/utils/nutritionalDisplay'
import NutritionIndicatorsTable from '@/components/admission/NutritionIndicatorsTable.vue'

const props = withDefaults(
  defineProps<{ records: NutritionRecord[]; indicatorRows?: NutritionalTableRow[] }>(),
  { indicatorRows: () => [] },
)
const sections = computed(() =>
  props.records.map((record) => ({
    record,
    groups: nutritionSections
      .map((section) => ({
        title: section.title,
        fields: section.fields
          .filter((field) => record[field.key] != null)
          .map((field) => ({
            label: field.label,
            value:
              typeof record[field.key] === 'boolean'
                ? record[field.key]
                  ? 'Sí'
                  : 'No'
                : record[field.key],
          })),
      }))
      .filter((section) => section.fields.length > 0),
  })),
)
</script>

<template>
  <section class="nutrition-summary" aria-labelledby="nutrition-saved-title">
    <h3 id="nutrition-saved-title">Valoración guardada</h3>
    <p v-if="!records.length">Esta atención no tiene una evaluación nutricional guardada.</p>
    <NutritionIndicatorsTable
      v-if="indicatorRows.length"
      :rows="indicatorRows"
      label="Indicadores nutricionales guardados"
    />
    <div v-for="item in sections" :key="item.record.id" class="nutrition-summary__record">
      <p>
        Evaluación #{{ item.record.id }} · {{ item.record.tipo || 'Grupo histórico no consignado' }}
      </p>
      <dl v-if="!indicatorRows.length" class="nutrition-summary__values">
        <div v-for="key in ['imc', 'waz', 'haz', 'whz'] as const" :key="key">
          <dt>{{ key.toUpperCase() }}</dt>
          <dd>{{ item.record[key] ?? 'Sin resultado guardado' }}</dd>
        </div>
      </dl>
      <section v-for="group in item.groups" :key="group.title">
        <h4>{{ group.title }}</h4>
        <dl class="nutrition-summary__values">
          <div v-for="field in group.fields" :key="field.label">
            <dt>{{ field.label }}</dt>
            <dd>{{ field.value }}</dd>
          </div>
        </dl>
      </section>
    </div>
  </section>
</template>

<style scoped>
.nutrition-summary {
  margin: 24px 0;
}
.nutrition-summary__record {
  margin: 16px 0;
}
.nutrition-summary__values {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 16px;
}
.nutrition-summary__values dt {
  color: var(--el-text-color-regular);
  font-size: 0.875rem;
}
.nutrition-summary__values dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
</style>
