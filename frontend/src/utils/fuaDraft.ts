import type { Patient } from '@/services/pacientes'
import type { AttentionCreatePayload } from '@/services/atenciones'
import type { EstablishmentCatalogItem, ProfessionalCatalogItem } from '@/services/catalogos'
import type { FuaPrintInput, FuaPrintSnapshot } from '@/types/fua'
import { gestationalAgeFromDueDate } from '@/utils/pregnancy'

type DraftEncounter = Pick<AttentionCreatePayload, 'fecha_atencion' | 'modalidad_atencion_codigo' |
  'peso_kg' | 'talla_cm' | 'presion_sistolica' | 'presion_diastolica' |
  'perimetro_abdominal_cm' | 'grupo_atencion_codigo' | 'fecha_probable_parto' | 'fecha_parto' |
  'valoracion_nutricional'>

/** UI estimate only; the saved projection always comes back from the server. */
export function buildFuaDraft(patient: Patient, encounter: DraftEncounter, supplement: FuaPrintInput,
  establishment?: EstablishmentCatalogItem, professional?: ProfessionalCatalogItem): FuaPrintSnapshot {
  const renaes = establishment?.codigo_renaes || ''
  const weight = encounter.peso_kg
  const height = encounter.talla_cm
  const assessedWeeks = encounter.valoracion_nutricional?.edad_gestacional_semanas
  const calculated = encounter.grupo_atencion_codigo === 'GESTANTES'
    ? gestationalAgeFromDueDate(encounter.fecha_atencion, encounter.fecha_probable_parto) : null
  const hasAssessment = encounter.grupo_atencion_codigo === 'GESTANTES' && assessedWeeks != null
  const validAssessment = hasAssessment && Number.isInteger(assessedWeeks) &&
    assessedWeeks >= 0 && assessedWeeks <= 45
  return {
    ...supplement, version: 1,
    tipo_atencion: encounter.modalidad_atencion_codigo,
    referencia_renipress: encounter.modalidad_atencion_codigo === 'REFERENCIA' ? supplement.referencia_renipress : null,
    referencia_nombre: encounter.modalidad_atencion_codigo === 'REFERENCIA' ? supplement.referencia_nombre : null,
    referencia_hoja: encounter.modalidad_atencion_codigo === 'REFERENCIA' ? supplement.referencia_hoja : null,
    codigo_renipress: supplement.codigo_renipress || (/^\d{8}$/.test(renaes) ? renaes : null),
    ipress_nombre: establishment?.nombre || '', profesional_nombre: professional?.nombre_completo || '',
    profesional_colegiatura: professional?.colegiatura || null, profesional_documento: null,
    tipo_documento: patient.tipo_documento_codigo,
    tdi: patient.tipo_documento_codigo === 'DNI' ? '2' : patient.tipo_documento_codigo === 'CE' ? '3' : null,
    numero_documento: patient.numero_documento, apellido_paterno: patient.apellido_paterno,
    apellido_materno: patient.apellido_materno, primer_nombre: patient.primer_nombre,
    otros_nombres: patient.otros_nombres, sexo_codigo: patient.sexo_codigo,
    fecha_nacimiento: patient.fecha_nacimiento, historia_clinica: patient.historia_clinica,
    fecha_atencion: encounter.fecha_atencion.slice(0, 10), hora_atencion: encounter.fecha_atencion.slice(11, 19),
    peso_kg: weight ?? null, talla_cm: height ?? null,
    presion_sistolica: encounter.presion_sistolica ?? null, presion_diastolica: encounter.presion_diastolica ?? null,
    // Se calcula con enteros y redondeo hacia arriba en el medio, igual que el
    // servidor: ``60 / (160/100)**2`` en coma flotante da 23.437499999999996 y
    // el redondeo binario imprimiría 23.437 en lugar de 23.438.
    imc: weight && height ? (Math.round((weight * 10_000_000) / (height * height)) / 1000).toFixed(3) : null,
    perimetro_abdominal_cm: encounter.perimetro_abdominal_cm ?? null,
    grupo_atencion_codigo: encounter.grupo_atencion_codigo || 'NINOS_ADOLESCENTES_ADULTOS_MAYORES',
    fecha_probable_parto: encounter.fecha_probable_parto ?? null,
    fecha_parto: encounter.fecha_parto ?? null,
    edad_gestacional_semanas: hasAssessment ? validAssessment ? assessedWeeks : null
      : calculated?.weeks ?? null,
    edad_gestacional_dias: hasAssessment ? null : calculated?.days ?? null,
    edad_gestacional_fuente: hasAssessment ? validAssessment ? 'VALORACION' : null
      : calculated ? 'FPP' : null,
  }
}
