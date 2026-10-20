# Revisión del backend: mantenibilidad y escalabilidad

Fecha: 19/10/2026. Revisión del estado de trabajo actual, incluidos los cambios locales existentes.

## Diagnóstico

El backend tiene una base razonable de monolito por capas. No es correcto calificar todo el proyecto como código espagueti: los controladores delegan, existen repositorios, contratos Pydantic, mappers y políticas de dominio separadas. Sin embargo, pacientes y atenciones acumulan responsabilidades y dependencias que ya dificultan mantener una única regla de acceso. Hay además consultas cuyo costo no queda limitado por el tamaño de la página solicitada.

La recomendación es refactorizar por partes y conservar la arquitectura actual. Esta revisión no aporta evidencia que justifique migrar a microservicios ni reescribir el backend.

## Alcance y comprobaciones

- Inventario de `app`: 105 archivos Python y 16 581 líneas, incluidos modelos y scripts. Se inspeccionaron especialmente servicios, repositorios, autorización, contratos, transacciones, configuración, despliegue y pruebas. Las cifras de tamaño sirven para localizar concentración de responsabilidades; no demuestran por sí solas mala calidad.
- `python -m pytest tests/unit --no-cov -q`: **465 pruebas aprobadas en 16,57 segundos**. La ejecución inicial dentro del aislamiento se bloqueó en la creación de un socket local de asyncio; se interrumpió y se repitió fuera del aislamiento, donde terminó correctamente.
- `python -m ruff check app tests migrations --select F`: **aprobado**.
- `python -m ruff check app --statistics`: **162 observaciones**: 82 UP037, 45 E501, 19 I001, 8 UP042, 3 UP017, 2 UP035, 2 UP047 y 1 UP046. Son principalmente estilo y modernización; no equivalen a 162 errores funcionales.
- Reproducción aislada de la inconsistencia de roles, utilizando los contratos y resolutores reales con repositorios sustituidos.
- Reproducción de consultas del catálogo con SQLAlchemy y SQLite exclusivamente en memoria: cuatro consultorios hijos con padres distintos, búsqueda por nombre de hijo y `limit=1`.
- No se ejecutó integración MySQL: `TEST_DATABASE_URL` no estaba configurada. No se midieron carga, latencia de producción, planes de ejecución ni capacidad máxima. No se verificó el umbral de cobertura del 90 % en esta ejecución unitaria sin cobertura.
- No se modificó código de aplicación ni los cambios previos del usuario. Este informe es el único archivo añadido por la revisión.

## Hallazgos prioritarios

### 1. La duplicación de autorización ya produce un comportamiento inconsistente

**Estado tras la corrección del 19/10/2026:** se ajustó la búsqueda para aceptar ADMIN + PROFESIONAL cuando existe vínculo profesional activo, conservando el ámbito clínico y el rechazo de ADMIN sin rol profesional. Se añadieron 17 casos de regresión; la suite unitaria completa pasó con **482 pruebas** (`--no-cov`) y el control Ruff de CI también pasó. El cambio corrige esta divergencia concreta; la unificación general de políticas sigue siendo una mejora de arquitectura pendiente. La evidencia siguiente describe el fallo encontrado antes de la corrección.

**Evidencia:** `app/services/discovery.py:43`, `app/services/discovery.py:123`, `app/services/attention.py:569`, `app/schemas/auth.py:15` y `app/domain/authorization.py:106`.

El contrato permite asignar simultáneamente ADMIN y PROFESIONAL. La política suma sus permisos. Sin embargo, `_professional_scope(..., allow_administrator=False)` rechaza cualquier conjunto que contenga ADMIN antes de considerar PROFESIONAL, mientras `_resolve_clinical_scope` acepta a la misma cuenta si tiene vínculo profesional activo.

**Reproducción:** con roles `[ADMIN, PROFESIONAL]`, usuario 1 y profesional activo 7, el permiso `ATENCION_LEER` está presente; la búsqueda obtiene `AuthorizationError: ROL_CLINICO_REQUERIDO`; el resolutor usado por el detalle devuelve `(7, {1})` con sede asignada 1. Es una reproducción de los resolutores, no una prueba HTTP con una cuenta real.

