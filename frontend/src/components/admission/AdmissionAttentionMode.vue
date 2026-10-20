<script setup lang="ts">
import type { AttentionCreatePayload } from '@/services/atenciones'

const mode = defineModel<AttentionCreatePayload['modalidad_atencion_codigo']>({ required: true })
</script>

<template>
  <div class="attention-mode-control">
    <el-form-item label="Modalidad de atención" prop="modalidad_atencion_codigo">
      <el-radio-group
        v-model="mode"
        class="attention-mode-selector"
        aria-label="Modalidad de atención"
      >
        <el-radio value="AMBULATORIA">Ambulatoria</el-radio>
        <el-radio value="REFERENCIA">Referencia</el-radio>
        <el-radio value="EMERGENCIA">Emergencia</el-radio>
      </el-radio-group>
    </el-form-item>
  </div>
</template>

<style scoped>
.attention-mode-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.attention-mode-selector :deep(.el-radio) {
  margin-right: 0;
}
</style>
