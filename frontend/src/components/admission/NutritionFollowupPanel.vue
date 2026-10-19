<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElButton } from 'element-plus'
import RiskDialog from '@/components/patient/RiskDialog.vue'
import type { Attention, NutritionalIndicatorsPreview } from '@/services/atenciones'
import type { RiskGroupCatalogItem } from '@/services/catalogos'
import type { Patient, PatientRisk } from '@/services/pacientes'

const props = defineProps<{
  result: NutritionalIndicatorsPreview | null
  patient: Patient
  groups: RiskGroupCatalogItem[]
  attention?: Attention | null
  canEdit: boolean
}>()
const emit = defineEmits<{ saved: [patient: Patient] }>()
const open = ref(false)
const selected = ref<{ codigo: string; motivo: string } | null>(null)
const evaluation = computed(() => props.result?.seguimiento)
const sourceDate = computed(() => props.attention?.fecha_atencion.slice(0, 10))
function alreadyRecorded(code: string) {
  const id = props.groups.find((g) => g.codigo === code)?.id
  // An open interval starting at this control also overlaps later periods.
  return props.patient.riesgos.some(
    (r) => r.grupo_riesgo_id === id && (!r.fecha_fin || r.fecha_fin >= (sourceDate.value ?? '')),
  )
}
function confirm(suggestion: { codigo: string; motivo: string }) {
  selected.value = suggestion
  open.value = true
}
function saved(risk: PatientRisk) {
  emit('saved', { ...props.patient, riesgos: [...props.patient.riesgos, risk] })
}
</script>

<template>
  <section
    v-if="evaluation"
    class="nutrition-followup"
    aria-label="Evaluación y seguimiento nutricional"
  >
    <h3>
      {{
        attention
          ? `Seguimiento del control guardado · ${sourceDate}`
          : 'Alertas de la valoración actual'
      }}
    </h3>
    <p v-if="evaluation.tendencia.estado === 'COMPARADO'">
      Desde {{ evaluation.tendencia.fecha_anterior }} ({{ evaluation.tendencia.dias }} días): peso
      {{ evaluation.tendencia.cambio_peso_kg }} kg; talla
      {{ evaluation.tendencia.cambio_talla_cm }} cm.
    </p>
    <p v-if="evaluation.tendencia.estado !== 'NO_APLICA'">{{ evaluation.tendencia.mensaje }}</p>
    <p v-if="result?.estado !== 'CALCULADO'">{{ result?.mensaje }}</p>
    <ul v-else-if="evaluation.sugerencias.length">
      <li v-for="suggestion in evaluation.sugerencias" :key="suggestion.codigo">
        <span>{{ suggestion.motivo }}</span>
        <ElButton
          v-if="attention && canEdit"
          size="small"
          :disabled="alreadyRecorded(suggestion.codigo)"
          @click="confirm(suggestion)"
        >
          {{
            alreadyRecorded(suggestion.codigo) ? 'Seguimiento registrado' : 'Confirmar seguimiento'
          }}
        </ElButton>
      </li>
    </ul>
    <p v-else>
      Sin sugerencias automáticas con los datos disponibles. Tamizaje nutricional: no evaluado.
    </p>
    <p class="nutrition-followup__note">
      {{ evaluation.mensaje }}
      {{ attention ? '' : 'Guarde primero la atención para vincular un seguimiento.' }}
    </p>
    <RiskDialog
      v-if="attention && selected"
      v-model="open"
      :patient-id="patient.id"
      :riesgo="null"
      :grupos-riesgo="groups"
      :source-attention-id="attention.id"
      :initial-code="selected.codigo"
      :initial-reason="selected.motivo"
      :initial-date="sourceDate"
      @saved="saved"
    />
  </section>
</template>

<style scoped>
.nutrition-followup {
  border-top: 1px solid var(--el-border-color-light);
  padding: 16px 0;
  color: var(--el-text-color-primary);
}
h3 {
  margin: 0 0 8px;
  font-size: 14px;
}
p,
li {
  margin: 8px 0;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
ul {
  padding-left: 20px;
}
li span {
  display: block;
  margin-bottom: 6px;
}
.nutrition-followup__note {
  color: var(--el-text-color-regular);
  font-size: 12px;
}
</style>