**Impacto:** una cuenta válida puede abrir un detalle y recibir 403 al buscar el historial. Cambiar permisos exige revisar varios lugares y favorece nuevas divergencias.

**Acción:** definir una política compartida para resolver la identidad clínica y la precedencia de roles. Conservar las diferencias legítimas entre leer, registrar, anular y emitir documentos. Añadir regresiones para roles simples, combinados, profesional inactivo y ausencia de vínculo.

### 2. El historial de atenciones tiene una ruta sin límite de resultados

**Estado tras la corrección del 20/10/2026:** la ruta rápida limita la consulta SQL a las últimas cinco atenciones, con orden por fecha e ID descendentes. Admisión identifica la lista como reciente y enlaza a la ficha del paciente, donde el historial completo se obtiene de cinco en cinco mediante la ruta de búsqueda paginada. Se conservan los registros anteriores y los filtros de acceso. La evidencia siguiente describe el comportamiento previo.

**Validación de la corrección:** 485 pruebas unitarias del backend aprobadas; 32 pruebas seleccionadas de interfaz y servicios aprobadas, incluidas navegación hacia las atenciones anteriores y regreso a las recientes; comprobación de tipos Vue/TypeScript, ESLint de los archivos de frontend afectados y Ruff de CI aprobados. No se ejecutó integración con MySQL.

**Evidencia:** `app/controllers/attention.py:102`, `app/services/attention.py:78`, `app/repositories/attention.py:43` y `app/mappers/attention.py:13`.

`GET /atenciones?paciente_id=...` devuelve una lista completa. El repositorio no aplica límite y carga relaciones de prestaciones, diagnósticos, paciente, consultorio y evaluaciones. El mapper devuelve también snapshots clínicos y FUA.

**Impacto:** el tiempo de consulta, memoria, serialización y transferencia crecen con toda la historia del paciente. Tener otra ruta paginada (`/atenciones/busqueda`) no limita esta ruta.

**Acción:** llevar los consumidores al contrato paginado y establecer un límite o una transición explícita para la ruta antigua. Usar un DTO de resumen para listas y cargar el detalle al abrir una atención. Verificar estabilidad del orden usando fecha e ID.

### 3. El catálogo pagina en memoria y puede ejecutar consultas por cada padre

**Evidencia:** `app/repositories/catalog.py:155`, especialmente líneas 181 y 188; `app/domain/office.py:77`; relación `Office.padre` en `app/models/organization.py:287`.

`page_offices` obtiene todos los consultorios que cumplen los filtros, calcula su disponibilidad recorriendo padres y finalmente aplica `items[offset:offset + limit]`. La consulta inicial no contiene LIMIT/OFFSET. Los padres se cargan de forma diferida cuando no estaban ya en la sesión.

**Comprobación:** con cuatro hijos cuyos nombres coinciden con la búsqueda y cuatro padres distintos cuyos nombres no coinciden, `limit=1` devolvió un elemento y total 4, pero ejecutó **6 SELECT**: consulta inicial, carga de establecimientos y cuatro consultas de padres. El experimento demuestra el patrón de acceso; no mide rendimiento MySQL.

**Impacto:** solicitar una página pequeña no reduce proporcionalmente el trabajo. Con más sedes, consultorios o profundidad, aumenta la cantidad de datos recorridos y pueden aparecer consultas N+1.

**Acción:** resolver disponibilidad y jerarquía antes de paginar en SQL, o disponer de una representación consultable de ancestros/disponibilidad. Como mejora intermedia, cargar la jerarquía por lotes. No basta con poner LIMIT antes del filtro Python: eso produciría páginas incompletas y totales incorrectos.

## Deuda de diseño que conviene atender

### 4. Pacientes y atenciones concentran demasiadas responsabilidades

**Evidencia:** `PatientService` ocupa un archivo de 1 165 líneas y tiene 42 métodos; `AttentionService`, un archivo de 780 líneas y 22 métodos. `AttentionService.create`, desde `app/services/attention.py:99`, ocupa 170 líneas.

