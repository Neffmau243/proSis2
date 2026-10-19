<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import fuaOfficialReferenceUrl from '@/assets/fua-v02-referencia.png'
import type { FuaPrintSnapshot } from '@/types/fua'
import FuaSheetPreview from '@/components/admission/FuaSheetPreview.vue'
import { useFuaCalibration } from '@/composables/useFuaCalibration'
import NutritionIndicatorsTable from '@/components/admission/NutritionIndicatorsTable.vue'
import { nutritionalTableRows, type NutritionalReferenceGroup } from '@/utils/nutritionalDisplay'
import {
  fuaDeliveryBox,
  fuaValues,
  fuaWarnings,
  fuaIdentityProblem,
  fuaUsesAbdominalPerimeter,
  layoutProblems,
  printFua,
} from '@/utils/fuaPrint'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{
  snapshot: FuaPrintSnapshot
  additionalCopy?: boolean
}>()
const {
  layout,
  storageError,
  saved,
  save,
  changed: changeGeometry,
  exportLayout,
  importLayout,
} = useFuaCalibration(() => visible.value)
const availableFields = computed(() =>
  layout.value.fields.filter(
    (field) => field.id !== 'codigo_renipress' || props.snapshot.renipress_preimpreso === false,
  ),
)
const selectedId = ref('ipress_nombre')
const selected = computed(() => layout.value.fields.find((field) => field.id === selectedId.value)!)
const acknowledged = ref(false)
const printing = ref(false)
const localError = ref('')
const tab = ref('datos')
const snapshot = computed(() => props.snapshot)
const values = computed(() => fuaValues(snapshot.value))
const nutritionGroup = computed<NutritionalReferenceGroup>(() => {
  if (snapshot.value.grupo_referencia) return snapshot.value.grupo_referencia
  if (snapshot.value.grupo_atencion_codigo === 'GESTANTES') return 'GESTANTE'
  if (snapshot.value.grupo_atencion_codigo === 'PUERPERAS') return 'PUERPERA'
  return [snapshot.value.pe, snapshot.value.te, snapshot.value.pt].some((value) => value != null)
    ? 'INFANTIL'
    : 'ADULTO'
})
const nutritionRows = computed(() =>
  nutritionalTableRows(
    {
      ...snapshot.value,
      grupo_referencia: snapshot.value.grupo_referencia ?? undefined,
      estado: snapshot.value.estado_nutricional ?? undefined,
    },
    nutritionGroup.value,
  ),
)
const warnings = computed(() => fuaWarnings(snapshot.value))
// El recuadro de parto imprime FPP o fecha real según el grupo; el PAB solo
// corresponde al grupo general.
const deliveryBox = computed(() => fuaDeliveryBox(snapshot.value))
const usesAbdominalPerimeter = computed(() => fuaUsesAbdominalPerimeter(snapshot.value))
const identityProblem = computed(() => fuaIdentityProblem(snapshot.value))
const geometryErrors = computed(() => layoutProblems(layout.value, values.value))
const personalCategory = computed(() => {
  const labels = {
    IPRESS: 'De la IPRESS',
    ITINERANTE: 'Itinerante',
    AISPED: 'Oferta flexible / AISPED',
  }
  return snapshot.value.personal_atiende ? labels[snapshot.value.personal_atiende] : 'Sin registrar'
})
const careLocation = computed(() => {
  const labels = { INTRAMURAL: 'Intramural', EXTRAMURAL: 'Extramural' }
  return snapshot.value.lugar_atencion ? labels[snapshot.value.lugar_atencion] : 'Sin registrar'
})
const canPrint = computed(
  () =>
    !identityProblem.value &&
    layout.value.calibrated &&
    !geometryErrors.value.length &&
    (!warnings.value.length || acknowledged.value),
)
const referenceValues = computed(() => ({
  ...values.value,
  codigo_renipress: snapshot.value.codigo_renipress || '',
}))
const canReview = computed(
  () =>
    !identityProblem.value &&
    !layoutProblems(layout.value, referenceValues.value).length &&
    (!warnings.value.length || acknowledged.value),
)
const printBlockReason = computed(() => {
  if (identityProblem.value) return identityProblem.value
  if (geometryErrors.value.length) return geometryErrors.value.join(' · ')
  if (!layout.value.calibrated)
    return 'Falta confirmar la calibración: pruebe el tamaño y la alineación antes de imprimir sobre la FUA preimpresa.'
  if (warnings.value.length && !acknowledged.value)
    return 'Confirme los campos pendientes en Datos de la FUA antes de imprimir.'
  return ''
})
const setupTab = computed(() =>
  identityProblem.value
    ? 'datos'
    : !layout.value.calibrated || geometryErrors.value.length
      ? 'calibracion'
      : 'datos',
)
const fieldControls = [
  { key: 'x', label: 'X (mm)', min: 0, max: 400 },
  { key: 'y', label: 'Y (mm)', min: 0, max: 600 },
  { key: 'width', label: 'Ancho (mm)', min: 1, max: 400 },
  { key: 'height', label: 'Alto (mm)', min: 1, max: 30 },
  { key: 'font', label: 'Fuente (pt)', min: 5, max: 20 },
  { key: 'step', label: 'Paso entre caracteres (mm; 0 = normal)', min: 0, max: 15 },
  { key: 'skip', label: 'Omitir caracteres iniciales (año preimpreso)', min: 0, max: 2 },
] as const

