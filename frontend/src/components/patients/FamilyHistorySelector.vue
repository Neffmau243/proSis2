<script setup lang="ts">
import { computed } from 'vue'

import type { FamilyHistoryCatalogItem } from '@/services/catalogos'
import { normalizeFamilyHistory, splitFamilyHistory } from '@/utils/familyHistory'

const props = withDefaults(
  defineProps<{
    modelValue: string | null
    options: FamilyHistoryCatalogItem[]
    disabled?: boolean
    loading?: boolean
  }>(),
  { disabled: false, loading: false },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const partialParts = computed(() => {
  const value = normalizeFamilyHistory(props.modelValue)
  if (!value) return { prefix: '', number: '' }
  const complete = splitFamilyHistory(value)
  if (complete) return complete
  const partial = value.match(/^([A-Z0-9]{0,4})-(\d{0,24})$/)
  return partial ? { prefix: partial[1]!, number: partial[2]! } : null
})
const selectedPrefix = computed({
  get: () => partialParts.value?.prefix ?? '',
  set: (prefix: string) => {
    if (!prefix) {
      emit('update:modelValue', null)
      return
    }
    emitParts(prefix, partialParts.value?.number ?? '')
  },
})
const familyNumber = computed({
  get: () => partialParts.value?.number ?? '',
  set: (value: string) => emitParts(selectedPrefix.value, value.replace(/\D/g, '').slice(0, 24)),
})
const colorOptions = computed(() => props.options.filter((option) => option.tipo === 'COLOR'))
const sectorOptions = computed(() => props.options.filter((option) => option.tipo === 'SECTOR'))
const selectedOption = computed(() =>
  props.options.find((option) => option.codigo === selectedPrefix.value),
)
const completedCode = computed(() => splitFamilyHistory(props.modelValue))
const legacyValue = computed(() => {
  const value = normalizeFamilyHistory(props.modelValue)
  if (!value || partialParts.value) return null
  return value
})

function emitParts(prefix: string, number: string): void {
  if (!prefix && !number) {
    emit('update:modelValue', null)
    return
  }
  emit('update:modelValue', `${prefix}-${number}`)
}
</script>

<template>
  <div class="family-history-selector">
    <el-select
      v-model="selectedPrefix"
      class="family-history-selector__prefix"
      clearable
      filterable
      :disabled="disabled"
      :loading="loading"
      aria-label="Color o sector de historia familiar"
      placeholder="Color o sector"
    >
      <el-option-group v-if="colorOptions.length" label="Colores">
        <el-option
          v-for="option in colorOptions"
          :key="option.codigo"
          :label="`${option.nombre} (${option.codigo})`"
          :value="option.codigo"
        >
          <span
            class="family-history-selector__swatch"
            :style="{ backgroundColor: option.color_hex ?? undefined }"
            aria-hidden="true"
          />
          <span>{{ option.nombre }}</span>
          <span class="family-history-selector__option-code">{{ option.codigo }}</span>
        </el-option>
      </el-option-group>
      <el-option-group v-if="sectorOptions.length" label="Sectores">
        <el-option
          v-for="option in sectorOptions"
          :key="option.codigo"
          :label="`${option.nombre} (${option.codigo})`"
          :value="option.codigo"
        >
          <span class="family-history-selector__sector" aria-hidden="true">S</span>
          <span>{{ option.nombre }}</span>
          <span class="family-history-selector__option-code">{{ option.codigo }}</span>
        </el-option>
      </el-option-group>
      <template #label>
        <span v-if="selectedOption" class="family-history-selector__selected">
          <span
            v-if="selectedOption.color_hex"
            class="family-history-selector__swatch"
            :style="{ backgroundColor: selectedOption.color_hex }"
            aria-hidden="true"
          />
          <span class="family-history-selector__selected-name" :title="selectedOption.nombre">
            {{ selectedOption.nombre }}
          </span>
        </span>
      </template>
    </el-select>

    <el-input
      v-model="familyNumber"
      class="family-history-selector__number"
      :disabled="disabled"
      :maxlength="24"
      inputmode="numeric"
      aria-label="Número de historia familiar"
      placeholder="N.° familiar"
    />

    <span
      v-if="completedCode"
      class="family-history-selector__code"
      :title="`Código guardado: ${modelValue}`"
    >
      {{ modelValue }}
    </span>
    <span v-else-if="legacyValue" class="family-history-selector__legacy">
      Valor anterior: {{ legacyValue }}. Seleccione un valor para reemplazarlo.
    </span>
  </div>
</template>

<style scoped>
.family-history-selector {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(10ch, 0.65fr);
  gap: 4px;
  align-items: center;
  width: 100%;
  min-width: 0;
}

.family-history-selector__prefix,
.family-history-selector__number {
  min-width: 0;
}

.family-history-selector__prefix :deep(.el-select__wrapper),
.family-history-selector__number :deep(.el-input__wrapper) {
  padding-inline: 6px;
}

.family-history-selector__prefix :deep(.el-select__wrapper) {
  gap: 4px;
}

.family-history-selector__swatch {
  display: inline-block;
  flex-shrink: 0;
  width: 12px;
  height: 12px;
  margin-right: 4px;
  border: 1px solid rgb(31 41 55 / 35%);
  border-radius: 3px;
  vertical-align: -1px;
}

.family-history-selector__sector {
  display: inline-grid;
  width: 16px;
  height: 16px;
  margin-right: 5px;
  place-items: center;
  border-radius: 3px;
  color: #304f6d;
  background: #e4edf6;
  font-size: 10px;
  font-weight: 700;
}

.family-history-selector__option-code {
  float: right;
  margin-left: 14px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.family-history-selector__selected {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  max-width: 100%;
}

.family-history-selector__selected-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.family-history-selector__code {
  grid-column: 1 / -1;
  justify-self: end;
  min-width: 0;
  max-width: 100%;
  color: var(--registration-ink, #304f6d);
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.family-history-selector__legacy {
  grid-column: 1 / -1;
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--el-color-warning-dark-2);
  font-size: 11px;
  line-height: 1.35;
}
</style>
