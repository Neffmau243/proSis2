<script setup lang="ts">
import { computed } from 'vue'
import type { OfficeAssignmentResponse } from '@/services/consultorios'

const props = defineProps<{
  assignment: OfficeAssignmentResponse
  professionalName: string
  today: string
  inactive: boolean
}>()
const emit = defineEmits<{
  edit: [assignment: OfficeAssignmentResponse]
  close: [assignment: OfficeAssignmentResponse]
  origin: [assignment: OfficeAssignmentResponse]
}>()
const finished = computed(
  () => !!props.assignment.fecha_fin && props.assignment.fecha_fin < props.today,
)
</script>

<template>
  <div class="assignment-row-actions">
    <el-button v-if="assignment.heredada" link type="primary" @click="emit('origin', assignment)"
      >Ver origen</el-button
    >
    <template v-else>
      <el-button
        link
        type="primary"
        :disabled="inactive || assignment.profesional_activo === false"
        @click="emit('edit', assignment)"
        >Editar asignación</el-button
      >
      <el-button
        link
        type="primary"
        :disabled="finished"
        :aria-label="`Cerrar asignación de ${professionalName}`"
        @click="emit('close', assignment)"
        >Cerrar</el-button
      >
    </template>
  </div>
</template>

<style scoped>
.assignment-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.assignment-row-actions :deep(.el-button) {
  margin: 0;
}
@media (max-width: 700px) {
  .assignment-row-actions :deep(.el-button) {
    min-height: 44px;
    padding-inline: 8px;
  }
}
</style>
