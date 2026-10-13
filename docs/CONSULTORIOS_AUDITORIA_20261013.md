# Revisión de consultorios y jerarquías — 13/10/2026

La pantalla y su consumo clínico **no están completamente alineados** con el flujo solicitado: establecimiento → área → servicio/especialidad, junto con consultorios físicos y subconsultorios. Hoy el sistema usa una sola fila para representar el área y una sola especialidad obligatoria por consultorio. Por eso Medicina termina siendo «Medicina» tanto en el nombre como en la especialidad.

Revisión de código, migraciones, ETL, navegador en `http://localhost:8000/configuracion/consultorios`, metadatos de MySQL en una transacción `READ ONLY` y reproducciones con objetos separados de la base. No se modificaron datos operativos ni reglas de la aplicación. La aclaración del usuario confirmó que necesita ambas jerarquías.

## Evidencia del origen y la base local

| Dato | Resultado verificado |
| --- | --- |
| Áreas de `etlSis/dump/20_catalogos.sql:475` | Medicina, Enfermería, Odontología, Psicología, Obstetricia, Nutrición, Laboratorio |
| Consultorios en la base | 42 activos, 6 establecimientos, 0 con padre |
| Especialidades | 33 filas; mezclan áreas, servicios, terapias y tipos de certificado |
| Grupo `Esp_Medicina` | Medicina General, DANT, Pediatría, Ginecología |
| Asignaciones consultorio–profesional | 372; los 62 profesionales tienen asignaciones actuales en las 6 sedes |
| Asignaciones con especialidad incompatible actualmente | 0 |
| Establecimientos activos sin microred vinculada | 6 de 6 |

`etlSis/schema.sql:104` define `cat_consultorio` con nombre y nombre normalizado: no contiene establecimiento, padre ni identificación de consultorio físico. La migración `20260926_0020_real_catalogs.py:221` infiere siete áreas para cada una de seis sedes. Las tablas/grupos `Esp_*` aportan contexto para asociar servicios con áreas, pero no prueban que existan salas físicas con esos nombres. Esa distinción debe conservarse al migrar.

Resultados reproducibles: [JSON de la auditoría](audits/consultorios_probe_20261013.json), [sonda de solo lectura](audits/consultorios_readonly_probe.py).

## Hallazgos priorizados

### P1 — Medicina General/Pediatría no pueden consumirse como servicios de Medicina

`app/services/attention.py:384`: si el consultorio tiene una especialidad, la atención debe llevar exactamente el mismo código. `frontend/src/views/AtencionNuevaView.vue:900` copia la especialidad del consultorio. Para `MED` es `ESPECIALIDADES:003`, mientras Pediatría es `ESP_MEDICINA:003`.

Reproducción en memoria: consultorio Medicina + atención Pediatría → `ESPECIALIDAD_INCOMPATIBLE`. Los datos sí existen, pero falta una relación área–servicios disponibles y una validación que la use. Cambiar solo el texto o cargar un árbol visual dejaría el error intacto.

### P1 — Las asignaciones iniciales dan un ámbito de seis sedes a todos los profesionales

`migrations/versions/20260926_0021_real_professionals.py:198` agrupa consultorios por especialidad; en la línea 236 asigna cada profesional a todos los consultorios de esa especialidad, sin una vinculación de origen con la sede. MySQL confirma 62 profesionales × 6 sedes = 372 asignaciones.

`app/repositories/patient.py:142` y `app/repositories/discovery.py:46` usan las asignaciones actuales para construir el ámbito de pacientes. La inferencia amplía el ámbito asistencial a las seis sedes. Se necesita contrastar las asignaciones reales antes de corregir datos; el origen disponible no justifica asignar ni retirar sedes específicas automáticamente.

### P1 — Cambiar la especialidad de un consultorio puede invalidar asignaciones existentes

`app/services/office.py:92`: la edición comprueba que la nueva especialidad esté activa, pero no que los profesionales con asignaciones actuales/futuras la tengan. En cambio, `OfficeAssignmentService.assign` sí exige compatibilidad, y `ProfessionalService.replace_specialties` protege especialidades usadas en asignaciones.

La reproducción de edición consulta consultorio, establecimiento y especialidad; no revisa asignaciones. Actualmente no hay incompatibilidades en la base, pero esta operación permite introducirlas. Debe validarse el conjunto de asignaciones afectadas antes de guardar.

### P1 — La baja de un padre no protege el estado de sus hijos

`app/services/office.py:123` desactiva únicamente la fila solicitada. La reproducción en memoria deja padre inactivo e hijo activo. Los catálogos y el contexto clínico solo comprueban el estado del hijo; no recorren sus ancestros. Un hijo sin especialidad tampoco recibe automáticamente la especialidad del padre.

No hay incidentes de este tipo en la base actual porque no tiene relaciones padre–hijo. Para el flujo requerido, hace falta una política explícita: bloquear la baja con descendientes activos o desactivar el subárbol con auditoría. La opción conservadora es bloquear y resolver primero los descendientes.

### P2 — El contrato consumido por otros usuarios pierde la jerarquía

`app/schemas/catalog.py:85`, `app/mappers/catalog.py:134`, `frontend/src/services/catalogos.ts:69`: `OfficeCatalogItem` no incluye `consultorio_padre_id`. El API administrativo sí lo entrega, pero está restringido a administración. Los consumidores clínicos no pueden reconstruir el árbol desde su catálogo.

`app/repositories/catalog.py:142` devuelve una lista plana ordenada por sede/código. Se necesita exponer padre y contexto del área en el catálogo compartido, con una definición consistente del estado efectivo y de los servicios disponibles.

