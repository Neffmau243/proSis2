# Riesgos, valoración nutricional y orden de etnias

Fecha: 17 de octubre de 2026, America/Lima.

Se probó la interfaz local en `http://127.0.0.1:8000` con la cuenta de demostración existente. Las altas y cambios se realizaron desde los formularios, exclusivamente sobre dos pacientes nuevos identificados como Prueba / Nutricional / Ficticio. No se emitieron documentos FUA. Las verificaciones de persistencia consistieron en navegar, recargar y leer nuevamente el historial desde la aplicación; una consulta directa a MySQL no estuvo disponible por restricciones de acceso a sockets del entorno.

## Casos creados y resultados observados

| Paciente | Nacimiento / edad a la atención | Mediciones ficticias | Resultado guardado |
| --- | --- | --- | --- |
| #20, PRUEBA-RIESGO-NINO-171026 | 2023-10-17 / 3 años | 10.5 kg, 93 cm | IMC 12.140; P/E -2.603, Bajo peso; T/E -0.833, Normal; P/T -3.336, Emaciación severa |
| #21, PRUEBA-RIESGO-ADULTO-171026 | 1991-10-17 / 35 años | 50 kg, 175 cm | IMC 16.327, Bajo peso; P/E, T/E y P/T: No aplica |

Las dos atenciones se guardaron en modalidad ambulatoria, Medicina / Medicina general. Después de recargar, cada historial conservó las mediciones y la valoración. Los campos de captura de una nueva atención vuelven a estar vacíos: el resultado anterior se consulta en el historial. En ambos casos el grupo de riesgo permaneció inicialmente en «Sin registrar» aun con resultados antropométricos alterados.

## Prueba del grupo de riesgo manual

En el paciente #20 se agregó un periodo de la opción existente «Riesgo de desnutrición aguda», iniciado el 16/10/2026, con una observación explícita de prueba funcional ficticia. La etiqueta se eligió únicamente para verificar el mecanismo de alta y cierre; no se presentó como equivalencia clínica de la emaciación severa calculada.

Al guardar sin fecha de fin, el nombre apareció en el resumen de riesgos vigentes. Luego se editó la fecha de fin a 16/10/2026. El resumen del día 17 volvió a «Sin registrar», y el desplegable conservó el periodo histórico del 16 al 16. El grupo y el inicio estaban bloqueados durante la edición. Los resultados nutricionales guardados permanecieron en el historial.

«Sin registrar» en ese resumen significa que no hay un periodo vigente registrado; por sí solo no acredita normalidad nutricional.

## Interpretación y manejo recomendado

La valoración nutricional y el seguimiento por grupos de riesgo son registros distintos. La aplicación calcula automáticamente indicadores y clasificaciones por atención, utilizando edad, sexo, fecha y mediciones. Actualmente el profesional registra y cierra los periodos de riesgo manualmente. No existe una conexión que asigne un grupo al guardar un resultado nutricional alterado.

Conviene mantener el cálculo automático y la confirmación profesional del seguimiento. Una mejora posterior podría sugerir un grupo adecuado a partir de la valoración, mostrando el motivo y dejando al profesional confirmar el inicio. Una nueva medición normal no debería cerrar por sí sola un seguimiento sin reglas clínicas acordadas. Esta revisión no implementa sugerencias ni asignación automática.

El catálogo observado en la interfaz contiene solo cuatro etiquetas heredadas: riesgo a delgadez, desnutrición aguda, desnutrición global y talla baja. No es un catálogo completo de condiciones o riesgos para todas las edades. Antes de automatizar asociaciones necesita definiciones clínicas, alcance por edad, separación entre riesgo y condición ya presente, reglas de alta/cierre y vínculo con la atención que origina la decisión. No se debe reutilizar una etiqueta infantil como diagnóstico de un adulto.

La aplicación ya calcula IMC en adultos y usa una referencia distinta para adultos mayores. Para escolares y adolescentes utiliza OMS 2007: T/E e IMC/edad y, dentro de su rango, P/E. Por tanto, no todos los indicadores relacionados con edad se limitan a menores de cinco años.

Fuentes de contraste:

- [OMS: referencias de 5 a 19 años](https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/): T/E e IMC/edad de 5 a 19 años, P/E de 5 a 10.
- [MINSA: RM 184-2012, valoración nutricional de la persona adulta](https://www.gob.pe/institucion/minsa/normas-legales/242399-184-2012-minsa).
- [OMS: malnutrición](https://www.who.int/en/news-room/fact-sheets/detail/malnutrition): el bajo peso también afecta a adultos; los hallazgos antropométricos requieren interpretación clínica.

## Orden de las etnias: causa y corrección

La API devuelve el catálogo por nombre (`CatalogRepository.list_ethnicities`), mientras que el selector muestra primero el código. Por eso se veía «1 · Achuar, 56 · Afroperuano, 2 · Aimara…».

Se ajustó `frontend/src/services/catalogos.ts` para entregar las etnias al frontend en orden numérico por código, conservando nombre y código oficial. La lista se copia antes de ordenar; no se modifica el arreglo recibido. El ajuste se comparte entre los consumidores de `catalogos.etnias()`.

En la interfaz ya compilada se verificó la secuencia 1, 2, 3…9, 10, 11…; se buscó «Quechuas», se seleccionó «40 · Quechuas» y se completó el registro del adulto de prueba. No se alteró el catálogo oficial ni se renumeraron sus opciones.

## Validación y evidencias

- 13 pruebas de servicios frontend aprobadas, incluida la regresión del orden numérico 9/10 y la conservación de los códigos.
- 46 pruebas Python de nutrición, catálogo de riesgos y servicio de pacientes aprobadas.
- `npm run build` aprobado, incluida la comprobación de tipos; aviso existente por tamaño de algunos paquetes.
- ESLint de los dos archivos frontend modificados sin errores. El formateador detectó formato previo en otras secciones del archivo de pruebas; se conservaron esas secciones para evitar cambios ajenos.
- Detector de Impeccable sobre el servicio modificado sin hallazgos; revisión visual del selector corregido.

Evidencias locales en `tmp/riesgos-nutricion-20261017/`:

- `nino-atencion-guardada.png` y `.txt`: resultado infantil guardado y riesgo sin asignación automática.
- `nino-riesgo-manual.png`: el periodo manual aparece como vigente.
- `nino-riesgo-cerrado.txt`: el periodo cerrado permanece en el desplegable histórico.
- `adulto-atencion-guardada.png` y `.txt`: IMC bajo con indicadores infantiles no aplicables.
- `adulto-tras-recarga.txt`: historial adulto recuperado después de recargar.
- `etnias-ordenadas.png`: selector con códigos en orden numérico.

Los dos pacientes y sus atenciones ficticias permanecen disponibles para revisión. El periodo funcional del niño quedó cerrado. Se preservaron los cambios que ya existían en `PacienteDetalleView.vue` antes de iniciar este trabajo.
