<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import type { CodeCatalogItem } from '@/services/catalogos'
import type { OfficeServiceAdd } from '@/services/consultorios'

const props = defineProps<{
  options: CodeCatalogItem[]
  loading: boolean
  saving: boolean
  error: string | null
}>()
const emit = defineEmits<{ add: [payload: OfficeServiceAdd]; cancel: []; retry: [] }>()
const source = shallowRef<'existing' | 'new'>('existing')
const name = shallowRef('')
const code = shallowRef<string | null>(null)
const localError = shallowRef<string | null>(null)
const isNew = computed(() => source.value === 'new' || (!props.loading && !props.options.length))
function submit(): void {
  if (props.saving || props.loading) return
  localError.value = null
  if (isNew.value) {
    if (name.value.trim().length < 2) {
      localError.value = 'Ingrese un nombre de al menos 2 caracteres.'
      return
    }
    emit('add', { nombre: name.value.trim() })
  } else {
    if (!code.value) {
      localError.value = 'Seleccione un servicio del catálogo.'
      return
    }
    emit('add', { codigo: code.value })
  }
}
</script>

<template>
  <section class="add-service" aria-label="Agregar servicio">
    <p class="add-service-title">Agregar servicio a este consultorio</p>
    <el-radio-group
      v-if="options.length"
      v-model="source"
      :disabled="saving || loading"
      aria-label="Origen del servicio"
      class="service-source"
    >
      <el-radio value="existing">Del catálogo</el-radio>
      <el-radio value="new">Nuevo servicio</el-radio>
    </el-radio-group>
    <p v-if="loading" class="add-service-help" role="status">Cargando servicios del área…</p>
    <template v-else-if="isNew">
      <label class="add-service-label">Nombre del nuevo servicio</label>
      <el-input
        v-model="name"
        aria-label="Nombre del nuevo servicio"
        maxlength="150"
        :disabled="saving"
        placeholder="Escriba el nombre"
        @keydown.enter.prevent="submit"
      />
      <p class="add-service-help">
        Se guardará en el catálogo de esta área y quedará habilitado en este consultorio.
      </p>
    </template>
    <template v-else>
      <label class="add-service-label">Servicio del catálogo</label>
      <el-select
        v-model="code"
        aria-label="Servicio del catálogo"
        filterable
        :disabled="saving"
        placeholder="Seleccione un servicio"
        class="add-service-select"
      >
        <el-option
          v-for="item in options"
          :key="item.codigo"
          :label="item.nombre"
          :value="item.codigo"
        />
      </el-select>
    </template>
    <p v-if="localError || error" class="add-service-error" role="alert">
      {{ localError || error }}
    </p>
    <div class="add-service-actions">
      <el-button size="small" :disabled="saving" @click="emit('cancel')"
        >Cancelar agregado</el-button
      >
      <el-button v-if="error" size="small" :disabled="saving" @click="emit('retry')"
        >Recargar catálogo</el-button
      >
      <el-button type="primary" size="small" :loading="saving" :disabled="loading" @click="submit"
        >Agregar servicio</el-button
      >
    </div>
  </section>
</template>

<style scoped>
.add-service {
  margin-block: 12px 20px;
  padding-block: 16px;
  border-block: 1px solid var(--el-border-color-lighter);
}
.add-service-title {
  margin: 0 0 12px;
  font-weight: 600;
}
.service-source {
  margin-bottom: 12px;
}
.add-service-label {
  display: block;
  margin-bottom: 8px;
  color: var(--el-text-color-regular);
}
.add-service-select {
  width: 100%;
}
.add-service-help {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}
.add-service-error {
  margin: 12px 0;
  color: color-mix(in srgb, var(--el-color-danger) 65%, var(--el-text-color-primary));
}
.add-service-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
.add-service-actions :deep(.el-button) {
  margin: 0;
}
</style>
