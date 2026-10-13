# Auditoría de alineación del proyecto con el FUA SIS

Fecha de referencia: 12/10/2026. Código revisado: `d072d5f` y estado local consultado durante esta revisión.

## Dictamen

**Alineación parcial. El proyecto guarda correctamente varios datos básicos y conserva una copia por atención, pero todavía no constituye un registro completo del FUA ni permite acreditar cumplimiento integral del estándar SIS.** Su alcance real sigue siendo el prellenado parcial sobre papel.

Hay tres cuestiones distintas: que el esquema tenga campos adecuados, que el usuario pueda capturarlos y que la salida los incluya. El esquema tiene algunas capacidades que el flujo de captura y la impresión todavía no utilizan. Tener datos completos de afiliación tampoco acredita que el asegurado esté vigente en SIS.

Esta revisión cubre almacenamiento, captura y proyección de impresión del FUA. No evalúa todo HIS/SIEN, no certifica exactitud clínica ni sustituye la revisión administrativa del establecimiento.

## Método y fuentes

- Lectura de modelos, contratos, servicios, repositorios, migraciones y componentes Vue relacionados con paciente, atención, FUA y laboratorio.
- Consultas agregadas a la base MySQL configurada, dentro de una **transacción READ ONLY**. No se crearon, corrigieron, anularon ni emitieron registros. Los resultados conservados no contienen nombres ni documentos de pacientes/profesionales.
- 60 pruebas focalizadas de backend y 68 pruebas focalizadas de frontend aprobadas.
- Reproducciones sintéticas de referencia descartada, tipo de diagnóstico libre, fecha de parto incoherente y diferencia de fecha entre atención y copia al recibir un timestamp UTC.
- Contraste con [RJ 000178-2024-SIS/J](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j), [Directiva 002-2024-SIS/GREP-V.02, anexos 1 y 3](https://cdn.www.gob.pe/uploads/document/file/7310926/6245149-directiva-n-02-2024-sis-grep-v-02-actualizado.pdf?v=1733872542) y [criterios RM-CV de 2026](https://www.gob.pe/institucion/sis/normas-legales/7772769-000002-2026-sis-grep), también revisados en la investigación anterior. El diseño RM-CV conserva la plantilla oficial.

Lista base de requisitos: [FUA_REQUERIMIENTOS.md](FUA_REQUERIMIENTOS.md). Evidencia agregada: [fua_20261012_aggregate.json](audits/fua_20261012_aggregate.json). Script de consulta: [fua_readonly_probe.py](audits/fua_readonly_probe.py).

## Lo observado en la base local

Los conteos describen exclusivamente la base local consultada; no se asume que todos los registros sean atenciones reales de producción.

| Comprobación | Resultado | Interpretación |
| --- | --- | --- |
| Tablas y columnas declaradas por ORM frente al esquema existente | 46 tablas; ninguna tabla/columna ORM ausente | No se detectó una migración pendiente que explique los faltantes observados. Esto no valida todos los índices/tipos ni todos los requisitos del SIS. |
| Revisión Alembic | `20261012_0032_lab_references` | Coincide con los campos de referencias de laboratorio revisados. |
| Pacientes | 16 | Ninguno sin primer nombre, ambos apellidos, sexo o historia clínica en los conteos ejecutados. |
| Pacientes clasificados como SIS | 10 | Los 10 tienen DIRESA, tipo y número. No se comprobó vigencia ni correspondencia externa con SIS. |
| DNI mal formado según ocho dígitos | 0 | Comprobación estructural, no verificación RENIEC. |
| Atenciones con estado ATENDIDO | 14 | Las 14 tienen copia `fua_impresion`, versión 2. |
| Atenciones sin prestaciones | 14 de 14 | Falta el código que identifica qué prestación fue brindada. |
| Atenciones sin diagnósticos | 14 de 14 | No hay diagnóstico CIE-10 asociado en el detalle clínico. |
| Atenciones sin peso o talla | 1 de 14 | Revisar aplicabilidad y completar por procedimiento clínico, sin rellenar retrospectivamente por inferencia. |
| Atenciones sin presión arterial completa | 2 de 14 | El sistema permite este registro parcial; se requiere validación por prestación. |
| Copias sin colegiatura | 11 de 14 | Corresponden en esta base a 8 atenciones con categoría BIOLOGO, 2 NUTRICIONISTA y 1 MEDICO. Verificar la colegiatura real y aplicabilidad; no inventar valores. |
| Profesionales activos | 72 | 1 sin documento y 35 sin colegiatura; la obligatoriedad debe determinarse por categoría. No todos esos profesionales están usados en las 14 atenciones. |
| Códigos de prestación 301-306 | Ninguno | El catálogo local no soporta actualmente el registro RM-CV. |
| Registros en tabla `fua` | 0 | No se observaron documentos emitidos para cotejar un número con la hoja física. |
| Establecimientos activos | 6 | Los 6 tienen RENAES numérico utilizable para formar el campo de ocho dígitos; eso no verifica vigencia RENIPRESS. Los 6 están configurados como IPRESS/intramural y código preimpreso. |
| Atenciones maternas | 0 | Las brechas maternas se comprobaron en código y reproducciones sintéticas, no como errores en pacientes de esta base. |

## Hallazgos prioritarios

### H1 — P1: el flujo guarda atenciones sin prestaciones ni diagnósticos

**Evidencia:** [AtencionNuevaView.vue:930](../frontend/src/views/AtencionNuevaView.vue#L930) arma el payload con identificación y mediciones, pero no envía `prestaciones` ni `diagnosticos`. [AttentionCreate:110](../app/schemas/attention.py#L110) permite ambas listas vacías. `_add_details` comprueba que los códigos enviados existan, pero no exige una prestación ni aplica una matriz SIS de completitud. Esto coincide con las 14 atenciones sin esos detalles en la base.

**Efecto:** `ATENDIDO` significa atención registrada en el sistema, pero no FUA clínicamente completo. Además, `FuaPrintSnapshot` no incluye prestación, UPS ni diagnósticos, por lo que enviar esas listas por API tampoco completa automáticamente la impresión.

**Corrección propuesta:** distinguir captura parcial y cierre de prestación; incorporar captura de código prestacional, UPS y diagnósticos con orden/tipo; incluirlos en la copia documental y salida. La validación debe ser por prestación y condición, sin exigir indiscriminadamente llenar todas las casillas. Requisitos afectados: RF-14, RF-15, RF-26, RF-34, RF-35.

### H2 — P1: no hay detalle estructurado ni impresión del reverso

**Evidencia:** los modelos clínicos revisados tienen prestaciones y diagnósticos, pero no un agregado de medicamentos/dispositivos con cantidades prescritas y entregadas ni procedimientos CPMS con cantidades indicadas y ejecutadas. El módulo de laboratorio registra una atención y notas/referencias; su payload no captura un panel de exámenes y resultados. Los resultados nutricionales existentes no equivalen al reverso completo.

La lista de campos en [fuaPrint.ts:148](../frontend/src/utils/fuaPrint.ts#L148) y `fuaPrintHtml` produce una sola superficie de datos del anverso parcial. No existen bloques de reverso dentro de ese flujo.

**Efecto:** no se puede reconstruir desde el sistema lo prescrito/entregado/ejecutado ni vincularlo al diagnóstico como exige el FUA del primer nivel. Fuente: directiva, pp. 36-39. Requisitos afectados: RF-29 a RF-33.

**Corrección propuesta:** agregar detalles de consumo y procedimientos vinculados al diagnóstico y número de FUA, con estados/resultados adecuados y salida del reverso; conservar espacios de conformidad y observaciones.

### H3 — P1: falta vincular el número del papel preimpreso con el registro

**Evidencia:** [DocumentService.issue_fua:90](../app/services/document.py#L90) genera un correlativo local usando RENIPRESS, lote y secuencia. En cambio, `FuaPrintSnapshot` no conserva `numero_fua`, y el diálogo explica que no reemplaza el número preimpreso. `FuaIssueInput` tampoco recibe el identificador de una hoja física.

**Efecto:** el prellenado puede salir sobre un formulario cuya numeración no queda vinculada al registro del sistema; emitir por el otro flujo genera un número que no se coteja con esa hoja. La estructura numérica es correcta, pero no hay control de rango oficial, reserva de formularios físicos ni protección contra cruces con otros sistemas. En esta base no hay FUA emitidos, por lo que no se observó una colisión real.

**Corrección propuesta:** definir un modo de uso. Si es preimpreso, registrar y validar el número físico, con rango autorizado y anverso/reverso concordantes. Si el sistema genera la numeración, controlar el rango asignado y usar ese mismo identificador en toda salida. Requisito RF-01 y RT-01.

### H4 — P1: la referencia de ingreso no llega a la copia del FUA

**Evidencia:** [AttentionModeCode:17](../app/schemas/attention.py#L17) solo admite AMBULATORIA y EMERGENCIA. En [build_fua_snapshot:33](../app/services/fua_print.py#L33), `tipo_atencion` se toma de esa modalidad; los datos del suplemento solo se copian si la modalidad es REFERENCIA. Esa rama no puede alcanzarse a través del contrato normal de creación.

**Reproducción:** una atención AMBULATORIA acompañada de `fua_datos` válido con REFERENCIA y los tres datos de origen genera copia AMBULATORIA y pierde el origen/hoja. Intentar enviar REFERENCIA como modalidad clínica es rechazado por el contrato. El nuevo campo `numero_referencia_ingreso` de laboratorio se guarda en la atención pero no resuelve el origen completo ni se copia al FUA.

**Corrección propuesta:** representar explícitamente la condición de referido y el origen del documento, sin confundirla con el proceso de referencia de salida; mapearla y validarla en la copia/impresión. RF-04, RF-05.

### H5 — P1: se excluye PAB de salud materna sin una regla clínica oficial

**Evidencia:** [AtencionNuevaView.vue:417](../frontend/src/views/AtencionNuevaView.vue#L417) ofrece PAB solo en el grupo general; [selectCareGroup:787](../frontend/src/views/AtencionNuevaView.vue#L787) borra su valor al cambiar grupo. [fuaUsesAbdominalPerimeter:90](../frontend/src/utils/fuaPrint.ts#L90) y el diálogo dejan de advertir su ausencia en gestantes/puérperas.

**Contraste:** en el anexo oficial, p. 11, la FPP/fecha real de parto está en datos del asegurado y PAB en actividades preventivas. Son casillas distintas. El instructivo, p. 29, indica registro de PAB en prestaciones preventivas/recuperativas; cualquier excepción debe proceder de una regla clínica vigente. Sustituir visualmente un control por otro no prueba una exención normativa.

**Corrección propuesta:** disponer de ambos datos en el flujo y aplicar su pertinencia con reglas oficiales. No borrar una medición capturada solo por cambiar la disposición de la interfaz. RF-12, RF-19. No se encontraron atenciones maternas en esta base para medir impacto histórico.

### H6 — P1: no se asegura completitud de la identidad del responsable

**Evidencia:** el snapshot copia documento y colegiatura del catálogo, que admite nulos; `fuaWarnings` no revisa esos campos. En la base hay 11 copias sin colegiatura, incluida una atención con categoría MEDICO.

**Efecto:** la salida puede omitir un dato obligatorio cuando corresponda al perfil. Una firma o sello manuscrito posterior no significa que el sistema guarde y reproduzca la casilla de colegiatura.

**Corrección propuesta:** verificar identidad, categoría y colegiatura del responsable antes de cerrar el FUA; incorporar especialidad/RNE cuando aplique y un procedimiento explícito de corrección documental. No actualizar automáticamente copias históricas a partir del catálogo actual. RF-27.

## Otras brechas y defectos comprobados

| ID / prioridad | Hallazgo | Evidencia y propuesta |
| --- | --- | --- |
| H7 / P1 | Sin catálogo 301-306 ni validación RM-CV | Consulta devuelve cero códigos. No se encontró motor de reglas SIS equivalente a RC01/RC04/RC12/RC14/RC30/RC31 y demás reglas aplicables. Agregar catálogo y fichas vigentes por prestación/condición, manteniendo el diseño oficial. No basta escoger un código por edad. |
| H8 / P2 | Tipo diagnóstico libre | `AttentionDiagnosisInput.tipo_diagnostico` admite cualquier texto de hasta 50 caracteres o nulo. Se reprodujo aceptación de `CUALQUIER_TEXTO`. Usar valores/mapeo P/D/R de ingreso y D/R de egreso, diferenciados, y exigirlos al cerrar cuando corresponda. |
| H9 / P2 | Fecha real de parto puede ser posterior a la atención | Un payload PUERPERAS con atención 12/10/2026 y parto 20/10/2026 pasa el contrato. Los servicios revisados no comparan esas fechas. Agregar validación de cronología real y de FPP según contexto. No se observó el problema en registros maternos locales porque no existen. |
| H10 / P2 | Fecha clínica y fecha impresa divergen con timestamps zonificados | Con `2026-10-12T02:00:00Z`, el servicio usa `.date()` como 12/10 para edad/validación y conserva el datetime recibido; el snapshot convierte a Lima y usa 11/10. En MySQL `DateTime` no conserva la zona. Normalizar al mismo criterio de tiempo antes de validar, calcular, persistir y proyectar. El flujo UI habitual envía hora local sin zona; el defecto se reprodujo con entrada API sintética. |
| H11 / P2 | Dependencia de zona horaria no asegurada en Windows | En `.venv`, `ZoneInfo('America/Lima')` falla por ausencia de `tzdata`; `issue_fua` falla en reproducción sintética antes de numerar. El Python del sistema sí dispone de Lima. Declarar/garantizar los datos de zonas en el entorno de despliegue; no concluir que el proceso API activo falla sin verificar qué intérprete utiliza. |
| H12 / alcance | Otros datos del formulario todavía ausentes o sin proyección | Destino del asegurado, hospitalización/corte, RN/APGAR, controles maternos completos, vacunas, firma/conformidad, representante de esa atención y otra IAFAS no tienen una proyección completa al FUA. Hay capacidades parciales en paciente, referencias y nutrición; no equivalen a que se registren e impriman en cada FUA. |

## Qué sí está bien alineado

- DNI y CE tienen mapeo explícito TDI 2/3. Se evita presentar el ID interno de la sede como RENIPRESS.
- DIRESA, tipo, número y secuencia SIS se guardan como texto, conservando ceros. Etnia se valida contra catálogo y no se deduce de nombre/domicilio.
- Al dejar SIS se limpia la afiliación de la ficha actual y se conserva la copia histórica de la atención.
- `build_fua_snapshot` toma identidad, sede, profesional y mediciones del servidor; la copia se guarda con la atención en la misma transacción. Cambiar después el paciente no cambia esa copia.
- IMC e indicadores nutricionales se calculan en backend; no se confía en un IMC enviado en el suplemento de impresión.
- Las prestaciones y diagnósticos que sí se envían por API se validan contra catálogos activos y se guardan con orden.
- El formateador de FUA usa estructura 8/2/8 y la secuencia local se reserva atómicamente. Eso garantiza el comportamiento local, no el rango asignado por SIS/red/UDR.
- La reimpresión usa la copia guardada y no crea otra atención; la salida escapa texto y comprueba geometría/desbordamientos.
- La calibración guarda geometría y no información clínica en `localStorage`. El módulo avisa que es uso local y que hay campos por completar a mano.

## Cobertura frente a la lista de requisitos

“Parcial” identifica implementación incompleta o pendiente de validación operativa; no representa una aprobación normativa.

| Requisitos | Estado de almacenamiento/captura | Estado de impresión |
| --- | --- | --- |
| RF-01, número único y ambos lados | Estructura y secuencia local disponibles; sin enlace a hoja física/rango oficial | Número fuera del snapshot; reverso no generado |
| RF-02 a RF-04, sede/personal/lugar/modalidad | Básicos disponibles; personal/lugar por configuración de sede; referencia incompleta | Parcial |
| RF-05, origen de referencia | Contrato de referencia suplementaria no alcanza el mapper; laboratorio solo conserva números | No llega correctamente a FUA |
| RF-06 a RF-07, documento/SIS | Básicos alineados estructuralmente; sin acreditación en línea | Disponibles en prellenado local |
| RF-08, otra IAFAS | Seguro catalogado en paciente; falta la proyección de institución/código individual a FUA | Ausente |
| RF-09 a RF-11, nombres/sexo/nacimiento/HC/etnia | Básicos disponibles, snapshot y catálogo | Disponibles |
| RF-12, salud materna/fechas | Condición y fechas parciales; cronología sin validación completa | FPP o fecha real según grupo |
| RF-13, datos RN | Sin captura/proyección completa del FUA | Ausente |
| RF-14 a RF-15, atención/UPS/prestaciones | Fecha/hora disponibles; prestaciones en API pero no capturadas por UI revisada; UPS no proyectada | Solo fecha/hora/modalidad |
| RF-16 a RF-18, hospitalización/vínculo/destino | Referencias de salida independientes; falta agregado FUA completo | Ausente |
| RF-19, mediciones | Básicas opcionales; PAB excluido de UI materna; ausencia de reglas de completitud por prestación | Parcial |
| RF-20 a RF-24, preventivos/materno/infantil/crónicos | Algunos campos nutricionales en API/modelo; faltan componentes y captura integrada | Parcial; muchos sin proyección |
| RF-25, vacunas | Sin detalle de vacunación del FUA | Ausente |
| RF-26, diagnósticos | Modelo/API parcial y sin captura UI; tipo libre; sin ingreso/egreso separados | Ausente |
| RF-27, responsable | Identidad y colegiatura de catálogo; incompletitud observada; faltan campos especializados en copia | Parcial |
| RF-28, conformidad | Se contempla completado manuscrito; sin registro de conformidad por FUA | Solo papel preimpreso/manual |
| RF-29 a RF-33, reverso | Sin detalle integral de consumo/procedimientos/conformidad | Ausente |
| RF-34 a RF-35, RM-CV/reglas | Códigos ausentes en base; sin motor SIS de completitud | No soportado por el flujo actual |

## Validación ejecutada y límites

Backend: `test_fua_print`, `test_document_number_formatter`, `test_patient_sis`, `test_patient_patch_contract` y `test_attention_service`: **60 aprobadas**, con un aviso de opción pytest de asyncio no reconocida.

Frontend: `fuaPrint`, `fuaAdmissionDraft`, `FuaPrintDialog`, `patientValidation`, `AdmissionPatientSummary` y `laboratory`: **68 aprobadas**. Los primeros intentos en sandbox fallaron al leer temporales de Vite; la ejecución fuera de ese aislamiento completó los seis archivos correctamente. No se atribuye ese fallo inicial al producto.

La prueba de matriz optativa `fuaMatrix` quedó omitida por no disponer del reporte sintético que requiere. No se ejecutaron tests de integración que crean registros en MySQL ni pruebas con impresora. No se consultó SIS/RENIPRESS/RENIEC para validar identidades, afiliaciones o vigencias. No se encontró evidencia suficiente para afirmar que el formato físico está alineado ni que un FUA digital esté implementado.

**Que estas pruebas pasen significa que el módulo hace lo previsto por sus pruebas actuales; no que cubra todos los requisitos oficiales.**

## Orden de corrección recomendado

1. Separar admisión/prellenado parcial y FUA completo. Capturar prestaciones, UPS y diagnósticos con validación de cierre por prestación, y resolver los responsables incompletos.
2. Corregir referencia de ingreso y el tratamiento de PAB materno; validar cronología y normalizar fechas.
3. Vincular número físico o rango autorizado con la copia por atención y ambas caras.
4. Implementar reverso estructurado y su salida; completar los campos condicionales de la cartera real de la posta.
5. Incorporar RM-CV/catálogos/reglas actuales y comprobar casos por curso de vida, condición y perfil profesional.
6. Validar físicamente la impresión y definir el proceso de conformidad/custodia. FUA digital/SETI requiere un alcance adicional con acreditación, firma digital y repositorio.

No se recomienda rellenar las 14 atenciones existentes por inferencia. Las correcciones históricas requieren revisión de los documentos fuente y un procedimiento trazable.

## Verificación adicional: documentos y formatos de 2025 y 2026

Revisión ampliada el **13/10/2026**, a solicitud del usuario. No se volvió a consultar ni modificar la base; los conteos anteriores corresponden a la auditoría previa.

### Qué documento determina el formato actual

1. **MINSA, 12/01/2025:** la [publicación sobre el FUA electrónico del Hospital Santa Rosa](https://www.gob.pe/institucion/minsa/noticias/1089667-hospital-santa-rosa-moderniza-su-servicio-de-emergencia-con-el-formato-unico-de-atencion-electronico) identifica expresamente la Directiva 002-2024-SIS/GREP-V.02 como su base. Sirve para corroborar su uso en 2025; una nota de prensa no sustituye el instructivo.
2. **SIS, publicación 14/05/2025:** [Trama de datos del FUA](https://www.gob.pe/institucion/sis/informes-publicaciones/7041412-trama-de-datos-del-fua), con [PDF oficial](https://cdn.www.gob.pe/uploads/document/file/8491198/7041412-documentotramadatos.pdf?v=1755189947). Se revisaron los contratos de afiliación/atención, diagnósticos, medicamentos, insumos, procedimientos y RN, pp. 9-17. Su control de versiones indica creación del documento el 10/02/2025. Es una especificación de intercambio electrónico, no una nueva distribución de la hoja de papel.
3. **SIS, 23/02/2026, vigencia 01/03/2026:** los [criterios RM-CV](https://www.gob.pe/institucion/sis/normas-legales/7772769-000002-2026-sis-grep), **p. 17, numeral 6.4.1**, mantienen explícitamente estructura, campos y diseño del FUA del anexo 1 de la V.02. Los códigos 301-306 se registran en la casilla existente de código prestacional; se conserva el reverso con consumos y procedimientos.

**Conclusión de la búsqueda:** el modelo de referencia confirmado para 2025 y por el documento de 2026 es el anexo 1 de la Directiva 002-2024-SIS/GREP-V.02. No se encontró en las fuentes revisadas un nuevo diseño anual independiente que sustituya ese anexo. La palabra “2024” en el nombre de la directiva no la convierte por sí sola en obsoleta en 2025 o 2026. El lote del número de FUA identifica el año de impresión según la especificación; no es por sí mismo una versión del diseño.

También se revisó el [manual MINSA de consulta externa SIHCE](https://www.minsa.gob.pe/sihce/manualess/MU_CONSULTA_EXTERNA.pdf): contiene un ejemplo de impresión y muestra captura de diagnóstico, prescripción, exámenes y destino, pero su ejemplo utiliza una distribución anterior. No se le asignó una fecha 2025/2026 por estar disponible actualmente en el sitio; para decidir la plantilla se priorizó el anexo normativo y la confirmación explícita de 2026.

### Evidencia visual conservada

- [Anverso oficial, p. 11 de la directiva](audits/fua-oficial-anverso.png).
- [Reverso oficial, p. 12 de la directiva](audits/fua-oficial-reverso.png).
- [Página 17 del documento 2026, que confirma invariabilidad del diseño](audits/fua-rmcv-2026-pagina17.png).
- [Imagen histórica utilizada como ayuda en el proyecto](fua.png).

Las imágenes oficiales se renderizaron desde los PDF del SIS, sin modificar sus campos y sin datos de pacientes.

### H13 — P1 para validar impresión: la imagen de ayuda no reproduce el diseño vigente

La imagen `docs/fua.png`, origen de la ayuda visual `fua-referencia.webp`, muestra un ejemplo con lote **17**, código de establecimiento rotulado **RENAES**, bloque de **institución educativa** y una distribución de actividades preventivas distinta del anexo normativo revisado.

En el anverso oficial actual, **IMC y PAB están en la fila de mediciones junto con peso, talla y PA**. En la imagen histórica aparecen dentro de otra distribución del bloque preventivo. El anexo actual también cambia el bloque de concepto prestacional respecto a esa imagen.

El código de impresión ya declara que las posiciones iniciales son aproximadas y exige calibración; por ello no se concluye que toda impresión calibrada esté desplazada. Sí se concluye que **usar esa imagen como única prueba de alineación no demuestra coincidencia con una hoja oficial actual**. Cambiar solo el lote a 25/26 o el tamaño de papel tampoco resuelve diferencias de distribución.

Corrección propuesta: utilizar una referencia oficial actual para la revisión visual y calibrar contra la hoja física que emplea la IPRESS, manteniendo un perfil identificable por plantilla/impresora. Los campos que hoy no tienen salida, como diagnósticos y reverso, requieren implementación además de calibración.

### Contraste adicional de datos con la trama 2025

| Elemento | Trama oficial 2025 | Proyecto | Resultado |
| --- | --- | --- | --- |
| DISA del contrato | 3 caracteres; obligatoriedad condicional | `sis_diresa`, texto de 3 caracteres | Tamaño compatible; requiere origen de acreditación real |
| Formato del contrato | 1 o 2 caracteres alfanuméricos | `sis_tipo`, texto de 1 o 2 caracteres | Tamaño compatible; no deducir del catálogo ETLSIS del seguro |
| Número del contrato | 8 o 9 dígitos, incluidos ceros iniciales | `sis_numero`, texto de 8 o 9 dígitos en ficha | Compatible estructuralmente |
| Secuencia del contrato | Hasta 2 dígitos, condicional | `sis_secuencia`, texto de hasta 2 dígitos | Compatible estructuralmente; no necesariamente visible en ficha |
| Identidad de contrato | Tabla e identificador de registro obligatorios en trama de atención | No están en el contrato específico de la copia FUA revisada | Pendiente para envío electrónico completo |
| Tipo documento | Catálogo electrónico distinto del papel: DNI 1; CE 3 | DNI/CE como códigos de ficha; TDI 2/3 para impresión de papel | Papel coherente con su instructivo. Un futuro exportador debe mapear al catálogo electrónico, sin copiar TDI 2 como DNI |
| Diagnóstico | Principal obligatorio; movimiento ingreso/egreso; tipos numéricos 1/2/4; CIE-10 sin punto para transmisión | Tipo libre y sin movimiento separado; el flujo revisado no captura diagnósticos | Requiere captura y serializador específico; no enviar las filas actuales directamente como trama |
| Medicamento/insumo/procedimiento | Código, diagnóstico asociado y cantidades prescrita/entregada; resultado del procedimiento cuando corresponda | Sin detalle integral del reverso | No alineado como registro electrónico completo |
| Prestación por curso de vida 2026 | Códigos 301-306 en `COD. PRESTA.`, con sus reglas | Ausentes en el catálogo de la auditoría previa | Pendiente |

El hecho de que el maestro de pacientes permita nombres/historias clínicas más largos que la trama no exige recortar la ficha. Requiere validación y un proceso de exportación que respete el contrato sin pérdida silenciosa. Igualmente, guardar un CIE-10 con punto es compatible con representación clínica/papel; el requisito de quitarlo corresponde a la transmisión electrónica.

**Resultado confirmado:** la estructura de las casillas de afiliación SIS está alineada con el documento 2025. La imagen de ayuda y la cobertura total de captura/impresión requieren trabajo. El proyecto todavía no implementa el FUA completo ni su trama de envío; esta conclusión es independiente de comprobar la vigencia individual de un paciente.