watch(
  () => [visible.value, props.snapshot] as const,
  ([open]) => {
    if (!open) return
    acknowledged.value = false
    localError.value = ''
  },
  { immediate: true },
)
function saveLayout(): void {
  if (save())
    ElMessage.success('Calibración guardada en este navegador, para todas las cuentas y pacientes.')
}
async function loadCalibration(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) await importLayout(file)
  input.value = ''
}
function useA4(): void {
  layout.value.width = 210
  layout.value.height = 297
  changeGeometry()
}
async function print(test: boolean, withReference = false): Promise<void> {
  if (printing.value || (!test && !(withReference ? canReview.value : canPrint.value))) return
  localError.value = ''
  printing.value = true
  try {
    await printFua(
      layout.value,
      withReference ? referenceValues.value : values.value,
      test,
      withReference ? fuaOfficialReferenceUrl : undefined,
      10,
    )
  } catch (error) {
    localError.value = error instanceof Error ? error.message : 'No se pudo imprimir.'
  } finally {
    printing.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="
      additionalCopy ? 'FUA adicional · copia de la atención guardada' : 'Imprimir FUA · uso local'
    "
    width="min(1120px, 96vw)"
    top="3vh"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <p class="fua-intro">
      Use «Ver FUA / guardar PDF» para ver los datos sobre el formulario en la vista de impresión.
      «Imprimir sobre FUA preimpresa» envía solo datos y marcas al papel que ya tiene el formulario.
      Se usa la copia conservada al guardar la atención; reimprimir no crea otra consulta ni
      reemplaza el número del papel preimpreso. Este sistema no envía datos al SIS.
    </p>
    <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
    <el-alert v-if="storageError" :title="storageError" type="error" :closable="false" />
    <el-alert v-if="identityProblem" :title="identityProblem" type="error" :closable="false" />
    <el-alert
      v-if="values.identity_note"
      :title="values.identity_note"
      type="info"
      :closable="false"
    />
    <el-tabs v-model="tab">
      <el-tab-pane label="Datos de la FUA" name="datos">
        <dl class="fua-summary">
          <div>
            <dt>Profesional responsable de la atención</dt>
            <dd>{{ snapshot.profesional_nombre?.trim() || 'Sin registrar' }}</dd>
          </div>
          <div>
            <dt>Personal que atiende · categoría FUA</dt>
            <dd>{{ personalCategory }}</dd>
          </div>
          <div>
            <dt>Lugar de atención</dt>
            <dd>{{ careLocation }}</dd>
          </div>
          <div>
            <dt>Atención en la FUA</dt>
            <dd>{{ snapshot.tipo_atencion || 'Sin registrar' }} · según la modalidad guardada</dd>
          </div>
          <div>
            <dt>IPRESS de la atención</dt>
            <dd>{{ snapshot.ipress_nombre || 'Sin registrar' }}</dd>
          </div>
          <div v-if="snapshot.contexto_territorial">
            <dt>Consultorio a la atención</dt>
            <dd>{{ snapshot.contexto_territorial.consultorio_ruta || 'Sin registrar' }}</dd>
          </div>
          <div v-if="snapshot.contexto_territorial">
            <dt>Servicio / especialidad a la atención</dt>
            <dd>{{ snapshot.contexto_territorial.especialidad_nombre || 'Sin registrar' }}</dd>
          </div>
          <div v-if="snapshot.contexto_territorial">
            <dt>Distrito / localidad de residencia a la atención</dt>
            <dd>
              {{ snapshot.contexto_territorial.distrito || 'Sin registrar' }} /
              {{ snapshot.contexto_territorial.localidad || 'Sin registrar' }}
            </dd>
          </div>
          <div>
            <dt>RENIPRESS</dt>
            <dd>
              {{ snapshot.codigo_renipress || 'Sin registrar' }}
              <span class="fua-field-note">{{
                snapshot.renipress_preimpreso !== false
                  ? 'Configurado como preimpreso: no se sobreimprime. Compruebe el código de su hoja.'
                  : 'Se imprime el código guardado de la IPRESS.'
              }}</span>
            </dd>
          </div>
          <div>
            <dt>Paciente</dt>
            <dd>
              {{ snapshot.apellido_paterno }} {{ snapshot.apellido_materno }},
              {{ snapshot.primer_nombre }} {{ snapshot.otros_nombres }}
            </dd>
          </div>
          <div>
            <dt>Afiliación SIS del paciente</dt>
            <dd>
              {{ values.sis_diresa || '—' }} · {{ values.sis_tipo || '—' }} ·
              {{ values.sis_numero || 'Sin registrar' }}
            </dd>
          </div>
          <div>
            <dt>Etnia declarada · código</dt>
            <dd>{{ snapshot.etnia_codigo || 'Sin declarar' }}</dd>
          </div>
          <div>
            <dt>Identificación</dt>
            <dd>
              {{ snapshot.tipo_documento }} {{ snapshot.numero_documento }} ·
              {{
                snapshot.tdi ? `TDI ${snapshot.tdi}` : 'Tipo indicado con abreviatura de uso local'
              }}
            </dd>
          </div>
          <div>
            <dt>Atención</dt>
            <dd>{{ snapshot.fecha_atencion }} · {{ snapshot.hora_atencion.slice(0, 5) }}</dd>
          </div>
          <div>
            <dt>Peso / talla / PA / IMC</dt>
            <dd>
              {{ values.peso_kg || '—' }} kg / {{ values.talla_cm || '—' }} cm /
              {{ values.pa || '—' }} mmHg / {{ values.imc || '—' }}
            </dd>
          </div>
          <div v-if="deliveryBox">
            <dt>{{ deliveryBox.label }}</dt>
            <dd>{{ deliveryBox.value || 'Sin registrar' }}</dd>
          </div>
          <div v-else-if="usesAbdominalPerimeter">
            <dt>Perímetro abdominal</dt>
            <dd>{{ values.perimetro_abdominal_cm || '—' }} cm</dd>
          </div>
        </dl>
        <section class="fua-nutrition" aria-labelledby="fua-nutrition-title">
          <h3 id="fua-nutrition-title">Valoración nutricional conservada</h3>
          <NutritionIndicatorsTable
            :rows="nutritionRows"
            label="Indicadores nutricionales conservados en la FUA"
          />
        </section>
        <p>
          El profesional se conserva con la atención. La categoría de personal y el lugar se copian
          de la configuración de la sede: «De la IPRESS» corresponde a personal con vínculo
          contractual con esa IPRESS; «Intramural» corresponde a atención dentro de la IPRESS.
          Compruebe que describan la atención realizada. La afiliación y la etnia provienen de la
          ficha del paciente; este módulo no acredita la cobertura SIS.
        </p>
        <el-alert
          v-if="warnings.length"
          type="warning"
          title="Campos pendientes de revisar"
          :closable="false"
        >
          <p>{{ warnings.join(' · ') }}</p>
        </el-alert>
        <el-checkbox v-if="warnings.length" v-model="acknowledged"
          >Revisé los faltantes; completaré los que correspondan a mano.</el-checkbox
        >
        <p>
          No es una validación integral del SIS: prestaciones, diagnósticos, firmas, vacunas y otros
          campos quedan fuera de este prellenado.
        </p>
      </el-tab-pane>
      <el-tab-pane label="Vista previa y calibración" name="calibracion">
        <p class="fua-storage-status" role="status">
          {{
            saved
              ? 'Calibración guardada automáticamente en este navegador.'
              : 'Todavía no hay una calibración guardada en este navegador.'
          }}
          Se reutiliza para todas las cuentas y pacientes de esta dirección de la aplicación. Al
          cambiar de navegador, dirección o equipo, importe una copia de la calibración.
        </p>
        <el-alert
          title="La plantilla es referencial; pruebe en papel en blanco antes de usar una FUA vigente."
          type="warning"
          :closable="false"
        />
        <ol class="fua-calibration-steps">
          <li>Seleccione el tamaño real de su hoja. Use A4 solo si mide 210 × 297 mm.</li>
          <li>
            Imprima una prueba sin datos en papel en blanco y compárela con su FUA preimpresa.
          </li>
          <li>
            Ajuste las posiciones y confirme la prueba física. Los cambios se guardan
            automáticamente.
          </li>
        </ol>
        <p>
          El texto continuo se ajusta automáticamente dentro de cada casilla, hasta un mínimo de 5
          pt. La vista previa y la impresión usan el mismo tamaño; no se recortan los datos ni se
          cambian las posiciones guardadas.
        </p>
        <div class="fua-calibration">
          <div class="fua-controls">
            <el-form label-position="top">
              <el-button class="fua-paper-preset" @click="useA4">Usar A4 (210 × 297 mm)</el-button>
              <el-form-item label="Ancho de la hoja (mm)"
                ><el-input-number
                  v-model="layout.width"
                  :min="100"
                  :max="400"
                  :value-on-clear="216"
                  @change="changeGeometry"
              /></el-form-item>
              <el-form-item label="Alto de la hoja (mm)"
                ><el-input-number
                  v-model="layout.height"
                  :min="150"
                  :max="600"
                  :value-on-clear="356"
                  @change="changeGeometry"
              /></el-form-item>
              <el-form-item label="Desplazamiento horizontal (mm)"
                ><el-input-number
                  v-model="layout.offsetX"
                  :min="-50"
                  :max="50"
                  :step="0.5"
                  :value-on-clear="0"
                  @change="changeGeometry"
              /></el-form-item>
              <el-form-item label="Desplazamiento vertical (mm)"
                ><el-input-number
                  v-model="layout.offsetY"
                  :min="-50"
                  :max="50"
                  :step="0.5"
                  :value-on-clear="0"
                  @change="changeGeometry"
              /></el-form-item>
              <el-form-item label="Campo a ajustar"
                ><el-select v-model="selectedId"
                  ><el-option
                    v-for="field in availableFields"
                    :key="field.id"
                    :value="field.id"
                    :label="field.label" /></el-select
              ></el-form-item>
              <el-checkbox v-model="selected.enabled" @change="changeGeometry"
                >Imprimir este campo</el-checkbox
              >
              <el-form-item
                v-for="control in fieldControls"
                :key="control.key"
                :label="control.label"
              >
                <el-input-number
                  v-model="selected[control.key]"
                  :min="control.min"
                  :max="control.max"
                  :step="control.key === 'skip' ? 1 : 0.5"
                  :precision="control.key === 'skip' ? 0 : 2"
                  :value-on-clear="control.min"
                  @change="changeGeometry"
                />
              </el-form-item>
            </el-form>
            <p class="fua-reference-note">
              Referencia única: anexo 1 de la Directiva SIS V.02. La vista previa y «Ver FUA /
              guardar PDF» usan la misma imagen. «Imprimir sobre FUA preimpresa» envía solo datos y
              marcas al papel que ya tiene el formulario.
            </p>
          </div>
          <FuaSheetPreview
            :layout="layout"
            :values="values"
            :background="fuaOfficialReferenceUrl"
            :inset="10"
            :selected-id="selectedId"
            :preprinted-renipress="snapshot.renipress_preimpreso !== false"
            @select="selectedId = $event"
          />
        </div>
        <p>
          Imprima a tamaño real / 100 %, sin márgenes ni encabezados. Seleccione en el controlador
          el mismo tamaño de papel. La vista previa del navegador no verifica la impresora física.
        </p>
        <el-alert
          v-if="geometryErrors.length"
          title="Ajustes necesarios para imprimir"
          type="error"
          :closable="false"
        >
          <ul>
            <li v-for="message in geometryErrors" :key="message">{{ message }}</li>
          </ul>
        </el-alert>
        <div class="fua-calibration-actions">
          <el-button :loading="printing" @click="print(true)">Imprimir prueba sin datos</el-button>
          <el-checkbox v-model="layout.calibrated"
            >Comprobé tamaño y alineación en una prueba física.</el-checkbox
          >
          <el-button @click="saveLayout">Guardar calibración</el-button>
          <el-button @click="exportLayout">Exportar calibración</el-button>
          <label for="fua-layout-import">Importar calibración</label>
          <input
            id="fua-layout-import"
            type="file"
            accept="application/json,.json"
            @change="loadCalibration"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <div class="fua-footer">
        <span v-if="!canPrint" role="status">{{ printBlockReason }}</span>
        <el-button v-if="!canPrint && tab !== setupTab" @click="tab = setupTab">{{
          setupTab === 'calibracion' ? 'Ir a calibración' : 'Revisar datos'
        }}</el-button>
        <el-button @click="visible = false">Cerrar</el-button>
        <el-button :loading="printing" :disabled="!canPrint" @click="print(false)"
          >Imprimir sobre FUA preimpresa</el-button
        >
        <el-button
          type="primary"
          :loading="printing"
          :disabled="!canReview"
          @click="print(false, true)"
        >
          Ver FUA / guardar PDF
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.fua-intro {
  margin-top: 0;
}
.fua-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.fua-summary dt {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.fua-summary dd {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}
.fua-field-note {
  display: block;
  margin-top: 4px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.fua-calibration-steps {
  margin: 16px 0;
  padding-left: 24px;
  line-height: 1.5;
}
.fua-paper-preset {
  margin-bottom: 16px;
}
.fua-nutrition {
  margin: 20px 0;
}
.fua-nutrition h3 {
  margin: 0 0 8px;
  font-size: 1rem;
}
.fua-calibration {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  gap: 20px;
  margin-top: 16px;
}
.fua-controls {
  max-height: 60vh;
  overflow: auto;
  padding-right: 12px;
}
.fua-controls input[type='file'] {
  max-width: 100%;
  margin: 8px 0;
}
.fua-reference-note {
  margin: 16px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.fua-storage-status {
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
.fua-calibration-actions input[type='file'] {
  max-width: 100%;
}
.fua-footer,
.fua-calibration-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}
.fua-footer span {
  margin-right: auto;
}
@media (max-width: 700px) {
  .fua-summary,
  .fua-calibration {
    grid-template-columns: minmax(0, 1fr);
  }
  .fua-controls {
    max-height: none;
  }
  .fua-footer {
    align-items: stretch;
  }
  .fua-footer .el-button {
    margin: 0;
  }
}
</style>
