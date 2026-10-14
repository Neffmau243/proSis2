# Revisión territorial, consultorios, paciente, historial y FUA

Fecha: 13/10/2026. Fuente: catálogos del snapshot local `etlSis/private/ace-source`.

**Corrección del 14/10/2026:** esta revisión llamó incorrectamente código SIS al `Codigo`
interno de las tablas Z_*. La separación entre `Codigo` y `Clave` y la revisión del formulario
están documentadas en [REGISTRO_TERRITORIAL_ETLSIS_20261014.md](REGISTRO_TERRITORIAL_ETLSIS_20261014.md).
La corrección de 38 valores era de códigos internos del catálogo; no acreditaba claves SIS.

## Resultado

Se mantiene el flujo clínico de tres campos: **Consultorio → Servicio / especialidad → Profesional**.
La residencia se identifica por **distrito UBIGEO → localidad SIS**. El establecimiento de registro
y el establecimiento de atención son referencias distintas: no se obliga al paciente a residir
en el distrito de la IPRESS que lo atiende.

La relación física es **establecimiento → consultorio padre → consultorio hijo**; el área y los
servicios se resuelven internamente. El establecimiento tiene su propio UBIGEO, independiente
del UBIGEO de residencia del paciente.

## Hallazgos y correcciones

1. La migración original numeraba las localidades según la posición del nombre. En `Z_01`
   (Alto Selva Alegre), el código original salta de 0050 a 0052: esto desplazó 38 códigos.
   La revisión `20261013_0034_locality_codes` corrige los códigos por localidad reconocida,
   conservando IDs, nombres y vínculos de pacientes. Rechaza conflictos con datos personalizados.
   No actualiza pacientes ni JSON históricos. Respaldo: `tmp/localidades_before_0034.json`.
2. El backend validaba distrito/localidad, pero permitía un texto distinto al nombre del catálogo.
   Ahora al crear o editar se guarda el nombre que corresponde al ID de localidad seleccionado.
   Una localidad de otro distrito se rechaza. Al quitar el ID sin enviar texto alternativo,
   también se elimina el nombre anterior. Se conserva compatibilidad con localidades históricas
   de texto libre cuando no hay ID de catálogo.
3. Las cargas de localidades podían terminar fuera de orden. Un composable compartido limpia
   las opciones inmediatamente, descarta respuestas antiguas y recorre todas las páginas.
   Descartar cambios o cambiar de paciente restaura su pareja distrito/localidad guardada.
4. Los cambios de claves del paciente invalidan las relaciones ORM correspondientes, para que
   la respuesta y la auditoría reflejen el distrito, localidad, inscripción y seguro actualizados.
5. Las nuevas atenciones guardan en `contexto_clinico` el distrito, localidad (ID/código/nombre),
   dirección, sede de registro, sede de atención y su ubicación, consultorio (ID/código/nombre/
   ruta/padre/ancestros), área, servicio y profesional. Esos datos se copian también al
   `contexto_territorial` de `fua_impresion`, dentro del JSON persistido de la atención.
6. Las nuevas respuestas e interfaces de historial usan el nombre y ruta conservados del
   consultorio, junto con la sede y el servicio. El detalle de atención muestra la residencia
   y la inscripción conservadas. El diálogo FUA permite revisar el contexto territorial guardado.
   La plantilla oficial de impresión conserva sus recuadros existentes.
7. La emisión del número FUA usa el RENIPRESS guardado en la copia de la atención; un cambio
   posterior del catálogo no cambia la IPRESS que identifica ese documento. Las atenciones
   anteriores sin copia FUA mantienen su comportamiento de consulta del catálogo.
8. La emisión FUA fallaba en Windows por ausencia de la base de zonas horarias. Se agregó
   `tzdata` como dependencia de Windows y se instaló en el entorno local del proyecto.

## Comprobación de los datos locales

La comparación final encuentra **475 localidades**, sin códigos faltantes o adicionales ni
desacuerdos de nombres normalizados y distrito frente al ETL. La normalización tolera espacios,
mayúsculas y comillas tipográficas; se mantienen los nombres legibles del catálogo existente.

