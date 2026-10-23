<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import AdmissionPatientSummary from '@/components/admission/AdmissionPatientSummary.vue'
import { pacientes, type Patient } from '@/services/pacientes'
import { catalogos, type CodeCatalogItem, type RiskGroupCatalogItem } from '@/services/catalogos'
import { useAuthStore } from '@/stores/auth'
import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
const props = defineProps<{ patientId: number }>()
const router = useRouter(),
  auth = useAuthStore()
const patient = shallowRef<Patient | null>(null),
  loading = shallowRef(false),
  error = shallowRef<string | null>(null)
const documents = shallowRef<CodeCatalogItem[]>([]),
  risks = shallowRef<RiskGroupCatalogItem[]>([])
const dirty = shallowRef(false),
  busy = shallowRef(false)
const { seleccionado, seleccionar, notificarCambio } = usePacienteSeleccionado()
const name = computed(() =>
  patient.value
    ? [
        patient.value.apellido_paterno,
        patient.value.apellido_materno,
        patient.value.primer_nombre,
        patient.value.otros_nombres,
      ]
        .filter(Boolean)
        .join(' ')
    : '',
)
let request = 0
async function load() {
  const current = ++request
  loading.value = true
  error.value = null
  patient.value = null
  dirty.value = false
  try {
    const [item, types, groups] = await Promise.all([
      pacientes.get(props.patientId),
      catalogos.tiposDocumento(),
      catalogos.gruposRiesgo(),
    ])
    if (current === request) {
      patient.value = item
      documents.value = types
      risks.value = groups
    }
  } catch (cause) {
    if (current === request)
      error.value = cause instanceof Error ? cause.message : 'No se pudo cargar el paciente.'
  } finally {
    if (current === request) loading.value = false
  }
}
function saved(item: Patient) {
  patient.value = item
  if (seleccionado.value?.id === item.id) seleccionar(item)
  notificarCambio()
}
async function confirmLeave(): Promise<boolean> {
  if (busy.value) return false
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm(
      'Hay cambios del paciente sin guardar. ¿Salir y descartarlos?',
      'Cambios sin guardar',
      { confirmButtonText: 'Salir sin guardar', cancelButtonText: 'Seguir editando', type: 'info' },
    )
    return true
  } catch {
    return false
  }
}
onBeforeRouteLeave(confirmLeave)
onBeforeRouteUpdate((to, from) => (to.params.id === from.params.id ? true : confirmLeave()))
watch(() => props.patientId, load, { immediate: true })
</script>
<template>
  <section class="patient-edit">
    <header class="patient-edit-header">
      <div>
        <h2>Editar paciente</h2>
        <p v-if="patient">
          {{ name }} · {{ patient.tipo_documento_codigo }} {{ patient.numero_documento }}
        </p>
        <p>Actualiza los datos de registro del paciente.</p>
      </div>
      <el-button
        :disabled="busy"
        @click="router.push({ name: 'paciente-detalle', params: { id: patientId } })"
        >Volver a ficha</el-button
      >
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false"
      ><el-button link @click="load">Reintentar</el-button></el-alert
    >
    <p v-if="loading" role="status">Cargando paciente…</p>
    <el-alert
      v-if="patient && !patient.estado"
      title="Este paciente está inactivo. Sus datos se muestran para consulta."
      type="info"
      :closable="false"
    />
    <AdmissionPatientSummary
      v-if="patient"
      :key="patient.id"
      :patient="patient"
      :can-edit="auth.hasPermission('PACIENTE_EDITAR')"
      :tipos-documento="documents"
      :grupos-riesgo="risks"
      @saved="saved"
      @dirty-change="dirty = $event"
      @busy-change="busy = $event"
    />
  </section>
</template>
<style scoped>
.patient-edit-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.patient-edit-header h2 {
  margin: 0;
}
.patient-edit-header p {
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.patient-edit {
  max-width: 1100px;
}
@media (max-width: 600px) {
  .patient-edit-header .el-button {
    min-height: 44px;
  }
}
</style>
