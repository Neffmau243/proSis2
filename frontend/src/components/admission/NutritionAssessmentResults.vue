<script setup lang="ts">
import { computed, useId } from 'vue'
import { ElInput } from 'element-plus'
import NutritionIndicatorsTable from '@/components/admission/NutritionIndicatorsTable.vue'
import type { CareGroupCode, NutritionalIndicatorsPreview } from '@/services/atenciones'
import {
  nutritionalBmiSummary,
  nutritionalRows,
  nutritionalTableRows,
  type NutritionalReferenceGroup,
  type NutritionalTableRow,
} from '@/utils/nutritionalDisplay'

const props = defineProps<{
  careGroup: CareGroupCode
  referenceGroup: NutritionalReferenceGroup
  ageMonths: number | null
  result: NutritionalIndicatorsPreview | null
  loading: boolean
  error: string | null
}>()

const general = computed(() => props.careGroup === 'NINOS_ADOLESCENTES_ADULTOS_MAYORES')
const id = useId()
const pendingValue = computed(() => (props.loading ? 'Calculando…' : 'No disponible'))
const rows = computed<NutritionalTableRow[]>(() => {
  if (!general.value) {
    return nutritionalTableRows(
      props.result,
      props.careGroup === 'GESTANTES' ? 'GESTANTE' : 'PUERPERA',
      pendingValue.value,
    )
  }
  // The general view retains the original growth indicators at every age.
  // An inapplicable indicator is never substituted with a BMI result.
  const values = nutritionalRows({ ...props.result, grupo_referencia: props.referenceGroup })
  return (['pe', 'te', 'pt'] as const).map((key, index) => {
    const outsideWeightAge = key === 'pe' && props.ageMonths != null && props.ageMonths > 120
    const value = outsideWeightAge ? 'No aplica' : values[index]!.value
    return {
      key,
      label: { pe: 'P/E', te: 'T/E', pt: 'P/T' }[key],
      value: value === 'No aplica' ? value : props.result ? value : pendingValue.value,
    }
  })
})
const bmiSummary = computed(() => (general.value ? nutritionalBmiSummary(props.result) : ''))
const applicability = computed(() => {
  if (!general.value) return ''
  if (props.referenceGroup === 'ADULTO' || props.referenceGroup === 'ADULTO_MAYOR')
    return 'P/E, T/E y P/T no aplican a esta edad. La valoración se realiza por IMC.'
  if (props.referenceGroup === 'ESCOLAR')
    return 'P/E tiene referencia hasta los 10 años; T/E e IMC/edad, hasta los 19. P/T corresponde a la referencia infantil de 0 a 5 años.'
  return ''
})
</script>

<template>
  <div
    class="nutrition-results"
    :data-care-group="careGroup"
    :aria-busy="loading"
    aria-live="polite"
  >
    <div
      v-if="general"
      class="nutrition-results__diagnoses"
      role="group"
      aria-label="Diagnósticos de peso/edad, talla/edad y peso/talla"
    >
      <span class="nutrition-results__diagnosis-title">DIAGNÓSTICO</span>
      <div class="nutrition-results__diagnosis-fields">
        <div v-for="row in rows" :key="row.key" class="nutrition-results__diagnosis-row">
          <label :for="`${id}-${row.key}`" class="nutrition-results__diagnosis-label">{{
            row.label
          }}</label>
          <ElInput
            :id="`${id}-${row.key}`"
            class="nutrition-results__diagnosis-value"
            :model-value="row.value"
            :title="row.value"
            :aria-label="`Diagnóstico ${row.label}`"
            readonly
          />
        </div>
      </div>
    </div>
    <NutritionIndicatorsTable
      v-else
      :rows="rows"
      :label="
        careGroup === 'GESTANTES'
          ? 'Valoración nutricional de gestantes'
          : 'Valoración nutricional de puérperas'
      "
    />
    <p v-if="bmiSummary" class="nutrition-results__bmi">{{ bmiSummary }}</p>
    <p v-if="applicability" class="nutrition-results__note">{{ applicability }}</p>
    <p v-if="error" class="nutrition-results__error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.nutrition-results__diagnoses {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--admission-space, 8px);
  align-items: center;
}
.nutrition-results__diagnosis-title,
.nutrition-results__diagnosis-label {
  color: var(--admission-ink, var(--el-text-color-regular));
  font-size: 12px;
}
.nutrition-results__diagnosis-fields {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.nutrition-results__diagnosis-row {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr);
  gap: var(--admission-space, 8px);
  align-items: center;
}
.nutrition-results__diagnosis-label {
  text-align: right;
}
.nutrition-results__diagnosis-value {
  width: 100%;
  min-width: 0;
}
.nutrition-results__bmi,
.nutrition-results__note,
.nutrition-results__error {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.nutrition-results__bmi {
  color: var(--el-text-color-primary);
  font-weight: 600;
}
.nutrition-results__note {
  color: var(--el-text-color-regular);
}
.nutrition-results__error {
  color: var(--el-color-danger);
}
</style>
