import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import type { FuaPrintSnapshot } from '../src/types/fua'
import {
  defaultFuaLayout, fuaDeliveryBox, fuaIdentityProblem, fuaPrintHtml, fuaValues, layoutProblems,
} from '../src/utils/fuaPrint'

// Opt-in: uses only snapshots produced by the isolated synthetic API/MySQL audit.
// Normal unit runs do not depend on an audit database or generated reports.
test.skipIf(!process.env.FUA_MATRIX_REPORT)(
  'every persisted ethnicity/document/mode/group combination renders a complete local FUA',
  () => {
    const report = JSON.parse(readFileSync(process.env.FUA_MATRIX_REPORT!, 'utf8')) as {
      database: string
      complete: boolean
      failed: number
      expected: number
      cases: unknown[]
      snapshots: { attention_id: number; snapshot: FuaPrintSnapshot }[]
    }
    expect(report.database).toMatch(/^ipress_test_admission_/)
    expect(report.complete).toBe(true)
    expect(report.failed).toBe(0)
    expect(report.snapshots).toHaveLength(report.expected)
    expect(report.cases).toHaveLength(report.expected)
    const layout = defaultFuaLayout()
    // A synthetic calibrated profile: 7 pt fits the longer foreign IDs and
    // SIS contracts with sequence. Physical printer alignment remains manual.
    for (const field of layout.fields) {
      if (['numero_documento', 'sis_numero'].includes(field.id)) field.font = 7
    }
    const fields = layout.fields.filter((field) => field.enabled)
    const parser = new DOMParser()
    for (const { attention_id, snapshot } of report.snapshots) {
      const context = `attention ${attention_id}: ${snapshot.tipo_documento}/${snapshot.etnia_codigo}/${snapshot.tipo_atencion}/${snapshot.grupo_atencion_codigo}`
      expect(fuaIdentityProblem(snapshot), context).toBeNull()
      const values = fuaValues(snapshot)
      expect(layoutProblems(layout, values), context).toEqual([])
      const doc = parser.parseFromString(fuaPrintHtml(layout, values), 'text/html')
      const printed = (id: string) => doc.body.children[fields.findIndex((field) => field.id === id)]?.textContent
      expect(printed('numero_documento'), context).toBe(snapshot.numero_documento)
      expect(printed('etnia_codigo'), context).toBe(snapshot.etnia_codigo || '')
      expect(printed('tdi'), context).toBe(snapshot.tdi || snapshot.tipo_documento)
      expect(printed('identity_note'), context).toBe(values.identity_note || '')
      expect(printed('atencion_ambulatoria'), context).toBe(snapshot.tipo_atencion === 'AMBULATORIA' ? 'X' : '')
      expect(printed('atencion_emergencia'), context).toBe(snapshot.tipo_atencion === 'EMERGENCIA' ? 'X' : '')
      expect(printed('gestante'), context).toBe(snapshot.grupo_atencion_codigo === 'GESTANTES' ? 'X' : '')
      expect(printed('puerpera'), context).toBe(snapshot.grupo_atencion_codigo === 'PUERPERAS' ? 'X' : '')
      expect(printed('sis_diresa'), context).toBe(snapshot.sis_diresa || '')
      expect(printed('sis_tipo'), context).toBe(snapshot.sis_tipo || '')
      expect(printed('sis_numero'), context).toBe(values.sis_numero)
      // Un solo recuadro de parto: FPP en gestantes y fecha real en puérperas.
      const parto = fuaDeliveryBox(snapshot)?.value ?? null
      expect(printed('parto_dia'), context).toBe(parto?.slice(8, 10) || '')
    }
  },
)
