<script setup lang="ts">
import { computed } from 'vue'
import PatientSisFields from './PatientSisFields.vue'
import PatientInsuranceBrand from './PatientInsuranceBrand.vue'
import PatientConditionSelect from './PatientConditionSelect.vue'
import FamilyHistorySelector from './FamilyHistorySelector.vue'
import { isSisInsurance } from '@/utils/patientInsurance'
import { localityOptions, localitySelection } from '@/utils/localitySelection'
import type {
  CodeCatalogItem,
  EstablishmentCatalogItem,
  FamilyHistoryCatalogItem,
  IdCatalogItem,
  LocalidadCatalogItem,
  UbigeoCatalogItem,
} from '@/services/catalogos'

import type {
  PatientRegistrationDraft,
  PatientRegistrationPatch,
} from './patientRegistration.types'

const props = defineProps<{
  form: PatientRegistrationDraft
  tiposDocumento: CodeCatalogItem[]
  sexos: CodeCatalogItem[]
  seguros: IdCatalogItem[]
  establecimientos: EstablishmentCatalogItem[]
  establecimientosLoading: boolean
  establecimientosError?: string | null
  ubigeos: UbigeoCatalogItem[]
  ubigeosLoading: boolean
  ubigeosError?: string | null
  localidades: LocalidadCatalogItem[]
  localidadesLoading: boolean
  localidadesError?: string | null
  historiasFamiliares: FamilyHistoryCatalogItem[]
  historiasFamiliaresLoading: boolean
}>()

const emit = defineEmits<{
  update: [changes: PatientRegistrationPatch]
  searchEstablecimientos: [query: string]
  searchUbigeos: [query: string]
}>()

const localitySuggestions = computed(() =>
  localityOptions(
    props.localidades,
    props.ubigeos.find((item) => item.codigo === props.form.ubigeo_residencia_codigo)?.distrito,
  ),
)
const selectedInsurance = computed(() =>
  props.seguros.find((item) => item.id === props.form.seguro_id),
)

function update(changes: PatientRegistrationPatch): void {
  emit('update', changes)
}

// Las listas Z_* sugieren nombres: el legado también guarda localidades escritas.
function updateLocality(value: number | string | null): void {
  const selection = localitySelection(value, props.localidades)
  emit('update', { ...selection, localidad: selection.localidad ?? '' })
}
</script>

<template>
  <section class="base-section" aria-labelledby="patient-data-title">
    <header class="base-section__header">
      <h3 id="patient-data-title" class="base-section__title">Base de datos</h3>
    </header>

    <div class="base-section__fields">
      <el-form-item class="base-field" label="N.° historia clínica">
        <el-input
          :model-value="form.historia_clinica"
          @update:model-value="update({ historia_clinica: $event })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Historia familiar" prop="historia_familiar">
        <FamilyHistorySelector
          :model-value="form.historia_familiar"
          :options="historiasFamiliares"
          :loading="historiasFamiliaresLoading"
          @update:model-value="update({ historia_familiar: $event ?? '' })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Tipo de documento" prop="tipo_documento_codigo">
        <el-select
          placeholder="Seleccione"
          :model-value="form.tipo_documento_codigo"
          @update:model-value="update({ tipo_documento_codigo: $event })"
        >
          <el-option
            v-for="tipo in tiposDocumento"
            :key="tipo.codigo"
            :label="tipo.nombre"
            :value="tipo.codigo"
          />
        </el-select>
      </el-form-item>

      <el-form-item class="base-field" label="N.° documento" prop="numero_documento">
        <el-input
          :model-value="form.numero_documento"
          @update:model-value="update({ numero_documento: $event })"
        />
      </el-form-item>

      <el-form-item
        class="base-field"
        label="Fecha de nacimiento"
        prop="fecha_nacimiento"
      >
        <el-date-picker
          :model-value="form.fecha_nacimiento"
          type="date"
          format="DD/MM/YYYY"
          value-format="YYYY-MM-DD"
          :disabled-date="(date: Date) => date.getTime() > Date.now()"
          @update:model-value="update({ fecha_nacimiento: $event ?? '' })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Apellido paterno">
        <el-input
          :model-value="form.apellido_paterno"
          @update:model-value="update({ apellido_paterno: $event })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Apellido materno">
        <el-input
          :model-value="form.apellido_materno"
          @update:model-value="update({ apellido_materno: $event })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Primer nombre" prop="primer_nombre">
        <el-input
          :model-value="form.primer_nombre"
          @update:model-value="update({ primer_nombre: $event })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Otros nombres">
        <el-input
          :model-value="form.otros_nombres"
          @update:model-value="update({ otros_nombres: $event })"
        />
      </el-form-item>

      <el-form-item class="base-field" label="Sexo">
        <el-select
          clearable
          placeholder="Seleccione"
          :model-value="form.sexo_codigo"
          @update:model-value="update({ sexo_codigo: $event })"
        >
          <el-option
            v-for="sexo in sexos"
            :key="sexo.codigo"
            :label="sexo.nombre"
            :value="sexo.codigo"
          />
        </el-select>
      </el-form-item>

      <el-form-item class="base-field" label="Distrito" :error="ubigeosError || undefined">
        <el-select
          clearable
          filterable
          remote
          :model-value="form.ubigeo_residencia_codigo"
          :remote-method="(query: string) => emit('searchUbigeos', query)"
          :loading="ubigeosLoading"
          placeholder="Distrito donde reside el paciente"
          @update:model-value="update({ ubigeo_residencia_codigo: $event })"
        >
          <el-option
            v-for="ubigeo in ubigeos"
            :key="ubigeo.codigo"
            :label="`${ubigeo.distrito} · ${ubigeo.provincia}`"
            :value="ubigeo.codigo"
          />
        </el-select>
      </el-form-item>

      <el-form-item class="base-field" label="Localidad" :error="localidadesError || undefined">
        <el-select
          clearable
          filterable
          allow-create
          default-first-option
          :model-value="form.localidad_id ?? (form.localidad || null)"
          :disabled="!form.ubigeo_residencia_codigo"
          :loading="localidadesLoading"
          :placeholder="
            form.ubigeo_residencia_codigo
              ? 'Seleccione o escriba la localidad'
              : 'Elija el distrito primero'
          "
          @update:model-value="updateLocality"
        >
          <el-option
            v-for="localidad in localitySuggestions"
            :key="localidad.value"
            :label="localidad.label"
            :value="localidad.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item class="base-field" label="Dirección">
        <el-input
          :model-value="form.direccion"
          placeholder="Ej. Calle Cahuide 504"
          @update:model-value="update({ direccion: $event })"
        />
      </el-form-item>

      <el-form-item
        class="base-field"
        label="Establecimiento"
        :error="establecimientosError || undefined"
      >
        <el-select
          clearable
          filterable
          remote
          :model-value="form.establecimiento_registro_id"
          :remote-method="(query: string) => emit('searchEstablecimientos', query)"
          :loading="establecimientosLoading"
          placeholder="Sede donde se registra al paciente"
          @update:model-value="update({ establecimiento_registro_id: $event })"
        >
          <el-option
            v-for="establecimiento in establecimientos"
            :key="establecimiento.id"
            :label="establecimiento.nombre"
            :value="establecimiento.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item class="base-field" label="Seguro de salud">
        <el-select
          clearable
          filterable
          placeholder="Seleccione"
          :model-value="form.seguro_id"
          @update:model-value="update({ seguro_id: $event })"
        >
          <el-option
            v-for="seguro in seguros"
            :key="seguro.id"
            :label="seguro.nombre"
            :value="seguro.id"
          />
        </el-select>
      </el-form-item>
    </div>
    <PatientSisFields
      :value="form"
      :affiliation-disabled="!isSisInsurance(selectedInsurance)"
      @update="update"
    >
      <template #insurance-brand>
        <PatientInsuranceBrand
          class="base-section__insurance-brand"
          :insurance="selectedInsurance"
          :insurance-id="form.seguro_id"
        />
      </template>
      <div class="base-section__fields">
        <el-form-item class="base-field" label="Condición">
          <PatientConditionSelect
            :model-value="form.condicion"
            @update:model-value="update({ condicion: $event ?? '' })"
          />
        </el-form-item>
      </div>
    </PatientSisFields>
  </section>
