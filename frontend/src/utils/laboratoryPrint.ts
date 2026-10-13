import type { Attention } from '@/services/atenciones'

const escape = (value: unknown) =>
  String(value ?? '—').replace(
    /[&<>"']/g,
    (char) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[char]!,
  )

/** Imprime exclusivamente datos de la atención guardada y su instantánea. */
export function laboratoryClinicalHtml(attention: Attention): string {
  const snapshot = attention.fua_impresion
  if (!snapshot) throw new Error('La atención no tiene una instantánea para imprimir.')
  const rows: [string, unknown][] = [
    ['Atención', attention.id],
    ['Historia clínica', snapshot.historia_clinica],
    ['Documento', `${snapshot.tipo_documento} ${snapshot.numero_documento}`],
    ['Apellido paterno', snapshot.apellido_paterno],
    ['Apellido materno', snapshot.apellido_materno],
    ['Primer nombre', snapshot.primer_nombre],
    ['Otros nombres', snapshot.otros_nombres],
    ['Nacimiento', snapshot.fecha_nacimiento],
    ['Sexo', snapshot.sexo_codigo],
    ['Establecimiento', snapshot.ipress_nombre],
    ['Consultorio', attention.consultorio_nombre],
    ['Profesional', snapshot.profesional_nombre],
    ['Fecha', snapshot.fecha_atencion],
    ['Hora', snapshot.hora_atencion],
    ['Modalidad', attention.modalidad_atencion_codigo],
    ['N.° de referencia', attention.numero_referencia_ingreso],
    ['N.° de contrarreferencia', attention.numero_contrarreferencia_ingreso],
    [
      'Código SIS',
      [snapshot.sis_diresa, snapshot.sis_tipo, snapshot.sis_numero, snapshot.sis_secuencia]
        .filter(Boolean)
        .join(' - ') || '—',
    ],
    ['Observaciones', attention.observaciones],
  ]
  return `<!doctype html><html lang="es"><head><meta charset="UTF-8"><title>HCI · Laboratorio</title>
    <style>@page{size:A4;margin:15mm}body{font:12px Arial;color:#000}h1{font-size:18px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #888;padding:6px;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere}th{width:30%}</style></head>
    <body><h1>Historia clínica · Atención de laboratorio</h1><table>${rows.map(([label, value]) => `<tr><th>${escape(label)}</th><td>${escape(value)}</td></tr>`).join('')}</table></body></html>`
}

export async function printLaboratoryClinical(attention: Attention): Promise<void> {
  const frame = document.createElement('iframe')
  frame.title = 'Impresión HCI de laboratorio'
  frame.style.cssText = 'position:fixed;left:-10000px;width:1px;height:1px;border:0'
  frame.setAttribute('aria-hidden', 'true')
  const ready = new Promise<void>((resolve, reject) => {
    frame.onload = () => resolve()
    frame.onerror = () => reject(new Error('No se pudo preparar la HCI.'))
  })
  frame.srcdoc = laboratoryClinicalHtml(attention)
  document.body.appendChild(frame)
  try {
    await ready
    await frame.contentDocument?.fonts.ready
    const target = frame.contentWindow
    if (!target) throw new Error('No se pudo abrir la impresión HCI.')
    target.addEventListener('afterprint', () => frame.remove(), { once: true })
    target.focus()
    target.print()
    window.setTimeout(() => frame.remove(), 120_000)
  } catch (cause) {
    frame.remove()
    throw cause
  }
}
