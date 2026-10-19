<script setup lang="ts">
import { computed } from 'vue'
import RiskGroupSelect from '@/components/patient/RiskGroupSelect.vue'

import type { RiskGroupCatalogItem } from '@/services/catalogos'

import type { ResponsibleRelationship, ResponsibleRow, RiskRow } from './patientRegistration.types'

type ParentRelationship = Extract<ResponsibleRelationship, 'MADRE' | 'PADRE'>
type ParentField = 'nombre_completo' | 'numero_documento'

defineProps<{
  gruposRiesgo: RiskGroupCatalogItem[]
}>()

const responsables = defineModel<ResponsibleRow[]>('responsables', { required: true })
const riesgos = defineModel<RiskRow[]>('riesgos', { required: true })
const telefonoPrincipal = defineModel<string>('telefonoPrincipal', { required: true })

const relacionAlMenor = computed<ResponsibleRelationship | null>(() => {
  const principal = responsables.value.find((responsable) => responsable.es_principal)
  return (principal ?? responsables.value[0])?.parentesco ?? null
})

const riesgoPrincipal = computed<RiskRow | null>(() => riesgos.value[0] ?? null)

function newResponsible(parentesco: ResponsibleRelationship, esPrincipal = false): ResponsibleRow {
  return {
    parentesco,
    nombre_completo: '',
    // El tipo acompaña al número, nunca al revés: el backend rechaza un tipo
    // de documento enviado sin su número.
    tipo_documento_codigo: null,
    numero_documento: null,
    telefono: null,
    es_principal: esPrincipal,
  }
}

/**
 * El formulario solo captura el DNI: el tipo se deduce de la presencia del
 * número para mantener el par tipo/número completo o vacío.
 */
function documentFields(field: ParentField, value: string): Partial<ResponsibleRow> {
  if (field === 'numero_documento') {
    const numero_documento = value || null
    return { numero_documento, tipo_documento_codigo: numero_documento ? 'DNI' : null }
  }
  return { nombre_completo: value }
}

function responsibleIndex(parentesco: ParentRelationship): number {
  return responsables.value.findIndex((responsable) => responsable.parentesco === parentesco)
}

function parentValue(parentesco: ParentRelationship, field: ParentField): string {
  return responsables.value[responsibleIndex(parentesco)]?.[field] ?? ''
}

function updateRelacionAlMenor(parentesco: ResponsibleRelationship | null): void {
  if (!parentesco) return

  const primaryIndex = responsables.value.findIndex((responsable) => responsable.es_principal)
  const matchingIndex = responsables.value.findIndex(
    (responsable) => responsable.parentesco === parentesco,
  )

  if (matchingIndex >= 0) {
    responsables.value = responsables.value.map((responsable, index) => ({
      ...responsable,
      es_principal: index === matchingIndex,
    }))
    return
  }

  if (primaryIndex < 0) {
    responsables.value = [...responsables.value, newResponsible(parentesco, true)]
    return
  }

  responsables.value = responsables.value.map((responsable, index) =>
    index === primaryIndex ? { ...responsable, parentesco } : responsable,
  )
}

function updateParentField(
  parentesco: ParentRelationship,
  field: ParentField,
  value: string,
): void {
  const index = responsibleIndex(parentesco)
  if (index < 0) {
    if (!value) return
    responsables.value = [
      ...responsables.value,
      { ...newResponsible(parentesco), ...documentFields(field, value) },
    ]
    return
  }

  responsables.value = responsables.value.map((responsable, rowIndex) =>
    rowIndex === index ? { ...responsable, ...documentFields(field, value) } : responsable,
  )
}

function updateRiskGroup(grupoRiesgoId: number | null): void {
  if (grupoRiesgoId === null) {
    riesgos.value = riesgos.value.slice(1)
    return
  }

  if (!riesgos.value.length) {
    riesgos.value = [
      {
        grupo_riesgo_id: grupoRiesgoId,
        fecha_inicio: '',
        fecha_fin: null,
        observacion: '',
      },
    ]
    return
  }

  riesgos.value = riesgos.value.map((riesgo, index) =>
    index === 0 ? { ...riesgo, grupo_riesgo_id: grupoRiesgoId } : riesgo,
  )
}

function updateRiskStartDate(fechaInicio: string): void {
  if (!riesgos.value.length) return

  riesgos.value = riesgos.value.map((riesgo, index) =>
    index === 0 ? { ...riesgo, fecha_inicio: fechaInicio } : riesgo,
  )
}

function updateRiskReason(observacion: string): void {
  riesgos.value = riesgos.value.map((risk, index) =>
    index === 0 ? { ...risk, observacion } : risk,
  )
}
</script>

