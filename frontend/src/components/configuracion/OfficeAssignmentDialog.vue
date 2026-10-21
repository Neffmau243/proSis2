<script setup lang="ts">
import { computed, reactive, shallowRef, useTemplateRef, watch } from 'vue'
import type { FormInstance, FormRules, SelectInstance } from 'element-plus'
import type { ProfessionalCatalogItem } from '@/services/catalogos'
import type { OfficeAssignmentCreatePayload } from '@/services/consultorios'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{
  officeName: string
  areaName?: string
  requirementName?: string
  linkArea?: boolean
  professionals: ProfessionalCatalogItem[]
  loading: boolean
  saving: boolean
  error: string | null
}>()
const emit = defineEmits<{
  search: [query: string]
  submit: [payload: OfficeAssignmentCreatePayload]
}>()
const formRef = useTemplateRef<FormInstance>('formRef')
const professionalRef = useTemplateRef<SelectInstance>('professionalRef')
const dateError = shallowRef<string | null>(null)
const form = reactive({
  profesional_id: null as number | null,
  fecha_inicio: '',
  fecha_fin: '',
  es_responsable: false,
})
const errorMessage = computed(() => props.error || dateError.value)
const rules: FormRules = {
  profesional_id: [{ required: true, message: 'Seleccione el profesional.', trigger: 'change' }],
  fecha_inicio: [{ required: true, message: 'Indique la fecha de inicio.', trigger: 'change' }],
}
watch(visible, (open) => {
  if (!open) return
  Object.assign(form, {
    profesional_id: null,
    fecha_inicio: '',
    fecha_fin: '',
    es_responsable: false,
  })
  dateError.value = null
  formRef.value?.clearValidate()
  emit('search', '')
})
function requestClose(): void {
  if (!props.saving) visible.value = false
}
async function submit(): Promise<void> {
  if (props.saving || !(await formRef.value?.validate().catch(() => false))) return
  dateError.value = null
  if (form.fecha_fin && form.fecha_fin < form.fecha_inicio) {
    dateError.value = 'La fecha de fin no puede ser anterior a la fecha de inicio.'
    return
  }
  if (form.profesional_id === null) return
  emit('submit', {
    profesional_id: form.profesional_id,
    fecha_inicio: form.fecha_inicio,
    fecha_fin: form.fecha_fin || null,
    es_responsable: form.es_responsable,
  })
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="Asignar profesional"
    width="min(540px, 94vw)"
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
    @update:model-value="requestClose"
    @opened="professionalRef?.focus()"
  >
    <p class="assignment-context">
      Consultorio: <strong>{{ officeName }}</strong>
    </p>
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="assignment-error"
    />
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :disabled="saving"
      label-position="top"
      @submit.prevent="submit"
    >
      <el-form-item label="Profesional" prop="profesional_id">
        <el-select
          ref="professionalRef"
          v-model="form.profesional_id"
          filterable
          remote
          :remote-method="(query: string) => emit('search', query)"
          :loading="loading"
          placeholder="Busque por nombre o colegiatura"
          no-data-text="Sin profesionales disponibles"
        >
          <el-option
            v-for="item in professionals"
            :key="item.id"
            :label="item.nombre_completo"
            :value="item.id"
          />
        </el-select>
        <p v-if="requirementName" class="assignment-hint">
          Este consultorio requiere {{ requirementName }}. El profesional debe tenerlo registrado.
        </p>
        <p v-else-if="linkArea" class="assignment-hint">
          Al asignar, se vincula también al profesional con el área{{
            areaName ? ` ${areaName}` : ''
          }}
          si aún no la tiene.
        </p>
        <p v-else class="assignment-hint">
          El profesional debe tener el área del consultorio registrada en su ficha.
        </p>
      </el-form-item>
      <el-form-item label="Fecha de inicio" prop="fecha_inicio">
        <el-date-picker v-model="form.fecha_inicio" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="Fecha de fin" prop="fecha_fin">
        <el-date-picker
          v-model="form.fecha_fin"
          type="date"
          value-format="YYYY-MM-DD"
          clearable
          placeholder="Opcional, sin fecha de fin"
        />
      </el-form-item>
      <el-form-item label="Responsable">
        <el-checkbox v-model="form.es_responsable">Es responsable del consultorio</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="requestClose">Cancelar</el-button>
      <el-button type="primary" :loading="saving" @click="submit">Guardar asignación</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.assignment-context {
  margin: 0 0 20px;
  line-height: 1.5;
}
.assignment-error {
  margin-bottom: 16px;
}
.assignment-hint {
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
.el-select,
:deep(.el-date-editor.el-input) {
  width: 100%;
}
</style>
