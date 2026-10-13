<script setup lang="ts">
import { computed, useId } from 'vue'
import SingleChoiceCheckboxes from '@/components/SingleChoiceCheckboxes.vue'
import type { CodeCatalogItem } from '@/services/catalogos'

const props = defineProps<{
  options: CodeCatalogItem[]
  disabled?: boolean
  error?: string
  checkboxes?: boolean
}>()
const model = defineModel<string | null>({ required: true })
const id = useId()
const choices = computed(() => {
  const options = props.options.map((item) => ({
    value: item.codigo,
    label: item.nombre,
  }))
  if (model.value && !options.some((item) => item.value === model.value)) {
    options.unshift({ value: model.value, label: model.value })
  }
  return options
})
</script>

<template>
  <div class="document-types" :class="{ 'document-types--checkboxes': checkboxes }">
    <SingleChoiceCheckboxes
      v-if="checkboxes"
      v-model="model"
      :options="choices"
      :disabled="disabled"
      label="Tipo de documento"
    />
    <template v-else>
      <label :for="id" class="document-types__label">Tipo documento</label>
      <el-select
        :id="id"
        v-model="model"
        :disabled="disabled"
        aria-label="Tipo de documento"
        :aria-invalid="Boolean(error)"
        :aria-describedby="error ? `${id}-error` : undefined"
        placeholder="Seleccione"
        class="document-types__options"
      >
        <el-option
          v-for="item in choices"
          :key="item.value"
          :value="item.value"
          :label="item.label"
        />
      </el-select>
    </template>
    <p v-if="error" :id="`${id}-error`" class="document-types__error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.document-types {
  display: grid;
  grid-template-columns: 102px minmax(0, 1fr);
  align-items: center;
  gap: 4px 8px;
}
.document-types--checkboxes {
  display: block;
}
.document-types__label {
  font-size: 12px;
  text-align: right;
  color: var(--admission-ink, #304f6d);
}
.document-types__options {
  min-width: 0;
  width: 100%;
}
.document-types__options :deep(.el-select__wrapper) {
  min-height: var(--el-component-size, 26px);
  padding-block: 0;
  font-size: 12px;
}
.document-types__error {
  grid-column: 2;
  margin: 4px 0;
  color: var(--el-color-danger);
  font-size: 12px;
}
@media (max-width: 560px) {
  .document-types {
    grid-template-columns: minmax(0, 1fr);
  }
  .document-types__label {
    text-align: left;
  }
  .document-types__error {
    grid-column: 1;
  }
}
</style>
