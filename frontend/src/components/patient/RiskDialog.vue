<template>
  <el-dialog
    :model-value="modelValue"
    :title="riesgo ? 'Editar periodo de riesgo' : 'Agregar periodo de riesgo'"
    width="min(520px, 94vw)"
    :close-on-click-modal="!saving"
    :close-on-press-escape="!saving"
    :show-close="!saving"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="dialog-alert"
    />

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving">
      <el-form-item label="Grupo de riesgo" prop="grupo_riesgo_id">
        <RiskGroupSelect
          v-model="form.grupo_riesgo_id"
          :groups="gruposRiesgo"
          :disabled="riesgo !== null"
        />
      </el-form-item>
      <el-form-item label="Fecha de inicio" prop="fecha_inicio">
        <el-date-picker
          v-model="form.fecha_inicio"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
          :disabled="riesgo !== null"
        />
      </el-form-item>
      <el-form-item label="Fecha de fin">
        <el-date-picker
          v-model="form.fecha_fin"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
          clearable
          placeholder="Sin fecha de fin (vigente)"
        />
      </el-form-item>
      <p v-if="sourceAttentionId || riesgo?.atencion_origen_id">
        Origen: atención #{{ sourceAttentionId || riesgo?.atencion_origen_id }}. La confirmación
        conserva la valoración guardada.
      </p>
      <el-form-item
        :label="modern ? 'Motivo y evaluación profesional' : 'Observación'"
        prop="observacion"
      >
        <el-input
          v-model="form.observacion"
          type="textarea"
          :rows="2"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
      <el-form-item v-if="!form.fecha_fin" label="Próximo control">
        <el-date-picker
          v-model="form.fecha_proximo_control"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item v-if="form.fecha_fin" label="Motivo de cierre" prop="motivo_cierre">
        <el-input v-model="form.motivo_cierre" type="textarea" :rows="2" maxlength="500" />
      </el-form-item>
      <p class="risk-help">
        Guardar registra su confirmación profesional. No genera diagnósticos CIE-10 ni completa
        tamizajes. La fecha de fin es el último día del periodo.
      </p>
    </el-form>

    <template #footer>
      <el-button :disabled="saving" @click="emit('update:modelValue', false)">Cancelar</el-button>
      <el-button type="primary" :loading="saving" @click="save">Guardar</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import RiskGroupSelect from './RiskGroupSelect.vue'
import type { FormInstance, FormRules } from 'element-plus'

import {
  pacientes,
  type PatientRisk,
  type RiskCreatePayload,
  type RiskUpdatePayload,
} from '@/services/pacientes'
import type { RiskGroupCatalogItem } from '@/services/catalogos'

const props = defineProps<{
  modelValue: boolean
  patientId: number
  /** Cuando se pasa, el diálogo edita; si no, crea. */
  riesgo: PatientRisk | null
  gruposRiesgo: RiskGroupCatalogItem[]
  sourceAttentionId?: number | null
  initialCode?: string
  initialReason?: string
  initialDate?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [riesgo: PatientRisk]
}>()

const formRef = ref<FormInstance>()
const saving = ref(false)
const errorMessage = ref<string | null>(null)

const form = reactive({
  grupo_riesgo_id: null as number | null,
  fecha_inicio: '',
  fecha_fin: null as string | null,
  observacion: '',
  fecha_proximo_control: null as string | null,
  motivo_cierre: '',
})
const modern = computed(() =>
  ['NUT_HALLAZGO', 'NUT_CRECIMIENTO', 'NUT_RIESGO_EVALUADO'].includes(
    props.gruposRiesgo.find((g) => g.id === form.grupo_riesgo_id)?.codigo ?? '',
  ),
)

const rules: FormRules = {
  grupo_riesgo_id: [
    { required: true, message: 'Seleccione el grupo de riesgo.', trigger: 'change' },
  ],
  fecha_inicio: [{ required: true, message: 'Indique la fecha de inicio.', trigger: 'change' }],
  observacion: [
    {
      validator: (_rule, value, callback) =>
        callback(
          modern.value && !value?.trim()
            ? new Error('Explique el motivo del seguimiento.')
            : undefined,
        ),
      trigger: 'blur',
    },
  ],
  motivo_cierre: [
    {
      validator: (_rule, value, callback) =>
        callback(
          modern.value && form.fecha_fin && !value?.trim()
            ? new Error('Indique el motivo de cierre.')
            : undefined,
        ),
      trigger: 'blur',
    },
  ],
}

function init(): void {
  errorMessage.value = null
  const source = props.riesgo
  form.grupo_riesgo_id =
    source?.grupo_riesgo_id ??
    props.gruposRiesgo.find((g) => g.codigo === props.initialCode)?.id ??
    null
  form.fecha_inicio = source?.fecha_inicio ?? props.initialDate ?? ''
  form.fecha_fin = source?.fecha_fin ?? null
  form.observacion = source?.observacion ?? props.initialReason ?? ''
  form.fecha_proximo_control = source?.fecha_proximo_control ?? null
  form.motivo_cierre = source?.motivo_cierre ?? ''
}

// Suggested follow-up mounts this dialog already open. Initialize that first
// render as well as later opens, before the professional edits the values.
watch(
  () => props.modelValue,
  (open) => {
    if (open) init()
  },
  { immediate: true },
)

async function save(): Promise<void> {
  if (saving.value) return
  saving.value = true
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    saving.value = false
    return
  }

  errorMessage.value = null
  try {
    const saved = props.riesgo
      ? await pacientes.updateRisk(
          props.patientId,
          props.riesgo.grupo_riesgo_id,
          props.riesgo.fecha_inicio,
          {
            fecha_fin: form.fecha_fin,
            observacion: form.observacion || null,
            fecha_proximo_control: form.fecha_fin ? null : form.fecha_proximo_control,
            motivo_cierre: form.fecha_fin ? form.motivo_cierre || null : null,
          } satisfies RiskUpdatePayload,
        )
      : await pacientes.addRisk(props.patientId, {
          grupo_riesgo_id: form.grupo_riesgo_id!,
          fecha_inicio: form.fecha_inicio,
          fecha_fin: form.fecha_fin,
          observacion: form.observacion || null,
          atencion_origen_id: props.sourceAttentionId ?? null,
          fecha_proximo_control: form.fecha_fin ? null : form.fecha_proximo_control,
          motivo_cierre: form.fecha_fin ? form.motivo_cierre || null : null,
        } satisfies RiskCreatePayload)

    emit('saved', saved)
    emit('update:modelValue', false)
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo guardar el periodo de riesgo.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.dialog-alert {
  margin-bottom: 16px;
}
.risk-help {
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
</style>