Pacientes coordina identidad, residencia, seguros, responsables, riesgos, seguimiento, acceso y auditoría. Atenciones combina identidad clínica, permisos, validación, nutrición, snapshots FUA, estado del paciente y persistencia. Son reglas relacionadas, pero tienen distintos motivos para cambiar.

Además, `_risk_origin` (`app/services/patient.py:956`) instancia `AttentionService` para obtener una respuesta completa; `AttentionService` depende de `AgeGroupService`; y `NutritionExportService` hereda de `AttentionService` (`app/services/nutrition_export.py:14`) para reutilizar repositorios y métodos privados. Es acoplamiento entre casos de uso, aunque no demuestra un ciclo de imports.

**Acción:** extraer políticas cohesivas de acceso y validación; separar coordinación de registro clínico de construcción de snapshots; proporcionar una lectura pequeña para el origen de riesgos. Sustituir la herencia de exportación por composición. Mantener una sola transacción para cada operación completa y evitar dividir archivos sin reducir dependencias.

### 5. La ausencia de contexto de autorización significa acceso interno sin restricciones

**Evidencia:** `app/services/patient.py:686`, `app/services/attention.py:582` y firmas de los métodos de lectura.

`actor_roles=None` omite las comprobaciones de ámbito. Está documentado para mantenimiento y pruebas, y los controladores inspeccionados pasan el principal: **no se demostró una ruta HTTP pública que explote este comportamiento**.

**Impacto de mantenimiento:** un futuro consumidor del servicio puede olvidar el contexto y obtener acceso amplio sin error. La seguridad depende de recordar una convención opcional en cada llamada.

**Acción:** exigir un contexto explícito para operaciones de usuario y ofrecer una vía interna deliberada para tareas de mantenimiento. Compartir las consultas de identidad profesional y asignaciones, repetidas en repositorios de pacientes, atenciones, documentos y descubrimiento.

### 6. Algunas respuestas se construyen después de confirmar la escritura

**Evidencia:** `app/services/attention.py:257` y `app/services/document.py:126`, `209`, `270`. En documentos se hace `refresh` después del commit; en creación de atención se consulta y mapea después del commit, dentro del mismo bloque que intenta rollback ante errores.

**Riesgo:** si falla la lectura posterior o la construcción del DTO, la petición informa un error aunque la escritura ya quedó guardada. El rollback posterior no deshace un commit. Un reintento de creación puede registrar otra atención porque no hay una clave de idempotencia del comando en ese flujo. No se provocó una caída real de MySQL durante la revisión.

**Acción:** realizar las lecturas y validaciones del DTO antes del commit cuando sea viable. Definir idempotencia para operaciones de creación susceptibles de reintentos. Mantener las transacciones en el nivel de caso de uso; los servicios actuales ya protegen muchas operaciones con commit/rollback y no se debe perder esa atomicidad al refactorizar.

## Preparación para crecer y mantener entregas reproducibles

### 7. Arrancar varias réplicas puede ejecutar migraciones en paralelo

**Evidencia:** `docker/entrypoint.sh:8` y `docker-compose.yml:48`.

Cada contenedor arranca con `RUN_MIGRATIONS=true` por defecto. Si se crean varias réplicas simultáneamente, todas intentarán `alembic upgrade head`; el script no coordina esa ejecución. Aumentar workers dentro de un único contenedor es distinto: el entrypoint se ejecuta una vez.

**Acción antes de replicar:** ejecutar migraciones como una tarea de despliegue única y arrancar las réplicas con `RUN_MIGRATIONS=false`, opción que el proyecto ya admite. Dimensionar también las conexiones: con los valores actuales, cada proceso tiene un pool de 5 y hasta 10 conexiones adicionales; el máximo potencial de la aplicación es `réplicas × workers × 15`, más otros clientes.

