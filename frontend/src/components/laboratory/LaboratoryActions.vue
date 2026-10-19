<script setup lang="ts">
import {
  CircleClose,
  DocumentAdd,
  DocumentCopy,
  DocumentChecked,
  Printer,
} from '@element-plus/icons-vue'
defineProps<{
  saving: boolean
  saved: boolean
  disabled: boolean
  printReady: boolean
  hciReady: boolean
  reason: string
  printReason?: string
}>()
const emit = defineEmits<{ save: []; print: []; additional: []; hci: []; exit: [] }>()
</script>

<template>
  <section class="lab-actions" aria-label="Acciones de laboratorio">
    <p v-if="reason && !saved" class="lab-actions__reason" role="status">{{ reason }}</p>
    <div class="lab-actions__tray">
      <el-button
        class="lab-action lab-action--save"
        type="primary"
        :loading="saving"
        :disabled="saving || (!saved && disabled)"
        :title="saved ? 'Preparar una nueva atención' : reason || 'Guardar la atención'"
        @click="emit('save')"
      >
        <el-icon><DocumentChecked /></el-icon><span>Grabar<br />Nuevo</span>
      </el-button>
      <el-button
        class="lab-action"
        :disabled="saving || !printReady"
        :title="printReason"
        @click="emit('print')"
      >
        <el-icon><Printer /></el-icon><span>Imprimir S.I.S.</span>
      </el-button>
      <el-button
        class="lab-action"
        :disabled="saving || !printReady"
        :title="printReason || 'Imprimir un ejemplar adicional del mismo FUA guardado'"
        @click="emit('additional')"
      >
        <el-icon><DocumentAdd /></el-icon><span>FUA<br />adicional</span>
      </el-button>
      <el-button class="lab-action" :disabled="saving || !hciReady" @click="emit('hci')">
        <el-icon><DocumentCopy /></el-icon><span>Imprimir<br />HCI</span>
      </el-button>
      <el-button
        class="lab-action lab-action--exit"
        type="danger"
        plain
        :disabled="saving"
        @click="emit('exit')"
      >
        <el-icon><CircleClose /></el-icon><span>Salir</span>
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.lab-actions {
  padding: 6px;
  border: 1px solid var(--admission-border);
  border-radius: 4px;
  background: var(--admission-panel);
}
.lab-actions__tray {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
}
.lab-action {
  width: 100%;
  min-width: 0;
  min-height: 48px;
  height: auto;
  margin: 0 !important;
  padding: 4px;
  border-radius: 2px;
  font-size: 11px;
  line-height: 1.2;
  white-space: normal;
}
.lab-action :deep(> span) {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
  line-height: 1.2;
}
.lab-action :deep(.el-icon) {
  margin: 0;
  font-size: 14px;
}
.lab-actions__reason {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
@media (max-width: 480px) {
  .lab-actions__tray {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
