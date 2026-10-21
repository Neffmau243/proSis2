<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useStaffCatalogs } from '@/composables/useStaffCatalogs'
import type { StaffCatalogKind } from '@/composables/useStaffCatalogs'
import { isStaffSpecialty } from '@/utils/staffSpecialties'
import StaffCatalogSection from './StaffCatalogSection.vue'

const props = defineProps<{ kind: StaffCatalogKind; areasOnly?: boolean }>()
const emit = defineEmits<{ created: [] }>()
const {
  professions,
  specialties,
  loading,
  saving,
  error,
  formError,
  creating,
  editing,
  deleting,
  deleteError,
  openDelete,
  cancelDelete,
  remove,
  load,
  open,
  openEdit,
  cancel,
  save,
} = useStaffCatalogs((action) => {
  ElMessage.success(
    action === 'deleted'
      ? 'Registro eliminado.'
      : action === 'updated'
        ? 'Cambios guardados.'
        : 'Registro creado.',
  )
  emit('created')
}, props.kind)
const visibleItems = computed(() =>
  props.kind === 'profesion' ? professions.value : specialties.value.filter(isStaffSpecialty),
)
</script>

<template>
  <div>
    <div v-if="error" class="catalogs-error">
      <el-alert :title="error" type="error" :closable="false" />
      <el-button :loading="loading" @click="load">Reintentar</el-button>
    </div>
    <StaffCatalogSection
      :kind="kind"
      :areas-only="areasOnly"
      :items="visibleItems"
      :loading="loading"
      :saving="saving"
      :creating="creating === kind"
      :editing="editing"
      :error="formError"
      @open="open(kind)"
      @edit="openEdit(kind, $event)"
      @delete="openDelete"
      @cancel="cancel"
      @submit="save(kind, $event)"
    />
    <el-dialog
      v-if="deleting"
      :model-value="true"
      title="Eliminar registro"
      width="min(480px, 94vw)"
      :close-on-click-modal="false"
      :close-on-press-escape="!saving"
      :show-close="!saving"
      @update:model-value="cancelDelete"
    >
      <p>¿Eliminar «{{ deleting.nombre }}» del catálogo?</p>
      <p>
        Solo se pueden eliminar registros que no estén vinculados. Esta acción no se puede deshacer.
      </p>
      <el-alert v-if="deleteError" :title="deleteError" type="error" :closable="false" />
      <template #footer>
        <el-button :disabled="saving" @click="cancelDelete">Cancelar</el-button>
        <el-button type="danger" :loading="saving" @click="remove">Eliminar registro</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.catalogs-error {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
</style>
