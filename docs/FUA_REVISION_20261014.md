# Revisión de Imprimir FUA · uso local — 14/10/2026

## Resultado

**Ajuste posterior solicitado en esta misma revisión:** se unificó la imagen activa
en `frontend/src/assets/fua-v02-referencia.png` para todos los perfiles, vista previa
y PDF. Se retiró el escaneo alternativo y el selector de referencia histórica.
La imagen antigua se archivó en `docs/referencias/fua/fua-historica.webp`, fuera del
build. Los perfiles históricos conservan su geometría y pasan automáticamente a
la referencia oficial; requieren comprobar la alineación una sola vez. Las
descripciones de la implementación inicial que aparecen abajo son antecedentes;
el comportamiento actual se documenta en `FUA_IMPRESION.md`.

Validación de la unificación: 42 pruebas focalizadas de frontend y 4 pruebas de
navegador aprobadas, incluyendo perfil histórico, normalización persistida y
coincidencia de la imagen de vista previa con la del PDF. TypeScript, build y
ESLint aprobados; la imagen histórica ya no figura entre los assets compilados.

Tras revisar una captura de la vista de impresión sin formulario, se hizo principal
**Ver FUA / guardar PDF**, que incluye el anexo y los datos. La alternativa de
papel ya impreso se renombró **Imprimir sobre FUA preimpresa**. La prueba de
navegador genera ahora el PDF con `printBackground: false`: conserva una imagen
del formulario, los datos y una página. Así se comprueba que la casilla Gráficos
de fondo no es necesaria para la salida con formulario. Pasaron 41 pruebas de
impresión/diálogo y las 4 de navegador para este ajuste.

El guardado de paciente y atención llega a MySQL; el módulo imprime una copia
documental creada en backend en la misma transacción que la atención. La base
local revisada tiene **16 atenciones y 16 copias FUA versión 2**. No hay diferencias
entre las columnas de peso, talla, presión sistólica/diastólica, IMC, perímetro
abdominal, historia clínica y modalidad y los respectivos valores del JSON.
Es una verificación de lo almacenado, no de la veracidad clínica o acreditación SIS.

Evidencia agregada, sin identidades: `audits/fua_20261014_aggregate.json`.
La consulta se ejecutó en una transacción explícita de solo lectura. No se
modificaron fichas, atenciones ni copias históricas.

## Calibración

Antes se guardaba únicamente al pulsar Guardar calibración, en la clave
`ipress.fua-layout.v1` de localStorage. El perfil no pertenece al paciente ni a la
cuenta: se comparte en el mismo navegador y origen (protocolo, dirección, puerto).
Cerrar sesión solo elimina la clave de sesión, no la de calibración. Cambiar
origen —por ejemplo localhost frente a 127.0.0.1—, equipo o navegador requiere
otro perfil; borrar almacenamiento también lo elimina.

Ahora los cambios y la confirmación se guardan automáticamente. El diálogo relee
el perfil al abrir y recibe cambios hechos por otras pestañas. Seleccionar un
campo no invalida la calibración; modificar su geometría sí. Se retiró el evento
genérico de cambio del formulario para que elegir un campo no active ese bloqueo.
Exportar/importar permite trasladar solo geometría. La importación conserva las
coordenadas y requiere confirmar la prueba física del equipo de destino.

Un perfil histórico conserva posiciones y confirmación. La referencia oficial se
activa automáticamente solo en perfiles nuevos. El cambio explícito de histórico
a V.02 parte de las posiciones de la nueva plantilla; el diálogo pide exportar
la calibración anterior antes de elegirlo. No se añade almacenamiento por paciente.

## Formato oficial y salida PDF

