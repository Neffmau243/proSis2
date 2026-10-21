<script setup lang="ts">
import { computed, reactive, useTemplateRef } from 'vue'
import type { FormInstance, FormRules, InputInstance } from 'element-plus'

import type { StaffCatalogKind, StaffCatalogEntry } from '@/composables/useStaffCatalogs'
import type { StaffCatalogPayload } from '@/services/catalogosPersonal'

const props = defineProps<{
  kind: StaffCatalogKind
  areasOnly?: boolean
  saving: boolean
  error: string | null
  record?: StaffCatalogEntry | null
}>()
const emit = defineEmits<{ submit: [payload: StaffCatalogPayload]; cancel: [] }>()
const formRef = useTemplateRef<FormInstance>('formRef')
const nameRef = useTemplateRef<InputInstance>('nameRef')
const form = reactive({
  nombre: props.record?.nombre ?? '',
  es_area: props.record
    ? Boolean('es_area' in props.record && props.record.es_area)
    : Boolean(props.areasOnly),
})
const maxLength = computed(() => (props.kind === 'profesion' ? 100 : 150))
const isArea = computed(() => form.es_area)
const isBaseArea = computed(() =>
  Boolean(props.record && 'es_area_base' in props.record && props.record.es_area_base),
)
const title = computed(() =>
  props.record
    ? props.kind === 'profesion'
      ? 'Editar profesión'
      : isArea.value
        ? 'Editar área'
        : 'Editar especialidad'
    : props.kind === 'profesion'
      ? 'Nueva profesión'
      : props.areasOnly
        ? 'Nueva área'
        : 'Nueva área o especialidad',
)
const nameLabel = computed(() =>
  props.kind === 'profesion'
    ? 'Nombre de la profesión'
    : isArea.value
      ? 'Nombre del área'
      : 'Nombre de la especialidad',
)
const rules = computed<FormRules>(() => ({
  nombre: [
    { required: true, whitespace: true, message: 'Ingrese el nombre.', trigger: 'blur' },
    {
      min: 2,
      max: maxLength.value,
      message: `Use entre 2 y ${maxLength.value} caracteres.`,
      transform: (value: string) => value.trim(),
      trigger: 'blur',
    },
  ],
}))

async function submit(): Promise<void> {
  if (props.saving || !(await formRef.value?.validate().catch(() => false))) return
  const nombre = form.nombre.trim()
  emit('submit', props.kind === 'especialidad' ? { nombre, es_area: form.es_area } : { nombre })
}

function requestClose(): void {
  if (!props.saving) emit('cancel')
}
</script>

<template>
  <el-dialog
    :model-value="true"
    :title="title"
    width="min(520px, 94vw)"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
    @update:model-value="requestClose"
    @opened="nameRef?.focus()"
  >
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      role="alert"
      class="catalog-form__error"
    />
    <p class="dialog-hint">
      {{
        record
          ? 'El nuevo nombre se mostrará donde se utiliza este registro.'
          : kind === 'profesion'
            ? 'Esta profesión estará disponible en la ficha del personal.'
            : areasOnly
              ? 'El área estará disponible al crear consultorios y asignar profesionales.'
              : 'Elige si registrarás un área de atención o una especialidad del profesional.'
      }}
    </p>
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :disabled="saving"
      label-position="top"
      @submit.prevent="submit"
    >
      <el-form-item v-if="kind === 'especialidad' && !areasOnly" label="Tipo de registro">
        <el-radio-group v-model="form.es_area" :disabled="isBaseArea" aria-label="Tipo de registro">
          <el-radio-button :value="true">Área</el-radio-button>
          <el-radio-button :value="false">Especialidad</el-radio-button>
        </el-radio-group>
        <p class="catalog-type-hint">
          {{
            isBaseArea
              ? 'Esta área base organiza servicios existentes; su tipo se conserva.'
              : form.es_area
                ? 'Agrupa consultorios y estará disponible como área asistencial.'
                : 'Describe la calificación del profesional y puede exigirse en un consultorio.'
          }}
        </p>
        <p v-if="record && !isBaseArea" class="catalog-type-hint">
          Para cambiar el tipo, el registro no debe estar usado por consultorios ni atenciones.
        </p>
      </el-form-item>
      <el-form-item :label="nameLabel" prop="nombre">
        <el-input
          ref="nameRef"
          v-model="form.nombre"
          :maxlength="maxLength"
          :placeholder="kind === 'profesion' ? 'Ej.: Tecnólogo médico' : 'Ej.: Cardiología'"
          autocomplete="off"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="requestClose">Cancelar</el-button>
      <el-button type="primary" :loading="saving" @click="submit">{{
        record
          ? 'Guardar cambios'
          : kind === 'profesion'
            ? 'Guardar profesión'
            : isArea
              ? 'Guardar área'
              : 'Guardar especialidad'
      }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.catalog-form__error {
  margin-bottom: 16px;
}
.dialog-hint {
  margin: 0 0 20px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
.catalog-type-hint {
  width: 100%;
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
</style>
