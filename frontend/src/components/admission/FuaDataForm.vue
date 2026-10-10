<script setup lang="ts">
import type { FuaPrintInput } from '@/types/fua'
import { normalizeFuaText } from '@/utils/fuaPrint'

const props = defineProps<{ value: FuaPrintInput }>()
const emit = defineEmits<{ change: [value: FuaPrintInput] }>()
const choices = [
  { key: 'personal_atiende', label: 'Personal que atiende', options: [['IPRESS', 'De la IPRESS'], ['ITINERANTE', 'Itinerante'], ['AISPED', 'AISPED / oferta flexible']] },
  { key: 'lugar_atencion', label: 'Lugar de atención', options: [['INTRAMURAL', 'Intramural'], ['EXTRAMURAL', 'Extramural']] },
  { key: 'tipo_atencion', label: 'Atención en la FUA', options: [['AMBULATORIA', 'Ambulatoria'], ['REFERENCIA', 'Referencia'], ['EMERGENCIA', 'Emergencia']] },
] as const
const texts: { key: keyof FuaPrintInput; label: string; max: number }[] = [
  { key: 'codigo_renipress', label: 'RENIPRESS (8 dígitos)', max: 8 },
  { key: 'sis_diresa', label: 'SIS · DIRESA / otros', max: 3 },
  { key: 'sis_tipo', label: 'SIS · Tipo de afiliación', max: 2 },
  { key: 'sis_numero', label: 'SIS · Número de afiliación', max: 30 },
  { key: 'sis_componente', label: 'SIS · Componente RN (si aplica)', max: 20 },
  { key: 'etnia_codigo', label: 'Etnia · Código verificado', max: 3 },
]
const reference: { key: keyof FuaPrintInput; label: string; max: number }[] = [
  { key: 'referencia_renipress', label: 'RENIPRESS de origen', max: 8 },
  { key: 'referencia_nombre', label: 'IPRESS de origen', max: 200 },
  { key: 'referencia_hoja', label: 'N.º hoja de referencia', max: 50 },
]
function update(key: keyof FuaPrintInput, value: string | null): void {
  const next = { ...props.value, [key]: normalizeFuaText(key, value) }
  if (key === 'personal_atiende' && value !== 'AISPED') next.codigo_aisped = null
  if (key === 'tipo_atencion' && value !== 'REFERENCIA') {
    next.referencia_renipress = null
    next.referencia_nombre = null
    next.referencia_hoja = null
  }
  emit('change', next)
}
</script>

<template>
  <el-form label-position="top" class="fua-data">
    <el-form-item v-for="choice in choices" :key="choice.key" :label="choice.label">
      <el-select :model-value="value[choice.key]" clearable placeholder="Sin declarar" @update:model-value="update(choice.key, $event)">
        <el-option v-for="[code, label] in choice.options" :key="code" :value="code" :label="label" />
      </el-select>
    </el-form-item>
    <el-form-item v-if="value.personal_atiende === 'AISPED'" label="Código AISPED">
      <el-input :model-value="value.codigo_aisped ?? ''" :maxlength="20" @update:model-value="update('codigo_aisped', $event)" />
    </el-form-item>
    <el-form-item v-for="field in texts" :key="field.key" :label="field.label">
      <el-input :model-value="value[field.key] ?? ''" :maxlength="field.max" @update:model-value="update(field.key, $event)" />
    </el-form-item>
    <template v-if="value.tipo_atencion === 'REFERENCIA'">
      <el-form-item v-for="field in reference" :key="field.key" :label="field.label">
        <el-input :model-value="value[field.key] ?? ''" :maxlength="field.max" @update:model-value="update(field.key, $event)" />
      </el-form-item>
    </template>
  </el-form>
</template>

<style scoped>
.fua-data { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 16px; }
@media (max-width: 700px) { .fua-data { grid-template-columns: minmax(0, 1fr); } }
</style>
