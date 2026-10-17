# Revisión de guardado en admisión — 17 de octubre de 2026

Se revisó `/admision?patientId=1`, los contratos del cliente y la API, las escrituras
en MySQL y la proyección usada para imprimir. Las escrituras de prueba se realizaron
exclusivamente con registros ficticios en una base nueva y desechable; la consulta al
catálogo de la base de uso fue de solo lectura.

## Por qué DIRESA no cambia al elegir otro establecimiento

Los seis establecimientos activos tienen `disa_codigo = 040`:

| Establecimiento | RENAES | DIRESA / DISA |
| --- | --- | --- |
| C.S. Alto Selva Alegre | 1291 | 040 |
| P.S. Apurímac | 1300 | 040 |
| CS. Independencia | 1302 | 040 |
| P.S. Leones del Misti | 1301 | 040 |
| P.S. San Juan Bautista | 1303 | 040 |
| P.S. Héroes del Cenepa | 1304 | 040 |

DIRESA identifica la región de la afiliación; RENAES identifica el establecimiento.
El campo SIS no debe recibir el RENAES ni el ID interno. La prueba de sugerencias
comprueba tanto el cambio entre DISA diferentes como la conservación de `040`
entre dos sedes que comparten DISA.

Una DIRESA de afiliación distinta ya guardada o una corrección manual se conserva.
La dirección, el distrito y la localidad no recalculan la afiliación SIS.

## Cuándo se guarda

1. Editar los datos de la ficha y el seguro cambia un borrador. **Guardar cambios**
   realiza el PATCH del paciente. **Descartar cambios** restaura la ficha confirmada.
2. Cambiar entre planes SIS puede sugerir otro formato. El número de afiliación
   propio de un plan no se inventa; los valores se validan antes del guardado.
   Pasar a un seguro ajeno a SIS limpia los campos SIS al guardar la ficha.
3. Madre y grupo de riesgo se confirman con **Guardar** en su respectivo diálogo.
   Esos registros se guardan por separado de los demás campos de la ficha.
4. **Guardar atención** registra consultorio, servicio/especialidad, profesional,
   modalidad y mediciones. Está bloqueado mientras la ficha tiene cambios pendientes
   o hay operaciones de edición en curso.
5. La atención conserva sus copias de identidad, contexto territorial y FUA. Un
   cambio posterior del seguro del paciente se usa para las próximas atenciones;
   no reescribe el FUA ya guardado.

El establecimiento de registro de la ficha y la sede del consultorio de la atención
son conceptos diferentes. Si ya se eligió consultorio, guardar otra sede en la ficha
no traslada silenciosamente ese consultorio.

## Datos revisados y salida en papel

«FUA» en la tabla describe la plantilla V.02 que implementa actualmente el proyecto.
No todos los datos de la ficha tienen un recuadro propio en ese formulario.

