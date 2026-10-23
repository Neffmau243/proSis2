# Administración de consultorios y servicios

Implementación y verificación del 22/10/2026.

## Uso

- **Consultorios y servicios** conserva el directorio y las rutas anteriores. Desde el detalle de cada consultorio se administran sus servicios y se abre la lista de profesionales de cada uno. Los consultorios dados de baja pueden reactivarse desde el detalle o el menú de acciones.
- **Configuración → Catálogo de servicios** abre `/configuracion/servicios`. También está disponible como pestaña del directorio de consultorios. Incluye búsqueda, filtro por área, inactivos, registro, edición de nombre, baja lógica, reactivación y enlaces a los consultorios donde se utiliza cada servicio.
- Registrar desde el catálogo no habilita el servicio en ningún consultorio. **Agregar servicio** dentro de un consultorio permite habilitar uno existente o registrar y habilitar uno nuevo, con ese alcance explicado en el formulario.
- El formulario de subconsultorio permite elegir entre los servicios habilitados. Para agregar otro, lleva a la gestión del consultorio principal y cierra el formulario sin guardar. Se eliminó el guardado inmediato de servicios dentro de ese formulario cancelable.
- **Profesionales**, junto a un servicio, muestra las asignaciones aplicables, sus fechas, estado y origen. Se pueden agregar varios profesionales, elegir uno o varios servicios para una asignación, editar su alcance o cerrar su vigencia. Las asignaciones heredadas llevan a su consultorio de origen para modificarlas.
- Si un profesional ya tiene una asignación en esas fechas en el consultorio, se utiliza **Editar servicios** para ampliar su alcance. Se conserva la regla anterior de evitar períodos superpuestos por profesional y consultorio y de gestionar el responsable a nivel de consultorio.

## Limpieza del código

El backend separa el CRUD de consultorios (`OfficeService`), el ciclo de asignaciones (`OfficeAssignmentService`), el catálogo general (`CareServiceCatalog`) y la habilitación en un consultorio (`OfficeCareService`). El registro y la normalización de servicios se reutilizan desde el catálogo, sin duplicar la generación de identidades. La habilitación dejó de llamar métodos privados de otro servicio. Las respuestas de las mutaciones se construyen antes de confirmar la transacción.

Las consultas de profesionales y la validación de admisión comparten `eligible_professional_ids`. El listado administrativo carga los nombres y el consultorio de origen desde el backend, sin depender de los primeros resultados del buscador. Las relaciones del listado se cargan en conjunto.

En Vue, el componente principal delega los formularios en `useOfficeForm` y las asignaciones en `useOfficeAssignments` y `OfficeAssignmentsDialog`. El catálogo se divide en estado, contenedor, lista y formulario. Las acciones de asignación se reutilizan entre la tabla de escritorio y la lista móvil. Se conservan Vue 3, TypeScript, Composition API y los componentes y estilos del proyecto.

## Compatibilidad y esquema

La migración `20261022_0041_assign_services` agrega únicamente la columna nullable `consultorio_profesionales.servicios_codigos`. Se aplicó a la base local y es la revisión actual de Alembic.

- `NULL` conserva el alcance anterior: todos los servicios permitidos por el consultorio, incluida la herencia.
- Una lista explícita limita esa asignación a los códigos indicados; la lista vacía se rechaza.
- Las asignaciones anteriores no se copian, reclasifican ni restringen automáticamente.
- Admisión y Laboratorio envían el servicio elegido al buscar profesionales. El servidor aplica la misma regla al validar una admisión.
- Registrar un servicio asistencial no concede una cualificación al personal. Los permisos de configuración y de gestión de personal mantienen sus controles diferenciados.
- Las bajas son lógicas. La baja global de un servicio en uso informa los consultorios activos que deben resolver su habilitación primero. Se mantienen los códigos y los registros clínicos históricos.

## Verificación

