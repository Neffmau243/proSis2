<template>
  <div>
    <div class="page-header">
      <h2>Atención #{{ attention?.id ?? attentionId }}</h2>
      <div>
        <el-button
          v-if="attention?.estado === 'ATENDIDO' && attention.fua_impresion"
          @click="printDialog = true"
          >Imprimir S.I.S.</el-button
        >
        <el-button
          v-if="attention?.estado === 'ATENDIDO' && can('ATENCION_ANULAR')"
          type="danger"
          plain
          @click="cancelDialog = true"
        >
          Anular atención
        </el-button>
        <el-button
          v-if="attention?.estado === 'ATENDIDO' && can('FUA_EMITIR')"
          @click="openDialog('fua')"
        >
          Registrar FUA
        </el-button>
        <el-button
          v-if="attention?.estado === 'ATENDIDO' && can('CERTIFICADO_EMITIR')"
          @click="openDialog('certificado')"
        >
          Emitir certificado
        </el-button>
        <el-button
          v-if="attention?.estado === 'ATENDIDO' && can('REFERENCIA_EMITIR')"
          @click="openDialog('referencia')"
        >
          Crear referencia
        </el-button>
        <el-button @click="router.back()">Volver</el-button>
      </div>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <el-card v-loading="loading">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="Paciente">{{ patientName }}</el-descriptions-item>
        <el-descriptions-item label="Estado">
          <el-tag :type="attention?.estado === 'ANULADO' ? 'danger' : 'success'">
            {{ attention?.estado }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Grupo etario">{{
          attention?.grupo_etario_codigo
        }}</el-descriptions-item>
        <el-descriptions-item label="Grupo de atención">{{
          careGroupLabel(attention?.grupo_atencion_codigo)
        }}</el-descriptions-item>
        <el-descriptions-item label="Fecha de atención">{{
          attention?.fecha_atencion
        }}</el-descriptions-item>
        <el-descriptions-item label="Fecha efectiva">{{
          attention?.fecha_atendido || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Modalidad">{{
          attention?.modalidad_atencion_codigo
        }}</el-descriptions-item>
        <el-descriptions-item label="Establecimiento">{{
          attention?.establecimiento_nombre || attention?.fua_impresion?.ipress_nombre || attention?.establecimiento_id
        }}</el-descriptions-item>
        <el-descriptions-item label="Consultorio">{{
          attention?.consultorio_ruta || attention?.consultorio_nombre || attention?.consultorio_id
        }}</el-descriptions-item>
        <el-descriptions-item label="Profesional">{{
          attention?.profesional_nombre || attention?.fua_impresion?.profesional_nombre || attention?.profesional_id
        }}</el-descriptions-item>
        <el-descriptions-item label="Servicio / especialidad">{{
          attention?.especialidad_nombre || attention?.especialidad_codigo || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Edad registrada">{{
          attention ? `${attention.edad_anios ?? '—'} años` : '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Historia clínica">{{
          attention?.historia_clinica_snapshot || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="N.º de referencia recibida">{{
          attention?.numero_referencia_ingreso || attention?.fua_impresion?.referencia_hoja || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="N.º de contrarreferencia recibida">{{
          attention?.numero_contrarreferencia_ingreso || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Historia familiar a la atención">{{
          attention?.contexto_clinico?.historia_familiar ?? 'Sin copia histórica'
        }}</el-descriptions-item>
        <el-descriptions-item label="Distrito de residencia a la atención">{{
          attention?.contexto_clinico?.distrito ?? 'Sin copia histórica'
        }}</el-descriptions-item>
        <el-descriptions-item label="Localidad a la atención">{{
          attention?.contexto_clinico?.localidad ?? 'Sin copia histórica'
        }}</el-descriptions-item>
        <el-descriptions-item label="Establecimiento de registro a la atención">{{
          attention?.contexto_clinico?.establecimiento_registro_nombre ?? 'Sin copia histórica'
        }}</el-descriptions-item>
        <el-descriptions-item label="Documento a la atención"
          >{{ attention?.contexto_clinico?.tipo_documento_codigo }}
          {{
            attention?.contexto_clinico?.numero_documento ?? 'Sin copia histórica'
          }}</el-descriptions-item
        >
        <el-descriptions-item label="Peso">{{ attention?.peso_kg ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="Talla">{{ attention?.talla_cm ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="Perímetro abdominal">{{
          attention?.perimetro_abdominal_cm ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Tipo de embarazo">{{
          pregnancyTypeLabel(attention?.tipo_embarazo_codigo)
        }}</el-descriptions-item>
        <el-descriptions-item label="Peso antes del embarazo">{{
          attention?.peso_antes_embarazo_kg ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item
          v-if="attention?.grupo_atencion_codigo === 'PUERPERAS'"
          label="Fecha del parto"
          >{{ attention?.fecha_parto ?? '—' }}</el-descriptions-item
        >
        <el-descriptions-item v-else label="Fecha probable de parto">{{
          attention?.fecha_probable_parto ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="P. sistólica">{{
          attention?.presion_sistolica ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="P. diastólica">{{
          attention?.presion_diastolica ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Temperatura">{{
          attention?.temperatura_c ?? '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Hora inicio">{{
          attention?.hora_inicio || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Hora fin">{{
          attention?.hora_fin || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Admisión">{{
          attention?.admision || '—'
        }}</el-descriptions-item>
        <el-descriptions-item label="Observaciones" :span="3">{{
          attention?.observaciones || '—'
        }}</el-descriptions-item>
      </el-descriptions>

      <NutritionRecordSummary
        :records="attention?.evaluaciones_nutricionales ?? []"
        :indicator-rows="historicalNutritionRows"
      />
      <NutritionExportPanel
        v-if="attention"
        :attention="attention"
        :can-manage="can('ATENCION_CREAR')"
        @updated="attention = $event"
      />

      <el-divider />
      <h3>Prestaciones</h3>
      <el-table :data="attention?.prestaciones ?? []" empty-text="Sin prestaciones">
        <el-table-column prop="numero_orden" label="N°" width="60" />
        <el-table-column prop="prestacion_codigo" label="Código" />
        <el-table-column prop="cantidad" label="Cantidad" width="120" />
      </el-table>

      <el-divider />
      <h3>Diagnósticos</h3>
      <el-table :data="attention?.diagnosticos ?? []" empty-text="Sin diagnósticos">
        <el-table-column prop="numero_orden" label="N°" width="60" />
        <el-table-column prop="cie10_codigo" label="CIE-10" />
        <el-table-column prop="tipo_diagnostico" label="Tipo" />
        <el-table-column prop="observacion" label="Observación" />
      </el-table>
    </el-card>

    <FuaPrintDialog
      v-if="attention?.fua_impresion && attention.estado === 'ATENDIDO'"
      v-model="printDialog"
      :snapshot="attention.fua_impresion"
    />
    <el-alert
      v-if="attention && !attention.fua_impresion"
      type="info"
      :closable="false"
      title="Esta atención anterior no tiene una copia de datos FUA guardada. No se reconstruye con datos actuales del paciente."
    />

    <!-- Anulación -->
    <el-dialog v-model="cancelDialog" title="Anular atención" width="480px" destroy-on-close>
      <el-alert
        v-if="cancelError"
        :title="cancelError"
        type="error"
        :closable="false"
        class="dialog-alert"
      />
      <el-form ref="cancelFormRef" :model="cancelForm" :rules="cancelRules" label-position="top">
        <el-form-item label="Justificación (mínimo 5 caracteres)" prop="observaciones">
          <el-input v-model="cancelForm.observaciones" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelDialog = false">Cancelar</el-button>
        <el-button type="danger" :loading="canceling" @click="doCancel">Anular</el-button>
      </template>
    </el-dialog>

    <!-- FUA -->
    <el-dialog v-model="fuaDialog" title="Registrar FUA" width="480px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        title="El número se forma con el RENIPRESS de la sede, el lote anual y un correlativo de ocho dígitos. Verifique que la IPRESS tenga asignado su rango antes de usarlo para un FUA oficial."
      />
      <el-form :model="fuaForm" label-position="top">
        <el-form-item label="Observaciones">
          <el-input v-model="fuaForm.observaciones" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fuaDialog = false">Cancelar</el-button>
        <el-button type="primary" :loading="emitting" @click="doEmitirFua">Emitir</el-button>
      </template>
    </el-dialog>

    <!-- Certificado -->
    <el-dialog v-model="certDialog" title="Emitir certificado" width="560px" destroy-on-close>
      <el-form :model="certForm" label-position="top">
        <el-form-item label="Tipo de certificado" required>
          <el-input v-model="certForm.tipo" placeholder="Ej. Certificado médico" />
        </el-form-item>
        <el-form-item label="Prestaciones (opcional)">
          <el-select
            v-model="certForm.prestaciones"
            multiple
            filterable
            remote
            :remote-method="searchCertPrestaciones"
            :loading="certPrestacionesLoading"
            style="width: 100%"
            placeholder="Busque prestaciones"
          >
            <el-option
              v-for="prestacion in certPrestaciones"
              :key="prestacion.codigo"
              :label="`${prestacion.codigo} — ${prestacion.descripcion}`"
              :value="prestacion.codigo"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="certDialog = false">Cancelar</el-button>
        <el-button type="primary" :loading="emitting" @click="doEmitirCertificado"
          >Emitir</el-button
        >
      </template>
    </el-dialog>

    <!-- Referencia -->
    <el-dialog v-model="refDialog" title="Crear referencia" width="560px" destroy-on-close>
      <el-form :model="refForm" label-position="top">
        <el-form-item label="Tipo de referencia" required>
          <el-input v-model="refForm.tipo" placeholder="Ej. REFERENCIA_MEDICA" />
        </el-form-item>
        <el-form-item label="Establecimiento de destino" required>
          <el-select
            v-model="refForm.establecimiento_destino_id"
            filterable
            remote
            :remote-method="searchDestinos"
            :loading="destinosLoading"
            style="width: 100%"
            placeholder="Busque el establecimiento destino"
          >
            <el-option v-for="est in destinos" :key="est.id" :label="est.nombre" :value="est.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Motivo" required>
          <el-input v-model="refForm.motivo" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="Observaciones">
          <el-input v-model="refForm.observaciones" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refDialog = false">Cancelar</el-button>
        <el-button type="primary" :loading="emitting" @click="doCrearReferencia">Crear</el-button>
      </template>
    </el-dialog>

    <!-- Resultado de documento emitido -->
    <el-dialog v-model="resultDialog" title="Documento emitido" width="480px" destroy-on-close>
      <el-result icon="success" :title="resultTitle" :sub-title="resultSubtitle" />
      <template #footer>
        <el-button type="primary" @click="resultDialog = false">Entendido</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import {
  catalogos,
  type EstablishmentCatalogItem,
  type ServiceCatalogItem,
} from '@/services/catalogos'
import { pacientes } from '@/services/pacientes'
import {
  atenciones,
  type Attention,
  type FuaResponse,
  type CertificateResponse,
  type ReferralResponse,
} from '@/services/atenciones'
import { careGroupLabel } from '@/utils/careGroup'
import { pregnancyTypeLabel } from '@/utils/pregnancy'
import FuaPrintDialog from '@/components/admission/FuaPrintDialog.vue'
import NutritionRecordSummary from '@/components/admission/NutritionRecordSummary.vue'
import NutritionExportPanel from '@/components/admission/NutritionExportPanel.vue'
import { nutritionalTableRows } from '@/utils/nutritionalDisplay'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const attentionId = Number(route.params.id)

const attention = ref<Attention | null>(null)
const historicalNutritionRows = computed(() =>
  attention.value?.valoracion_calculada
    ? nutritionalTableRows(attention.value.valoracion_calculada)
    : [],
)
const printDialog = ref(false)
const patientName = ref('—')
const loading = ref(false)
const errorMessage = ref<string | null>(null)

const cancelDialog = ref(false)
const cancelFormRef = ref<FormInstance>()
const canceling = ref(false)
const cancelError = ref<string | null>(null)
const cancelForm = reactive({ observaciones: '' })
const cancelRules: FormRules = {
  observaciones: [
    { required: true, message: 'La anulación requiere una justificación.', trigger: 'blur' },
    { min: 5, message: 'Mínimo 5 caracteres.', trigger: 'blur' },
  ],
}

const fuaDialog = ref(false)
const fuaForm = reactive({ observaciones: '' })

const certDialog = ref(false)
const certForm = reactive({ tipo: '', prestaciones: [] as string[] })
const certPrestaciones = ref<ServiceCatalogItem[]>([])
const certPrestacionesLoading = ref(false)

const refDialog = ref(false)
const refForm = reactive({
  tipo: '',
  establecimiento_destino_id: null as number | null,
  motivo: '',
  observaciones: '',
})
const destinos = ref<EstablishmentCatalogItem[]>([])
const destinosLoading = ref(false)

const emitting = ref(false)
const resultDialog = ref(false)
const resultTitle = ref('')
const resultSubtitle = ref('')

function can(permission: string): boolean {
  return auth.hasPermission(permission)
}

async function searchCertPrestaciones(query: string): Promise<void> {
  certPrestacionesLoading.value = true
  try {
    const page = await catalogos.prestaciones(query || undefined, 25, 0)
    certPrestaciones.value = page.items
  } finally {
    certPrestacionesLoading.value = false
  }
}

async function searchDestinos(query: string): Promise<void> {
  destinosLoading.value = true
  try {
    const page = await catalogos.establecimientos(query || undefined, 25, 0)
    destinos.value = page.items
  } finally {
    destinosLoading.value = false
  }
}

function openDialog(kind: 'fua' | 'certificado' | 'referencia'): void {
  errorMessage.value = null
  if (kind === 'fua') {
    fuaForm.observaciones = ''
    fuaDialog.value = true
  } else if (kind === 'certificado') {
    certForm.tipo = ''
    certForm.prestaciones = []
    certDialog.value = true
  } else {
    refForm.tipo = ''
    refForm.establecimiento_destino_id = null
    refForm.motivo = ''
    refForm.observaciones = ''
    refDialog.value = true
  }
}

function showResult(title: string, subtitle: string): void {
  resultTitle.value = title
  resultSubtitle.value = subtitle
  resultDialog.value = true
}

async function doCancel(): Promise<void> {
  const valid = await cancelFormRef.value?.validate().catch(() => false)
  if (!valid) return
  canceling.value = true
  cancelError.value = null
  try {
    const updated = await atenciones.cancel(attentionId, {
      observaciones: cancelForm.observaciones,
    })
    attention.value = updated
    cancelDialog.value = false
    ElMessage.success('Atención anulada.')
  } catch (error) {
    cancelError.value = error instanceof Error ? error.message : 'No se pudo anular.'
  } finally {
    canceling.value = false
  }
}

async function doEmitirFua(): Promise<void> {
  emitting.value = true
  errorMessage.value = null
  try {
    const result: FuaResponse = await atenciones.emitirFua({
      atencion_id: attentionId,
      observaciones: fuaForm.observaciones || null,
    })
    fuaDialog.value = false
    showResult(
      'FUA registrado',
      `Número: ${result.numero_fua ?? result.id}. RENIPRESS ${result.codigo_renipress ?? '—'}, lote ${result.lote_fua ?? '—'}.`,
    )
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'No se pudo emitir el FUA.'
  } finally {
    emitting.value = false
  }
}

async function doEmitirCertificado(): Promise<void> {
  if (!certForm.tipo.trim()) {
    errorMessage.value = 'Indique el tipo de certificado.'
    return
  }
  emitting.value = true
  errorMessage.value = null
  try {
    const result: CertificateResponse = await atenciones.emitirCertificado({
      atencion_id: attentionId,
      tipo: certForm.tipo.trim(),
      prestaciones: certForm.prestaciones,
    })
    certDialog.value = false
    showResult('Certificado emitido', `Número: ${result.numero_certificado}`)
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo emitir el certificado.'
  } finally {
    emitting.value = false
  }
}

async function doCrearReferencia(): Promise<void> {
  if (!refForm.tipo.trim() || !refForm.establecimiento_destino_id || !refForm.motivo.trim()) {
    errorMessage.value = 'Complete tipo, establecimiento de destino y motivo.'
    return
  }
  emitting.value = true
  errorMessage.value = null
  try {
    const result: ReferralResponse = await atenciones.crearReferencia({
      atencion_id: attentionId,
      tipo: refForm.tipo.trim(),
      establecimiento_destino_id: refForm.establecimiento_destino_id,
      motivo: refForm.motivo.trim(),
      observaciones: refForm.observaciones || null,
      estado: 'PENDIENTE',
    })
    refDialog.value = false
    showResult('Referencia creada', `Número: ${result.numero_referencia ?? result.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'No se pudo crear la referencia.'
  } finally {
    emitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    attention.value = await atenciones.get(attentionId)
    printDialog.value = route.query.imprimirFua === '1' && !!attention.value.fua_impresion
    if (attention.value) {
      const historical = attention.value.contexto_clinico
      if (historical) {
        patientName.value =
          [
            historical.apellido_paterno,
            historical.apellido_materno,
            historical.primer_nombre,
            historical.otros_nombres,
          ]
            .filter(Boolean)
            .join(' ') || `Paciente #${attention.value.paciente_id}`
        return
      }
      try {
        const patient = await pacientes.get(attention.value.paciente_id)
        patientName.value = [
          patient.apellido_paterno,
          patient.apellido_materno,
          patient.primer_nombre,
        ]
          .filter(Boolean)
          .join(' ')
      } catch {
        patientName.value = `Paciente #${attention.value.paciente_id}`
      }
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0;
}

.form-alert {
  margin-bottom: 16px;
}

.dialog-alert {
  margin-bottom: 16px;
}
</style>
