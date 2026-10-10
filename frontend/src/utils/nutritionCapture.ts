import type { NutritionCapture, NutritionScope } from '@/types/nutritionRecord'

export interface NutritionField {
  key: keyof NutritionCapture
  label: string
  kind: 'number' | 'text' | 'date' | 'boolean'
  min?: number
  max?: number
  precision?: number
  scopes?: NutritionScope[]
}
export interface NutritionSection {
  id: string
  title: string
  description?: string
  fields: NutritionField[]
}
const child: NutritionScope[] = ['NINO']
const adult: NutritionScope[] = ['ADULTO']
export const nutritionSections: NutritionSection[] = [
  {
    id: 'laboratorio',
    title: 'Laboratorio y altitud',
    description:
      'Deje vacío lo no medido. Hb y su fecha se registran juntas; la Hb corregida requiere altitud y método.',
    fields: [
      {
        key: 'hemoglobina',
        label: 'Hemoglobina (g/dL)',
        kind: 'number',
        min: 0.01,
        max: 30,
        precision: 2,
      },
      { key: 'fecha_hemoglobina', label: 'Fecha del resultado de Hb', kind: 'date' },
      {
        key: 'altitud_msnm',
        label: 'Altitud de residencia (msnm)',
        kind: 'number',
        min: -500,
        max: 9000,
        precision: 2,
      },
      {
        key: 'hemoglobina_corregida',
        label: 'Hb corregida registrada (g/dL)',
        kind: 'number',
        min: 0.01,
        max: 30,
        precision: 2,
      },
      {
        key: 'metodo_correccion_hb',
        label: 'Método o referencia de corrección',
        kind: 'text',
        max: 200,
      },
      {
        key: 'hematocrito',
        label: 'Hematocrito (%)',
        kind: 'number',
        min: 0.01,
        max: 100,
        precision: 2,
      },
    ],
  },
  {
    id: 'materna',
    title: 'Seguimiento de la gestante',
    description: 'La ganancia de peso se interpreta clínicamente según la semana gestacional.',
    fields: [
      {
        key: 'edad_gestacional_semanas',
        label: 'Edad gestacional (semanas)',
        kind: 'number',
        min: 0,
        max: 45,
        scopes: ['GESTANTE'],
      },
      {
        key: 'estado_ganancia_peso',
        label: 'Estado de ganancia de peso valorado',
        kind: 'text',
        max: 100,
        scopes: ['GESTANTE'],
      },
    ],
  },
  {
    id: 'infantil',
    title: 'Programas y seguimiento infantil',
    description: 'Sin dato, No y Sí son valores distintos. SIS se toma de la ficha del paciente.',
    fields: [
      ...(['juntos', 'pin', 'crecer'] as const).map((key) => ({
        key,
        label: key.toUpperCase(),
        kind: 'boolean' as const,
        scopes: child,
      })),
      ...(
        [
          ['nro_controles_cred', 'N.° controles CRED'],
          ['nro_sachets', 'N.° sachets'],
          ['nro_consejerias', 'N.° consejerías'],
          ['nro_sesiones', 'N.° sesiones'],
          ['nro_visitas', 'N.° visitas'],
        ] as const
      ).map(([key, label]) => ({
        key,
        label,
        kind: 'number' as const,
        min: 0,
        max: 65535,
        scopes: child,
      })),
    ],
  },
  {
    id: 'escolar',
    title: 'Datos escolares',
    fields: (
      [
        ['institucion_educativa', 'Institución educativa'],
        ['nivel_educativo', 'Nivel educativo'],
        ['grado', 'Grado'],
        ['turno', 'Turno'],
        ['codigo_matricula', 'Código de matrícula'],
        ['seccion', 'Sección'],
        ['aula', 'Aula'],
      ] as const
    ).map(([key, label]) => ({
      key,
      label,
      kind: 'text' as const,
      max: key === 'institucion_educativa' ? 200 : 100,
      scopes: child,
    })),
  },
  {
    id: 'valoracion',
    title: 'Valoración profesional',
    fields: [
      {
        key: 'diagnostico',
        label: 'Diagnóstico / interpretación profesional',
        kind: 'text',
        max: 500,
      },
    ],
  },
  {
    id: 'legado',
    title: 'Códigos del registro legado (opcional)',
    description:
      'Transcriba solo valores de un registro de origen. Su significado no está homologado. Pending no controla el estado de envío actual.',
    fields: [
      ...(['p65', 'vl', 'cp'] as const).map((key) => ({
        key,
        label: key.toUpperCase(),
        kind: 'number' as const,
        min: -2147483648,
        max: 2147483647,
        scopes: adult,
      })),
      {
        key: 'flag_legacy',
        label: 'Flag (origen)',
        kind: 'number',
        min: -2147483648,
        max: 2147483647,
        scopes: child,
      },
      {
        key: 'pending_legacy',
        label: 'Pending (origen)',
        kind: 'boolean',
        scopes: ['ADULTO', 'GESTANTE', 'PUERPERA'],
      },
    ],
  },
]

export function sectionsForScope(scope: NutritionScope) {
  return nutritionSections
    .map((section) => ({
      ...section,
      fields: section.fields.filter((field) => !field.scopes || field.scopes.includes(scope)),
    }))
    .filter((section) => section.fields.length > 0)
}

export function nutritionPayload(
  draft: NutritionCapture,
  scope: NutritionScope,
): NutritionCapture | null {
  const applicable = new Set(
    sectionsForScope(scope).flatMap((section) => section.fields.map((f) => f.key)),
  )
  const entries = Object.entries(draft).filter(
    ([key, value]) =>
      applicable.has(key as keyof NutritionCapture) && value != null && value !== '',
  )
  return entries.length ? (Object.fromEntries(entries) as NutritionCapture) : null
}

export function nutritionErrors(draft: NutritionCapture, born: string, attended: string): string[] {
  const errors: string[] = []
  const hasHb = draft.hemoglobina != null
  if (hasHb !== Boolean(draft.fecha_hemoglobina))
    errors.push('Complete hemoglobina y fecha del resultado juntas.')
  if (
    draft.fecha_hemoglobina &&
    (draft.fecha_hemoglobina < born || draft.fecha_hemoglobina > attended.slice(0, 10))
  )
    errors.push('La fecha de Hb debe estar entre el nacimiento y la atención.')
  if (
    draft.hemoglobina_corregida != null &&
    (!hasHb || draft.altitud_msnm == null || !draft.metodo_correccion_hb?.trim())
  )
    errors.push('La Hb corregida requiere Hb medida, altitud y método de corrección.')
  if (draft.metodo_correccion_hb?.trim() && draft.hemoglobina_corregida == null)
    errors.push('Complete la Hb corregida o retire el método de corrección.')
  return errors
}
