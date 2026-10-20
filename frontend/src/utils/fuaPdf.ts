import {
  fuaDocumentTitle,
  fuaFieldFont,
  layoutProblems,
  parseFuaLayout,
  type FuaDocumentKind,
  type FuaLayout,
} from './fuaPrint'

/** Build the actual file; saving must not depend on an iframe's print dialog or tab title. */
export async function createFuaPdf(
  layout: FuaLayout,
  values: Record<string, string>,
  background: Uint8Array,
  documentKind: FuaDocumentKind = 'atencion',
): Promise<{ data: ArrayBuffer; filename: string }> {
  const safe = parseFuaLayout(JSON.stringify(layout))
  if (layoutProblems(safe, values).length) throw new Error('Revise las posiciones de la FUA.')
  const { jsPDF } = await import('jspdf')
  const pdf = new jsPDF({
    unit: 'mm',
    format: [safe.width, safe.height],
    orientation: safe.width > safe.height ? 'landscape' : 'portrait',
    compress: true,
    putOnlyUsedFonts: true,
  })
  const title = fuaDocumentTitle(values, false, documentKind)
  pdf.setProperties({ title })
  // Same reference image, margins, geometry and font sizes as the on-screen FUA.
  pdf.addImage(background, 'PNG', 10, 10, safe.width - 20, safe.height - 20)
  pdf.setFont('helvetica', 'normal')
  pdf.setFontSize(8)
  pdf.text('VISTA DE REVISIÓN · PRELLENADO PARCIAL · USO LOCAL', 10, 2, { baseline: 'top' })
  pdf.setFont('courier', 'normal')
  for (const field of safe.fields.filter((item) => item.enabled)) {
    const value = (values[field.id] || '').slice(field.skip)
    if (!value) continue
    pdf.setFontSize(fuaFieldFont(field, value))
    const x = field.x + safe.offsetX
    const y = field.y + safe.offsetY
    if (field.step) {
      for (const [index, char] of [...value].entries()) {
        pdf.text(char, x + index * field.step, y, { baseline: 'top' })
      }
    } else {
      pdf.text(value, x, y, { baseline: 'top' })
    }
  }
  return { data: pdf.output('arraybuffer'), filename: `${title}.pdf` }
}

export async function prepareFuaPdf(
  layout: FuaLayout,
  values: Record<string, string>,
  backgroundUrl: string,
  documentKind: FuaDocumentKind = 'atencion',
): Promise<{ data: ArrayBuffer; filename: string }> {
  const response = await fetch(backgroundUrl)
  if (!response.ok) throw new Error('No se pudo cargar el formulario FUA. Vuelva a intentarlo.')
  const background = new Uint8Array(await response.arrayBuffer())
  return createFuaPdf(layout, values, background, documentKind)
}
