# Recorrido visual de gestante, puérpera y recién nacido

Fecha: 17/10/2026. Todos los pacientes, documentos y medidas nuevos son ficticios. Operaciones realizadas desde las pantallas con medico.demo; no se usaron tests automatizados ni escrituras SQL o API para crear estas atenciones. No se modificó código de la aplicación. Este resultado final actualiza los pendientes de avance.md.

## Resultado confirmado

La misma paciente #18, Prueba Materna Elena Simulada, DNI ficticio 99061701, pasó de GESTANTE a PUERPERA al guardar una nueva atención del grupo Puérperas con fecha de parto 16/10/2026. Sus controles anteriores siguen conservados como Gestantes. La condición PUERPERA y las atenciones se volvieron a comprobar después del reinicio del servidor.

Se registró al bebé #19, Ficticio Prueba Nicolas Simulado, nacido 16/10/2026. Su ficha muestra RECIEN NACIDO. La pestaña Responsables conserva a Prueba Materna Elena Simulada, DNI 99061701, como MADRE activa y principal (Sí). Madre e hijo comparten historia familiar AZ-171026. El vínculo se ingresó manualmente como responsable; no se comprobó un enlace navegable entre ambas fichas ni un episodio de parto que cree automáticamente al hijo.

## Combinaciones guardadas y documentos locales

| Atención | Paciente y grupo | Modalidad | Fecha de atención | FUA local emitido |
| --- | --- | --- | --- | --- |
| #23 | Madre / Gestantes | Ambulatoria | 01/10/2026 09:00 | 00001291-26-00000002 |
| #24 | Madre / Gestantes | Emergencia | 15/10/2026 18:00 | 00001291-26-00000005 |
| #25 | Misma madre / Puérperas | Emergencia | 16/10/2026 18:00 | 00001291-26-00000006 |
| #27 | Misma madre / Puérperas | Ambulatoria | 17/10/2026 09:00 | 00001291-26-00000003 |
| #26 | Bebé de un día / grupo general | Ambulatoria | 17/10/2026 10:00 | 00001291-26-00000004 |

Cada emisión se confirmó mediante el mensaje Documento emitido / FUA registrado de la interfaz. Los FUA llevan observaciones que identifican la prueba ficticia y su uso local, sin atención real ni facturación SIS. Los correlativos reflejan el orden de emisión de la prueba, no el orden de las fechas simuladas.

Todas las consultas se registraron en C.S. ALTO SELVA ALEGRE, MEDICINA / MEDICINA GENERAL, con ELSA GUILLEN TOCCAS, profesional de la cuenta medico.demo. Se probó el grupo obstétrico dentro de ese consultorio; no se afirma haber recorrido el módulo específico de Obstetricia con una cuenta obstetra.

## Datos comprobados en las pantallas

Gestantes: embarazo único, talla 160 cm, peso pregestacional 58 kg, FPP 20/10/2026, peso actual 68 kg y luego 70 kg. Se mostraron IMC pregestacional 22.656, clasificación Normal y cambios de peso de 10 y 12 kg.

Puérperas: parto 16/10/2026, peso actual 65 y luego 64 kg, peso pregestacional 58 kg, PA 110/70 y temperatura 36.6 y 36.5 °C. La fecha de parto apareció en detalle y en el prellenado del FUA.

Bebé: peso 3.25 kg, talla 50 cm, temperatura 36.6 °C; PA y perímetro abdominal se dejaron sin registrar. La atención conservó esos valores, IMC 13 e indicadores infantiles P/E, T/E y P/T Normal (Z -0.139, -0.032 y -0.267). La admisión recuperó el nombre de su madre y la salida FUA conservó la afiliación ficticia 040 · E-99061702-01, incluida la secuencia RN 01.

## Límites y dificultades observadas

- La transición a puérpera requirió seleccionar ese grupo e ingresar la fecha del parto en una atención posterior. Registrar al bebé no fue un proceso automático de nacimiento ni reemplazó las consultas de gestante.
- Cada nueva admisión materna volvió al grupo general aunque la ficha tuviera condición GESTANTE o PUERPERA; hubo que volver a seleccionar el grupo correcto y escribir los datos obstétricos. Es un punto de confusión para usuarios nuevos.
- Como el bebé no tiene DNI en la simulación, se utilizó OTRO con un identificador ficticio. El FUA advierte que esa abreviatura es local y no es un código TDI SIS. No se verificó un flujo oficial de CNV ni de afiliación real.
- Las atenciones siguen mostrando Sin diagnósticos y Sin prestaciones. La pantalla indica que esos datos, las firmas y otros campos quedan fuera del prellenado. Por tanto, se verificó registro, conservación de datos y emisión local de número FUA, no una atención clínica completa ni un FUA oficial listo para presentar.
- Se volvió a pulsar Ver FUA / guardar PDF en la nueva pestaña, para la atención #25, después de revisar los campos pendientes. No apareció una salida descargable ni un diálogo de impresión accesible y no se obtuvo un PDF. Se conservó una captura del intento y se recargó para salir. La impresión física y su calibración tampoco se verificaron.

## Evidencias

Las capturas de confirmación de emisión están en gestante-fua-emitido.png, gestante-emergencia-fua-emitido.png, puerpera-fua-emitido.png, puerpera-emergencia-fua-emitido.png y bebe-fua-emitido.png. El vínculo persistente puede verse en vinculo-madre-bebe-final.png; la condición materna después del reinicio, en madre-puerpera-tras-reinicio.png. Se conservaron además estados de interfaz en archivos de texto, historial materno y la captura pdf-intento-tras-reinicio.png.

Se dejaron abiertas las fichas de madre y bebé para revisión.
