<script setup lang="ts">
import { useTemplateRef } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { EstablishmentCatalogItem, SpecialtyCatalogItem } from '@/services/catalogos'
import type { OfficeForm } from './officeForm'

const visible = defineModel<boolean>({ required: true })
defineProps<{
  form: OfficeForm
  title: string
  error: string | null
  saving: boolean
  editing: boolean
  establishments: EstablishmentCatalogItem[]
  loading: boolean
  areas: SpecialtyCatalogItem[]
}>()
const emit = defineEmits<{
  change: [value: Partial<OfficeForm>]
  search: [query: string]
  save: []
}>()
const formRef = useTemplateRef<FormInstance>('formRef')
const rules: FormRules = {
  establecimiento_id: [
    { required: true, message: 'Seleccione el establecimiento.', trigger: 'change' },
  ],
  codigo: [{ required: true, whitespace: true, message: 'Ingrese el código.', trigger: 'blur' }],
  nombre: [
    { required: true, whitespace: true, message: 'Ingrese el nombre.', trigger: 'blur' },
    { min: 2, message: 'Mínimo 2 caracteres.', trigger: 'blur' },
  ],
  area_codigo: [{ required: true, message: 'Seleccione el área asistencial.', trigger: 'change' }],
}

defineExpose({
  validate: () => formRef.value?.validate() ?? Promise.resolve(false),
  clearValidate: () => formRef.value?.clearValidate(),
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="min(640px, 94vw)"
    class="office-form-dialog care-config"
    modal-class="care-config-overlay"
    :close-on-click-modal="!saving"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      role="alert"
      class="form-alert"
    />
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :disabled="saving"
      label-position="top"
      @submit.prevent
    >
      <el-form-item label="Establecimiento" prop="establecimiento_id">
        <el-select
          :model-value="form.establecimiento_id"
          @update:model-value="emit('change', { establecimiento_id: $event || null })"
          filterable
          remote
          :remote-method="(query: string) => emit('search', query)"
          :loading="loading"
          :disabled="editing"
          placeholder="Seleccione un establecimiento"
        >
          <el-option
            v-for="item in establishments"
            :key="item.id"
            :label="item.nombre"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="Código" prop="codigo">
        <el-input
          :model-value="form.codigo"
          @update:model-value="emit('change', { codigo: $event })"
          maxlength="30"
        />
      </el-form-item>
      <el-form-item label="Nombre del consultorio" prop="nombre">
        <el-input
          :model-value="form.nombre"
          @update:model-value="emit('change', { nombre: $event })"
          maxlength="150"
        />
      </el-form-item>
      <el-form-item label="Área asistencial" prop="area_codigo">
        <el-select
          :model-value="form.area_codigo"
          @update:model-value="emit('change', { area_codigo: $event })"
          filterable
          placeholder="Seleccione el área"
        >
          <el-option
            v-for="item in areas"
            :key="item.codigo"
            :label="item.nombre"
            :value="item.codigo"
          />
        </el-select>
        <p v-if="editing" class="hint">
          El área debe ser compatible con los servicios y profesionales ya configurados.
        </p>
      </el-form-item>
    </el-form>
    <p class="hint service-help">
      {{
        editing
          ? 'Administra los servicios/especialidades y sus profesionales desde «Gestionar servicios».'
          : 'Después de guardar, abre «Gestionar servicios» para agregar servicios/especialidades y asignar sus profesionales.'
      }}
    </p>
    <template #footer>
      <el-button :disabled="saving" @click="visible = false">Cancelar</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save')">Guardar</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
:global(.el-dialog.office-form-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100dvh - 48px);
  margin-block: 24px;
}
:global(.office-form-dialog .el-dialog__body) {
  overflow-y: auto;
  min-height: 0;
}
:global(.office-form-dialog .el-dialog__header),
:global(.office-form-dialog .el-dialog__footer) {
  flex-shrink: 0;
}
.form-alert {
  margin-bottom: 16px;
}
.el-select {
  width: 100%;
}
.hint {
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.6;
  margin: 8px 0 0;
}
.service-help {
  margin-top: 16px;
}
@media (max-width: 600px) {
  :global(.office-form-dialog .el-input__wrapper),
  :global(.office-form-dialog .el-select__wrapper),
  :global(.office-form-dialog .el-button) {
    min-height: 44px;
  }
}
</style>
