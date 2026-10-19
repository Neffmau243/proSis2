# Prueba de recorrido de posta - 17/10/2026

Recorrido realizado desde la interfaz de http://127.0.0.1:8000 con la cuenta medico.demo, rol PROFESIONAL. Todos los datos clínicos nuevos son ficticios. No se modificó el código ni se escribieron registros mediante SQL o llamadas directas a la API.

## Registros creados

- Paciente #17: Prueba Lucero Mateo Simulado.
- DNI ficticio: 99061017. Historia clínica: PRUEBA-20261017-NINO.
- Nacimiento: 17/04/2023. Sexo masculino. Grupo etario NIÑO.
- Madre responsable: Aurelia Prueba Lucero Ficticia, DNI 98032888, ya presente en la base como paciente de prueba. La pestaña Responsables muestra el parentesco MADRE y estado Activo.
- Seguro seleccionado para la simulación: S.I.S. Gratuito. No se verificó afiliación externa.
- Sede y residencia: C.S. ALTO SELVA ALEGRE / ALTO SELVA ALEGRE.
- Atención #20: primera prueba con WOODWARD PAJA CALLO. Guardada como ATENDIDO. La emisión del FUA fue rechazada porque ese profesional no corresponde a medico.demo. Permanece guardada y no tiene FUA emitido por este recorrido.
- Atención #21: segunda prueba con ELSA GUILLEN TOCCAS, profesional vinculado a medico.demo. Guardada como ATENDIDO.
- FUA local emitido para #21: 00001291-26-00000001, RENIPRESS 00001291, lote 26. La interfaz confirmó Documento emitido / FUA registrado. Se incluyó una observación que identifica expresamente el caso como prueba con datos ficticios, sin atención real ni facturación SIS.

## Mediciones simuladas y persistencia

Peso 15 kg, talla 100 cm, perímetro abdominal 50 cm, presión 90/60 mmHg y temperatura 36.6 °C. El sistema calculó IMC 15, P/E Z -0.187, T/E Z 0.034 y P/T Z -0.288. Los tres indicadores se mostraron como Normal. Se comprobó su conservación en el historial y en el detalle de atención al navegar y recargar.

## Dificultades y alcance

1. Desde la ficha recién creada, Admisión estaba deshabilitada hasta regresar a Base de datos y seleccionar al paciente mediante la búsqueda por DNI. Esto dificulta el recorrido de un usuario nuevo.
2. La admisión permite elegir a otro profesional y guardar la atención. La incompatibilidad con la cuenta se informa recién al emitir el FUA: «Solo puede emitir documentos de sus propias atenciones». La pantalla no indicaba qué profesional estaba vinculado a medico.demo. Para continuar se realizó una consulta de solo lectura a la base local y se repitió la atención desde la interfaz con la profesional correcta.
3. Cambiar el grupo etario exige guardar primero los datos del paciente y después la atención. La interfaz informó el orden necesario.
4. Imprimir S.I.S. recuperó los datos guardados y mostró el prellenado sobre la plantilla FUA. Indicó pendientes de colegiatura y etnia; permitió continuar tras revisar los faltantes.
5. Ver FUA / guardar PDF no mostró el diálogo de impresión en el navegador integrado; un intento quedó cargando y se recuperó recargando. No se obtuvo un archivo PDF ni se verificó impresión física. No se confirmó una calibración física que no se había realizado.
6. El detalle presenta Sin prestaciones y Sin diagnósticos. En el recorrido de admisión no se encontraron controles para completarlos. La propia pantalla de impresión explica que diagnósticos, prestaciones, firmas y vacunas quedan fuera del prellenado. Por ello, la emisión local exitosa no prueba que una atención clínica o un FUA oficial estén completos.
7. Otra consulta y FUA adicional aparecen deshabilitados como aún no disponibles.

Resultado: registro del menor, responsable materna, guardado de atención, cálculo nutricional, persistencia y emisión local de FUA comprobados. Exportación PDF, impresión física y circuito clínico completo pendientes de validación.

Evidencias: fua-emitido.png y fua-bloqueo-profesional.png, en esta misma carpeta.
