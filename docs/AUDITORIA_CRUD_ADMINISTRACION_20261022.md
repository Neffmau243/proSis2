# Revisión estricta del CRUD administrativo

Estado posterior: los hallazgos de esta revisión fueron corregidos. Ver
[implementación y validaciones](CRUD_ADMINISTRACION_COMPLETADO_20261022.md).
El contenido siguiente conserva el diagnóstico anterior a las correcciones.

Fecha: 2026-10-22. Alcance: establecimientos, áreas, consultorios, catálogo de servicios,
servicios habilitados por consultorio y asignaciones de profesionales.

**Resultado: no cumple todavía el CRUD completo y consistente en cada nivel.**

Se revisaron vistas, formularios, contratos HTTP, validaciones y pruebas existentes.
Las reproducciones adicionales utilizaron TestClient y SQLite en memoria, con la
fixture `scene` de `tests/unit/test_care_service_admin.py`. No se modificaron datos
locales reales, código funcional, permisos ni lógica de admisión/FUA en esta revisión.

## Matriz

| Nivel | Crear | Consultar | Editar | Baja / retirar | Resultado |
| --- | --- | --- | --- | --- | --- |
| Establecimientos, catálogo general | Sí | Lista y detalle | Datos administrativos | Sí, con bloqueo si hay consultorios activos; reactivación | Disponible |
| Áreas, catálogo compartido | Sí | Lista y usos | Nombre | Sí, pero sus protecciones se pueden eludir desde Servicios | Inconsistente |
| Consultorios | Sí | Lista filtrada y detalle | Código, nombre y área compatible | Sí; reactivación y validaciones de jerarquía | Disponible |
| Servicios, catálogo general | Sí | Lista y consultorios vinculados | Nombre | Sí; reactivación y bloqueo por usos del servicio | Disponible, con fallo al compartir identidad con áreas |
| Servicios dentro de un consultorio | Crear o habilitar uno existente | Servicios y cantidad de profesionales | No permite editar el nombre desde este contexto | Quitar el vínculo, conservando el servicio global | Parcial para el flujo solicitado |
| Asignaciones de profesionales | Sí, admite más de dos profesionales | Por consultorio y servicio | Solo servicios; sin edición general de fecha de inicio o responsable | Cierre con fecha de fin, conservando historial | Edición restringida; CRUD general parcial |

La baja lógica, la conservación del historial y los bloqueos por dependencias son
reglas correctas; no se consideran operaciones faltantes. Tampoco es obligatorio
que los códigos internos inmutables se puedan editar.

## Hallazgos

### 1. Alta prioridad: Servicios permite eludir la protección del CRUD de áreas

Origen: `app/services/care_service_catalog.py`, funciones `service_areas`, `update`,
`set_active` y `_get`. El catálogo admite registros que también son áreas. Su baja
comprueba los consultorios que **habilitan ese código como servicio**, mientras que
`AreaAdministration.set_active` protege las áreas base y sus dependencias como área.
Estas comprobaciones no son equivalentes.

Reproducción aislada A:

1. Área base `ESPECIALIDADES:003` activa, consultorio activo con esa área y servicios
   explícitos `[ESP_MEDICINA:001, ESP_MEDICINA:003]`.
2. `DELETE /configuracion/areas/ESPECIALIDADES:003` responde **409**, correctamente.
3. `DELETE /configuracion/servicios/ESPECIALIDADES:003` responde **200** y desactiva
   el mismo registro del área.
4. `PATCH /configuracion/consultorios/{id}` con solo un nombre nuevo responde **422**,
   código `AREA_CONSULTORIO_INVALIDA`.

Reproducción aislada B:

1. Existen las áreas MEDICINA y NUTRICION.
2. Renombrar MEDICINA a NUTRICION mediante `/configuracion/areas/{codigo}` responde
   **409** por duplicidad.
3. El mismo cambio mediante `/configuracion/servicios/{codigo}` responde **200**.
4. El catálogo de áreas termina mostrando dos áreas llamadas NUTRICION.

Corrección prioritaria: aplicar las mismas invariantes a los registros compartidos
por ambas rutas, antes de introducir una separación de identidades o migraciones.
Una separación futura debe conservar códigos y relaciones clínicas existentes.
Añadir regresiones que cubran ambas rutas para baja y renombrado.

### 2. Servicios del consultorio carece de edición en ese contexto

Origen: `frontend/src/components/configuracion/OfficeServicesPanel.vue`, acciones
de cada servicio. Solo existen Profesionales y Quitar. Agregar permite crear o
habilitar; renombrar obliga a salir al catálogo general.

Para el flujo solicitado falta un acceso contextual a la edición. Debe dejar claro
que el nombre pertenece al catálogo compartido y que renombrarlo afecta a los otros
consultorios que utilizan el mismo código. Quitar de un consultorio y dar de baja
globalmente deben seguir siendo acciones distintas.

### 3. La edición de asignaciones no cubre todos sus datos

Origen: `app/schemas/office.py`, `OfficeAssignmentScope`, y
`app/services/office_assignment.py`, `update_scope` y `close`.
La interfaz `OfficeAssignmentActions.vue` ofrece Editar servicios y Cerrar.

El responsable y la fecha de inicio se eligen al crear, pero no tienen un caso de
uso de corrección. El cierre no permite ampliar una vigencia ya definida. Esto es
una edición deliberadamente restringida, no un CRUD general de la asignación.
Antes de ampliarla hay que definir qué se puede corregir y cómo preservar periodos
y atenciones existentes; no basta con reutilizar el formulario de alta.

## Contexto jerárquico

- El detalle de establecimiento es una vista de áreas agrupadas y consultorios;
  editar o dar de baja la sede requiere volver al listado general.
- El área es un catálogo compartido; no existe una entidad independiente de área
  por establecimiento con su propio CRUD. No debe presentarse como tal.
- El alta de consultorio desde una sede precarga sede y área, pero permite cambiarlas.
  Tras guardar se recarga el directorio con sus filtros anteriores. Si se elige otra
  sede o área, el nuevo registro puede quedar fuera del listado visible. Es una
  limitación de continuidad del contexto, no una ausencia del endpoint de creación.

## Verificación

- Backend: **65 pruebas aprobadas** en `test_care_configuration_admin.py`,
  `test_care_service_admin.py`, `test_office_service_catalog.py` y `test_office_service.py`.
  Ejecución focalizada con `--no-cov`; no representa una medición de cobertura global.
- Frontend: **44 pruebas aprobadas** en `ConsultoriosView.test.ts`,
  `CareConfiguration.test.ts` y `CareServiceCatalog.test.ts`, con dos trabajadores.
- La primera ejecución parcial del backend pasó sus 65 casos, pero el comando
  falló por el umbral global de cobertura del 90%; se repitió como prueba focalizada
  sin cobertura. No se cambió ese umbral ni la configuración del proyecto.
- Los dos fallos entre rutas se reprodujeron adicionalmente con HTTP sobre SQLite
  aislado. Los casos existentes no cubren esas combinaciones.
- No se ejecutó el CRUD contra la base real ni se generaron o modificaron FUA.

## Orden de corrección

1. Unificar protecciones y validación de nombres de áreas/servicios; añadir regresiones.
2. Ofrecer edición contextual de servicios con alcance global explícito.
3. Definir y cubrir la corrección segura de asignaciones.
4. Completar las acciones de detalle y la continuidad del contexto tras crear.
