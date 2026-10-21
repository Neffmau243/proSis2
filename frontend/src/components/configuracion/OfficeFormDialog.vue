<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type {
  CodeCatalogItem,
  EstablishmentCatalogItem,
  SpecialtyCatalogItem,
} from '@/services/catalogos'
import type { OfficeResponse } from '@/services/consultorios'
import type { OfficeForm } from './officeForm'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{
  form: OfficeForm
  title: string
  error: string | null
  saving: boolean
  editing: boolean
  establishments: EstablishmentCatalogItem[]
  loading: boolean
  areas: SpecialtyCatalogItem[]
  specialtyNames: Record<string, string>
  parents: OfficeResponse[]
  services: CodeCatalogItem[]
}>()
const additionalRequirement = computed(() => {
  const parent = props.parents.find((item) => item.id === props.form.consultorio_padre_id)
  const code = props.form.especialidad_codigo || parent?.especialidad_requerida_codigo
  return code && code !== props.form.area_codigo ? props.specialtyNames[code] || code : ''
})
const emit = defineEmits<{
  change: [value: Partial<OfficeForm>]
  search: [query: string]
  save: []
}>()
const formRef = ref<FormInstance>()
const rules: FormRules = {
  establecimiento_id: [
    { required: true, message: 'Seleccione el establecimiento.', trigger: 'change' },
  ],
  codigo: [{ required: true, message: 'Ingrese el código.', trigger: 'blur' }],
  nombre: [
    { required: true, message: 'Ingrese el nombre.', trigger: 'blur' },
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
  <el-dialog v-model="visible" :title="title" width="min(640px, 94vw)">
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      role="alert"
      class="form-alert"
    />
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="Establecimiento" prop="establecimiento_id">
        <el-select
          :model-value="form.establecimiento_id"
          @update:model-value="
            emit('change', { establecimiento_id: $event || null, consultorio_padre_id: null })
          "
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
      <el-form-item label="Nombre del consultorio físico" prop="nombre">
        <el-input
          :model-value="form.nombre"
          @update:model-value="emit('change', { nombre: $event })"
          maxlength="150"
        />
      </el-form-item>
      <el-form-item label="Área asistencial" prop="area_codigo">
        <el-select
          :model-value="form.area_codigo"
          @update:model-value="
            emit('change', {
              area_codigo: $event,
              especialidad_codigo: null,
              servicios_codigos: null,
              consultorio_padre_id: null,
            })
          "
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
      </el-form-item>
      <p v-if="additionalRequirement" class="hint" role="status">
        Este consultorio conserva un requisito de su configuración anterior:
        {{ additionalRequirement }}.
      </p>
      <el-form-item label="Consultorio padre" prop="consultorio_padre_id">
        <el-select
          :model-value="form.consultorio_padre_id"
          @update:model-value="
            emit('change', { consultorio_padre_id: $event || null, servicios_codigos: null })
          "
          clearable
          filterable
          placeholder="Principal, sin padre"
        >
          <el-option
            v-for="item in parents"
            :key="item.id"
            :label="`${item.codigo} · ${item.ruta || item.nombre}`"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <details class="additional-settings">
        <summary>Servicios de atención</summary>
        <p class="hint">
          Se usan los servicios del área o del consultorio padre. Puedes limitar cuáles se atienden
          aquí.
        </p>
        <el-form-item label="Servicios habilitados">
          <el-checkbox
            :model-value="form.servicios_codigos === null"
            @update:model-value="
              emit('change', {
                servicios_codigos: $event ? null : services.map((item) => item.codigo),
              })
            "
          >
            Usar servicios del área o del consultorio padre
          </el-checkbox>
          <el-select
            :model-value="form.servicios_codigos ?? services.map((item) => item.codigo)"
            aria-label="Servicios habilitados del consultorio"
            @update:model-value="emit('change', { servicios_codigos: $event })"
            multiple
            filterable
            :disabled="form.servicios_codigos === null"
            placeholder="Seleccione los servicios habilitados"
          >
            <el-option
              v-for="item in services"
              :key="item.codigo"
              :label="item.nombre"
              :value="item.codigo"
            />
          </el-select>
          <p class="hint">
            El padre define la jerarquía física. Los servicios definen qué atención se puede
            registrar aquí.
          </p>
        </el-form-item>
      </details>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">Cancelar</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save')">Guardar</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.form-alert {
  margin-bottom: 16px;
}
.el-select {
  width: 100%;
}
.additional-settings {
  margin: 8px 0 16px;
}
.additional-settings summary {
  cursor: pointer;
  margin-bottom: 16px;
}
.hint {
  color: var(--el-text-color-regular);
  font-size: 13px;
  margin: 8px 0 0;
}
</style>