<template>
  <aside class="family-sections" aria-label="Datos familiares y grupos de riesgo">
    <section class="family-section">
      <header class="family-section__header">
        <h3 class="family-section__title">Datos familiares <span>(solo niños menores)</span></h3>
      </header>

      <div class="family-section__fields">
        <el-form-item class="family-field" label="Relación al menor">
          <el-select
            clearable
            placeholder="Seleccione"
            :model-value="relacionAlMenor"
            @update:model-value="updateRelacionAlMenor"
          >
            <el-option label="Madre" value="MADRE" />
            <el-option label="Padre" value="PADRE" />
            <el-option label="Tutor" value="TUTOR" />
          </el-select>
        </el-form-item>
      </div>
    </section>

    <section class="family-section">
      <header class="family-section__header">
        <h3 class="family-section__title">Datos del padre</h3>
      </header>

      <div class="family-section__fields">
        <el-form-item class="family-field" label="Apellidos y nombres">
          <el-input
            :model-value="parentValue('PADRE', 'nombre_completo')"
            @update:model-value="updateParentField('PADRE', 'nombre_completo', $event)"
          />
        </el-form-item>
        <el-form-item class="family-field family-field--short" label="Nro. DNI">
          <el-input
            :model-value="parentValue('PADRE', 'numero_documento')"
            @update:model-value="updateParentField('PADRE', 'numero_documento', $event)"
          />
        </el-form-item>
      </div>
    </section>

    <section class="family-section">
      <header class="family-section__header">
        <h3 class="family-section__title">Datos de la madre</h3>
      </header>

      <div class="family-section__fields">
        <el-form-item class="family-field" label="Apellidos y nombres">
          <el-input
            :model-value="parentValue('MADRE', 'nombre_completo')"
            @update:model-value="updateParentField('MADRE', 'nombre_completo', $event)"
          />
        </el-form-item>
        <el-form-item class="family-field family-field--short" label="Nro. DNI">
          <el-input
            :model-value="parentValue('MADRE', 'numero_documento')"
            @update:model-value="updateParentField('MADRE', 'numero_documento', $event)"
          />
        </el-form-item>
      </div>
    </section>

    <section class="family-section family-section--contact">
      <div class="family-section__fields">
        <el-form-item class="family-field" label="Nro. celular">
          <el-input v-model="telefonoPrincipal" />
        </el-form-item>
        <el-form-item class="family-field" label="Grupo de riesgo">
          <RiskGroupSelect
            :groups="gruposRiesgo"
            :model-value="riesgoPrincipal?.grupo_riesgo_id ?? null"
            @update:model-value="updateRiskGroup"
          />
        </el-form-item>
        <el-form-item v-if="riesgoPrincipal" class="family-field" label="Inicio del riesgo">
          <el-date-picker
            :model-value="riesgoPrincipal.fecha_inicio"
            type="date"
            value-format="YYYY-MM-DD"
            @update:model-value="updateRiskStartDate($event ?? '')"
          />
        </el-form-item>
      </div>
      <el-form-item v-if="riesgoPrincipal" label="Motivo y evaluación profesional">
        <el-input
          :model-value="riesgoPrincipal.observacion"
          type="textarea"
          maxlength="500"
          @update:model-value="updateRiskReason"
        />
      </el-form-item>
    </section>
  </aside>
</template>

<style scoped>
.family-sections {
  display: grid;
  align-content: start;
  gap: 6px;
  min-width: 0;
  --el-component-size: var(--registration-control-size, 28px);
}

/* El wrapper del select debe seguir la misma altura que los inputs vecinos. */
.family-sections :deep(.el-select__wrapper) {
  min-height: var(--el-component-size);
  padding-top: 0;
  padding-bottom: 0;
}

.family-section {
  min-width: 0;
  padding: 0 8px 8px;
  border: 1px solid var(--registration-border, #b9cbdf);
  border-radius: 4px;
  background: var(--registration-panel, #e8eff7);
}

.family-section--contact {
  padding-top: 8px;
}

.family-section__header {
  margin: 0 -8px 6px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--registration-border, #b9cbdf);
  background: var(--registration-heading, #d4e1ef);
}

.family-section__title {
  margin: 0;
  color: var(--registration-ink, #304f6d);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
}

.family-section__title span {
  font-weight: 600;
}

.family-section__fields {
  display: grid;
  gap: 4px;
}

.family-section__fields :deep(.family-field) {
  display: block;
  min-width: 0;
  margin: 0;
}

.family-section__fields :deep(.family-field .el-form-item__label) {
  height: auto;
  display: block;
  margin: 0 0 2px;
  padding: 0;
  color: var(--registration-ink, #304f6d);
  font-size: 12px;
  line-height: 1.2;
}

.family-section__fields :deep(.family-field .el-form-item__content) {
  min-width: 0;
  margin-left: 0 !important;
}

.family-section__fields :deep(.family-field--short .el-form-item__content) {
  max-width: 160px;
}

.family-section__fields :deep(.el-select),
.family-section__fields :deep(.el-date-editor) {
  width: 100%;
}

.family-section__fields :deep(.el-input__inner),
.family-section__fields :deep(.el-select__selected-item),
.family-section__fields :deep(.el-select__placeholder) {
  font-size: 12px;
}

@media (max-width: 640px) {
  .family-sections {
    --el-component-size: 36px;
  }
}
</style>
