<script setup lang="ts" generic="T extends string">
defineProps<{
  options: { value: T; label: string; disabled?: boolean }[]
  label: string
  disabled?: boolean
}>()
const model = defineModel<T | null>({ required: true })
</script>

<template>
  <div class="single-choice" role="group" :aria-label="label">
    <el-checkbox
      v-for="option in options"
      :key="option.value"
      :model-value="model === option.value"
      :disabled="disabled || option.disabled"
      @change="model = option.value"
      >{{ option.label }}</el-checkbox
    >
  </div>
</template>

<style scoped>
.single-choice {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 14px;
}
.single-choice :deep(.el-checkbox) {
  height: 26px;
  margin-right: 0;
}
.single-choice :deep(.el-checkbox__label) {
  font-size: 12px;
  white-space: normal;
}
</style>
