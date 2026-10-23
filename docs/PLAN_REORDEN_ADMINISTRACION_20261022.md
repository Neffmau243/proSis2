# Plan para ordenar la administración y el registro de pacientes

Fecha: 22/10/2026. Estado: plan original; recorrido administrativo principal implementado posteriormente.

Actualización: el recorrido administrativo principal y sus comprobaciones se entregaron después de este plan. Ver [implementación y verificación](REORDEN_ADMINISTRACION_IMPLEMENTADO_20261022.md). El diagnóstico siguiente conserva la situación revisada originalmente.

## Objetivo

Que el administrador pueda mantener establecimientos, áreas, consultorios, servicios y asignaciones sin confundir la estructura administrativa con la atención del paciente. Conservar el recorrido clínico actual de Admisión y la emisión de FUA.

La revisión abarca rutas, navegación, componentes administrativos, permisos, modelos y endpoints existentes. No se ejecutaron mutaciones de negocio ni pruebas en esta revisión: el entregable es este plan. Reemplaza las propuestas anteriores de navegación que colocaban áreas y catálogo general como pestañas dentro del CRUD de consultorios.

## Diagnóstico comprobado

| Elemento | Situación actual | Consecuencia |
| --- | --- | --- |
| Establecimientos | Hay modelo persistido y consulta autenticada `GET /catalogos/establecimientos`; no se encontró vista ni API administrativa para su CRUD | El flujo comienza en consultorios, con establecimientos que el administrador no puede mantener desde esa pantalla |
| Áreas | Se gestionan desde la pestaña «Áreas de atención» de Consultorios, mediante el catálogo de especialidades de personal | La categoría parece subordinada a la entidad que debería clasificar; sus permisos dependen de gestionar profesionales |
| Servicios | Existe `/configuracion/servicios` y también una pestaña con el mismo catálogo en Consultorios | Hay dos entradas de mantenimiento general sin una función diferente |
| Consultorios | Tienen CRUD y detalle para servicios/profesionales; pertenecen a un establecimiento y tienen un código de área | Falta una navegación contextual que explique esas relaciones |
| Profesionales | Su registro general está en Personal y cuentas; sus asignaciones por servicio están en el detalle del consultorio | La separación es válida, pero debe quedar explícita: registrar una persona y asignarla no son la misma operación |
| Pacientes | El listado es «Base de datos»; existen alta, ficha y API de edición | El mantenimiento administrativo no está reunido en un recorrido claro |
| Edición de pacientes | `/pacientes/:id/editar` redirige a Admisión; «Modificar datos» está comentado en el menú | ADMIN puede editar pacientes en la API, pero no tiene `ATENCION_CREAR` para abrir Admisión; falta un acceso de edición independiente |

Referencias principales: `frontend/src/router/index.ts`, `frontend/src/layouts/AppLayout.vue`, `frontend/src/components/configuracion/ConsultoriosPanel.vue`, `frontend/src/components/configuracion/StaffCatalogsPanel.vue`, `app/controllers/catalog.py`, `app/controllers/staff_catalog.py`, `app/controllers/patient.py`, `app/models/organization.py` y `app/domain/authorization.py`.

## Organización propuesta

La secuencia de configuración es establecimiento → área → consultorio → servicios habilitados → profesionales asignados. Es un recorrido de administración; no exige crear un registro nuevo de cada catálogo cada vez ni recorrer todas las pantallas para editar algo conocido.

Las áreas son un catálogo compartido. Un establecimiento puede tener consultorios del área Nutrición sin crear otra categoría Nutrición propia de esa sede. En el modelo actual esa presencia se obtiene de los consultorios del establecimiento; no existe una relación independiente de «área habilitada por establecimiento». La primera entrega utilizará esa relación existente. Si posteriormente se necesita habilitar áreas antes de tener consultorios, esa relación requerirá una decisión funcional y un cambio explícito de modelo.

Los servicios se registran en un catálogo general y se habilitan en los consultorios compatibles. Se conserva la posibilidad actual de agregar un servicio nuevo desde el detalle, explicando que también se registra en el catálogo. No se duplicará el catálogo por establecimiento ni se creará una tabla de consultorios hijos para representar cada servicio.

