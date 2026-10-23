<script setup lang="ts">
import { shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import { serviciosAsistenciales, type CareService } from '@/services/serviciosAsistenciales'
import { consultorios, type OfficeResponse } from '@/services/consultorios'
import type { CodeCatalogItem } from '@/services/catalogos'
import CareServiceFormDialog from './CareServiceFormDialog.vue'

const props = defineProps<{ officeId: number; service: CodeCatalogItem; disabled: boolean }>()
const emit = defineEmits<{ updated: [office: OfficeResponse] }>()
const target = shallowRef<CareService | null>(null)
const visible = shallowRef(false),
  loading = shallowRef(false),
  saving = shallowRef(false)
const error = shallowRef<string | null>(null)
async function open() {
  if (loading.value || saving.value || props.disabled) return
  loading.value = true
  error.value = null
  try {
    target.value = await serviciosAsistenciales.get(props.service.codigo)
    visible.value = true
  } catch (cause) {
    ElMessage.error(
      cause instanceof Error ? cause.message : 'No se pudo abrir el servicio. Reintenta.',
    )
  } finally {
    loading.value = false
  }
}
async function save(payload: { nombre: string }) {
  if (!target.value || saving.value) return
  saving.value = true
  error.value = null
  try {
    await serviciosAsistenciales.update(target.value.codigo, payload.nombre)
    emit('updated', await consultorios.get(props.officeId))
    visible.value = false
    ElMessage.success('Servicio actualizado en el catálogo y sus consultorios.')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'No se pudo actualizar el servicio.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-button
    :disabled="disabled"
    :loading="loading"
    :aria-label="`Editar servicio ${service.nombre}`"
    @click="open"
    >Editar</el-button
  >
  <CareServiceFormDialog
    v-model="visible"
    :service="target"
    :areas="[]"
    :saving="saving"
    :error="error"
    @save="save"
  />
</template>
