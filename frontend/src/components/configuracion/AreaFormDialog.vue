<script setup lang="ts">
import './careConfiguration.css'
const visible = defineModel<boolean>({ required: true })
const name = defineModel<string>('name', { required: true })
defineProps<{ editing: boolean; saving: boolean; error: string | null }>()
const emit = defineEmits<{ save: [] }>()
</script>
<template>
  <el-dialog
    v-model="visible"
    :title="editing ? 'Editar área' : 'Nueva área'"
    width="min(500px,94vw)"
    class="area-dialog care-config"
    modal-class="care-config-overlay"
    :close-on-click-modal="!saving"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-form label-position="top" @submit.prevent="emit('save')"
      ><el-form-item label="Nombre del área" required
        ><el-input
          v-model="name"
          aria-label="Nombre del área"
          maxlength="150"
          :disabled="saving" /></el-form-item
    ></el-form>
    <p class="area-help">
      {{
        editing
          ? 'El código y los vínculos existentes se conservan.'
          : 'El sistema generará su código. Podrás usar esta área en consultorios de distintos establecimientos.'
      }}
    </p>
    <template #footer
      ><el-button :disabled="saving" @click="visible = false">Cancelar</el-button
      ><el-button type="primary" :loading="saving" @click="emit('save')"
        >Guardar área</el-button
      ></template
    >
  </el-dialog>
</template>
<style scoped>
.area-help {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  font-size: 13px;
}
@media (max-width: 600px) {
  :global(.area-dialog .el-button),
  :global(.area-dialog .el-input__wrapper) {
    min-height: 44px;
  }
}
</style>