</template>

<style scoped>
.base-section {
  min-width: 0;
  padding: 0 8px 6px;
  border: 1px solid var(--registration-border, #b9cbdf);
  border-radius: 4px;
  background: var(--registration-panel, #e8eff7);
  --el-component-size: var(--registration-control-size, 28px);
}

/* El wrapper del select debe seguir la misma altura que los inputs vecinos. */
.base-section :deep(.el-select__wrapper) {
  min-height: var(--el-component-size);
  padding-top: 0;
  padding-bottom: 0;
}

.base-section__header {
  margin: 0 -8px 6px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--registration-border, #b9cbdf);
  background: var(--registration-heading, #d4e1ef);
}

.base-section__title {
  margin: 0;
  color: var(--registration-ink, #304f6d);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
}

.base-section__fields {
  display: grid;
  gap: 2px;
}

.base-section__fields :deep(.base-field) {
  display: grid;
  grid-template-columns: 136px minmax(0, 1fr);
  align-items: start;
  min-width: 0;
  margin: 0;
}

.base-section__fields :deep(.base-field .el-form-item__label) {
  display: flex;
  width: 100%;
  box-sizing: border-box;
  min-height: var(--el-component-size);
  align-items: center;
  height: auto;
  /* Element Plus le pone 8px de margen inferior a la etiqueta en label-position
     "top"; dentro de la grilla eso la subía 4px respecto al centro de la fila. */
  margin: 0;
  padding: 0 8px 0 0;
  color: var(--registration-ink, #304f6d);
  font-size: 12px;
  line-height: 1.2;
  justify-content: flex-end;
  text-align: right;
}

.base-section__fields :deep(.base-field .el-form-item__content) {
  min-width: 0;
  margin-left: 0 !important;
}

.base-section__fields :deep(.el-form-item__error) {
  position: static;
  flex-basis: 100%;
  padding-top: 4px;
}

.base-section__fields :deep(.base-field.is-error) {
  margin-bottom: 4px;
}

.base-section__fields :deep(.el-select),
.base-section__fields :deep(.el-date-editor) {
  width: 100%;
}

.base-section__fields :deep(.el-input__inner),
.base-section__fields :deep(.el-select__selected-item),
.base-section__fields :deep(.el-select__placeholder) {
  font-size: 12px;
}

@media (max-width: 640px) {
  .base-section__fields :deep(.base-field) {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }

  .base-section__fields :deep(.base-field .el-form-item__label) {
    min-height: 0;
    padding-right: 0;
    justify-content: flex-start;
    text-align: left;
  }

  .base-section {
    --el-component-size: 36px;
  }
}
</style>
