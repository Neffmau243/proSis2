# Revisión de colegiaturas de profesionales — 21 de octubre de 2026

## Alcance y verificación

Se contrastaron las nueve tablas de profesionales del snapshot ACE, el catálogo SQL generado por el ETL y la migración 20260926_0021_real_professionals. Las huellas SHA-256 de ambas copias de Data_base.mdb coinciden con el manifiesto del snapshot; también se verificó el hash de cada tabla de profesionales utilizada. Esta comprobación valida la correspondencia de los archivos, no la exactitud profesional de los datos históricos.

No se pudo inspeccionar la sesión ADMIN ni consultar la base activa: localhost:8000 y MySQL en localhost:3306 no están disponibles desde este entorno. No se modificó código, base de datos, cuentas ni asignaciones.

## Caso solicitado: Ana Brigitte Herrera Espinoza

En Profesionales (Codigo 31), la colegiatura es "-". No se encontró una colegiatura alternativa para su DNI o su nombre en las tablas Prof_*. El ETL conserva "-" en cat_profesional (id 19), y el generador de la migración lo transforma en None, que se persiste como NULL. La pantalla muestra "Sin colegiatura" cuando el campo está vacío. Esto significa que no hay una colegiatura registrada en estos datos; no demuestra que la persona carezca de colegiación.

## Hallazgo en la deduplicación

etlSis/etl_mysql.py procesa primero Profesionales y después Prof_*. Si ya vio el DNI, ejecuta continue y omite toda la ficha posterior, sin completar campos vacíos de la primera ficha. Hay ocho colegiaturas numéricas, sin valores alternativos contradictorios por el mismo DNI en las fuentes revisadas, que se perdieron de este modo.

| Profesional | Tabla con el dato | Colegiatura del origen |
|---|---|---|
| YURI JULIA DELGADO USNAYO | Prof_Enfermera | 14657 |
| EDITH SULMA QUISPE MACHACA | Prof_Enfermera | 21053 |
| MIRYAM TORRES QUEQUEZANA | Prof_Nutricion | 2412 |
| CLEMENCIA SILVIA MURGUIA VIZCARDO | Prof_Psicologo | 8519 |
| MARIZOL QUISPE SULLO | Prof_Obstetriz | 17828 |
| JUDITH BERTHA COYA QUIZA | Prof_Medico | 38136 |
| LUIS ENRIQUE DEL CARPIO BELLIDO POSTIGO | Prof_Medico | 21733 |
| MARLENI JULIA GALLEGOS ARTEAGA | Prof_Obstetriz | 2171 |

## Conteos

- 62 profesionales en el catálogo SQL y la migración.
- 36 con colegiatura numérica y 26 con NULL en la migración.
- 8 de esos 26 tienen un dato recuperable mediante coincidencia exacta de DNI.
- Los otros 18, incluida Ana, no tienen colegiatura numérica recuperable por DNI ni por las mismas palabras del nombre en las nueve tablas de profesionales revisadas.
- Con una corrección de esos ocho casos quedarían 44 con dato y 18 sin dato; estos son conteos de los archivos de importación, no de la base en ejecución.

## Corrección propuesta

Completar la colegiatura ausente de una ficha usando el dato numérico de otra ficha con el mismo DNI, registrar su procedencia y reportar cualquier conflicto; no sobrescribir valores existentes automáticamente. Mantener los códigos e identidades ya asignados. Para una instalación que ya aplicó la migración 0021, preparar una migración nueva que actualice únicamente colegiaturas vacías o marcadores y compruebe la identidad; editar la migración antigua no actualizará las instalaciones existentes.

En la interfaz, "Colegiatura no registrada" describiría con mayor precisión un valor vacío. Para Ana se necesita una fuente adicional antes de completar ese campo.
