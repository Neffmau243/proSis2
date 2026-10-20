# E2E de paciente referido a laboratorio y descarga del FUA

Fecha de ejecución: 19/10/2026. Aplicación real: `http://localhost:8000/laboratorio`.

## Corrección del guardado PDF

La verificación inicial observó el título de impresión, pero no guardó un archivo. El usuario informó que el resultado salía en blanco o sin nombre. Se reemplazó «Ver FUA / guardar PDF» por **«Descargar FUA PDF»**, que genera un archivo PDF en el navegador mediante jsPDF y descarga un enlace con nombre explícito. El archivo incluye la imagen del formulario y los textos de la instantánea guardada, con las mismas posiciones y tamaños de fuente de la vista previa. La impresión sobre papel preimpreso conserva su acción independiente.

Se repitió el recorrido real desde el historial de la atención 43, tanto en **FUA adicional guardado** como en **Imprimir FUA guardado**. En ambas rutas el navegador confirmó una descarga real con el nombre base `REF.Lab-AURELIA PRUEBA LUCERO FICTICIA-2026-10-18.pdf`. Si ya existe un archivo con ese nombre, el navegador puede añadir un sufijo numérico.

El archivo descargado se abrió con pypdf y se renderizó con Poppler para inspección visual:

- Una página, 107856 bytes, imagen del formulario presente y metadato de título correcto.
- Textos comprobados: AURELIA, PRUEBA, LUCERO, FICTICIA, documento 98032888, RENIPRESS de origen 00001234 y hoja E2E-LAB-191026-01.
- Formulario y campos visibles en la imagen renderizada; no se observó una página en blanco.
- Historial con seis filas después de las descargas, sin nueva atención; consola sin errores.
- 53 pruebas de las utilidades FUA/PDF y del guardado/consulta histórica de laboratorio aprobadas. Tres casos de componente centrados en PDF aprobados, incluyendo descarga con nombre y error de generación sin enlace vacío. Tipos y compilación aprobados.
- Las especificaciones Playwright se actualizaron para inspeccionar descargas binarias; su ejecución no forma parte de esta repetición. La comprobación E2E se hizo en la página local mediante el navegador de Codex.

Evidencia: `output/pdf/REF.Lab-AURELIA PRUEBA LUCERO FICTICIA-2026-10-18.pdf`, `tmp/laboratorio-e2e-20261019/pdf-descargado.png` y `tmp/laboratorio-e2e-20261019/descarga-pdf-corregida.jpg`.

Las secciones siguientes conservan el alcance y los resultados de la primera ejecución, anterior a esta corrección.

## Resultado

Recorrido ejecutado en el navegador contra el backend local, con el paciente ficticio 14 y la cuenta clínica de pruebas documentada. Se creó únicamente la atención **43**, con fecha **18/10/2026 a las 10:15**, para distinguir la fecha de atención de la fecha de impresión.

El título que recibió el navegador durante la impresión fue:

`REF.Lab-AURELIA PRUEBA LUCERO FICTICIA-2026-10-18`

## Comprobaciones

| Paso | Resultado |
| --- | --- |
| Entrar sin paciente seleccionado | Guardado e impresión bloqueados. |
| Buscar por documento y seleccionar paciente | Se cargaron identidad, afiliación y laboratorio correspondientes. |
| Seleccionar REFERENCIA sin origen completo | Guardado bloqueado. |
| Completar origen sin número de hoja | Guardado bloqueado. |
| Registrar origen, hoja y profesional | Atención 43 guardada; observaciones identifican expresamente la prueba como ficticia. |
| Revisar el historial y contador | Filas de historial de 5 a 6; contador del turno de 0 a 1. |
| Abrir FUA desde laboratorio | Copia guardada con modalidad REFERENCIA, origen y hoja correctos. |
| Generar «Ver FUA / guardar PDF» | El título real de la pestaña durante la impresión coincidió con REF.Lab, paciente y fecha 2026-10-18. |
| Recargar, buscar y consultar atención 43 | Se conservaron los datos de la atención y su origen. |
| Preparar FUA adicional desde el historial | Conservó el título y fecha históricos aunque el formulario nuevo mostraba 19/10/2026. |
| Revisar duplicados tras reimprimir | Historial con 6 filas: no se creó una segunda atención. |
| Consultar errores de consola | Sin errores registrados en la página. |

Datos de origen de prueba: RENIPRESS `00001234`, nombre `IPRESS ORIGEN FICTICIA E2E`, hoja `E2E-LAB-191026-01`.

## Cambio implementado

La utilidad de impresión admite un contexto de documento. Laboratorio envía `REF.Lab` tanto para el FUA recién guardado como para la consulta histórica y la copia adicional. El título se aplica al HTML imprimible y a la pestaña mientras se prepara la impresión, para cubrir el nombre sugerido por Chromium.

El diálogo muestra «Nombre al guardar PDF». Admisión conserva su prefijo `atencion`. La prueba de calibración sin datos mantiene su título genérico. El nombre y fecha provienen de la instantánea de la atención, sin consultar el reloj ni reconstruir datos del paciente actual.

## Validación de código

- 50 pruebas de utilidad FUA, guardado de laboratorio y consulta histórica aprobadas.
- Una prueba de componente adicional aprobada para el título, cambio de fecha y separación de contextos. Se ejecutó solo ese caso del archivo de componentes; no es una afirmación de aprobación de toda la suite nutricional previamente observada.
- Tipos Vue/TypeScript, ESLint de los archivos de impresión modificados y compilación de producción aprobados.

## Límites de la prueba

Se activó la generación de impresión del navegador y se canceló, sin imprimir físicamente ni confirmar una calibración en papel. El título fue observado durante esa salida; el archivo PDF no se guardó en disco. El nombre es la sugerencia que recibe el navegador al guardar como PDF.

La prueba cubre el circuito actualmente implementado de atención de un paciente referido y su FUA. No representa una integración real con REFCON/SIS ni el procesamiento de muestras y resultados, pendientes en el plan.

Evidencia local: `tmp/laboratorio-e2e-20261019/resultado.json` y `tmp/laboratorio-e2e-20261019/fua-ref-lab-43.jpg`.
