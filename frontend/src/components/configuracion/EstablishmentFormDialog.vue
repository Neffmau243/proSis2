<script setup lang="ts">
import './careConfiguration.css'
import { watch } from 'vue'
import type { EstablishmentDraft } from '@/services/configuracionAtencion'
import { catalogos, type UbigeoCatalogItem } from '@/services/catalogos'
import { useRemoteCatalog } from '@/composables/useRemoteCatalog'
const visible = defineModel<boolean>({ required: true })
const props = defineProps<{
  draft: EstablishmentDraft
  editing: boolean
  saving: boolean
  error: string | null
}>()
const emit = defineEmits<{ change: [value: Partial<EstablishmentDraft>]; save: [] }>()
const districts = useRemoteCatalog<UbigeoCatalogItem>({
  fetch: (query) => catalogos.ubigeos(query, 25, 0),
  key: (item) => item.codigo,
})
watch(visible, (open) => {
  if (open) void districts.load(props.draft.ubigeo_codigo || undefined)
})
</script>
<template>
  <el-dialog
    v-model="visible"
    :title="editing ? 'Editar establecimiento' : 'Nuevo establecimiento'"
    width="min(620px,94vw)"
    class="establishment-dialog care-config"
    modal-class="care-config-overlay"
    :close-on-click-modal="!saving"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-form label-position="top" :disabled="saving" @submit.prevent="emit('save')">
      <el-form-item label="Nombre" required
        ><el-input
          :model-value="draft.nombre"
          aria-label="Nombre del establecimiento"
          maxlength="200"
          @update:model-value="emit('change', { nombre: $event })"
      /></el-form-item>
      <el-form-item label="Abreviatura"
        ><el-input
          :model-value="draft.abreviatura"
          maxlength="50"
          @update:model-value="emit('change', { abreviatura: $event || null })"
      /></el-form-item>
      <el-form-item label="Código RENAES / RENIPRESS"
        ><el-input
          :model-value="draft.codigo_renaes"
          maxlength="30"
          @update:model-value="emit('change', { codigo_renaes: $event || null })"
      /></el-form-item>
      <el-form-item label="Código IDEESS"
        ><el-input
          :model-value="draft.codigo_ideess"
          maxlength="30"
          @update:model-value="emit('change', { codigo_ideess: $event || null })"
      /></el-form-item>
      <el-form-item label="Distrito">
        <el-select
          :model-value="draft.ubigeo_codigo"
          aria-label="Distrito del establecimiento"
          clearable
          filterable
          remote
          :remote-method="
            (query: string) =>
              districts.search(
                query,
                districts.items.value.filter((item) => item.codigo === draft.ubigeo_codigo),
              )
          "
          :loading="districts.loading.value"
          placeholder="Buscar distrito"
          @update:model-value="emit('change', { ubigeo_codigo: $event || null })"
        >
          <el-option
            v-for="item in districts.items.value"
            :key="item.codigo"
            :value="item.codigo"
            :label="`${item.departamento} / ${item.provincia} / ${item.distrito}`"
          />
        </el-select>
        <p v-if="districts.error.value" role="alert">
          {{ districts.error.value }}
          <el-button link @click="districts.load()">Reintentar</el-button>
        </p>
      </el-form-item>
    </el-form>
    <template #footer
      ><el-button :disabled="saving" @click="visible = false">Cancelar</el-button
      ><el-button type="primary" :loading="saving" @click="emit('save')"
        >Guardar establecimiento</el-button
      ></template
    >
  </el-dialog>
</template>
<style scoped>
.el-select {
  width: 100%;
}
:global(.establishment-dialog) {
  max-height: calc(100dvh - 48px);
  margin-block: 24px;
  display: flex;
  flex-direction: column;
}
:global(.establishment-dialog .el-dialog__body) {
  overflow-y: auto;
}
@media (max-width: 600px) {
  :global(.establishment-dialog .el-input__wrapper),
  :global(.establishment-dialog .el-select__wrapper),
  :global(.establishment-dialog .el-button) {
    min-height: 44px;
  }
}
</style>
