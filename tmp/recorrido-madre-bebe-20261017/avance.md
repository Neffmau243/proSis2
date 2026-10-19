# Recorrido visual de madre y recién nacido - 17/10/2026

Se realizaron las operaciones clínicas desde las pantallas del sistema, con datos ficticios y la cuenta medico.demo. No se usaron tests automatizados ni llamadas directas a API/SQL para crear estos registros.

## Registros guardados y comprobados en pantalla

- Madre #18: Prueba Materna Elena Simulada, DNI ficticio 99061701, HC PRUEBA-MADRE-171026, historia familiar AZ-171026.
- Atención #23: Gestantes / Ambulatoria, 01/10/2026 09:00, embarazo único, peso 68 kg, talla 160 cm, peso pregestacional 58 kg, FPP 20/10/2026. FUA local emitido y confirmado: 00001291-26-00000002.
- Atención #24: Gestantes / Emergencia, 15/10/2026 18:00, peso 70 kg, talla 160 cm, peso pregestacional 58 kg, embarazo único y misma FPP. Guardada y comprobada en el historial materno.
- Atención #25: Puérperas / Emergencia, 16/10/2026 18:00, fecha del parto 16/10/2026, peso 65 kg, talla 160 cm, peso pregestacional 58 kg. La ficha de la misma madre cambió a PUERPERA después de guardar. Sus atenciones anteriores siguieron como Gestantes en el historial.
- Recién nacido #19: Ficticio Prueba Nicolas Simulado, nacido 16/10/2026, documento provisional ficticio OTRO RN-FICTICIO-171026, HC PRUEBA-RN-171026, historia familiar AZ-171026.
- En Responsables del bebé se guardó a Prueba Materna Elena Simulada, DNI 99061701, parentesco MADRE, activa y principal. Se comprobó el indicador Sí en Principal tras editarlo. La relación se registró manualmente mediante los datos de responsable y la historia familiar compartida; no se verificó un enlace navegable a la ficha de la madre ni un episodio de parto que agrupe ambos registros.
- Atención del bebé: Ambulatoria / grupo general, 17/10/2026 10:00, peso 3.25 kg, talla 50 cm y temperatura 36.6 °C, sin PA ni PAB. Guardada como ATENDIDO, condición del paciente RECIEN NACIDO, indicadores infantiles Normal y Z P/E -0.139, T/E -0.032, P/T -0.267, IMC 13. El ID de esta atención aún debía confirmarse desde la pestaña Atenciones del bebé. No se debe asumir un ID por la secuencia de creación.
- Afiliación SIS ficticia del bebé: 040 / E / 99061702 / RN 01. El prellenado recuperó 040 · E-99061702-01 y el nombre de la madre apareció en admisión.
- Atención #27: Puérperas / Ambulatoria, 17/10/2026 09:00, fecha del parto 16/10/2026, peso 64 kg, talla 160 cm, peso pregestacional 58 kg, PA 110/70, temperatura 36.5 °C. Guardada, reabierta en detalle y comprobada en historial. La fecha de parto también apareció en el prellenado FUA.

Las cinco atenciones anteriores se realizaron en C.S. ALTO SELVA ALEGRE / MEDICINA / MEDICINA GENERAL con ELSA GUILLEN TOCCAS, profesional vinculado a la cuenta. Son una simulación funcional local, no atención real.

## Pendiente al interrumpirse el servidor

En el último estado observado se había abierto Registrar FUA en la atención #27, con la observación aún sin ingresar. No se había confirmado su emisión. Tampoco se había emitido el FUA del bebé ni confirmado el ID de su atención. Al retomar, comprobar primero el estado para evitar duplicar documentos.

Continuar revisando la persistencia de madre y bebé después del reinicio, emitir los documentos locales de prueba pendientes y revisar la salida imprimible. Las pantallas siguen mostrando Sin diagnósticos / Sin prestaciones y explican que la impresión es un prellenado parcial local. No se logró descargar PDF en los intentos anteriores con el navegador integrado. El documento OTRO del bebé muestra una advertencia: la abreviatura es local y no es un código TDI SIS.

En cada nueva admisión materna el formulario volvió al grupo general aunque la ficha tenía condición GESTANTE o PUERPERA. Hubo que seleccionar explícitamente el grupo correcto y volver a ingresar los datos obstétricos. Es una dificultad de uso a considerar; no se cambió código durante este recorrido.

## Reinicio solicitado por el usuario

Se volvió a iniciar Uvicorn en 127.0.0.1:8000 con reload, usando el Python de .venv. Tras un primer intento con Start-Process, se inició directamente en una sesión persistente de ejecución (sesión 49452, reloader 18716, servidor 15632), cuyo log confirmó Application startup complete. Los archivos server-out.log y server-error.log corresponden al primer intento de arranque, no a la sesión persistente final.

El entorno de control del navegador perdió su sesión anterior y, al intentar recuperar la pestaña conocida, la política de seguridad del navegador rechazó el acceso. No se intentó eludir el bloqueo con otra superficie ni con llamadas de API. Hace falta que el usuario vuelva a abrir la página y permita restablecer el acceso de la herramienta antes de continuar las pruebas visuales.

## Evidencias

En esta carpeta se conservaron capturas y estados de interfaz: madre-condicion-puerpera.png, madre-historial-final.png, bebe-madre-responsable.png, bebe-admision.txt, bebe-fua.txt, gestante-fua-emitido.png, puerpera-ambulatoria-fua.txt y otros archivos de cada paso.
