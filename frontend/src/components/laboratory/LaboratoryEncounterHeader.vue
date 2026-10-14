<script setup lang="ts">
import { computed, inject, shallowRef } from 'vue'
import { topbarActionsKey } from '@/layouts/topbar'

const topbarTarget = inject(topbarActionsKey, shallowRef<HTMLElement | null>(null))
defineProps<{ disabled?: boolean }>()
const model = defineModel<string>({ required: true })
const day = computed({
  get: () => model.value.slice(0, 10),
  set: (value: string) => {
    if (value) model.value = `${value}T${model.value.slice(11, 19)}`
  },
})
const hour = computed({
  get: () => model.value.slice(11, 19),
  set: (value: string) => {
    if (value) model.value = `${day.value}T${value.length === 5 ? `${value}:00` : value}`
  },
})
</script>

<template>
  <Teleport :to="topbarTarget ?? 'body'" :disabled="!topbarTarget">
    <div class="lab-clock">
      <span class="lab-clock__label">Fecha / hora de atención</span>
      <div class="lab-clock__fields">
        <el-input
          v-model="hour"
          type="time"
          step="1"
          :disabled="disabled"
          aria-label="Hora de atención"
        />
        <el-date-picker
          v-model="day"
          type="date"
          format="DD/MM/YYYY"
          value-format="YYYY-MM-DD"
          :clearable="false"
          :disabled="disabled"
          aria-label="Fecha de atención"
        />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.lab-clock {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  align-self: center;
  flex-wrap: wrap;
  gap: 6px 8px;
  min-width: 0;
}
.lab-clock__label {
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.lab-clock__fields {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}
.lab-clock__fields :deep(.el-input:first-child) {
  width: 126px;
}
.lab-clock__fields :deep(.el-date-editor) {
  width: 138px;
}
@media (max-width: 560px) {
  .lab-clock {
    justify-content: flex-start;
  }
  .lab-clock__label {
    flex-basis: 100%;
  }
  .lab-clock__fields {
    flex: 1;
  }
  .lab-clock__fields :deep(.el-input:first-child) {
    flex: 0 1 126px;
    min-width: 0;
  }
  .lab-clock__fields :deep(.el-date-editor) {
    flex: 1 1 138px;
    min-width: 0;
  }
}
</style>
