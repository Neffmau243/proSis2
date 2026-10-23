# Plan de mejora de la administración de consultorios

Fecha: 22/10/2026. Estado: propuesta; sin cambios en la aplicación ni en sus datos.

Actualización: la implementación posterior y sus verificaciones están documentadas en [Administración de consultorios y servicios](ADMIN_CONSULTORIOS_IMPLEMENTACION_20261022.md). Este documento conserva el diagnóstico y el plan originales.

## Objetivo y criterio principal

Hacer sencillo el CRUD administrativo de consultorios, sus servicios y sus profesionales, tomando como referencia la organización que ya utiliza `medico.demo` en admisión. El ejemplo funcional indicado por el usuario es un consultorio de Medicina con servicios como Medicina General y, según la configuración que corresponda, Obstetricia. Ese ejemplo no autoriza a reclasificar los datos ni a imponer otro modelo de negocio.

El administrador debe poder crear y consultar consultorios, editar sus datos, gestionar los servicios que ofrecen, mantener un catálogo general de esos servicios y administrar varios profesionales en cada contexto de atención. Tener tres, diez o más profesionales no debe requerir crear consultorios adicionales.

## Evidencia revisada y límites

- Revisión del código local actual, incluidos sus cambios pendientes, de los componentes de configuración, contratos HTTP, servicios, modelos y validaciones de admisión.
- Revisión de capturas existentes de directorio, detalle y creación de subconsultorios. Son evidencia previa y no una verificación visual de la sesión actual.
- El navegador de revisión llegó a `/login?redirect=/configuracion/consultorios/43`; no comparte la sesión administrativa del usuario. No se verificó en vivo el contenido actual del consultorio 43 ni la cuenta `medico.demo`.
- No se ejecutaron altas, ediciones, bajas o admisiones. Tampoco se ejecutaron pruebas: el entregable de esta revisión es el plan.

## Problemas concretos encontrados

1. **Dos formas de representar servicios en la interfaz.** El detalle muestra servicios habilitados y, aparte, subconsultorios cuya creación comienza eligiendo un servicio. El administrador necesita comprender esa diferencia técnica para completar tareas habituales.
2. **El mantenimiento general está fragmentado.** Existe gestión de catálogos de personal, pero excluye expresamente varios códigos de servicios asistenciales. No debe presentarse ese panel como si fuera el CRUD general de los servicios visibles en admisión.
3. **Crear y habilitar están acoplados.** El alta de un servicio desde un consultorio también lo habilita allí. Si ocurre dentro del formulario de subconsultorio, cancelar ese formulario no revierte el servicio ya guardado.
4. **Las asignaciones carecen de contexto de servicio explícito.** Se guardan por consultorio, profesional y fecha de inicio. Ya admiten múltiples profesionales; no se encontró un límite de dos. La consulta clínica también acepta asignaciones heredadas de consultorios padres.
5. **No se distingue suficientemente el alcance de las acciones.** Cambiar el nombre global de un servicio, quitarlo de un consultorio, darlo de baja y cerrar la asignación de un profesional son operaciones diferentes.
6. **Hay restricciones que la pantalla debe explicar.** La disponibilidad de servicios depende del área y de la jerarquía, y hay validaciones al editar configuraciones con asignaciones. El ejemplo Medicina/Obstetricia debe contrastarse con la configuración real antes de cambiar o conservar un filtro concreto.
7. **La recuperación de bajas está incompleta en el contrato revisado.** Hay baja lógica de consultorios, pero no se encontró una acción de reactivación expuesta en sus rutas actuales.

## Propuesta de navegación

Mantener la entrada **Configuración > Consultorios** y ofrecer dos destinos claramente identificados:

| Destino | Tarea principal | Información visible |
| --- | --- | --- |
| Consultorios | Crear, consultar, editar, dar de baja y reactivar | Nombre, establecimiento, estado, servicios y cantidad de profesionales |
| Catálogo de servicios | Consultar todos los servicios, registrar, editar y gestionar su estado | Nombre, código, área o relaciones actuales, estado y consultorios donde se utiliza |

El detalle `/configuracion/consultorios/:id` conserva su enlace y reúne la gestión cotidiana:

