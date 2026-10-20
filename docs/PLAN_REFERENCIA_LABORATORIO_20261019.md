# Plan de implementación de referencia y contrarreferencia de laboratorio

Fecha: 19/10/2026. Estado: plan por etapas; primera entrega implementada.

### Avance de implementación

Primera entrega implementada el 19/10/2026: campos de documentos recibidos aclarados, consulta de números en historial/detalle y reimpresión FUA/HCI desde laboratorio. También se conectó el origen de referencia con el contrato FUA existente, mediante selección explícita de modalidad REFERENCIA y captura de RENIPRESS, IPRESS y hoja. No se modificaron los FUA históricos.

Las etapas de documentos vinculados, muestras, resultados y emisión de contrarreferencia continúan pendientes. Detalle de cambios y comprobaciones: [LABORATORIO_REFERENCIA_IMPLEMENTACION_20261019.md](LABORATORIO_REFERENCIA_IMPLEMENTACION_20261019.md).

## Objetivo

Permitir recibir o emitir una referencia de laboratorio, seguir la solicitud y sus muestras, registrar resultados validados y emitir una contrarreferencia vinculada al documento original. Mantener trazabilidad por paciente, establecimiento, atención y profesional.

La primera entrega mejorará el registro que ya existe. Las siguientes completarán el circuito documental y de laboratorio.

## Punto de partida comprobado

- La pantalla `/laboratorio?paciente_id=14` guarda una atención con `numero_referencia_ingreso` y `numero_contrarreferencia_ingreso`. Son textos opcionales de hasta 50 caracteres, no documentos emitidos.
- La atención ficticia 41 conserva `001565` y `00007`; el historial se actualiza. Su modalidad es AMBULATORIA y `fua_impresion.referencia_hoja` está vacío.
- `Referral`, `DocumentService.create_referral` y `POST /documentos/referencias` ya crean referencias con origen, destino, motivo y numeración. Las nuevas referencias comienzan en PENDIENTE.
- `documento_series` ya reserva correlativos en una transacción. Hay estados de referencia definidos, pero falta implementar su consulta y transiciones operativas.
- Admisión ya tiene componentes y contratos para origen de referencia y proyección FUA. Laboratorio todavía no los utiliza.
- La HCI de laboratorio incluye los números de ingreso; el historial y el detalle general no los muestran como campos propios.
- ADMIN administra; PROFESIONAL opera atenciones. Conservar esta separación y el ámbito por establecimiento.
- La revisión anterior ejecutó 8 pruebas de backend y 10 de frontend, todas aprobadas. Esto valida los casos existentes, no el circuito aún pendiente.

## Reglas del diseño

1. Separar documento recibido y documento emitido. El número externo se conserva literalmente; el sistema genera correlativo únicamente para sus propias emisiones.
2. Separar referencia del paciente y remisión de muestras. Recibir una muestra no crea automáticamente una atención presencial del paciente ni incrementa su contador de atenciones.
3. Tratar la referencia como contexto de una atención, no como dato permanente de la ficha del paciente.
4. Conservar los registros históricos y sus instantáneas FUA. No completar retrospectivamente origen, resultados o vínculos que no constan en los datos.
5. No suponer que un número es único en todo el país. Considerar emisor, período y tipo documental; los datos antiguos incompletos no permiten deduplicación automática fiable.
6. Mantener el circuito local. La conexión con REFCON, NETLAB o SIS requerirá contratos y accesos oficiales en una etapa específica.

## Etapa 0 — Cerrar el contrato funcional

Antes de cambiar reglas clínicas o impresos:

- Documentar cuatro casos: atención directa; paciente referido; muestra recibida sin paciente; devolución de resultados.
- Precisar qué documento respalda el actual campo de contrarreferencia de ingreso. Mantenerlo como recibido hasta que exista un caso de emisión explícito.
- Contrastar los campos de las hojas con los anexos 02.1 y 02.2 de la NT 018 y con el procedimiento utilizado por el establecimiento.
- Revisar el formato FUA aplicable y la modalidad REFERENCIA ya implementada en admisión. Tener un número recibido no basta para clasificar la atención ni llenar el impreso.
- Definir el profesional responsable de recepción, validación de resultados y emisión. Aplicar los permisos existentes; cualquier ampliación deberá quedar explícita en la política y sus pruebas.

**Salida:** matriz de casos, campos y reglas de impresión. Las transiciones propuestas abajo son decisiones de software que deben ajustarse a ese procedimiento, no una afirmación de obligatoriedad nacional.

## Etapa 1 — Completar el registro actual

### Cambios

- Identificar los campos como «N.º de referencia recibida» y «N.º de contrarreferencia recibida», con una ayuda breve sobre su procedencia.
- Mostrar ambos números en el detalle de la atención y permitir consultarlos desde el historial de laboratorio.
- Conservar ceros iniciales y caracteres admitidos por los documentos externos; normalizar únicamente espacios exteriores y valores vacíos.
- Permitir reabrir una atención de laboratorio guardada y preparar su HCI desde los datos persistidos, incluso después de recargar.
- Mantener los dos campos opcionales para atención directa y para registros históricos incompletos. No obligar a llenar ambos.

