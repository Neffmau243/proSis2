<script setup lang="ts">
import { computed } from 'vue'
import type { RiskGroupCatalogItem } from '@/services/catalogos'

const props = defineProps<{
  modelValue: number | null
  groups: RiskGroupCatalogItem[]
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const legacy = new Set(['NUT_DELGADEZ', 'NUT_DESN_AGUDA', 'NUT_DESN_GLOBAL', 'NUT_TALLA_BAJA'])
const sections = computed(() => [
  {
    label: 'Evaluación y seguimiento',
    groups: props.groups.filter((g) => !legacy.has(g.codigo ?? '')),
  },
  { label: 'Legado ETLSIS', groups: props.groups.filter((g) => legacy.has(g.codigo ?? '')) },
])
</script>

<template>
  <el-select
    :model-value="modelValue"
    :disabled="disabled"
    filterable
    clearable
    placeholder="Seleccione"
    style="width: 100%"
    @update:model-value="emit('update:modelValue', $event || null)"
  >
    <el-option-group v-for="section in sections" :key="section.label" :label="section.label">
      <el-option
        v-for="group in section.groups"
        :key="group.id"
        :label="group.nombre"
        :value="group.id"
      />
    </el-option-group>
  </el-select>
</template>