```text
Configuración de atención
  Establecimientos
    Detalle del establecimiento
      Áreas con sus consultorios
        Consultorio
          Servicios habilitados
            Profesionales y vigencias
  Catálogos compartidos
    Áreas de atención
    Servicios / especialidades

Personal y cuentas
  Profesionales
  Cuentas de usuario
  Profesiones y cualificaciones del personal

Operación diaria
  Pacientes
    Registrar / buscar / consultar / editar / dar de baja según permisos
    Admisión, cuando el usuario tenga permiso clínico
      Consultorio → servicio → profesional → guardar atención → FUA
```

El paciente es independiente del catálogo de configuración. Puede conservar su establecimiento de registro, pero no queda adscrito permanentemente a un servicio por ser creado. El contexto de consultorio, servicio y profesional se selecciona para cada atención. Un profesional también puede atender varios servicios: la asignación es una relación con alcance y vigencia, no otra copia del profesional.

## Plan por entregas

### 1. Unificar navegación y separar pacientes de configuración

- Crear una entrada administrativa «Configuración de atención» y ordenar establecimientos, áreas, consultorios y servicios dentro de ella.
- Dar a Áreas una ruta propia y al catálogo general de servicios una sola ruta canónica. Sustituir las pestañas duplicadas de Consultorios por enlaces contextuales.
- Mantener un acceso directo a consultorios con filtros por establecimiento y área. Añadir navegación contextual que conserve esos filtros al volver.
- Presentar Pacientes como módulo operativo reconocible, conservando Base de datos como listado existente y los enlaces anteriores.
- Mantener Personal y cuentas como registro general; desde cada servicio se seleccionan profesionales ya registrados.

Resultado: cada catálogo tiene un lugar de mantenimiento identificable; no se obliga a pasar por un consultorio para crear un área.

### 2. Completar el CRUD de establecimientos

- Implementar listado administrativo paginado con búsqueda, activos/inactivos, alta, edición, detalle, baja lógica y reactivación.
- Reutilizar el modelo actual: nombre, abreviatura, códigos RENAES/RENIPRESS e IDEESS cuando correspondan, ubicación y referencias territoriales existentes. Los identificadores internos se generan en servidor.
- Agrupar la configuración propia de FUA del establecimiento como opciones específicas; conservar sus valores actuales al editar el nombre u otros datos.
- Validar duplicados conforme a las restricciones existentes y auditar cambios. Explicar dependencias antes de una baja; no dar de baja en cascada consultorios, pacientes o asignaciones.
- Desde el detalle, mostrar consultorios agrupados por área y permitir crear uno con establecimiento/área precargados.

Resultado: se puede gestionar el inicio del recorrido sin editar directamente la base de datos.

### 3. Dar a Áreas una administración propia

- Crear una vista dedicada con búsqueda, alta, edición, consulta de uso y estado conforme a sus dependencias.
- Separar la presentación y los contratos de áreas de los de cualificaciones profesionales. Reutilizar la persistencia y los códigos existentes en esta entrega.
- Mostrar dónde se usa cada área: establecimientos y consultorios. Mantener las áreas base requeridas por la lógica clínica protegidas frente a cambios incompatibles.
- Completar las operaciones de baja/reactivación cuando falten, con reglas explícitas para registros vinculados. No convertir un área en una especialidad profesional por editar un selector de tipo.
- Al crear un área nueva, ofrecer continuar a sus servicios y consultorios sin inventar códigos clínicos equivalentes ni copiar configuraciones de otras áreas.

Resultado: el administrador entiende que registra una categoría reutilizable y puede consultar sus usos.

### 4. Consolidar consultorios, servicios y asignaciones

