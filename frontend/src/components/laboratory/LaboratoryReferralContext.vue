<script setup lang="ts">
import AdmissionReferralFields from '@/components/admission/AdmissionReferralFields.vue'
import type { AttentionCreatePayload } from '@/services/atenciones'

defineProps<{ disabled: boolean }>()
const mode = defineModel<AttentionCreatePayload['modalidad_atencion_codigo']>('mode', {
  required: true,
})
const renipress = defineModel<string>('renipress', { required: true })
const name = defineModel<string>('name', { required: true })
const sheet = defineModel<string>('sheet', { required: true })
</script>

<template>
  <section class="lab-referral" aria-label="Procedencia de la atención">
    <span id="lab-mode-label">Modalidad de atención</span>
    <el-radio-group v-model="mode" aria-labelledby="lab-mode-label" :disabled="disabled">
      <el-radio value="AMBULATORIA">Ambulatoria</el-radio>
      <el-radio value="REFERENCIA">Referencia</el-radio>
      <el-radio value="EMERGENCIA">Emergencia</el-radio>
    </el-radio-group>
    <template v-if="mode === 'REFERENCIA'">
      <h3 class="lab-referral__title">IPRESS que refiere al paciente</h3>
      <AdmissionReferralFields
        v-model:renipress="renipress"
        v-model:name="name"
        v-model:sheet="sheet"
        :show-sheet="false"
      />
      <p class="lab-referral__help">
        Complete el origen y el N.º de referencia recibida de la ficha. Se conservarán en el FUA de
        esta atención.
      </p>
    </template>
  </section>
</template>

<style scoped>
.lab-referral {
  padding: 6px 8px;
  font-size: 12px;
}
.lab-referral :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 0 12px;
}
.lab-referral :deep(.el-radio) {
  margin-right: 0;
}
.lab-referral__title {
  margin: 6px 0;
  font-size: 12px;
}
.lab-referral__help {
  margin: 4px 0;
  line-height: 1.4;
  color: var(--el-text-color-regular);
}
</style>