### P2 — La interfaz mezcla grupos y presenta combinaciones sin contexto

`frontend/src/views/ConsultoriosView.vue:123`: el formulario ofrece las 33 especialidades sin filtrar por área. Verificado en navegador: al editar Medicina aparecen Certificado Psicológico, Consulta Nutricional, Inyectable, Materno y las especialidades médicas en la misma lista.

`frontend/src/views/ConsultoriosView.vue:433`: el selector de padre elimina solo el propio consultorio, no sus descendientes, y carga únicamente los primeros 100 resultados. El backend sí rechaza el ciclo. El nombre del padre se resuelve exclusivamente con las filas visibles (`:370`), por lo que un padre oculto termina como «Consultorio #id».

`frontend/src/views/AtencionNuevaView.vue:822`: el selector de profesionales consume el catálogo general, sin consultorio ni vigencia. `loadConsultorios` carga solo la primera página de 50; hoy los 42 consultorios caben, pero no es suficiente para un catálogo ampliado con subconsultorios.

`frontend/src/composables/useLaboratory.ts:101`: Laboratorio se detecta buscando «LAB» y por código/nombre, en lugar de una relación de área. Un subconsultorio «Toma de muestras» con otro código puede quedar fuera. La selección por sede usa el primer consultorio encontrado, sin distinguir padre/hijo.

### P2 — Documentación y pruebas discrepan sobre asignaciones al registrar atención

`GUIA_FRONTEND_RUTAS.md:323` dice que se valida asignación vigente y se rechaza con `PROFESIONAL_NO_ASIGNADO`. El validador clínico actual no hace esa comprobación; `tests/integration/test_mysql_attention_flow.py:226` espera crear correctamente una atención en un consultorio sin asignación.

No debe cambiarse esa política bajo la premisa de que sea un error accidental: existe una prueba que la permite. Hay que resolver la discrepancia y aplicar la regla elegida de forma uniforme en documentación, selectores, backend y pruebas. El ámbito de acceso al paciente y el permiso del usuario sí se comprueban en otras partes del servicio.

## Qué sí funciona

- Administración de consultorios restringida al permiso administrativo.
- Código único por establecimiento, normalización de códigos y baja lógica con auditoría.
- Padre del mismo establecimiento, rechazo del propio consultorio como padre y detección de ciclos en backend.
- Alta de asignaciones con especialidad compatible, control de fechas y superposición para el mismo profesional/consultorio.
- Integridad actual de las especialidades de las 372 asignaciones.

## Flujo que debe quedar implementado

1. Seleccionar establecimiento y área asistencial.
2. Mostrar sus consultorios físicos y subconsultorios, con padre, ruta y estado efectivos.
3. Ofrecer los servicios/especialidades habilitados para esa área y ese consultorio; por ejemplo, Medicina → Medicina General/Pediatría/Ginecología según disponibilidad configurada.
4. Resolver profesionales y vigencias según la política de asignación acordada.
5. Validar en backend la misma combinación que ofrece la interfaz y guardar los identificadores precisos para el historial/documentos.

El modelo debe distinguir **área asistencial**, **servicio/especialidad** y **consultorio físico**. La FK `consultorio_padre_id` sirve para la jerarquía física; hace falta además una relación explícita para los servicios habilitados. Los grupos `Esp_*` son evidencia para preparar ese mapeo, sujeto a las duplicaciones y normalizaciones del ETL. Los certificados y actividades no deben tratarse automáticamente como nuevas salas.

Para las columnas solicitadas: Código y Nombre deben identificar el consultorio; Establecimiento debe resolver la sede; Área debe mostrarse explícitamente; Servicios/especialidades debe listar lo habilitado; Consultorio padre debe mostrar código/nombre/ruta; Estado debe explicar la disponibilidad considerando ancestros. Las acciones deben proteger descendientes y asignaciones existentes.

Orden de corrección propuesto: definir ambos modelos y el mapeo del ETL; ampliar contratos compartidos; alinear validaciones y asignaciones; conectar configuración/admisión/laboratorio al mismo contrato; presentar árbol y filtros en la interfaz. No se recomienda generar subconsultorios físicos ficticios ni modificar asignaciones masivamente a partir del nombre de la especialidad.

## Validación realizada y límites

- Frontend: `ConsultoriosView.test.ts` y `services.test.ts`: **16 pruebas aprobadas**.
- Backend: `test_attention_service.py` y `test_authorization.py`: **16 pruebas aprobadas**.
- MySQL: consultas agregadas en `START TRANSACTION READ ONLY` y `ROLLBACK`.
- Reproducciones separadas de la base: incompatibilidad Pediatría/Medicina, pérdida del padre en DTO, baja de padre con hijo activo y edición sin comprobación de asignaciones.
- Navegador: listado real, edición de Medicina y catálogo general de especialidades; formulario descartado sin guardar.
- La ejecución adicional de contratos HTTP quedó detenida sin concluir; no se contabiliza como aprobada. No se ejecutó la integración que migra/vacía una base de pruebas: `TEST_DATABASE_URL` no está configurada.

Las pruebas aprobadas validan comportamiento existente, no certifican la nueva jerarquía. Falta implementar y verificar su flujo completo antes de considerarlo alineado.

Revisión adicional de controles según [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md): `frontend/src/views/ConsultoriosView.vue:17` — el filtro de establecimiento depende del placeholder y carece de etiqueta accesible; `:183` — «Vigente» usa solo `fecha_fin === null` y puede representar incorrectamente una asignación futura. Son mejoras específicas de interfaz posteriores a resolver el modelo.