- Backend: **842 pruebas unitarias aprobadas**, incluidas pruebas HTTP y persistencia SQLite aislada para CRUD, permisos, rollback de auditoría, reactivación, tres profesionales en un servicio, alcance por servicio y herencia.
- Frontend: **473 pruebas aprobadas y una omitida** en la suite completa. Incluye configuración, catálogo, admisión, rutas y navegación por permisos.
- Comprobación de tipos y compilación de producción aprobadas. La compilación conserva el aviso general de Vite por paquetes de más de 500 kB.
- Ruff y ESLint del alcance modificado aprobados; detector de interfaz sin hallazgos.
- Revisión en vivo como administrador del consultorio 43 y del catálogo general. Se revisaron escritorio y móvil de 390 × 844, incluidas las asignaciones como lista móvil.
- Comprobación en vivo como `medico.demo` en `/admision?patientId=16698`: Medicina conserva Medicina General, DANT, Pediatría, Ginecología y Medicina; Medicina General devuelve 16 profesionales en la configuración actual.
- Las mutaciones funcionales se probaron con datos aislados. No se guardaron admisiones ni se crearon o modificaron registros de configuración de negocio durante el recorrido visual local.

## Capturas

Ajuste posterior de nombres: el catálogo muestra el nombre propio de cada subconsultorio, con establecimiento y consultorio principal como contexto. Los consultorios principales que habilitan el servicio se muestran en un detalle separado. Si no existen subconsultorios, la pantalla lo explica sin presentar a los principales como subconsultorios. El servicio general deja de repetir el nombre del área como subtítulo. Verificación de este ajuste: 58 pruebas backend y 40 frontend aprobadas, tipos, compilación, Ruff, ESLint y detector sin hallazgos; revisión de escritorio y móvil sin modificar registros.

- `audits/subconsultorios-nombre-propio-escritorio-20261022.png`
- `audits/subconsultorios-nombre-propio-movil-20261022.png`

- `audits/admin-servicios-catalogo-escritorio-20261022.png`
- `audits/admin-servicios-catalogo-movil-20261022.png`
- `audits/admin-consultorio-43-escritorio-20261022.png`
- `audits/admin-consultorio-43-movil-20261022.png`
- `audits/admin-profesionales-servicio-escritorio-20261022.png`
- `audits/admin-profesionales-servicio-movil-20261022.png`


## Aclaración del flujo: una sola gestión de servicios

La aclaración del usuario reemplaza el flujo de creación separado descrito anteriormente: para esta pantalla, los subconsultorios corresponden a los servicios/especialidades. Se retira la tarjeta inferior «Subconsultorios», su tabla y los accesos «Nuevo subconsultorio» del directorio. El detalle conserva «Servicios / especialidades» y la gestión de profesionales por servicio. Se eliminan también los eventos y cálculos usados exclusivamente por la sección retirada. No se eliminan ni migran registros históricos.

Verificación de este ajuste: 33 pruebas de consultorios y catálogo aprobadas; tipos, compilación de producción y ESLint aprobados; detector de interfaz sin hallazgos. Revisión en vivo de escritorio y móvil: una sola sección de servicios y ninguna tabla inferior de subconsultorios.

- `audits/consultorio-servicios-unicos-escritorio-20261022.png`
- `audits/consultorio-servicios-unicos-movil-20261022.png`


## Formulario de consultorio sin jerarquía administrativa

Tras la aclaración del modelo consultorio → servicios/especialidades → profesionales, el alta y la edición muestran únicamente establecimiento, código, nombre del consultorio y área asistencial. Se eliminan el selector de padre, la selección duplicada de servicios, el formulario separado de creación de subconsultorios, sus props/eventos y las consultas de opciones de padres. Los servicios y sus profesionales se gestionan desde el detalle del consultorio. El catálogo muestra una sola lista de consultorios vinculados por servicio, sin separarlos en principales y subconsultorios.

El alta envía un consultorio independiente. La edición de código/nombre usa un PATCH parcial: no reenvía ni restablece servicios, especialidad, relaciones históricas ni asignaciones. Si el usuario cambia el área, se envía ese cambio explícito y se mantienen las validaciones del servidor. No hay migración ni eliminación de datos clínicos o relaciones históricas en este ajuste.

Verificación: 97 pruebas frontend aprobadas, incluidas configuración, Admisión y FUA; 96 pruebas backend aprobadas entre las suites seleccionadas y la confirmación de la nueva regresión HTTP de renombrado con tres profesionales. Tipos, compilación de producción, ESLint y Ruff aprobados. Revisión visual del formulario en escritorio y móvil, sin guardar cambios de negocio.

- `audits/consultorio-editar-sin-padre-escritorio-20261022.png`
- `audits/consultorio-editar-sin-padre-movil-20261022.png`
