// Dev-only visual fixture: no authentication, APIs, or real patient data.
import { createApp, h, ref } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '../src/assets/main.css'
import FuaPrintDialog from '../src/components/admission/FuaPrintDialog.vue'
import { emptyFuaInput } from '../src/utils/fuaPrint'
import type { FuaPrintSnapshot } from '../src/types/fua'

const sample: FuaPrintSnapshot = {
  ...emptyFuaInput(), version: 2, renipress_preimpreso: true, personal_atiende: 'IPRESS', lugar_atencion: 'INTRAMURAL',
  tipo_atencion: 'AMBULATORIA', codigo_renipress: '00000001', sis_diresa: '001',
  sis_tipo: '2', sis_numero: '00000001', etnia_codigo: null, ipress_nombre: 'IPRESS DE PRUEBA',
  profesional_nombre: 'PROFESIONAL DE PRUEBA', profesional_documento: '00000002',
  profesional_colegiatura: '00000', tipo_documento: 'DNI', tdi: '2', numero_documento: '00000001',
  apellido_paterno: 'PACIENTE', apellido_materno: 'SINTÉTICO', primer_nombre: 'ANA', otros_nombres: 'MARÍA',
  sexo_codigo: 'F', fecha_nacimiento: '1990-01-02', historia_clinica: 'PRUEBA-001',
  fecha_atencion: '2026-09-19', hora_atencion: '09:05:00', peso_kg: '60', talla_cm: '160',
  presion_sistolica: 120, presion_diastolica: 80, imc: '23.438', perimetro_abdominal_cm: '80',
  grupo_atencion_codigo: 'NINOS_ADOLESCENTES_ADULTOS_MAYORES', fecha_probable_parto: null, fecha_parto: null,
}
const documentCase = new URLSearchParams(location.search).get('document')
if (documentCase && ['CE', 'PAS', 'DE', 'OTRO'].includes(documentCase)) {
  sample.tipo_documento = documentCase
  sample.tdi = documentCase === 'CE' ? '3' : null
  sample.numero_documento = documentCase === 'CE' ? '001234567' : 'AB001234'
}
createApp({
  setup() {
    const visible = ref(true)
    const snapshot = ref(sample)
    return () => h('main', [
      h('p', 'Prueba visual con datos sintéticos. No guarda atenciones ni llama al backend.'),
      h('button', { onClick: () => { visible.value = true } }, 'Abrir prueba FUA'),
      h(FuaPrintDialog, { modelValue: visible.value, snapshot: snapshot.value,
        'onUpdate:modelValue': (value: boolean) => { visible.value = value },
      }),
    ])
  },
}).use(ElementPlus).mount('#app')