### Archivos principales

`frontend/src/components/laboratory/LaboratoryPatientPanel.vue`, `LaboratoryHistory.vue`, `LaboratoryWorkspace.vue`, `frontend/src/composables/useLaboratory.ts`, `frontend/src/views/AtencionDetalleView.vue` y `frontend/src/utils/laboratoryPrint.ts`.

**Aceptación:** guardar, recargar, consultar e imprimir `001565` y `00007` sin perderlos ni atribuirlos a otro paciente; no crear otra atención al reimprimir.

## Etapa 2 — Vincular referencias recibidas y emitidas

### Datos

- Mantener `referencias` para los documentos emitidos que ya maneja el proyecto.
- Agregar un registro estructurado de documentos recibidos: tipo, número externo, fecha/período cuando conste, paciente, establecimiento emisor y receptor, motivo y usuario receptor.
- Vincular las atenciones con el documento recibido mediante una relación explícita. Un mismo documento puede originar varias atenciones; evitar duplicarlo por cada consulta.
- Relacionar una contrarreferencia recibida con su referencia original cuando se conozca. Admitir «vínculo pendiente» para documentos históricos incompletos.
- Distinguir referencias para paciente y para muestras mediante un tipo controlado en los nuevos flujos; conservar los tipos históricos de texto libre.
- Preservar los campos actuales de atención por compatibilidad. No convertir sus números antiguos en documentos verificados automáticamente.

### Servicios y API

- Agregar consultas paginadas y detalle para documentos recibidos y emitidos, filtradas por ámbito autorizado.
- Reutilizar creación de referencias y numeración existentes; agregar operaciones dedicadas para aceptar, atender, contrarreferir, cerrar o anular según el caso.
- Prohibir que el cliente cambie libremente el estado. Validar transición, actor y establecimiento en el servicio.
- Registrar historial de cambios con fecha, responsable y motivo; usar bloqueo o control de versión para operaciones concurrentes.
- Hacer idempotentes recepción y emisión ante doble clic o reintento de red, sin prohibir varias referencias legítimas para una misma atención.
- Verificar el período del correlativo frente a la fecha de emisión, incluyendo atenciones de años anteriores, y conservar todos los números ya emitidos.

**Aceptación:** localizar una referencia, ver origen/destino y atenciones vinculadas; impedir vínculos con otro paciente o establecimiento no autorizado; conservar identidad y número durante todo el seguimiento.

## Etapa 3 — Conectar el contexto de referencia con el FUA

- Reutilizar los campos de origen, RENIPRESS y hoja ya disponibles en admisión. Extraer el contrato compartido para evitar versiones distintas en ambas pantallas.
- Mantener una única fuente del número recibido. El número de una referencia de salida no sustituye al de la hoja con la que llegó el paciente.
- Cuando el caso corresponda a REFERENCIA según el contrato de la etapa 0, validar origen completo y guardar su proyección FUA en la misma transacción que la atención.
- Si el caso es atención directa, conservar su modalidad y no marcar REFERENCIA por haber escrito un número en un campo.
- Una recepción exclusiva de muestras no debe producir por sí sola una atención del paciente o un FUA.
- Mantener inmutables las instantáneas emitidas. Las correcciones posteriores necesitan un mecanismo explícito con trazabilidad.

**Aceptación:** un caso de paciente referido con origen completo conserva esos datos al recargar y reimprimir; la atención directa no se reclasifica; una referencia saliente no sobrescribe el origen recibido.

## Etapa 4 — Solicitud, muestras y resultados

### Modelo mínimo

| Entidad | Datos y relaciones principales |
| --- | --- |
| Solicitud de laboratorio | Paciente, solicitante, origen, laboratorio receptor, motivo, exámenes y referencia vinculada si existe. Atención opcional cuando solo se recibe una muestra. |
| Examen solicitado | Código del catálogo aplicable, descripción conservada y estado individual. |
| Muestra | Identificador propio, solicitud/exámenes, tipo, toma, remisión, recepción y rechazo con motivo. |
| Resultado | Examen, muestra cuando corresponda, contenido, unidades/rangos aplicables, versión, profesional y fecha de validación. |

- Reutilizar el catálogo de prestaciones para identificar exámenes cuando sea adecuado; no asumir que contiene unidades, rangos o requisitos de muestra.
- Soportar varios exámenes y muestras por solicitud. La identidad de una muestra será distinta al DNI, historia clínica y número de referencia.
- Proponer estados separados: solicitud registrada/en proceso/completada/anulada; muestra registrada/enviada/recibida/rechazada; resultado borrador/validado/corregido.
- Registrar quién recibe, procesa y valida. Un resultado validado se corrige mediante una nueva versión con motivo, sin borrar la anterior.
- Tratar la recepción de una muestra en un laboratorio y el traslado a otro como eventos trazables; verificar siempre paciente y solicitud.
- El primer alcance contempla resultados cargados manualmente. Integración con analizadores, rangos especializados y automatización requieren diseño adicional por prueba.

