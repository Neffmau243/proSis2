<script setup lang="ts">
import { computed, shallowRef, useId, watch } from 'vue'
import { ArrowDown, Edit } from '@element-plus/icons-vue'
import ResponsibleDialog from '@/components/patient/ResponsibleDialog.vue'
import RiskDialog from '@/components/patient/RiskDialog.vue'
import type { Patient, PatientResponsible, PatientRisk } from '@/services/pacientes'
import type { CodeCatalogItem, RiskGroupCatalogItem } from '@/services/catalogos'

const props = defineProps<{
  patient: Patient
  disabled?: boolean
  canEdit: boolean
  tiposDocumento: CodeCatalogItem[]
  gruposRiesgo: RiskGroupCatalogItem[]
}>()
const emit = defineEmits<{ saved: [patient: Patient]; busyChange: [busy: boolean] }>()
const responsibleOpen = shallowRef(false)
const riskOpen = shallowRef(false)
const editingResponsible = shallowRef<PatientResponsible | null>(null)
const editingRisk = shallowRef<PatientRisk | null>(null)
const id = useId()
const activeRisks = computed(() => {
  const now = new Date()
  const today = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10)
  return props.patient.riesgos.filter(
    (item) => item.fecha_inicio <= today && (!item.fecha_fin || item.fecha_fin >= today),
  )
})
function riskName(item: PatientRisk): string {
  return (
    item.grupo_riesgo_nombre ??
    props.gruposRiesgo.find((group) => group.id === item.grupo_riesgo_id)?.nombre ??
    `Grupo ${item.grupo_riesgo_id}`
  )
}
const riskSummary = computed(() => [...new Set(activeRisks.value.map(riskName))].join(' · '))
const activeResponsibles = computed(() => props.patient.responsables.filter((item) => item.activo))
const mother = computed(
  () =>
    activeResponsibles.value.find((item) => item.parentesco === 'MADRE' && item.es_principal) ??
    activeResponsibles.value.find((item) => item.parentesco === 'MADRE'),
)
const busy = computed(() => responsibleOpen.value || riskOpen.value)
watch(busy, (value) => emit('busyChange', value), { flush: 'sync' })
function editResponsible(item: PatientResponsible | null) {
  editingResponsible.value = item
  responsibleOpen.value = true
}
function editRisk(item: PatientRisk | null) {
  editingRisk.value = item
  riskOpen.value = true
}
function onRiskCommand(command: string) {
  if (props.disabled || !props.canEdit) return
  if (command === 'add') editRisk(null)
  else {
    const item = props.patient.riesgos.find(
      (risk) => `${risk.grupo_riesgo_id}|${risk.fecha_inicio}` === command,
    )
    if (item) editRisk(item)
  }
}
function responsibleSaved(item: PatientResponsible) {
  const others = props.patient.responsables.filter((existing) => existing.id !== item.id)
  emit('saved', { ...props.patient, responsables: [...others, item] })
}
function riskSaved(item: PatientRisk) {
  const others = props.patient.riesgos.filter(
    (existing) =>
      existing.grupo_riesgo_id !== item.grupo_riesgo_id ||
      existing.fecha_inicio !== item.fecha_inicio,
  )
  const group = props.gruposRiesgo.find((option) => option.id === item.grupo_riesgo_id)
  emit('saved', {
    ...props.patient,
    riesgos: [
      ...others,
      { ...item, grupo_riesgo_nombre: item.grupo_riesgo_nombre ?? group?.nombre ?? null },
    ],
  })
}
</script>

<template>
  <section class="patient-relations" aria-label="Responsables y riesgos del paciente">
    <div class="patient-relations__entry">
      <label :for="`${id}-risk`" class="patient-relations__title">Grupo de riesgo</label>
      <el-dropdown
        v-if="canEdit"
        class="patient-relations__risk"
        trigger="click"
        :disabled="disabled"
        @command="onRiskCommand"
      >
        <button
          :id="`${id}-risk`"
          class="patient-relations__risk-trigger"
          type="button"
          :disabled="disabled"
          :title="riskSummary || 'Sin seguimiento vigente registrado'"
          aria-label="Grupo de riesgo"
        >
          <span class="patient-relations__risk-value">{{ riskSummary || 'Sin seguimiento vigente registrado' }}</span>
          <el-icon><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="item in patient.riesgos"
              :key="`${item.grupo_riesgo_id}|${item.fecha_inicio}`"
              :command="`${item.grupo_riesgo_id}|${item.fecha_inicio}`"
            >
              Editar {{ riskName(item) }} · {{ item.fecha_inicio }}
              {{ item.fecha_fin ? ` a ${item.fecha_fin}` : ' · Sin cierre' }}
            </el-dropdown-item>
            <el-dropdown-item command="add">Agregar riesgo</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-input
        v-else
        :id="`${id}-risk`"
        :model-value="riskSummary"
        placeholder="Sin seguimiento vigente registrado"
        readonly
        aria-label="Grupo de riesgo"
      />
    </div>
    <slot name="ethnicity" />
    <div class="patient-relations__entry">
      <label :for="`${id}-mother`" class="patient-relations__title">Nombre de madre</label>
      <el-input
        :id="`${id}-mother`"
        class="patient-relations__mother"
        :model-value="mother?.nombre_completo ?? ''"
        placeholder="Sin registrar"
        readonly
        :title="mother?.nombre_completo"
        aria-label="Nombre de madre"
      >
        <template v-if="canEdit" #suffix>
          <el-button
            link
            :icon="Edit"
            :disabled="disabled"
            :aria-label="mother ? 'Editar madre' : 'Agregar madre'"
            :title="mother ? 'Editar madre' : 'Agregar madre'"
            @click="editResponsible(mother ?? null)"
          />
        </template>
      </el-input>
    </div>
    <slot name="condition" />
    <ResponsibleDialog
      v-model="responsibleOpen"
      :patient-id="patient.id"
      :responsible="editingResponsible"
      :tipos-documento="tiposDocumento"
      @saved="responsibleSaved"
    />
    <RiskDialog
      v-model="riskOpen"
      :patient-id="patient.id"
      :riesgo="editingRisk"
      :grupos-riesgo="gruposRiesgo"
      @saved="riskSaved"
    />
  </section>
</template>

<style scoped>
.patient-relations {
  display: grid;
  gap: 2px;
}
.patient-relations__entry {
  display: grid;
  grid-template-columns: 102px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}
.patient-relations__title {
  margin: 0;
  font-size: 12px;
  font-weight: 400;
  color: var(--admission-ink, #304f6d);
  text-align: right;
}
.patient-relations__risk {
  min-width: 0;
  width: 100%;
}
.patient-relations__risk-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  width: 100%;
  min-width: 0;
  min-height: var(--el-component-size, 28px);
  padding: 4px 8px;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  font: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.patient-relations__risk-trigger:disabled {
  cursor: not-allowed;
  color: var(--el-disabled-text-color);
}
.patient-relations__risk-trigger:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.patient-relations__risk-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.patient-relations__mother :deep(.el-input__suffix .el-button) {
  min-width: 24px;
  min-height: 24px;
}
@media (max-width: 560px) {
  .patient-relations__entry {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
  }
  .patient-relations__title {
    text-align: left;
  }
}
</style>
