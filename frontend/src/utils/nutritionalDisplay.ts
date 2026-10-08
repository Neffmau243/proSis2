import type { Attention, NutritionalIndicatorsPreview } from '@/services/atenciones'

/** Display the applicable BMI results already calculated by the server. */
export function nutritionalBmiSummary(result: NutritionalIndicatorsPreview | null): string {
  if (!result) return ''
  const parts: string[] = []
  if (result.imc != null) parts.push(`IMC: ${result.imc}`)
  if (result.imc_edad != null) parts.push(`IMC/edad: Z ${result.imc_edad}`)
  if (result.imc_pregestacional != null) parts.push(`IMC pregestacional: ${result.imc_pregestacional}`)
  if (parts.length && result.diagnostico_imc) parts.push(result.diagnostico_imc)
  if (result.ganancia_peso_kg != null) parts.push(`Cambio de peso: ${result.ganancia_peso_kg} kg`)
  return parts.join(' · ')
}

/** Explain the scope of the reference selected by the server, without extrapolating scores. */
export function nutritionalLimits(result: NutritionalIndicatorsPreview | null): string {
  if (!result) return ''
  switch (result.grupo_referencia) {
    case 'ADULTO':
    case 'ADULTO_MAYOR':
      return 'P/E, T/E y P/T no aplican: esta edad está fuera de las tablas de crecimiento utilizadas. La valoración disponible es por IMC.'
    case 'GESTANTE':
      return 'P/E, T/E y P/T no aplican al grupo Gestantes. Se muestran el IMC pregestacional y el cambio de peso cuando hay datos suficientes.'
    case 'PUERPERA':
      return 'P/E, T/E y P/T no aplican al grupo Puérperas. Se muestran el IMC pregestacional y el cambio de peso cuando hay datos suficientes; el IMC actual es de seguimiento del puerperio.'
    case 'ESCOLAR':
      return 'P/T corresponde a la referencia infantil. OMS 2007 cubre T/E e IMC/edad de 61 a 228 meses y P/E hasta 120 meses. Fuera de esos rangos no se extrapolan resultados.'
    default:
      return 'Referencia infantil OMS 2006 (hasta aproximadamente 60 meses). P/T también depende del rango de talla de la tabla.'
  }
}

export function nutritionalStatus(result: NutritionalIndicatorsPreview | null): string {
  if (!result) return 'Ingrese peso y talla y revise la fecha de atención para calcular la valoración.'
  const summary = nutritionalBmiSummary(result)
  return [summary ? `Resultado disponible: ${summary}.` : '', nutritionalLimits(result), result.mensaje]
    .filter(Boolean).join(' ')
}

type NutritionHistory = Pick<Attention, 'pe' | 'te' | 'pt' | 'edad_anios' | 'grupo_atencion_codigo' | 'valoracion_calculada'>

/** Preserve saved scores; explain applicability even for entries without a snapshot. */
export function nutritionalHistoryValue(row: NutritionHistory, indicator: 'pe' | 'te' | 'pt'): string {
  if (row[indicator] != null) return row[indicator]
  const snapshot = row.valoracion_calculada
  if (snapshot) {
    if (snapshot[indicator] != null) return snapshot[indicator]
    const index = { pe: 0, te: 1, pt: 2 }[indicator]
    return nutritionalRows(snapshot)[index]?.value === 'No aplica' ? 'No aplica' : '—'
  }
  // Use the age saved at the encounter, never the patient's current age.
  const age = row.edad_anios
  if (row.grupo_atencion_codigo === 'GESTANTES' || row.grupo_atencion_codigo === 'PUERPERAS'
    || (age != null && (age >= 20 || (indicator === 'pe' && age >= 11) || (indicator === 'pt' && age >= 6)))) {
    return 'No aplica'
  }
  return '—'
}

/** Select the applicable results without relabeling one indicator as another. */
export function nutritionalRows(result: NutritionalIndicatorsPreview | null) {
  if (!result) return ['Diagnóstico P/E', 'Diagnóstico T/E', 'Diagnóstico P/T'].map(label => ({ label, value: 'Ingrese peso y talla' }))
  const group = result.grupo_referencia ?? 'INFANTIL'
  const value = (raw: string | null | undefined, diagnosis?: string | null, z = false) =>
    raw == null ? 'No disponible' : `${diagnosis ? `${diagnosis} · ` : ''}${z ? 'Z: ' : ''}${raw}`
  const notApplicable = ['ADULTO', 'ADULTO_MAYOR', 'GESTANTE', 'PUERPERA'].includes(group)
  const rows = [
    { label: 'Diagnóstico P/E', value: value(result.pe, result.diagnostico_peso_edad, true) },
    { label: 'Diagnóstico T/E', value: value(result.te, result.diagnostico_talla_edad, true) },
    { label: 'Diagnóstico P/T', value: value(result.pt, result.diagnostico_peso_talla, true) },
  ]
  if (notApplicable) return rows.map(row => ({ ...row, value: 'No aplica' }))
  if (group === 'ESCOLAR') {
    rows[2]!.value = 'No aplica'
    if (result.pe == null && result.estado === 'CALCULADO') rows[0]!.value = 'No aplica'
  }
  return rows
}
