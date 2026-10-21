# Profesiones y especialidades de Personal

La pantalla `/configuracion/personal` incluye la pestaña **Profesiones y especialidades**
para las cuentas con permiso `PROFESIONAL_GESTIONAR` (actualmente ADMIN). También puede
abrirse directamente con `?tab=catalogos`.

- Una **profesión** describe la formación de la persona y se selecciona en su ficha.
- Una **especialidad** se asigna desde la acción Especialidades de la ficha. Si se
  asignan especialidades, se mantiene la regla de exactamente una principal.
- Crear estos registros no cambia cuentas, roles, asignaciones, áreas, servicios
  habilitados ni especialidades ya existentes. Una especialidad creada aquí no se
  convierte automáticamente en un área ni en un servicio de un consultorio.

## Alta

La profesión requiere nombre (2–100 caracteres). La especialidad requiere nombre
(2–150) y permite elegir Tipo de registro: Área o Especialidad. El tipo se guarda
en `especialidades.es_area`, tanto al crear como al editar. El grupo opcional se conserva en la API
por compatibilidad, pero no se muestra como campo ni como columna. Los nombres se guardan en mayúsculas
y con espacios normalizados. Se comprueban duplicados sin distinguir mayúsculas,
acentos ni espacios repetidos, incluyendo registros inactivos del mismo tipo.

## Presentación simplificada

Se muestra una tabla con selector entre Profesiones y Áreas y especialidades,
búsqueda y botón Nueva profesión o Nueva especialidad, siguiendo el patrón de los
paneles administrativos de Personal y Consultorios. El alta se abre en un modal
con Cancelar y Guardar en el pie. Al guardar se cierra el modal y se actualiza la
tabla; un error conserva el nombre dentro del modal. Mientras se guarda se bloquean
los envíos repetidos y el cierre. El foco inicial va al nombre y Enter permite
guardar. Los registros asistenciales heredados de las
tablas `Esp_*`, certificados y otras listas de servicios no se ofrecen como nuevas
especialidades en Personal. Las áreas se identifican con la etiqueta Área.

El catálogo completo se conserva para Consultorios y Atenciones. No se borran ni
se recodifican servicios como CANASTA TBC; los nombres de tablas ETL tampoco se
muestran como grupos al usuario. Si una ficha ya tenía asignado un servicio, su
edición conserva esa opción marcada como registro anterior. Una especialidad
nueva puede compartir nombre con un servicio heredado (por ejemplo Pediatría),
manteniendo códigos y usos separados.

La profesión recibe un ID autogenerado. La especialidad recibe un código interno
`ESP-` seguido de 16 caracteres derivados de su nombre normalizado; esto evita
duplicar altas simultáneas de la misma especialidad sin alterar códigos antiguos.
No se permite suministrar códigos existentes, estado ni campos adicionales.

Los nuevos endpoints son:

- `POST /api/v1/configuracion/catalogos-personal/profesiones`
- `POST /api/v1/configuracion/catalogos-personal/especialidades`

La lectura reutiliza los catálogos autenticados existentes en `/api/v1/catalogos`.
Cada alta y su auditoría se guardan en la misma transacción. La pestaña actualiza
su lista tras guardar y avisa al formulario de profesionales para recargar ambos
selectores sin perder el estado del formulario. La acción Editar cambia el nombre
y, en registros propios sin uso operativo, el tipo. Conserva IDs, códigos, grupo y
estado. Se auditan los datos anteriores y nuevos. La migración
`20261021_0040_staff_area_type` agrega la columna y marca las ocho áreas base
existentes. Los registros personalizados previos conservan su clasificación como
especialidad hasta que el administrador elija cambiarla; no se infiere por el nombre.

La edición usa `PATCH /api/v1/configuracion/catalogos-personal/profesiones/{id}` y
`PATCH /api/v1/configuracion/catalogos-personal/especialidades/{codigo}`.

## Eliminación

Cada fila ofrece Eliminar y abre una confirmación con el nombre del registro.
Los endpoints `DELETE` utilizan las mismas rutas individuales que la edición y
responden 204 cuando se elimina un registro sin uso. La eliminación es física,
permite reutilizar el nombre y conserva una auditoría DELETE en la misma transacción.
La API comprueba vínculos con profesionales, consultorios y atenciones, y responde
409 si el registro está en uso; las claves foráneas protegen también las asignaciones
concurrentes. Las áreas base que organizan los servicios están protegidas y los
servicios heredados no se pueden eliminar desde Personal. El error se muestra en
el modal sin quitar la fila. Solo ADMIN puede eliminar.

Las áreas personalizadas sin uso también se pueden eliminar. `es_area_base`
identifica las áreas del catálogo inicial: en ellas se bloquea cambiar el tipo y
eliminar porque sus servicios heredados dependen de esa clasificación. Un cambio
de tipo en un registro personalizado usado por consultorios o atenciones responde
409 y conserva tanto el nombre anterior como el tipo. Las asignaciones a la ficha
de un profesional mantienen el mismo código al cambiar el tipo.

## Vínculo con Consultorios

El formulario distingue Área asistencial, Especialidad requerida y Servicios de
atención. Una especialidad nueva de Personal puede seleccionarse como requisito
del consultorio sin convertirse en servicio. Si no se elige una especialidad, se
hereda la del consultorio padre o se exige el área. El servidor comprueba que el
profesional asignado tenga la calificación requerida. La profesión describe su
formación, pero no tiene una relación directa con el consultorio.

Las áreas nuevas aparecen como Área asistencial en Consultorios y como área en
la ficha profesional. Se aceptan en la API y pueden utilizarse en Admisión. Su
servicio inicial es el propio registro del área; los servicios heredados adicionales
de las áreas base conservan las relaciones de `app/domain/office.py`.

El acceso es otro vínculo: una ficha profesional puede existir sin cuenta. Para
emitir documentos clínicos, la cuenta con rol PROFESIONAL debe estar vinculada
al profesional responsable de la atención. Que otra cuenta pueda registrar una
admisión no la habilita para emitir el FUA de ese responsable.

El alta del profesional ahora permite seleccionar profesión, áreas y especialidades
en el mismo modal. Se agrupan visualmente las áreas y las especialidades, y cuando
hay más de una selección se permite elegir la principal. La ficha y sus vínculos
se crean con un solo POST y una única transacción del backend.

## Validación del 21 de octubre de 2026

- 82 pruebas backend en la revisión de simplificación: altas mediante HTTP y SQLite aislado, lectura desde los
  catálogos existentes, asignabilidad en fichas profesionales, auditoría,
  duplicados, permisos, reversión de transacciones y regresiones de consultorios.
- 41 pruebas frontend: panel simplificado, clasificación de servicios, formulario
  de profesionales, Personal y consultorios. Incluye la conservación de opciones
  históricas al editar una ficha.
- `vue-tsc --build`, compilación Vite, ESLint de los archivos modificados y Ruff.
- Revisión visual en escritorio y a 390 × 844, con creación de una especialidad
  usando el arnés sintético `frontend/tests/staff-catalogs-harness.html`.
- Comprobación de que el OpenAPI del servidor local incluye ambas rutas nuevas.

Las pruebas no crean registros en la base real. No se ejecutó integración contra
MySQL en esta comprobación; las pruebas transaccionales nuevas usan SQLite.

La revisión posterior del modal pasó 46 pruebas de interfaz de Personal,
Profesionales, Cuentas, Consultorios y el nuevo panel, además de compilación,
tipado y lint. Se verificó visualmente el alta de una profesión mediante Enter
en un viewport móvil y su aparición en la tabla, usando datos sintéticos.
