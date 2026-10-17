# Importación completa de usuarios, pacientes e historia clínica

Revisión: 17 de octubre de 2026. Proyecto `proySis`.

## Decisión recomendada

Mantener las 36 revisiones Alembic y desarrollar un importador operativo por fases si el origen es Access. No añadir el padrón completo dentro de una «supermigración».

Si lo que se quiere es trasladar **la base MySQL actual a otro servidor**, la operación es distinta: respaldo consistente y restauración de esa base, preservando IDs, relaciones, hashes de contraseña y `alembic_version`; después se aplican únicamente las revisiones pendientes. No se vuelve a importar Access para trasladar una instalación ya existente. Restaurar sobre un destino con datos propios exige otra estrategia de conciliación; no se debe sobrescribir ese destino como si estuviera vacío.

Un único comando de instalación puede orquestar estructura, importación y validación. Eso no exige reunir toda la lógica y todos los datos en un único archivo de migración.

## Alcance y evidencia

Se revisaron las 36 revisiones y sus operaciones, modelos, scripts de inicialización y semillas, autorización de pacientes, ETL local y pruebas de migración. Se consultó MySQL mediante una transacción explícita `READ ONLY`; se ejecutó `alembic check`, que compara metadatos sin aplicar revisiones. No se ejecutaron `upgrade`, `downgrade`, reinicios ni importaciones.

Se validaron las huellas del snapshot ACE y sus archivos mediante `etlSis/snapshot.py`. La huella del `Data_base.mdb` de la raíz coincide con la del snapshot. Se recalculó el plan completo con `etlSis/planner.py`, versión 2.0.0 y fecha de referencia 2026-10-17. No se publican nombres, documentos ni claves personales en este informe.

