<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { atenciones, type Attention } from '@/services/atenciones'
const props = defineProps<{ attention: Attention; canManage: boolean }>()
const emit = defineEmits<{ updated: [attention: Attention] }>()
const busy = shallowRef(false)
const error = shallowRef('')
const receipt = shallowRef('')
const record = computed(() => props.attention.evaluaciones_nutricionales?.[0])
const ready = computed(
  () =>
    props.canManage &&
    props.attention.estado === 'ATENDIDO' &&
    !!props.attention.contexto_clinico &&
    props.attention.evaluaciones_nutricionales?.length === 1,
)
const stateLabel = computed(
  () =>
    ({
      PENDIENTE: 'Pendiente de exportar',
      EXPORTADO: 'Archivo de revisión exportado',
      ENVIADO: 'Envío externo registrado manualmente',
    })[record.value?.estado_exportacion ?? 'PENDIENTE'],
)

async function download() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const data = await atenciones.exportNutrition(props.attention.id)
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = `nutricion-revision-${props.attention.id}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    emit('updated', data.atencion as Attention)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudo descargar. Intente de nuevo.'
  } finally {
    busy.value = false
  }
}
async function confirm() {
  if (busy.value || receipt.value.trim().length < 5) return
  busy.value = true
  error.value = ''
  try {
    emit('updated', await atenciones.confirmNutritionSent(props.attention.id, receipt.value.trim()))
    receipt.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'No se pudo registrar la constancia.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="nutrition-export" aria-labelledby="nutrition-export-title">
    <h3 id="nutrition-export-title">Exportación de nutrición</h3>
    <p>
      Archivo JSON para revisión. La compatibilidad con SIS/SIEN está pendiente de homologación.
    </p>
    <p role="status">
      {{ record?.estado_exportacion ? stateLabel : 'Sin estado de exportación documentado' }}
    </p>
    <p v-if="record?.constancia_envio">
      Constancia de envío externo: {{ record.constancia_envio }}
    </p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-button v-if="ready" :loading="busy" @click="download">Descargar para revisión</el-button>
    <p v-else-if="!attention.contexto_clinico">
      Sin contexto histórico completo para exportar esta atención.
    </p>
    <div
      v-if="ready && record?.estado_exportacion === 'EXPORTADO'"
      class="nutrition-export__receipt"
    >
      <label for="nutrition-receipt">Constancia del envío realizado externamente</label>
      <el-input
        id="nutrition-receipt"
        v-model="receipt"
        :maxlength="200"
        :disabled="busy"
        placeholder="Número de constancia o referencia verificable"
      />
      <p class="nutrition-export__hint">
        Regístrela únicamente después de realizar el envío por el canal correspondiente. Esta acción
        no transmite datos.
      </p>
      <el-button :disabled="receipt.trim().length < 5" :loading="busy" @click="confirm"
        >Registrar constancia de envío externo</el-button
      >
    </div>
  </section>
</template>

<style scoped>
.nutrition-export {
  margin: 24px 0;
  max-width: 65ch;
}
.nutrition-export__receipt {
  display: grid;
  gap: 12px;
  margin-top: 24px;
}
.nutrition-export__hint {
  margin: 0;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
</style>
