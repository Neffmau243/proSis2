<script setup lang="ts">
import { reactive, useTemplateRef, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { SpecialtyCatalogItem } from '@/services/catalogos'
import type { CareService } from '@/services/serviciosAsistenciales'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{
  service: CareService | null
  areas: SpecialtyCatalogItem[]
  saving: boolean
  error: string | null
}>()
const emit = defineEmits<{ save: [payload: { nombre: string; area_codigo: string }] }>()
const formRef = useTemplateRef<FormInstance>('formRef')
const form = reactive({ nombre: '', area_codigo: '' })
const rules: FormRules = {
  nombre: [
    {
      required: true,
      min: 2,
      message: 'Ingrese un nombre de al menos 2 caracteres.',
      trigger: 'blur',
    },
  ],
  area_codigo: [{ required: true, message: 'Seleccione el área del servicio.', trigger: 'change' }],
}
watch(visible, (open) => {
  if (!open) return
  form.nombre = props.service?.nombre || ''
  form.area_codigo = props.service?.area_codigos[0] || ''
  formRef.value?.clearValidate()
})
async function save() {
  if (props.saving || !(await formRef.value?.validate().catch(() => false))) return
  emit('save', { nombre: form.nombre.trim(), area_codigo: form.area_codigo })
}
</script>

<template>
  <el-dialog
    v-model="visible"
    class="care-config"
    modal-class="care-config-overlay"
    :title="service ? 'Editar servicio' : 'Registrar servicio'"
    width="min(520px, 94vw)"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <p class="form-context">
      {{
        service
          ? `El cambio de nombre se reflejará en los ${service.consultorios.length} consultorios vinculados. El código y el historial se conservan.`
          : 'Registra el servicio en el catálogo general. Después podrás habilitarlo en los consultorios de su área.'
      }}
    </p>
    <p v-if="service?.area_codigos.includes(service.codigo)" class="form-context">
      Este registro también identifica un área compartida. Su nombre se actualizará en ambos
      catálogos.
    </p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :disabled="saving"
      label-position="top"
      @submit.prevent="save"
    >
      <el-form-item label="Nombre del servicio" prop="nombre">
        <el-input v-model="form.nombre" maxlength="150" aria-label="Nombre del servicio" />
      </el-form-item>
      <el-form-item v-if="!service" label="Área de atención" prop="area_codigo">
        <el-select
          v-model="form.area_codigo"
          filterable
          aria-label="Área del servicio"
          placeholder="Seleccione el área"
        >
          <el-option
            v-for="area in areas"
            :key="area.codigo"
            :label="area.nombre"
            :value="area.codigo"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="visible = false">Cancelar</el-button>
      <el-button type="primary" :loading="saving" @click="save">{{
        service ? 'Guardar cambios' : 'Registrar servicio'
      }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.form-context {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  margin: 0 0 20px;
}
</style>
