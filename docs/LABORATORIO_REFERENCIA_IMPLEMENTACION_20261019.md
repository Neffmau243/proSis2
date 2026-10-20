# Laboratorio: documentos recibidos y FUA — primera entrega

Fecha: 19/10/2026.

## Comportamiento implementado

- La ficha identifica referencia y contrarreferencia como números de documentos recibidos, conserva los ceros y explica que escribirlos no emite hojas nuevas.
- El historial muestra ambos números. «Consultar / reimprimir» carga la atención persistida sin reemplazar el borrador de una atención nueva.
- La consulta histórica permite preparar HCI, FUA y copia adicional usando exclusivamente la instantánea guardada. La disponibilidad de impresión SIS se basa en la afiliación conservada en esa copia, no en cambios posteriores de la ficha.
- Se descartan consultas que terminen después de cambiar de paciente/consultorio o cerrar el diálogo. También se verifica que la atención devuelta corresponda al contexto solicitado.
- La modalidad REFERENCIA pide origen completo: RENIPRESS de ocho dígitos, nombre de IPRESS y número recibido. El mismo número alimenta `numero_referencia_ingreso` y `fua_datos.referencia_hoja`.
- La API rechaza dos números de hoja distintos y, para una referencia sin número de ingreso separado, toma la hoja validada del FUA.
- El detalle general y la HCI muestran los números recibidos; la HCI también incluye el origen que conserva la instantánea.
- Reutiliza el contrato y los componentes de referencia/FUA de admisión. No necesita migraciones ni cambia permisos.

## Pruebas ejecutadas

- 56 pruebas de contratos de referencia, proyección FUA y descubrimiento de laboratorio aprobadas.
- 11 pruebas adicionales de servicio y mapper de atenciones aprobadas.
- 25 pruebas específicas de frontend aprobadas: guardado de laboratorio, consulta histórica y aislamiento de respuestas, HCI, historial, ficha de paciente y detalle.
- Prueba adicional del nuevo diálogo aprobada.
- Revisión de regresión de FUA y admisión: 33 pruebas aprobadas y un fallo previo en `FuaPrintDialog.test.ts`, caso «un adolescente conserva el grupo escolar con indicadores parcialmente aplicables». Espera P/E, T/E y P/T, mientras el componente actual muestra IMC/edad y T/E. El componente FUA, su utilidad y ese archivo de prueba coinciden con HEAD; no se alteraron para este cambio.
- Comprobación de tipos Vue/TypeScript y compilación de producción aprobadas. ESLint pasó en los componentes/composables de laboratorio y el componente compartido modificados. Ruff pasó para los archivos Python modificados excluyendo UP042, advertencia previa de las clases Enum existentes.

## Comprobación en navegador local

1. Paciente ficticio 14: abrir desde laboratorio la atención anterior 41, visualizar `001565` y `00007` y preparar su FUA sin crear otra atención.
2. Registrar la atención ficticia **42** el 19/10/2026 a las 09:45, modalidad REFERENCIA, hoja **000042**, RENIPRESS **00001234** y nombre **IPRESS ORIGEN FICTICIA DE PRUEBA**. La observación identifica expresamente el caso como ficticio.
3. Abrir «Imprimir S.I.S.» desde laboratorio: el resumen conserva los tres datos de origen. La plantilla de vista previa contiene la marca X de REFERENCIA y los valores exactos de RENIPRESS, origen y hoja.
4. Recargar la aplicación, consultar la atención 42 desde el historial y abrir «Imprimir FUA guardado»: se conservan modalidad, origen y hoja sin crear otra atención.
5. No se marcó una calibración física como comprobada ni se imprimió en una impresora. No hubo envío a SIS, MINSA o a otra IPRESS.

La compilación actual queda disponible en `http://localhost:8000/laboratorio?paciente_id=14`. El historial permite volver a consultar la atención 42.

## Alcance pendiente

Este cambio conecta recepción de pacientes y reimpresión local. Siguen pendientes la vinculación formal entre documentos, las solicitudes y muestras, los resultados validados, la emisión de contrarreferencia y el registro de su entrega/recepción. El FUA conserva los datos que corresponden a su formato; no sustituye los documentos de resultados o contrarreferencia.
