<script setup lang="ts">
import { computed } from 'vue'
import { fuaFieldFont, type FuaLayout } from '@/utils/fuaPrint'

const props = defineProps<{
  layout: FuaLayout
  values: Record<string, string>
  background: string
  inset: number
  selectedId: string
  preprintedRenipress: boolean
}>()
const emit = defineEmits<{ select: [id: string] }>()
const fields = computed(() =>
  props.layout.fields.filter(
    (field) => field.enabled && (field.id !== 'codigo_renipress' || !props.preprintedRenipress),
  ),
)
</script>

<template>
  <div class="fua-preview-scroll" aria-label="Vista previa de posiciones sobre la hoja">
    <div class="fua-preview" :style="{ width: `${layout.width}mm`, height: `${layout.height}mm` }">
      <img
        :src="background"
        alt="Plantilla FUA de referencia"
        class="fua-background"
        :style="{
          left: `${inset}mm`,
          top: `${inset}mm`,
          width: `${layout.width - 2 * inset}mm`,
          height: `${layout.height - 2 * inset}mm`,
        }"
      />
      <button
        v-for="field in fields"
        :key="field.id"
        type="button"
        class="fua-position"
        :class="{ 'fua-position--selected': selectedId === field.id }"
        :aria-label="`Ajustar ${field.label}`"
        :title="field.label"
        :style="{
          left: `${field.x + layout.offsetX}mm`,
          top: `${field.y + layout.offsetY}mm`,
          width: `${field.width}mm`,
          height: `${field.height}mm`,
          fontSize: `${fuaFieldFont(field, (values[field.id] || '').slice(field.skip))}pt`,
        }"
        @click="emit('select', field.id)"
      >
        <template v-if="field.step && values[field.id]">
          <span
            v-for="(char, index) in [...(values[field.id] || '').slice(field.skip)]"
            :key="index"
            :style="{ position: 'absolute', left: `${index * field.step}mm` }"
            >{{ char }}</span
          >
        </template>
        <template v-else>{{ (values[field.id] || '').slice(field.skip) || '·' }}</template>
      </button>
    </div>
  </div>
</template>

<style scoped>
.fua-preview-scroll {
  max-height: 65vh;
  overflow: auto;
  background: var(--el-fill-color);
  padding: 12px;
  border: 1px solid var(--el-border-color);
}
.fua-preview {
  position: relative;
  background: white;
  zoom: 0.7;
}
.fua-background {
  position: absolute;
  z-index: 0;
  object-fit: fill;
  pointer-events: none;
}
.fua-position {
  position: absolute;
  z-index: 1;
  margin: 0;
  padding: 0;
  border: 0;
  outline: 0.2mm dashed #677386;
  text-align: left;
  background: transparent;
  color: #111;
  font-family: 'Courier New', monospace;
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
}
.fua-position--selected,
.fua-position:focus-visible {
  outline: 0.6mm solid #1252a1;
  background: #e5f0ff;
}
.fua-position:hover {
  background: #e5f0ff;
}
</style>