Las recomendaciones sobre separar importaciones grandes del historial de esquema coinciden con [Alembic: Data Migrations](https://alembic.sqlalchemy.org/en/latest/cookbook.html#data-migrations-general-techniques). La precaución con interrupciones de DDL se apoya en [MySQL 8: implicit commits](https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html).

## Estado comprobado de la instalación actual

| Comprobación | Resultado |
| --- | --- |
| Revisiones del repositorio | 36, cadena lineal, un único head |
| Head del código | `20261014_0036_locality_keys` |
| Versión de MySQL configurada | `20261014_0036_locality_keys` |
| Tablas ORM | 45 |
| Tablas en MySQL | 46, incluida `alembic_version` |
| Tablas o columnas ORM ausentes | Ninguna |
| `alembic check` | `No new upgrade operations detected.` |
| Usuarios | 11, todos activos; uno sin profesional vinculado |
| Profesionales | 72 |
| Pacientes | 16 |
| Atenciones operativas | 19 |
| `importaciones_legado` | 0 |
| `registros_legado` | 0 |
| `atenciones_legado` | 0 |
| Pacientes con `codclie_legacy` | 0 |
| `paciente_codigos_externos` / `paciente_anexos_legacy` | 0 / 0 |
| Responsables | 1 fila; este conteo no prueba cumplimiento por paciente |
| Localidades | 475 |
| `cie10` / `prestaciones` | 0 / 0 |
| Asignaciones de consultorio | 372, correspondientes a 62 profesionales y 42 consultorios |
| Usuarios activos vinculados a profesional sin asignación por fechas | 9 |

Estos datos muestran que el padrón completo de Access no está importado mediante el mecanismo de archivo legado. No permiten afirmar que ningún dato individual del origen haya sido copiado por otras vías: hay ejemplos reales sembrados desde Python.

El esquema actualizado no demuestra integridad de una futura importación. `alembic check` tampoco valida identidades, equivalencia clínica ni completitud del origen.

## Revisión de todas las migraciones

Los números siguientes identifican los archivos en `migrations/versions/`; la revisión completa y su encadenamiento se comprobaron con `ScriptDirectory`.

| Revisión | Qué hace | Implicación para importar |
| --- | --- | --- |
| 0001 | Crea el esquema inicial, relaciones y catálogos mínimos. | Crea tablas de pacientes y usuarios, pero no carga el padrón. Crea CIE-10 y prestaciones sin poblarlas. |
| 0002 | Crea `documento_series`. | Los correlativos históricos requieren conciliación independiente antes de emitir documentos nuevos. |
| 0003 | Completa rangos etarios inicialmente vacíos. | Configura clasificación; no importa edades ni pacientes. |
| 0004 | Consolida roles en ADMIN y PROFESIONAL, elimina asignaciones REGISTRO/AUDITOR y desactiva usuarios sin roles. | Modifica datos existentes de autorización. No preserva automáticamente los permisos del sistema antiguo. |
| 0005 | Agrega bloqueo de acceso, versión de credenciales y límite persistente. | Importar usuarios exige hashes válidos y estado coherente; no trasladar sesiones antiguas como si fueran identidades. |
| 0006 | Normaliza FUA BORRADOR a EMITIDO, valida estados y exige que el certificado corresponda al profesional de la atención. | Una historia incompatible puede bloquear el upgrade; no corregir firmantes por suposición. |
| 0007 | Agrega IMC y referencia nutricional a la atención. | No calcula ni carga automáticamente el histórico. |
| 0008 | Permite evaluación nutricional sin `tipo`. | Su downgrade elimina evaluaciones con `tipo IS NULL`; no es una reversión sin pérdida. |
| 0009 | Agrega profesional que registra o traslada al paciente. | Afecta acceso asistencial. No asignar todos los pacientes al usuario que ejecuta el importador. |
| 0010 | Limpia localidad cuando repite el código UBIGEO. | Es una transformación de datos; el texto descartado no se reconstruye en downgrade. |
| 0011 | Agrega grupo de atención con valor general para registros anteriores. | Ese valor no acredita que una atención histórica fuera o no obstétrica. |
| 0012 | Agrega peso previo y tipo de embarazo. | Los valores ausentes deben conservarse como desconocidos. |
| 0013 | Agrega fecha probable de parto. | No equivale a fecha real del parto. |
| 0014 | Agrega snapshot JSON de impresión FUA. | No reconstruye snapshots históricos. |
| 0015 | Agrega campos SIS, catálogo de 59 etnias y configuración de impresión por sede. | No asigna afiliación ni etnia a pacientes. |
| 0016 | Crea `importaciones_legado`, `registros_legado`, `atenciones_legado`. | Es la infraestructura para preservar el origen; no contiene el proceso que lo carga. |
| 0017 | Agrega planes de seguro y Sanidad. | No reasigna pacientes. Seguro desconocido no equivale a SIN_SEGURO. |
| 0018 | Crea localidades, vínculo a pacientes y códigos de seguros; siembra 29 distritos y 475 localidades. | También enlaza pacientes existentes por distrito y nombre normalizado. El código de localidad cambia de significado en 0036. |
| 0019 | Siembra seis establecimientos con RENAES válido. | No promueve placeholders o establecimientos sin identificación fiable. |
| 0020 | Siembra DIRESA, cuatro redes, 47 microredes, 33 especialidades y 42 consultorios. | Redes y consultorios incluyen inferencias del código; no constituyen prueba de organización física histórica. |
| 0021 | Siembra siete profesiones, 62 profesionales, especialidades y asignaciones desde 2024-01-01. | Esos profesionales no son cuentas de acceso. Las asignaciones por área en todas las sedes son inferidas y deben revisarse. |
| 0022 | Normaliza códigos de especialidad a mayúsculas y propaga por FK. | El importador debe usar los códigos vigentes y resolver referencias. |
| 0023 | Agrega cuatro etiquetas de riesgo nutricional. | No asigna riesgos ni acredita diagnósticos históricos. |
| 0024 | Agrega JSON de valoración nutricional calculada. | No recalcula registros anteriores. |
| 0025 | Crea perfiles y cuentas PROFESIONAL para nueve operadores, con hash bcrypt de su documento como clave inicial. | Es una carga parcial y fija en código, no un importador de todos los operadores. Tiene riesgos de permisos, colisión y rollback descritos abajo. |
| 0026 | Agrega componentes de identificación del FUA. | No descompone ni verifica todos los números históricos. |
| 0027 | Agrega DIRESA SIS y asigna `040` a seis sedes. | No acredita afiliación de pacientes. |
| 0028 | Agrega fecha real del parto. | Mantener separada de la fecha probable. |
| 0029 | Agrega sufijo documental, contexto clínico y campos nutricionales/educativos/exportación. | Solo amplía estructura. No importa nuevamente Access ni acredita envíos históricos. |
| 0030 | Agrega JOVEN y divide el rango ADULTO. | Conserva grupos históricos; bloquea rangos personalizados incompatibles en vez de sobrescribirlos. |
| 0031 | Crea y siembra 21 prefijos de historia familiar. | No normaliza las historias familiares existentes; el número local conserva ceros como texto. |
| 0032 | Agrega identificadores de referencia de ingreso a laboratorio. | No importa documentos de referencia antiguos. |
| 0033 | Agrega área y servicios de consultorio, con backfill del área reconocida. | Conserva IDs y no crea salas físicas adicionales. Revisar recuperación si falla entre columna y FK. |
| 0034 | Corrige 38 códigos de localidad desplazados por el salto de Z_01. | Preserva IDs, vínculos y JSON histórico; rechaza conflictos ajenos a la semilla reconocida. |
| 0035 | Completa distrito de seis IPRESS verificadas cuando falta. | No debe confundirse el distrito del establecimiento con residencia del paciente. |
| 0036 | Renombra el código interno a `codigo_catalogo` y agrega `codigo_sis` con claves de origen. | La clave SIS puede faltar o repetirse. No es identificador único ni acredita homologación vigente. |

## Qué se carga actualmente y qué falta

`bootstrap_database` crea la base si falta y llama a `alembic upgrade head`. No lee Access. En una instalación vacía sí ejecuta las semillas incluidas en las revisiones, incluidos personal y las nueve cuentas de 0025.

`seed_demo_data --real-only` recorre una constante de **13 pacientes** en Python; no recorre el archivo Access. Está restringido a desarrollo. Tampoco conserva `codclie_legacy` en esos ejemplos. Que se llame `real-only` no significa «importar todos los datos reales».

`etlSis/etl_mysql.py` es un ETL anterior hacia **otro esquema**, `sishosp_clean`. Su `schema.sql` incluye `DROP DATABASE IF EXISTS sishosp_clean`. Sus tablas y reglas no son el contrato actual de la API: no utilizar sus dumps para poblar directamente `sistema_salud_ipress`.

En `etlSis/` también existe trabajo posterior útil: extracción ACE de solo lectura, verificación de huellas, normalización, planificador sin escrituras y utilidades de sandbox. No encontré en el árbol revisado un comando que persista ese plan completo en las tablas actuales. Ese directorio está ignorado por Git: un despliegue desde el repositorio no lo recibe por defecto. No eliminarlo sin conservar los recursos necesarios para completar la importación.

Las entidades de `app/models/legacy.py` están registradas, pero no encontré una ruta de consulta clínica que exponga `atenciones_legado`. Guardar el histórico y hacerlo visible con permisos en la aplicación son entregables distintos.

## Origen comprobado y calidad de datos

El snapshot verificado contiene **82 tablas y 142.231 filas**. Entre ellas:

| Conjunto | Filas |
| --- | ---: |
| `Pacientes` | 73.209 |
| `Atencion` enumeradas | 59.213 |
| `Pacientes_ref` | 8.561 |
| `Operarios` | 25 |

Hay una discrepancia que debe investigarse: Access reporta 59.215 atenciones en el manifiesto, pero el lector enumera 59.213. No afirmar que se conservó el 100 % de las atenciones hasta explicar esa diferencia; tampoco suponer sin evidencia que existen dos registros recuperables.

El planificador recalculado produce:

| Clasificación preliminar | Filas |
| --- | ---: |
| Pacientes aceptados por sus reglas actuales | 48.199 |
| Pacientes pendientes: 73.209 − 48.199 | 25.010 |
| Filas de `Pacientes_ref` pendientes de identidad | 8.561 |
| Atenciones clasificadas HISTORICO_VINCULADO | 54.601 |
| Atenciones clasificadas HISTORICO_PENDIENTE | 4.612 |

Los **48.199 no son una promesa de importación operativa inmediata**. El planificador es anterior a varios cambios y no aplica todas las reglas actuales de API, responsables de menores, historias familiares, localidad normalizada, conciliación con MySQL existente ni autorización. Su clasificación de vínculo tampoco equivale a validación completa de una atención nueva.

Incidencias relevantes, medidas como filas afectadas por cada regla:

| Regla del planificador | Incidencias |
| --- | ---: |
| DNI inválido o ausente | 21.652 |
| DNI duplicado | 3.325 |
| Mismo nombre/fecha repetidos | 180 |
| Código de cliente inválido o duplicado | 2 |
| Historia de atención no coincide con la del paciente | 1.471 |
| Atención con cliente no resuelto | 102 |
| Sede de registro no resuelta | 6.186 |
| Afiliación SIS incompleta o inconsistente | 47.396 |
| Fecha de inscripción posiblemente predeterminada | 45.857 |

Las incidencias se superponen; no se suman para calcular pacientes únicos. Una fila con inscripción predeterminada puede tener identidad aceptable, por ejemplo.

El dump ETL antiguo reporta otros totales y criterios de rechazo. No mezclar esos resultados con los del snapshot ACE actual. La comparación existente de lectores también muestra diferencias de valores y formatos; contar filas iguales por sí solo no demuestra equivalencia.

## Usuarios: problemas concretos de 0025

1. El origen tiene 25 filas de operadores; la revisión lleva nueve parejas fijas de identidad/clave. Hay que inventariar y conciliar las 25, sin inferir que las restantes sean automáticamente cuentas habilitables o personas distintas.
2. Almacena documentos personales en código y usa esos mismos valores como claves iniciales, aunque en MySQL guarde bcrypt. Para la carga definitiva, conservar identidades y revisar permisos, y usar activación o restablecimiento seguro. El código actual no implementa una obligación de cambio en primer acceso.
3. Convierte operadores en PROFESIONAL. El origen de una cuenta de admisión no demuestra habilitación clínica. Si se requiere un rol administrativo de registro, hay que definirlo explícitamente y adaptar permisos, no fabricar una identidad asistencial.
4. Si existe el nombre de usuario derivado, salta la cuenta sin comprobar que pertenezca a la misma persona. Si ya existe una cuenta del profesional con otro nombre, la restricción única `usuarios.profesional_id` puede impedir la inserción. El futuro importador debe informar ambos conflictos.
5. No asigna consultorios. En la base actual hay nueve usuarios profesionales activos sin asignaciones por fechas. Autenticarse no garantiza poder registrar una atención.
6. Su downgrade identifica cuentas por nombre y elimina cuentas, roles y auditorías asociadas; no es una reversión adecuada para una instalación con actividad. Otras FK, como la de creador de atenciones, también pueden impedir la baja física.

Las 62 filas de profesionales de 0021 proceden del catálogo compuesto del ETL. Su `codigo_legacy` usa el ID de ese catálogo, no necesariamente el `Codigo` de una tabla Access concreta. No emparejar namespaces distintos únicamente porque compartan un número.

## Pacientes e historia: reglas que debe resolver el importador

**Identidad y referencias.** `pacientes` exige tipo/número de documento y nacimiento; son únicos el documento compuesto y `codclie_legacy`. No es posible volcar todas las filas dañadas sin decidir su tratamiento. No inventar DNI, nacimientos ni sufijos para evadir duplicados. Un eventual soporte de pacientes sin documento necesita una decisión de dominio y, si corresponde, una migración pequeña propia.

**IDs.** Usar el autoincremental del destino y una correspondencia persistente entre origen, tabla, clave/fila original y destino. La numeración por posición que propone el planificador no puede usarse como PK en una base con datos. `Pacientes_ref.Codclie` no pertenece automáticamente al mismo espacio de identidades que `Pacientes.Codclie`.

**Datos ya existentes.** Conciliar también contra pacientes inactivos. Los 13 ejemplos reales podrían coincidir por documento con Access aunque no tengan código legacy; no crear una segunda identidad ni actualizar silenciosamente datos clínicos. Distinguir creación, vínculo confirmado, actualización autorizada y conflicto.

**Menores.** El servicio exige responsable activo. Las reglas del planificador no lo comprueban. Cuando el origen no permita acreditar al responsable, conservar el registro y tratarlo como pendiente de regularización según una política explícita.

**Geografía y seguro.** Resolver establecimiento por identificación verificada, distrito por UBIGEO y localidad dentro del distrito. Desde 0036 `codigo_catalogo` y `codigo_sis` representan valores distintos. Afiliación histórica incompleta no se completa con el DNI o con la DIRESA de la sede por suposición.

**Acceso asistencial.** La autorización depende de sede asignada, relación asistencial o profesional de registro. No asignar al administrador de importación como autor clínico ni dar acceso global como atajo. Un vínculo en `atenciones_legado` no participa por sí solo en las consultas actuales de ámbito profesional.

**Atenciones.** La tabla operativa exige paciente, sede, profesional, consultorio, modalidad, grupo etario y fecha. Conservar encuentros incompletos en `atenciones_legado` sin atribuirlos a un profesional genérico. Promover a tablas operativas solo con correspondencias verificadas y reglas históricas explícitas. No ejecutar las 59.213 filas como nuevas atenciones del día ni reemplazar snapshots originales por cálculos actuales.

**Diagnósticos, prestaciones y documentos.** CIE-10 y prestaciones están vacíos en esta instalación. Los campos `Codigo_*` del legado requieren identificar su significado y catálogo; no todos son códigos CIE-10. Conservar referencias, FUA y certificados sin emitir documentos nuevos ni consumir correlativos como efecto de la importación. Antes de reanudar emisión, comprobar unicidad y series.

**Secretos de operadores.** El archivo fuente contiene claves. Preservar el original con acceso restringido; no copiar contraseñas en claro a reportes, logs o al JSON consultable de archivo. La preservación íntegra del origen y la exposición de datos a la aplicación deben tener controles distintos.

## Diseño recomendado de la carga

1. **Inventario y respaldo restaurable.** Definir si se importa Access o se traslada MySQL. Identificar destino, huella, fecha de corte y tablas; comprobar restauración en un destino aislado.
2. **Esquema vigente.** Aplicar las revisiones faltantes en una copia de ensayo. Mantener Alembic para estructura y transformaciones acotadas.
3. **Archivo del origen.** Registrar fuente y versión del importador en `importaciones_legado`; conservar filas, huellas, decisiones e incidencias en `registros_legado`, con tratamiento específico de secretos. Una tabla de archivo puede contener datos pendientes sin convertirlos en pacientes operativos.
4. **Correspondencias.** Resolver catálogos, personal, cuentas y pacientes contra los ya existentes. No usar nombres solos para fusionar personas. Reutilizar `destino_tabla`/`destino_id` donde alcance; añadir una tabla de correspondencias si hacen falta varias relaciones por registro.
5. **Carga por dependencias.** Catálogos → profesionales y asignaciones verificadas → cuentas/roles → pacientes y relaciones → historia clínica y documentos verificables. Archivar lo incompleto y mantener una cola de revisión.
6. **Lotes reanudables.** Confirmar por lote coherente, con checkpoint y trazabilidad. Las relaciones de cada agregado deben persistir juntas. Ante un error, revertir el lote y registrar la incidencia sin perder el avance confirmado.
7. **Conciliación.** Para cada tabla, cuadrar filas de origen con archivadas y su clasificación; para entidades destino, separar nuevas, vinculadas, actualizadas y pendientes. Verificar huérfanos, restricciones, documentos, roles, sedes y diferencias de valores.
8. **Piloto y ensayo completo.** Probar casos limpios, duplicados, sin documento, menores sin responsable, referencias ambiguas, usuarios existentes e interrupciones. Repetir el mismo origen debe crear cero entidades adicionales.
9. **Corte.** Si Access sigue recibiendo datos, congelar escritura para el snapshot final o diseñar una captura explícita de cambios. El SHA del archivo evita repetir exactamente la misma fuente, pero no impide duplicados entre dos versiones distintas del MDB.
10. **Consulta del histórico.** Añadir la lectura autorizada del archivo clínico a la aplicación. Verificar que usuarios habilitados puedan encontrar pacientes e historia sin ampliar indebidamente su ámbito.

Un comando futuro podría ofrecer simulación, piloto, aplicación y reanudación. **Es una propuesta: el repositorio revisado todavía no ofrece un importador completo con esos modos.** Las tablas de 0016 son una base útil, pero no garantizan por sí solas checkpoints, deduplicación entre fuentes y reanudación.

## Riesgos del historial de migraciones

- No todas las revisiones permiten reintento después de DDL parcial. En particular 0024, 0026 y 0029 agregan columnas sin inspección previa; 0036 renombra y agrega columnas sin guardas de estado. 0018 y 0033 pueden dejar una columna creada y una FK pendiente que su guarda no vuelve a intentar. Es un riesgo de recuperación, no evidencia de corrupción actual.
- Un `upgrade head` repetido cuando la base ya está en head no prueba que una revisión interrumpida sea reintentable: Alembic ni siquiera la ejecuta en ese caso.
- MySQL hace commits implícitos para operaciones DDL. `transaction_per_migration=True` en `env.py` no convierte toda la instalación en una transacción reversible.
- Varios downgrades preservan datos de catálogo deliberadamente; otros borran columnas/tablas, evaluaciones o cuentas y auditorías. No usar `downgrade base` para deshacer una importación en una base real.
- No sustituir la cadena con `stamp head`: sellar una versión no ejecuta sus transformaciones ni importa datos.
- README aún menciona head 0010, 39 tablas y una foto de 13 pacientes; el análisis del 26/09 llega a 0022. Son documentos históricos o desactualizados, no evidencia del estado actual.

La recuperación de una importación debe apoyarse en respaldo probado, trazabilidad y correcciones hacia delante. Una reversión por lote solo es viable si se distinguen entidades nuevas de filas vinculadas o modificadas y se comprueba que no recibieron actividad posterior.

## Validación realizada y límites

- Pasaron **48 pruebas unitarias** de contrato de migraciones, SIS de pacientes, seguros, localidades, establecimientos, operadores, riesgos y bootstrap, con `--no-cov`.
- Hubo una advertencia de pytest por la opción desconocida `asyncio_default_fixture_loop_scope`; no impidió esas pruebas.
- `alembic check` no detectó nuevas operaciones de upgrade contra la MySQL configurada.
- Se verificó el snapshot y se recalculó el plan sin escrituras en el origen ni en MySQL.
- No se reconstruyó una base vacía ni se probó el upgrade desde cada revisión antigua. No se ejecutó la integración cuyo fixture hace downgrade/upgrade. Esos ensayos deben hacerse sobre MySQL desechable o una copia aislada, no sobre la instalación actual.
- El análisis de datos usa el planificador existente, con sus límites expresados arriba; no constituye una validación clínica exhaustiva ni una autorización de todas las cuentas.

## Siguiente trabajo concreto

Conservar la cadena actual y convertir los componentes de extracción/planificación en un módulo de importación entregable y probado. Primero cerrar identidad sin documento, correspondencias entre namespaces, responsables, roles y acceso al histórico. Después implementar simulación y conciliación, ejecutar piloto en copia aislada y ensayar la carga completa con reanudación.

Si se necesita ampliar el esquema para correspondencias, estados o soporte documental, hacerlo mediante revisiones nuevas y pequeñas posteriores a 0036. Esas migraciones preparan la capacidad de importar; los datos concretos se cargan desde la fuente controlada mediante el importador.
