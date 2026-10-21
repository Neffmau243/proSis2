<script setup lang="ts">
import { computed } from 'vue'
import type { SpecialtyCatalogItem } from '@/services/catalogos'
import { isStaffSpecialty } from '@/utils/staffSpecialties'

const props = defineProps<{
  options: SpecialtyCatalogItem[]
  selected: string[]
  principal: string | null
}>()
const emit = defineEmits<{
  'update:selected': [value: string[]]
  'update:principal': [value: string | null]
}>()
const areas = computed(() => props.options.filter((item) => item.es_area))
const specialties = computed(() =>
  props.options.filter((item) => !item.es_area && isStaffSpecialty(item)),
)
const selectedOptions = computed(() =>
  props.options.filter((item) => props.selected.includes(item.codigo)),
)

function select(values: string[]): void {
  emit('update:selected', values)
  if (!props.principal || !values.includes(props.principal)) {
    emit('update:principal', values[0] ?? null)
  }
}
</script>

<template>
  <el-form-item label="Áreas y especialidades">
    <el-select
      :model-value="selected"
      multiple
      filterable
      placeholder="Seleccione las que correspondan"
      style="width: 100%"
      @update:model-value="select"
    >
      <el-option-group v-if="areas.length" label="Áreas de atención">
        <el-option
          v-for="item in areas"
          :key="item.codigo"
          :label="item.nombre"
          :value="item.codigo"
        />
      </el-option-group>
      <el-option-group v-if="specialties.length" label="Especialidades">
        <el-option
          v-for="item in specialties"
          :key="item.codigo"
          :label="item.nombre"
          :value="item.codigo"
        />
      </el-option-group>
    </el-select>
    <p class="qualification-hint">
      El área habilita la asignación a consultorios. La especialidad describe la atención del
      profesional.
    </p>
  </el-form-item>
  <el-form-item v-if="selected.length > 1" label="Principal">
    <el-select
      :model-value="principal"
      style="width: 100%"
      @update:model-value="emit('update:principal', $event)"
    >
      <el-option
        v-for="item in selectedOptions"
        :key="item.codigo"
        :label="item.nombre"
        :value="item.codigo"
      />
    </el-select>
  </el-form-item>
</template>

<style scoped>
.qualification-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
</style>
