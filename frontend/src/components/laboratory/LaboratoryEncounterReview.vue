<script setup lang="ts">
import { computed } from 'vue'
import type { Attention } from '@/services/atenciones'

const opened = defineModel<boolean>({ required: true })
const props = defineProps<{
  attention: Attention | null
  loading: boolean
  error: string
  printing: boolean
  sisReady: boolean
}>()
const emit = defineEmits<{ print: []; additional: []; hci: [] }>()
const patientName = computed(() => {
  const snapshot = props.attention?.fua_impresion
  return (
    [
      snapshot?.apellido_paterno,
      snapshot?.apellido_materno,
      snapshot?.primer_nombre,
      snapshot?.otros_nombres,
    ]
      .filter(Boolean)
      .join(' ') || 'Sin copia histórica'
  )
})
</script>

<template>
  <el-dialog
    v-model="opened"
    title="Atención de laboratorio guardada"
    width="min(640px, 95vw)"
    destroy-on-close
  >
    <div v-loading="loading" class="lab-review">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-descriptions v-else-if="attention" :column="1" border>
        <el-descriptions-item label="Atención"
          >#{{ attention.id }} · {{ attention.estado }}</el-descriptions-item
        >
        <el-descriptions-item label="Paciente">{{ patientName }}</el-descriptions-item>
        <el-descriptions-item label="Historia clínica">{{
          attention.historia_clinica_snapshot || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Fecha de atención">{{
          attention.fecha_atencion
        }}</el-descriptions-item>
        <el-descriptions-item label="Modalidad">{{
          attention.modalidad_atencion_codigo
        }}</el-descriptions-item>
        <el-descriptions-item label="IPRESS de origen">{{
          attention.fua_impresion?.referencia_nombre || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="RENIPRESS de origen">{{
          attention.fua_impresion?.referencia_renipress || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="N.º de referencia recibida">{{
          attention.numero_referencia_ingreso || attention.fua_impresion?.referencia_hoja || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="N.º de contrarreferencia recibida">{{
          attention.numero_contrarreferencia_ingreso || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Observaciones">{{
          attention.observaciones || '—'
        }}</el-descriptions-item>
      </el-descriptions>
    </div>
    <p v-if="attention && !attention.fua_impresion" role="status">
      Esta atención no tiene una copia histórica para imprimir.
    </p>
    <template #footer>
      <el-button @click="opened = false">Cerrar</el-button>
      <el-button :disabled="loading || printing || !attention?.fua_impresion" @click="emit('hci')"
        >Imprimir HCI guardada</el-button
      >
      <el-button :disabled="loading || printing || !sisReady" @click="emit('additional')"
        >FUA adicional guardado</el-button
      >
      <el-button type="primary" :disabled="loading || printing || !sisReady" @click="emit('print')"
        >Imprimir FUA guardado</el-button
      >
    </template>
  </el-dialog>
</template>

<style scoped>
.lab-review {
  min-height: 80px;
}
.lab-review :deep(.el-descriptions__content) {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