- Mantener en el formulario del consultorio establecimiento, código, nombre y área; precargar el contexto al abrirlo desde una sede o área.
- Conservar el detalle de servicios como punto de habilitación local. Distinguir registrar en catálogo, habilitar, quitar del consultorio y dar de baja globalmente.
- Mantener el catálogo general como mantenimiento compartido de nombres, códigos, estado y usos. Los cambios globales deben indicar su alcance.
- Dentro de cada servicio, mostrar todos los profesionales, su vigencia y acciones de asignación/cierre. Probar tres o más profesionales y un profesional en varios servicios.
- Conservar asignaciones anteriores y su alcance; no redistribuirlas automáticamente por coincidencia de nombres. Preservar compatibilidad con relaciones históricas que aún utiliza el backend.
- Guardar cambios parciales: renombrar un consultorio no restablece área, servicios ni asignaciones.

Resultado: una única gestión de cada entidad y un recorrido local claro para configurar la atención.

### 5. Completar el mantenimiento independiente de pacientes

- Habilitar «Editar datos del paciente» desde listado/ficha con `PACIENTE_EDITAR`, sin requerir crear una atención.
- Implementar la ruta de edición propia reutilizando los campos, validaciones y lógica de guardado del editor existente. Admisión podrá seguir mostrando ese mismo editor compartido.
- Mantener registro, búsqueda, ficha, edición y baja lógica autorizada; proteger contra duplicados según los contratos actuales.
- Conservar los permisos clínicos de Admisión/FUA. No concederlos a ADMIN para resolver una limitación de navegación administrativa.
- Conservar la búsqueda y selección de pacientes y los parámetros de los enlaces existentes de Admisión.

Resultado: ADMIN puede mantener pacientes y el profesional puede seguir admitiéndolos con el flujo actual.

### 6. Verificar compatibilidad y publicar por etapas

- Definir permisos administrativos de establecimientos y áreas cuando se implementen sus endpoints; aplicarlos en API, rutas y menú. Conservar el límite entre administración y actos clínicos.
- Mantener los enlaces actuales a consultorios, servicios y pacientes mediante rutas estables o redirecciones compatibles.
- Reutilizar el esquema actual; agregar migraciones únicamente para necesidades de persistencia identificadas. No renumerar códigos ni reconstruir jerarquías a partir de nombres.
- Verificar FUA y documentos históricos: sus datos guardados no se reescriben por modificar configuración. El campo «Tipo de atención» conserva su origen actual en la modalidad de atención.
- Ejecutar pruebas de permisos, transacciones, dependencias, CRUD nuevo y elegibilidad compartida entre catálogo y guardado clínico. Revisar escritorio, móvil, teclado, errores y recuperación de formularios.

## Criterios de aceptación

1. ADMIN puede crear un establecimiento, seleccionar/crear un área compartida, crear un consultorio, habilitar un servicio y asignarle al menos tres profesionales.
2. Hay una sola pantalla principal de mantenimiento general para cada entidad. Los accesos contextuales reutilizan esa implementación y conservan filtros.
3. Un área usada en dos establecimientos conserva una sola identidad de catálogo.
4. Consultorios mantiene acceso directo; no se exige recorrer cuatro pantallas para editar uno conocido.
5. ADMIN puede editar datos del paciente sin permiso de Admisión, ni permiso para emitir FUA.
6. Registrar un paciente no requiere crear o volver a configurar establecimiento, área, consultorio o servicio.
7. El profesional conserva paciente → Admisión → consultorio → servicio → profesional; lo que puede seleccionar coincide con la validación de guardado.
8. Editar nombres, cerrar asignaciones o dar de baja configuraciones conserva el historial y los documentos existentes.
9. Un establecimiento inactivo no permite nuevas configuraciones o atenciones activas incompatibles; no se ejecutan bajas masivas implícitas.
10. Las nuevas pantallas muestran estados de carga, vacío, error, inactivo y sin permiso, con recuperación clara y controles utilizables en móvil.

## Orden de ejecución recomendado

Primero, crear las rutas y navegación canónicas y corregir la edición administrativa de pacientes. Después, completar establecimientos y separar la administración de áreas. Finalmente, conectar el recorrido contextual y verificar toda la configuración contra Admisión/FUA. Cada entrega debe quedar utilizable y comprobada antes de continuar.

El alcance no incluye rehacer Admisión, cambiar la organización territorial superior, introducir un área distinta por establecimiento ni reestructurar de una vez las tablas históricas de especialidades.