La lectura agregada encontró 16 pacientes sin cruces distrito/localidad ni discrepancias entre
nombre e ID de localidad; 14 atenciones sin cruces consultorio/establecimiento. Las 14 tienen
copia FUA; solo 4 tienen el contexto clínico anterior, que aún no incluía toda la nueva jerarquía.
No se consultaron ni publicaron identidades en esta auditoría agregada.

**Pendiente resuelto:** el ETL no aportaba el distrito de las seis sedes. Se verificaron sus
códigos RENIPRESS en el [directorio de GERESA Arequipa, página 1](https://pagina.saludarequipa.gob.pe/wp-content/uploads/2024/10/Horario_Atencion_GERESA.pdf),
y el UBIGEO en el [documento MINSA/PCRIS, páginas 41, 43, 44, 91, 122 y 149](https://repositorio.pcris.gob.pe/Archivos/DocumentoExpedienteMPV82401082023170156.pdf).
Los seis corresponden a Alto Selva Alegre, provincia y departamento Arequipa, **040102**.

| RENIPRESS | Sede del catálogo local | UBIGEO |
| --- | --- | --- |
| 00001291 | C.S. Alto Selva Alegre | 040102 |
| 00001300 | P.S. Apurímac | 040102 |
| 00001302 | C.S. Independencia | 040102 |
| 00001301 | P.S. Leones del Misti | 040102 |
| 00001303 | P.S. San Juan Bautista | 040102 |
| 00001304 | P.S. Héroes del Cenepa | 040102 |

La revisión `20261013_0035_site_district` completa únicamente ubicaciones faltantes y verifica
la identidad del distrito. Acepta el mismo RENIPRESS con diferentes ceros iniciales, conserva
los códigos y nombres del ETL y respeta cualquier sede ya configurada. No usa IDs internos ni
la residencia del paciente para identificar la IPRESS. El vínculo de localidad de residencia
continúa siendo propio del paciente; no se introduce un selector clínico adicional.

La migración se aplicó a las seis sedes locales con respaldo en
`tmp/establecimientos_before_0035.json`. Las huellas comparadas antes/después confirman que
los vínculos territoriales del paciente y los contextos históricos/FUA permanecen iguales.
Evidencia de catálogo y fuentes: `docs/audits/establishment_district_20261013.json`.
El catálogo de `localhost:8000` se comprobó con `medico.demo`: las seis sedes exponen el
UBIGEO y distrito correctos. El servidor estaba detenido al iniciar esta comprobación y se
levantó en segundo plano para dejar la aplicación disponible.

Las atenciones anteriores no se rellenaron con datos actuales: no sería evidencia de dónde
residía el paciente o cómo se llamaba el consultorio cuando fueron atendidas. Los registros
antiguos sin ruta histórica pueden seguir mostrando el nombre del catálogo como referencia.
La conservación completa de la nueva jerarquía aplica a las atenciones creadas con esta versión.

## Validación

- Backend: **412 pruebas unitarias aprobadas** después de la revisión 0035.
- MySQL: **45 pruebas aprobadas** en una base nueva y desechable, incluyendo paciente,
  consultorios, catálogos, atención, historial y emisión FUA con rol profesional.
- Frontend: suite general de **307 pruebas aprobadas y 1 omitida**, más las verificaciones
  posteriores de localidades y editor (15) y detalle/registro/FUA (31), todas aprobadas.
- Compilación de producción y tipos aprobados. Lint de los cambios aprobado; Ruff conserva
  sin cambios los enums anteriores mediante la exclusión de su advertencia existente UP042.
- Prueba real de interfaz con `medico.demo` en una copia temporal `127.0.0.1:8001`, paciente
  ficticio y consultorio hijo. Se comprobó el FUA guardado y su residencia/consultorio/servicio.
  Evidencia: `docs/audits/territorio-fua-medico-qa.jpg`.
- La prueba de persistencia cambia posteriormente la residencia, el nombre del padre/hijo y
  el nombre/RENIPRESS de la sede: el historial y la copia FUA original permanecen iguales;
  la emisión FUA conserva el RENIPRESS original.

Los avisos de dependencias de TestClient/configuración pytest y de tamaño de los paquetes del
frontend ya existentes no impidieron las pruebas ni la compilación.