| Datos de la vista | Persistencia | Impresión actual en FUA |
| --- | --- | --- |
| N.° H. clínica | Ficha y copia en atención | Sí |
| Historia familiar | Ficha y contexto de atención | No tiene un campo independiente en la plantilla |
| Tipo y número de documento | Ficha y copia FUA | Sí; TDI se deriva del documento compatible |
| Fecha de nacimiento | Ficha y copia FUA | Sí |
| Apellido paterno, apellido materno, primer nombre, otros nombres | Ficha y copia FUA | Sí |
| Sexo | Ficha y copia FUA | Sí |
| Distrito, localidad y dirección | Ficha y contexto territorial de la atención | Conservados para consulta; no se sobreimprimen como campos adicionales |
| Establecimiento | Ficha como sede de registro; atención como sede del consultorio | Nombre de IPRESS de la atención; RENIPRESS según configuración de hoja preimpresa |
| Seguro | Ficha y código del plan en el contexto de atención | Se imprime la afiliación SIS correspondiente; el nombre del plan no se imprime en un campo adicional |
| DIRESA, tipo y número SIS | Ficha y copia FUA | Sí; se conserva también la secuencia/RN existente |
| Teléfono | Ficha | Sin campo propio en esta plantilla |
| Grupo de riesgo | Relación de riesgos con fechas de vigencia | No se convierte automáticamente al casillero específico «grupo de riesgo HVB» del FUA |
| Nombre de madre | Responsable con parentesco MADRE | Sin campo propio «Nombre de madre»; no se infiere el representante firmante |
| Grupo etáreo del selector | `condicion` en ficha | No se imprime como texto adicional |
| Modalidad de atención | Atención y copia FUA | Sí, marcas de ambulatoria/emergencia |
| Consultorio | Atención y contexto territorial | Falta homologación e impresión del código oficial UPS |
| Servicio / especialidad | Atención y contexto territorial | No equivale automáticamente al código de prestación SIS; el prellenado actual no imprime ese código |
| Profesional | Atención y copia FUA | Nombre, documento y colegiatura; la firma no se genera |
| Grupo de atención | Atención y copia FUA | Marcas de gestante/puérpera cuando corresponda |
| Peso y talla | Atención y copia FUA | Sí |
| Perímetro abdominal | Atención y copia FUA | Sí para el grupo general; el recuadro correspondiente cambia en atención materna |
| Presión diastólica y sistólica | Atención y copia FUA | Sí, como presión arterial |
| Temperatura | Atención | No tiene un recuadro propio en la plantilla implementada |
| Edad a la atención | Calculada por el servidor y conservada en contexto | Sin texto adicional de edad en esta plantilla |
| Valoración nutricional, IMC, P/E, T/E y P/T | Recalculados por el servidor y conservados en atención/copia FUA | IMC en papel; los demás resultados se consultan en el panel nutricional, sin agregar casilleros |

El selector llamado «Grupo etáreo» edita la condición de la ficha. Al guardar una
atención, el servidor vuelve a determinar esa condición según edad y grupo de
atención; puede sustituir el valor previo. La edad de la atención se calcula por
separado. Para un adulto, P/E, T/E y P/T nulos significan «no aplica»; el IMC sí se
calcula con peso y talla válidos.

## Alcance del FUA

La impresión existente es un **prellenado parcial**. La plantilla no imprime aún
UPS, código de prestación ni la sección de diagnósticos CIE-10. «Servicio /
especialidad» del formulario no es una prestación SIS ni un diagnóstico.

La copia local del instructivo FUA V.02, apartado 1.4 b–c (página 26), establece un
código UPS y un código de prestación; el apartado 1.7 trata los diagnósticos. Antes
de ampliar el llenado automático se necesita una correspondencia explícita entre
los catálogos del sistema y esos códigos oficiales. No es correcto usar un ID interno
como sustituto. Las firmas y los demás datos clínicos que el módulo no captura deben
completarse según la prestación realizada.

Referencia: [RJ 000178-2024-SIS/J y anexos](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j).
Se contrastó el texto local `tmp/pdfs/sis-fua-v02.txt` con la plantilla del proyecto;
la página oficial respondió 418 al intentar abrirla y su publicación se corroboró
en los resultados del sitio oficial. Esta revisión describe la implementación V.02,
sin certificar la vigencia de todas las reglas operativas del SIS en 2026.

## Verificación

- 94 pruebas frontend aprobadas de admisión, ficha, responsables, sugerencias y FUA;
  una prueba opcional de matriz omitida porque necesita un informe externo.
- 11 pruebas de sugerencias SIS aprobadas tras agregar la regresión de dos sedes
  que comparten `040` (incluyen 10 de las 94 anteriores).
- 30 pruebas HTTP/MySQL aprobadas de pacientes, atención y documentos. Incluyen la
  nueva prueba integral que modifica todos los campos de ficha enumerados, guarda
  madre y riesgo, vuelve a leerlos, registra mediciones, comprueba el FUA, cambia
  Gratuito → NRUS → EsSalud y verifica que el FUA previo no se altere.
- La base temporal se eliminó al terminar. No se guardaron cambios en pacientes ni
  atenciones de la base usada por `localhost:8000`.
- 107 pruebas unitarias de backend pasaron sus aserciones. La primera ejecución de
  ese subconjunto terminó con error por el umbral global de cobertura del 90 %,
  que incluye módulos ajenos a la selección; no hubo fallos de aserciones.

No se cambió el comportamiento del producto: el catálogo explica el `040` constante
y las pruebas de persistencia no mostraron pérdida de los datos revisados. Se agregaron
regresiones y este informe para documentar el guardado y las limitaciones de impresión.
