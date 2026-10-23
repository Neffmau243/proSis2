# CRUD administrativo: correcciones implementadas

## Resultado

Se completaron los casos pendientes de la auditoría sin cambiar códigos clínicos,
relaciones existentes, permisos ni plantillas de FUA. La navegación horizontal y el
estilo compartido de administración se conservan.

| Nivel | Operaciones disponibles |
| --- | --- |
| Establecimientos | Crear, listar, consultar detalle, editar identidad, dar de baja y reactivar. Editar y cambiar estado también están disponibles dentro de su ficha. |
| Áreas compartidas | Crear, consultar usos, renombrar, dar de baja y reactivar. Las áreas base y las dependencias activas siguen protegidas. |
| Consultorios | Crear, listar por sede/área, consultar, editar, dar de baja y reactivar. Al crear se abre el nuevo consultorio con la sede y área realmente guardadas. |
| Catálogo general de servicios | Crear, listar, consultar un registro, renombrar, dar de baja y reactivar. Los registros que también son áreas respetan sus reglas compartidas. |
| Servicios del consultorio | Crear o habilitar, consultar, editar el nombre desde su contexto, gestionar profesionales y quitar el vínculo. La edición informa que el nombre es compartido. |
| Asignaciones | Crear, consultar por consultorio/servicio, editar fechas, responsable y servicios, y cerrar con fecha de fin. Admite varios profesionales por servicio. |

Dar de baja conserva el registro y su historial. Quitar un servicio de un consultorio
conserva el catálogo general. Eliminar físicamente áreas base, cambiar códigos de
referencia o cambiar de persona una asignación histórica no son operaciones expuestas.
Para otra persona se crea su propia asignación.

## Backend

- `CareAreaRules` aplica protección de estado y nombres a los registros compartidos.
  El renombrado desde Áreas y Servicios utiliza el mismo caso de uso, incluida la
  comprobación de nombres de servicios del área. No se puede desactivar un área base
  ni eludir dependencias por la ruta del catálogo de servicios.
- Nuevo `GET /configuracion/servicios/{codigo}` para abrir una edición contextual
  con datos actuales y el número de consultorios vinculados.
- Nuevo `PATCH /configuracion/consultorios/{id}/profesionales/{profesionalId}/{inicio}`
  para editar la asignación completa. El cuerpo requiere inicio, fin, responsable y
  alcance de servicios; el consultorio y la persona mantienen su identidad.
- Se comprueban oficina y profesional activos, requisito del consultorio, servicios
  habilitados, fechas válidas, solapamientos del mismo profesional y responsables
  coincidentes en el periodo.
- El cambio de fechas y el cierre no pueden dejar atenciones existentes fuera del
  periodo. Se consideran también las oficinas que heredan la asignación. Se auditan
  los valores anteriores y nuevos. Los errores revierten la transacción, incluido
  un cambio de la fecha que forma parte de la clave del registro.
- Las rutas anteriores de asignación, edición de alcance y cierre se conservan.
  No se añadieron columnas ni migraciones para estas correcciones.

## Frontend

- El servicio habilitado ofrece Editar, Profesionales y Quitar. La edición reutiliza
  el formulario del catálogo y explica su alcance global; los errores conservan lo escrito.
- El formulario de asignación admite alta y edición, mantiene fija la persona en
  edición y precarga periodo, responsable y servicios. El pie permanece visible y
  el cuerpo puede desplazarse cuando la altura es limitada.
- El detalle de establecimiento reutiliza el mantenimiento existente para editar,
  dar de baja y reactivar, sin cargar otra lista general.
- Crear un consultorio conduce al detalle recién creado, incluso si se cambió la sede
  o el área inicialmente precargadas. No queda oculto bajo los filtros anteriores.

## Verificación

- Frontend completo: **491 pruebas aprobadas y 1 omitida**. Incluye las regresiones
  de admisión y FUA y los nuevos casos de edición contextual, errores del formulario,
  asignación completa, acciones de sede y navegación tras crear.
- Unitarias del backend: **861 pruebas aprobadas** después del último ajuste de reglas.
- Se ejecutó la suite completa con MySQL desechable: 1050 casos pasaron inicialmente
  y cuatro casos señalaron ajustes en las propias pruebas. Los cuatro fueron cubiertos
  por una repetición de 10 casos aprobados. El contrato del catálogo se actualizó para
  incluir el campo existente `es_area_base`; el escenario antiguo de admisión ahora
  habilita explícitamente su servicio y requisito. La nueva prueba clínica utiliza
  el usuario profesional para crear la atención, conservando los permisos de ADMIN.
- La prueba nueva de MySQL guarda una atención a través de la API clínica, intenta
  retirar su fecha mediante edición de asignación y comprueba que se rechaza y que
  `fecha_atencion` y `fua_impresion` siguen idénticos.
- La comprobación final de reglas compartidas repitió **26 casos aprobados**, incluyendo
  MySQL y las unitarias de establecimientos, áreas, servicios y asignaciones.
- Cobertura global del backend: **96,95 %**, superior al umbral original del 90 %.
  Se usa cobertura acumulada para las repeticiones focalizadas; no se redujo el umbral.
- Compilación de producción, tipos, ESLint de los archivos afectados y Ruff correctos.
- Revisión de las acciones y formularios en 1280 × 720 y 390 × 844. Sin desplazamiento
  horizontal de página en los estados comprobados.

Las integraciones utilizaron esquemas locales nuevos con nombre
`ipress_test_crud_20261022_*`, diferentes de la base de trabajo, y se eliminaron al
terminar. La revisión en el navegador abrió y canceló formularios sin guardar cambios
en registros reales. El servidor local se reinició para servir el backend actualizado.

## Evidencias visuales

- [Editar servicio en escritorio](audits/crud-servicio-editar-escritorio-20261022.png)
- [Editar servicio en móvil](audits/crud-servicio-editar-movil-20261022.png)
- [Editar asignación en escritorio](audits/crud-asignacion-editar-escritorio-20261022.png)
- [Editar asignación en móvil](audits/crud-asignacion-editar-movil-20261022.png)
- [Acciones de sede en escritorio](audits/crud-establecimiento-acciones-escritorio-20261022.png)
- [Acciones de sede en móvil](audits/crud-establecimiento-acciones-movil-20261022.png)