El endpoint `/health` es únicamente de vida del proceso (`app/api/router.py:25`), y Docker usa ese endpoint. No confirma disponibilidad de MySQL. Añadir readiness de dependencias y mediciones de latencia, errores y conexiones permitiría decidir cuándo ampliar capacidad. No hay evidencia suficiente para afirmar cuántos usuarios soporta hoy.

### 8. La puerta de calidad ejecuta menos reglas de las declaradas

**Evidencia:** `pyproject.toml:31` y `.github/workflows/ci.yml:41`.

Se configuran E, F, I, B y UP, pero CI fuerza únicamente F. Por eso pasa el control de nombres/errores estáticos básicos mientras permanecen 162 observaciones en `app`. Esto es deuda de consistencia, no evidencia de que el código falle en ejecución.

Además, `requirements.txt` permite intervalos amplios para casi todas las dependencias y no hay archivo de bloqueo Python identificado en el repositorio. Instalar en momentos distintos puede resolver versiones distintas. Las dependencias de pruebas también se instalan en la imagen de producción.

**Acción:** adoptar progresivamente las reglas previstas y fijar una resolución reproducible de dependencias. Separar dependencias de ejecución y desarrollo. Evitar una reforma masiva de formato junto con cambios funcionales.

### 9. Documentación y contratos históricos necesitan una fuente más clara

**Evidencia:** `README.md:82` indica un head antiguo (`20260916_0010_locality`), mientras la migración más reciente inspeccionada declara `20261019_0039_referral_assign`. `app/services/nutrition_context.py:82` escribe `version=2`, pero `AttentionResponse.contexto_clinico` es un `dict[str, Any]` (`app/schemas/attention.py:270`). Existe tipado parcial de ubicación y el snapshot FUA sí declara versiones.

**Impacto:** la documentación puede orientar incorrectamente una instalación y el contexto clínico completo depende de claves textuales compartidas entre productores, mappers y exportadores. Agregar una versión numérica sin un contrato completo deja parte de las incompatibilidades para ejecución.

**Acción:** actualizar o generar la información de migraciones y tipar las versiones completas del contexto histórico, con lectores compatibles para registros anteriores. Conservar los snapshots: son una buena decisión para evitar que cambios de catálogos reescriban el pasado.

## Buenas prácticas que sí están presentes

- Los controladores inspeccionados son pequeños y delegan los casos de uso.
- Hay contratos de entrada/salida y mappers explícitos, con cuidado en distinguir PATCH omitido de null.
- Existen políticas puras en `app/domain`; no se encontraron imports de servicios, repositorios o modelos dentro de esa capa.
- Se usan restricciones, claves foráneas, índices relevantes y bloqueos de filas para varias invariantes. La reserva de numeración documental usa una fila bloqueada; la anulación y emisión coordinan el bloqueo de atención.
- La sesión se cierra por petición; los repositorios no son dueños generales del commit.
- Hay autorización tanto de acción como de objeto, recarga de roles desde persistencia y versión de credenciales.
- Los snapshots preservan contexto histórico y la auditoría acompaña numerosas escrituras.
- La suite incluye pruebas unitarias y de integración MySQL; CI dispone de MySQL desechable y configura un umbral de cobertura del 90 %. Esa configuración no sustituye medir la cobertura en una ejecución completa.

## Orden recomendado

1. Corregir la divergencia de roles y añadir una matriz de regresión compartida.
2. Limitar las lecturas de historial y corregir la paginación/carga de jerarquías. Medir consultas y tamaño de respuesta antes y después.
3. Extraer acceso clínico y construcción de snapshots; desacoplar exportación y origen de riesgos. Mantener las pruebas y la atomicidad como protección.
4. Tratar respuestas posteriores al commit e idempotencia de escrituras.
5. Antes de desplegar varias réplicas, separar migraciones, dimensionar pools y añadir readiness/mediciones.
6. Alinear CI, resolución de dependencias y documentación.

El mayor riesgo actual es que nuevas funciones sigan ampliando los mismos servicios y duplicando reglas. La estructura permite corregirlo de manera incremental; las limitaciones de carga identificadas necesitan mediciones con MySQL y datos representativos antes de prometer una capacidad concreta.