**Aceptación:** seguir dos muestras y varios exámenes de un paciente sin mezclarlos; rechazar una muestra con motivo; validar y corregir un resultado conservando ambas versiones.

## Etapa 5 — Emitir y recibir la contrarreferencia

- Crear una entidad de contrarreferencia vinculada a una referencia original emitida o recibida, según el circuito.
- Conservar origen, destino, fechas, profesional responsable, resumen, recomendaciones y versiones exactas de los resultados incluidos.
- Generar correlativo propio por establecimiento y período utilizando `documento_series`, con un tipo distinto del de referencia.
- Permitir un borrador. Emitir únicamente con datos suficientes y resultados validados para los exámenes incluidos.
- Diferenciar devolución parcial y final cuando falten resultados. Una devolución parcial no cierra automáticamente toda la solicitud.
- Generar la hoja de contrarreferencia y anexos de resultados a partir de una instantánea persistida, alineada con el formato acordado en la etapa 0.
- Registrar por separado emisión, entrega y recepción por el establecimiento solicitante. Generar un PDF no prueba su recepción.
- Cerrar el circuito conforme a la regla acordada; conservar evidencia de comunicación y recepción sin afirmar integración con servicios externos.

**Aceptación:** emitir una devolución ligada al documento original, reimprimir sin duplicarla, registrar su recepción y mostrar qué exámenes/resultados siguen pendientes.

## Organización de la interfaz

Mantener la pantalla actual como acceso a la atención. Agregar secciones enfocadas, progresivamente:

- Documentos recibidos: selección o registro de origen y documento.
- Solicitudes y muestras: recepción, seguimiento y pendientes.
- Resultados: edición, validación y versiones.
- Contrarreferencia: preparación, emisión, impresión y entrega.

Los componentes Vue serán de presentación y contratos tipados; la coordinación irá en composables. El backend conservará el flujo router → servicio → repositorio → modelo. No concentrar el nuevo circuito en `LaboratoryWorkspace.vue` ni en el servicio general de atenciones.

## Migraciones y compatibilidad

- Verificar el head real de Alembic antes de crear cada migración. El árbol actual contiene las revisiones 0038 y 0039 de referencia en admisión, con cambios locales en curso.
- Usar migraciones aditivas y probarlas con una copia de la base; conservar atenciones, números, referencias y FUA existentes.
- Incorporar índices para búsqueda por paciente, establecimiento, estado, documento y fecha.
- Validar claves foráneas y duplicados antes de activar restricciones sobre datos históricos. No deduplicar únicamente por número externo.
- Separar la publicación del registro documental y la del procesamiento de laboratorio, para entregar mejoras sin exigir completar todo el módulo.

## Verificación y entregables

| Entrega | Alcance | Pruebas mínimas |
| --- | --- | --- |
| 1 | Etapas 0–1: semántica, consulta y HCI | Ceros, vacíos, recarga, reimpresión, permisos y aislamiento entre pacientes. |
| 2 | Etapas 2–3: documentos y FUA | Vínculos, estados inválidos, origen/destino, numeración concurrente, idempotencia, ámbito y FUA conservado. |
| 3 | Etapa 4: laboratorio | Varias muestras/exámenes, recepción sin consulta presencial, rechazo y versiones de resultados. |
| 4 | Etapa 5: devolución | Parcial/final, resultados validados, emisión concurrente, impresión, recepción y cierre. |

Combinar pruebas de dominio y servicios, integración con MySQL desechable, pruebas de componentes y recorridos de navegador con pacientes ficticios. Revisar visualmente los impresos. No usar pacientes reales para poblar casos de prueba ni presentar estas verificaciones como homologación MINSA/SIS.

**Caso final de extremo a extremo:** registrar una referencia → recibir paciente o muestra según corresponda → procesar exámenes → validar resultados → emitir contrarreferencia vinculada → registrar recepción → consultar e imprimir el historial completo.

## Referencias de trabajo

- Revisión funcional local: `tmp/lab-ref-review-20261019/revision.md` y atención ficticia 41.
- [NT 018, RM 751-2004/MINSA](https://www.gob.pe/institucion/minsa/normas-legales/253117-751-2004-minsa): base documental y anexos; validar su aplicación al procedimiento concreto.
- [Texto completo de la norma y formatos](https://larcoherrera.gob.pe/wp-content/uploads/2020/08/RESOLUCION.pdf).
- [NTS 072, RM 627-2008/MINSA](https://www.gob.pe/institucion/minsa/normas-legales/354769-627-2008-): organización de patología clínica.
- [Manual REFCON, Hospital San José del Callao, 2024](https://www.gob.pe/institucion/hsj/normas-legales/5480026-rd123-2024-hsj-grc): referencia operativa institucional; no asumir que define todos los procedimientos de otros establecimientos.