- Cabecera con nombre, establecimiento, estado y **Editar consultorio**.
- Una lista principal **Servicios de este consultorio**, con nombre del servicio, estado y cantidad de profesionales aplicables.
- Acciones por servicio: **Ver profesionales**, **Asignar profesionales** y **Quitar del consultorio**.
- Acción principal **Agregar servicio existente** y acción secundaria **Registrar nuevo servicio**. El formulario explica si también quedará habilitado en este consultorio.
- Los subconsultorios existentes siguen siendo accesibles. La jerarquía se presenta en una sección secundaria cuando sea relevante; no se convierte cada servicio en un subconsultorio ni se reclasifican registros automáticamente.

Dentro de **Ver profesionales**, mostrar una lista completa con búsqueda, estado de vigencia, inicio, fin y origen de la asignación. Distinguir las asignaciones directas de las heredadas y permitir navegar al origen para modificarlas. Los nombres deben resolverse aunque el profesional no esté entre los primeros resultados del buscador.

## Reglas de operación

- **Servicio asistencial y especialidad del personal:** respetar las distinciones del sistema actual. Registrar un servicio no concede automáticamente una cualificación profesional. En pantalla se usarán los nombres que reconoce el usuario de admisión.
- **Catálogo general:** permite registrar un servicio sin tener que crear antes un consultorio. Reutiliza los códigos existentes, evita duplicados normalizados y permite consultar los inactivos. No confundir este catálogo con otros catálogos de prestaciones del sistema.
- **Edición global:** renombrar un servicio conserva su identidad y avisa en qué consultorios se refleja el cambio. No se reescriben atenciones ni documentos históricos.
- **Habilitación local:** quitar un servicio de un consultorio no lo elimina del catálogo. Antes de guardar, mostrar dependencias y explicar qué debe resolverse si hay subconsultorios u otras relaciones afectadas.
- **Baja global:** dar de baja un servicio impide nuevos usos conforme a su vigencia y conserva el historial. Mostrar el alcance antes de confirmar. La eliminación definitiva se reserva a registros sin referencias, si se mantiene esa operación.
- **Profesionales:** permitir varios por servicio/contexto y varias asignaciones para un mismo profesional cuando sean válidas. Evitar duplicados y superposición de vigencias para la misma relación; cerrar una asignación no elimina al profesional.
- **Responsable:** separar visualmente esa función de la lista de profesionales. Conservar la regla actual de responsable por consultorio hasta que exista una necesidad confirmada de cambiar su alcance.
- **Permisos:** comprobar la autorización tanto en la interfaz como en la API. Asignar personal y modificar sus cualificaciones deben conservar controles diferenciados.
- **Formularios:** una acción de guardar debe tener un alcance explícito. Evitar altas ocultas dentro de formularios cancelables; mantener los datos escritos ante errores y ofrecer reintento.

## Plan de implementación por entregas

### 1. Fijar la referencia funcional

Con acceso a las sesiones correspondientes, registrar cómo ve `medico.demo` los consultorios, servicios y profesionales, y contrastarlo con el consultorio 43. Revisar datos y consultas sin crear atenciones en los registros reales. Identificar qué servicios son habilitaciones, cuáles están representados por subconsultorios y qué asignaciones son heredadas.

**Salida:** una matriz de consultorio → servicios visibles → profesionales disponibles por fecha, junto con las restricciones reales. Esta matriz será la referencia para evitar regresiones, incluida la combinación Medicina/Obstetricia mencionada por el usuario.

### 2. Ordenar la gestión de consultorios

Simplificar el directorio y el detalle conforme a la navegación propuesta. Reutilizar las operaciones actuales de alta, edición y baja; completar la reactivación con las mismas validaciones de establecimiento, jerarquía y servicios. Hacer visible la gestión de profesionales desde el contexto que el administrador reconoce.

**Salida:** CRUD de consultorios comprensible y acceso directo a servicios y profesionales, sin cambiar las selecciones de admisión.

### 3. Completar el catálogo general de servicios

Crear una superficie administrativa para los servicios asistenciales reales, con consulta, búsqueda, registro independiente, edición, baja y reactivación. Añadir las operaciones de API que falten. Reutilizar identidades del catálogo existente y las relaciones de área válidas; no duplicar los servicios bajo un catálogo nuevo.