Referencia: [RJ 000178-2024-SIS/J y Directiva 002-2024-SIS/GREP-V.02](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j),
anexo 1, página 11. Su uso en 2025 también está documentado por
[MINSA, FUA electrónico del Hospital Santa Rosa, 12/01/2025](https://www.gob.pe/institucion/minsa/noticias/1089667-hospital-santa-rosa-moderniza-su-servicio-de-emergencia-con-el-formato-unico-de-atencion-electronico).
La [trama SIS publicada el 14/05/2025](https://www.gob.pe/institucion/sis/informes-publicaciones/7041412-trama-de-datos-del-fua)
define intercambio electrónico, no una nueva distribución anual del papel.
Se contrastó el anexo completo almacenado en `tmp/pdfs/sis-fua-v02.pdf` y sus
imágenes oficiales conservadas en el repositorio. La consulta web corroboró las
publicaciones; el servidor del SIS no permitió descargar nuevamente la directiva.

La antigua imagen mostraba RENAES, lote 17 e institución educativa, con IMC/PAB
en posiciones diferentes. El nuevo PNG es una extracción del formulario oficial,
sin el encabezado editorial de la directiva. Se obtuvo con Poppler de la página
11 a 108 dpi, área x=195, y=203, ancho=598, alto=989 px. La cuadrícula de posiciones
iniciales usa ese mismo espacio. La referencia se coloca a 10 mm del borde en el
perfil inicial de 216 × 356 mm; ese tamaño sigue siendo configurable y debe
comprobarse contra la hoja realmente usada por la IPRESS.

- **Imprimir solo datos:** mantiene la salida sin imagen para papel preimpreso.
- **PDF / imprimir con referencia:** incluye fondo, datos, RENIPRESS y leyenda
  «Vista de revisión · prellenado parcial · uso local». Permite guardar como PDF
  desde el diálogo del navegador sin confirmar antes la prueba física.
- **Imprimir prueba sin datos:** mantiene cruces y recuadros sin datos del paciente
  ni formulario de fondo.

Los datos y sus coordenadas usan el mismo generador HTML en los dos modos de
salida. Se verifica la carga de la imagen antes de imprimir. Los documentos,
códigos, fechas y mediciones conservan su tratamiento previo y no se sustituyen
por datos del formulario referencial. No se inventan número de FUA, firmas o sellos.

Se alineó la validación del complemento documental con el backend: DIRESA admite
tres caracteres alfanuméricos y es condicional, mientras tipo y número deben ir
juntos cuando existe afiliación. Código AISPED y datos de referencia solo se
aceptan con sus categorías correspondientes. El contrato de la ficha del paciente
sigue validando su número de afiliación de 8/9 dígitos; no se amplió ese maestro.

## Campos de las capturas del usuario

| Campo | Almacenamiento y origen | Salida del FUA |
| --- | --- | --- |
| Documento, apellidos, nombres, sexo, nacimiento | Ficha del paciente; copia al guardar atención | TDI/número, nombres, marcas de sexo y casillas de fecha |
| Historia clínica | Paciente y `atenciones.historia_clinica_snapshot` | La copia de esa atención |
| DIRESA, tipo y número SIS; secuencia | Columnas de texto del paciente; copia solo para régimen SIS | DIRESA separada de tipo/número/RN, sin perder ceros |
| Etnia | Ficha y catálogo activo; copia de atención | Código declarado, sin inferirlo |
| Modalidad | `atenciones.modalidad_atencion_codigo` | Marca ambulatoria/emergencia guardada |
| Profesional | Relación de atención y copia de nombre/documento/colegiatura | Recuadro del responsable; aviso cuando faltan documento o colegiatura |
| Consultorio y servicio/especialidad | Atención y contexto territorial conservado | No se convierten automáticamente en código prestacional ni UPS SIS |
| Grupo de atención | Atención | Marca gestante/puérpera; el grupo general no tiene una marca específica |
| Peso, talla, PA, IMC, perímetro abdominal | Atención; IMC calculado por backend | Casillas de mediciones; PA solo cuando ambos valores existen |
| FPP / fecha real de parto | Atención según grupo | Mismo recuadro, con fecha correspondiente a gestante o puérpera |
| Temperatura | `atenciones.temperatura_c`, enviada por el formulario y devuelta por API | Sin casilla propia en este anverso; 14 atenciones tienen temperatura, ninguna la proyecta al FUA |
| Teléfono, domicilio, distrito/localidad, historia familiar | Ficha de paciente; los territorios también quedan en el contexto de atención | No son casillas propias de este prellenado |
| Madre / grupo de riesgo | Relaciones de responsables y riesgos del paciente | No se imprimen como casillas genéricas del anverso |

La copia mantiene el estado al guardar: editar hoy la afiliación/nombre/profesional
no reescribe una FUA histórica. Los datos de paciente pendientes deben guardarse
antes de registrar la atención. Los componentes de edición conservan sus flujos
PATCH y los de madre/riesgo sus endpoints propios.

## Pendientes de cobertura detectados

La base tiene 16/16 atenciones sin prestaciones ni diagnósticos asociados;
12/16 copias sin colegiatura, 1/16 sin peso o talla y 2/16 sin PA completa. No hay
documentos emitidos en `fua` ni códigos 301–306 en el catálogo consultado. Las
copias guardadas no cubren número físico, UPS/prestación, diagnósticos, destino,
vacunas, hospitalización, consumos/procedimientos del reverso ni conformidades
completas. El cambio de referencia no crea esos datos.

El módulo sigue siendo un **prellenado parcial**, y no se puede afirmar que cubra
todo el FUA 2025. La lista normativa amplia y los requisitos condicionales siguen
en `FUA_REQUERIMIENTOS.md`; este ajuste responde a persistencia, correspondencia
de campos y revisión visual del prellenado existente.

## Validación

- Backend: 49 pruebas de FUA, SIS/paciente, PATCH y atención aprobadas.
- Frontend: 78 pruebas distintas de impresión, diálogo, borrador, resumen,
  validación y editor de paciente aprobadas en las ejecuciones focalizadas.
- Microsoft Edge/Playwright: 3 pruebas aprobadas (calibración/recarga, salida con
  referencia y traslado de posiciones). Todas usan datos sintéticos y no llaman
  al backend. Capturas de escritorio, móvil y hoja de revisión conservadas en `audits`.
- TypeScript, compilación de producción y ESLint focalizado aprobados. Detector
  de interfaz sin hallazgos. Aviso de bundle general mayor a 500 KB ya existente.
- PDF sintético generado por el navegador: una página de aproximadamente
  216 × 356 mm; texto y fondo revisados. Muestra:
  `audits/fua-v02-revision-sintetica-20261014.pdf`.

No se realizó impresión física. La alineación con la impresora y el papel de la
posta requiere su prueba en blanco; no se certifica por la captura o el PDF.
