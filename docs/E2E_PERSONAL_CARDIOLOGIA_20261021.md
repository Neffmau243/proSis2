# Prueba E2E desde Personal hasta FUA — 21/10/2026

## Entorno y método

Recorrido manual automatizado por la interfaz real en `http://localhost:8000`,
con una sesión nueva. Se empezó en Personal y no se reutilizaron los registros
de pruebas anteriores ni el harness de interfaz. Las altas se realizaron mediante
formularios visibles; no se insertaron registros por SQL ni se invocaron APIs para
saltarse pasos. Los datos de paciente y profesional son ficticios y están marcados
como prueba. Las contraseñas no se incluyen en este informe.

## Registros creados

| Elemento | Valor |
| --- | --- |
| Profesión | MÉDICO CIRUJANO E2E 2110 |
| Especialidad | CARDIOLOGÍA E2E 2110 |
| Profesional | PRUEBA E2E CARDIOLOGÍA OCTUBRE |
| Documento del profesional | 99002110, ficticio |
| Colegiatura | E2E2110, ficticia |
| Área del profesional y consultorio | MEDICINA |
| Especialidad principal del profesional | CARDIOLOGÍA E2E 2110 |
| Consultorio | CARDIOLOGÍA E2E 2110, código CARD-E2E2110 |
| IPRESS | C.S. ALTO SELVA ALEGRE |
| Asignación | Responsable, desde 21/10/2026, sin fecha de fin |
| Paciente | PRUEBA CARDIOLOGIA PACIENTE E2E |
| DNI e historia | 99002111 / E2E-CARD-2110, ficticios |
| Ficha | `/pacientes/28963` |
| Atención | `/atenciones/45`, 21/10/2026 10:33:30, ATENDIDO |
| Servicio | MEDICINA GENERAL |
| FUA registrado | 00001291-26-00000007 |

Se registraron peso 70 kg, talla 170 cm, PA 120/80 y temperatura 36.5 °C.
El IMC calculado y conservado fue 24.221. Se seleccionó SIS Gratuito como dato
ficticio de la prueba; no se verificó cobertura ni se enviaron datos al SIS.

## Hallazgos y correcciones

1. Personal permitía crear y editar catálogos, pero no borrar pruebas. Se añadió
   Eliminar con confirmación, auditoría y protección de referencias. Las áreas
   base y los servicios heredados están protegidos.
2. Consultorios mezclaba «Servicios / especialidades» y no ofrecía la especialidad
   nueva como requisito. Se separó Especialidad requerida de Servicios de atención.
   El servidor aceptó la calificación nueva conservando el área y sus servicios.
3. La profesión es un dato de la ficha; no se asigna directamente al consultorio.
   La asignación vincula persona, consultorio y fechas. Se verificó que el nuevo
   profesional apareciera en Admisión después de su asignación vigente.
4. Una ficha profesional sin cuenta sirve para seleccionar al responsable en
   Admisión. Sin embargo, `medico.demo` no pudo emitir el FUA de otro responsable:
   el servidor respondió «Solo puede emitir documentos de sus propias atenciones».
   Con autorización expresa se creó una cuenta temporal con rol PROFESIONAL,
   vinculada a la persona nueva. Desde ella se registró el FUA correctamente.
5. Guardar el paciente abre su ficha sin habilitar Admisión en la barra lateral.
   Fue necesario volver a Base de datos y buscar el DNI. La búsqueda única lo
   seleccionó y habilitó Admisión. Es una fricción de navegación pendiente.
6. El área, la especialidad profesional y el servicio siguen siendo conceptos
   distintos. Cardiología se configuró como requisito del consultorio bajo
   Medicina; no se creó un servicio clínico nuevo llamado Cardiología. Las áreas
   y sus servicios siguen definidos en `app/domain/office.py`.

## Resultado y límites

La atención se reabrió desde el historial después de recargar: había una sola
atención para el paciente, con el consultorio y el responsable nuevos. Se descargó
el PDF desde Imprimir S.I.S. y se revisó su única página renderizada. El responsable,
DNI, historia y mediciones se imprimieron correctamente. El consultorio y el
servicio se conservan y se muestran en Datos de la FUA; el formulario oficial
usado como fondo no tiene un recuadro específico de consultorio físico.

Registrar FUA y descargar el prellenado son operaciones diferentes. El primero
reserva un número local; la descarga usa la copia guardada de la atención y no
reemplaza el número del papel preimpreso. Este documento es un prellenado parcial:
no se completaron diagnósticos, prestaciones ni firmas. No se realizó una impresión
física ni se confirmó calibración de impresora.

Se intentó registrar un segundo FUA desde la cuenta responsable. La interfaz
mostró «La atención ya tiene un FUA emitido» y no generó otro número. El botón
Registrar FUA sigue disponible aunque el documento exista: hay protección en el
servidor, pero falta anticipar esa condición en la presentación de la ficha.

La cuenta temporal `cardio.e2e.2110` se dio de baja después de emitir el FUA.
Se confirmó su estado Inactivo en Cuentas de usuario con Incluir inactivos.
La ficha del profesional y sus vínculos se conservaron para revisar el recorrido.

También se creó y eliminó desde Personal la especialidad sin vínculos
`E2E DESCARTABLE ELIMINAR 2110`: el catálogo pasó de 10 a 11 y volvió a 10 filas.
El registro desapareció y no se eliminaron las pruebas previas del usuario.

## Evidencia

- `docs/audits/e2e-cardio-asignacion-20261021.png`
- `docs/audits/e2e-cardio-admision-20261021.png`
- `docs/audits/e2e-cardio-atencion45-20261021.png`
- `docs/audits/e2e-cardio-fua-datos-20261021.png`
- `docs/audits/e2e-cardio-fua-registrado-20261021.png`
- `docs/audits/e2e-cardio-fua-duplicado-bloqueado-20261021.png`
- `docs/audits/e2e-cardio-cuenta-inactiva-20261021.png`
- `docs/audits/e2e-cardio-catalogo-final-20261021.png`
- `docs/audits/e2e-cardio-fua-20261021.pdf` y su página renderizada `.png`

Además de este recorrido real: 79 pruebas unitarias backend, 21 pruebas de interfaz
y 2 pruebas de integración MySQL aprobaron. La integración usó un esquema temporal
separado y no sustituye la prueba E2E descrita arriba.

Comprobación final: después de recompilar y recargar Personal, el registro
descartable eliminado no reapareció. La repetición de las 13 pruebas del panel de
catálogos, `vue-tsc --build`, ESLint, Ruff y la compilación Vite finalizaron sin errores.
