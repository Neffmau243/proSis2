<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import fuaReferenceUrl from '@/assets/fua-referencia.webp'
import type { FuaPrintSnapshot } from '@/types/fua'
import NutritionIndicatorsTable from '@/components/admission/NutritionIndicatorsTable.vue'
import { nutritionalTableRows, type NutritionalReferenceGroup } from '@/utils/nutritionalDisplay'
import {
  defaultFuaLayout,
  FUA_LAYOUT_KEY,
  fuaDeliveryBox,
  fuaFieldFont,
  fuaValues,
  fuaWarnings,
  fuaIdentityProblem,
  fuaUsesAbdominalPerimeter,
  layoutProblems,
  parseFuaLayout,
  printFua,
} from '@/utils/fuaPrint'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{
  snapshot: FuaPrintSnapshot
  additionalCopy?: boolean
}>()
const layout = ref(defaultFuaLayout())
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
// La plantilla incluida es solo una guía; el escaneo alternativo no se persiste.
const customBackground = ref('')
const background = computed(() => customBackground.value || fuaReferenceUrl)
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
try {
  const saved = localStorage.getItem(FUA_LAYOUT_KEY)
  if (saved) layout.value = parseFuaLayout(saved)
} catch {
  localError.value = 'No se pudo leer la calibración. Se usan posiciones de ejemplo.'
}

function saveLayout(): void {
  try {
    localStorage.setItem(
      FUA_LAYOUT_KEY,
      JSON.stringify(parseFuaLayout(JSON.stringify(layout.value))),
    )
    ElMessage.success('Calibración guardada en este navegador, sin datos del paciente.')
  } catch {
    localError.value =
      'No se pudo guardar la calibración. Revise sus valores o el almacenamiento del navegador.'
  }
}
function changeGeometry(): void {
  layout.value.calibrated = false
}
function useA4(): void {
  layout.value.width = 210
  layout.value.height = 297
  changeGeometry()
}
function loadBackground(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (
    !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) ||
    file.size > 10 * 1024 * 1024
  ) {
    localError.value = 'Use un escaneo PNG, JPG o WebP de hasta 10 MB.'
    return
  }
  if (customBackground.value) URL.revokeObjectURL(customBackground.value)
  customBackground.value = URL.createObjectURL(file)
}
function clearCustomBackground(): void {
  if (customBackground.value) URL.revokeObjectURL(customBackground.value)
  customBackground.value = ''
}
watch(visible, (open) => {
  if (!open) clearCustomBackground()
})
onBeforeUnmount(clearCustomBackground)
async function print(test: boolean): Promise<void> {
  if (printing.value || (!test && !canPrint.value)) return
  localError.value = ''
  printing.value = true
  try {
    await printFua(layout.value, values.value, test)
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
      Copia conservada al guardar la atención. Reimprimir no crea otra consulta. Solo se imprimen
      datos y marcas; el número del formulario preimpreso no se reemplaza. Este sistema no envía
      datos al SIS.
    </p>
    <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
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
              {{ snapshot.sis_diresa || '—' }} · {{ values.sis_numero_completo || 'Sin registrar' }}
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
          <li>Ajuste las posiciones, confirme la prueba física y guarde la calibración.</li>
        </ol>
        <p>
          El texto continuo se ajusta automáticamente dentro de cada casilla, hasta un mínimo de 5
          pt. La vista previa y la impresión usan el mismo tamaño; no se recortan los datos ni se
          cambian las posiciones guardadas.
        </p>
        <div class="fua-calibration">
          <div class="fua-controls">
            <el-form label-position="top" @change="changeGeometry">
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
              Se muestra una FUA histórica solo para comparar posiciones. No se envía, no se guarda
              y nunca se imprime.
            </p>
            <label for="fua-scan">Usar un escaneo propio como guía temporal</label>
            <input
              id="fua-scan"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              @change="loadBackground"
            />
            <el-button v-if="customBackground" @click="clearCustomBackground"
              >Volver a la plantilla referencial</el-button
            >
          </div>
          <div class="fua-preview-scroll" aria-label="Vista previa de posiciones sobre la hoja">
            <div
              class="fua-preview"
              :style="{ width: `${layout.width}mm`, height: `${layout.height}mm` }"
            >
              <img
                :src="background"
                alt="Plantilla FUA de referencia; no se imprime"
                class="fua-background"
              />
              <button
                v-for="field in availableFields.filter((f) => f.enabled)"
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
                @click="selectedId = field.id"
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
        <el-button type="primary" :loading="printing" :disabled="!canPrint" @click="print(false)"
          >Imprimir solo datos</el-button
        >
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
  width: 100%;
  height: 100%;
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