Separar el guardado global del servicio de su habilitación en un consultorio. Cuando se soliciten ambas acciones juntas, deben tener una confirmación clara y un resultado consistente, sin guardados parciales inesperados.

**Salida:** administrar todos los servicios desde un lugar y habilitarlos en los consultorios correspondientes.

### 4. Hacer explícita la gestión de profesionales

Exponer las asignaciones y su origen desde cada servicio. Si un subconsultorio existente ya representa exactamente ese servicio, utilizar su contexto real sin crear otro registro. Las asignaciones del padre que hoy aplican a varios servicios deben seguir identificadas como heredadas; no copiarlas como si fueran asignaciones específicas.

Cuando la relación actual no permita expresar «este profesional atiende este servicio, pero no los otros del mismo consultorio», añadir una relación explícita de asignación al contexto consultorio + servicio. Esta ampliación debe ser localizada y conservar las asignaciones anteriores con su alcance actual. No requiere reemplazar la organización de consultorios ni migrar automáticamente personal a servicios por coincidencia de nombres.

Incluir selección de varios profesionales, búsqueda paginada, consulta de vigencias, corrección de asignaciones futuras y cierre de asignaciones vigentes con auditoría. Si se añade la relación específica, la consulta de profesionales y la validación del guardado de admisión deben usar la misma regla de elegibilidad.

**Salida:** poder gestionar tres o más profesionales en un servicio y comprender exactamente por qué aparecen disponibles en admisión.

### 5. Verificar y publicar el flujo completo

Realizar pruebas de API y persistencia sobre el CRUD, permisos, dependencias, vigencias y transacciones. En frontend, cubrir navegación y formularios según los comportamientos que cambien; comprobar tipos y compilación. Revisar escritorio y móvil, teclado, foco y mensajes.

Usar datos de prueba aislados para el recorrido completo: crear consultorio → registrar o seleccionar servicio → habilitarlo → asignar al menos tres profesionales → consultar y editar → cerrar una asignación → comprobar admisión → dar de baja y reactivar.

**Salida:** las configuraciones existentes mantienen su comportamiento y los cambios administrativos se reflejan correctamente en las nuevas selecciones de admisión.

## Archivos principales del alcance

- Interfaz: `frontend/src/components/configuracion/ConsultoriosPanel.vue`, `OfficeServicesPanel.vue`, `OfficeFormDialog.vue`, `OfficeAssignmentDialog.vue`, `StaffCatalogsPanel.vue` y `frontend/src/services/consultorios.ts`.
- Administración: `app/controllers/office.py`, `app/services/office.py`, `app/services/office_service.py` y contratos asociados.
- Compatibilidad: `app/domain/office.py`, `app/repositories/catalog.py`, `app/repositories/attention.py` y `app/services/attention_validation.py`.
- Modelos y migraciones: solo si la asignación específica por servicio o las operaciones de vigencia necesitan nuevos datos; no se presupone una reconstrucción del esquema.

## Criterios de aceptación

1. Un administrador puede completar el CRUD de consultorios desde una navegación clara, incluida la consulta de inactivos y la reactivación.
2. Puede consultar y mantener todos los servicios asistenciales desde un catálogo general, sin entrar primero en un consultorio.
3. Puede distinguir crear un servicio, habilitarlo en un consultorio, quitarlo de allí y darlo de baja globalmente.
4. Puede consultar y gestionar al menos tres profesionales para un mismo servicio/contexto, distinguiendo asignaciones directas e heredadas.
5. No es necesario crear un consultorio adicional por cada profesional ni duplicar servicios existentes.
6. La organización y las combinaciones válidas que hoy utiliza `medico.demo` se conservan; cualquier diferencia detectada se resuelve antes de activar una nueva regla.
7. La elegibilidad que muestra admisión coincide con la validación del servidor para la fecha seleccionada.
8. Cancelar un formulario no deja altas inesperadas, y las bajas o renombrados preservan el historial clínico.

Prioridad recomendada: ordenar consultorios y completar el catálogo de servicios primero; después completar la gestión contextual de profesionales y verificar el recorrido clínico. El alcance es mejorar la administración de la estructura actual.
