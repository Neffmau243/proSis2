<script setup lang="ts">
import {
  CircleClose,
  CirclePlus,
  EditPen,
  MoreFilled,
  Setting,
  User,
} from '@element-plus/icons-vue'
import type { OfficeResponse } from '@/services/consultorios'

const props = defineProps<{ row: OfficeResponse }>()
const emit = defineEmits<{
  edit: [row: OfficeResponse]
  assignments: [row: OfficeResponse]
  deactivate: [row: OfficeResponse]
  reactivate: [row: OfficeResponse]
  open: [row: OfficeResponse]
}>()

function runSecondaryAction(command: string): void {
  if (command === 'reactivate' && !props.row.activo) emit('reactivate', props.row)
  if (!props.row.activo) return
  if (command === 'deactivate') emit('deactivate', props.row)
}
</script>

<template>
  <div class="office-actions" role="group" :aria-label="`Acciones de ${row.nombre}`">
    <el-button
      type="primary"
      link
      class="services-action"
      :aria-label="`Gestionar servicios de ${row.nombre}`"
      @click="emit('open', row)"
    >
      <el-icon class="action-icon" aria-hidden="true"><Setting /></el-icon>
      <span>Gestionar servicios</span>
    </el-button>
    <el-button
      type="primary"
      link
      class="edit-action"
      :aria-label="`Editar ${row.nombre}`"
      @click="emit('edit', row)"
    >
      <el-icon class="action-icon" aria-hidden="true"><EditPen /></el-icon>
      <span>Editar</span>
    </el-button>
    <el-button
      type="primary"
      link
      class="assignments-action"
      :aria-label="`Asignaciones de ${row.nombre}`"
      @click="emit('assignments', row)"
    >
      <el-icon class="action-icon" aria-hidden="true"><User /></el-icon>
      <span>Profesionales</span>
    </el-button>
    <el-dropdown trigger="click" @command="runSecondaryAction">
      <el-button
        link
        class="more-action"
        :aria-label="`Más acciones de ${row.nombre}`"
        title="Más acciones"
      >
        <el-icon aria-hidden="true"><MoreFilled /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item v-if="!row.activo" command="reactivate" :icon="CirclePlus">
            Reactivar consultorio
          </el-dropdown-item>
          <el-dropdown-item
            command="deactivate"
            :icon="CircleClose"
            :divided="!row.activo"
            :disabled="!row.activo"
            class="deactivate-action"
          >
            Dar de baja
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.office-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.office-actions :deep(.el-button) {
  min-height: 30px;
  margin: 0;
  padding: 0;
  border-radius: 6px;
  font-size: 12px;
  transition:
    background-color 150ms ease-out,
    color 150ms ease-out;
}
.office-actions :deep(.el-button:focus-visible) {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.office-actions :deep(.services-action) {
  flex-basis: 100%;
  justify-content: flex-start;
}
.office-actions :deep(.edit-action),
.office-actions :deep(.services-action) {
  padding-inline: 6px;
  background: var(--el-color-primary-light-9);
  color: color-mix(in srgb, var(--el-color-primary) 65%, var(--el-text-color-primary));
  font-weight: 500;
}
.office-actions :deep(.edit-action:hover),
.office-actions :deep(.edit-action:active),
.office-actions :deep(.services-action:hover),
.office-actions :deep(.services-action:active) {
  background: var(--el-color-primary-light-8);
}
.office-actions :deep(.assignments-action) {
  color: var(--el-text-color-regular);
}
.office-actions :deep(.assignments-action:hover) {
  color: color-mix(in srgb, var(--el-color-primary) 65%, var(--el-text-color-primary));
}
.office-actions :deep(.more-action) {
  width: 28px;
  color: var(--el-text-color-regular);
  font-size: 16px;
}
.office-actions :deep(.more-action:hover),
.office-actions :deep(.more-action[aria-expanded='true']) {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}
.action-icon {
  margin-right: 4px;
  font-size: 14px;
}
.office-actions :deep(.el-button .el-icon + span) {
  margin-left: 0;
}
.deactivate-action:not(.is-disabled) {
  color: color-mix(in srgb, var(--el-color-danger) 65%, var(--el-text-color-primary));
  --el-dropdown-menuItem-hover-color: color-mix(
    in srgb,
    var(--el-color-danger) 65%,
    var(--el-text-color-primary)
  );
  --el-dropdown-menuItem-hover-fill: var(--el-color-danger-light-9);
}
@media (max-width: 600px) {
  .office-actions :deep(.el-button) {
    min-height: 44px;
  }
  .office-actions :deep(.more-action) {
    width: 44px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .office-actions :deep(.el-button) {
    transition: none;
  }
}
</style>
