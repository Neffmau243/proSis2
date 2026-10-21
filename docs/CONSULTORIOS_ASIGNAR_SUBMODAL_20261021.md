# Asignación de profesionales en un submodal

El formulario de asignación estaba debajo de la tabla del consultorio. Una lista
larga desplazaba el formulario y dificultaba acceder a los campos y los botones.

Ahora Asignar profesional abre un diálogo independiente sobre la lista. El nuevo
componente `OfficeAssignmentDialog.vue` contiene selección del profesional, fechas,
responsable y validación. El panel conserva las peticiones al servidor y la lista.
El formulario indica el consultorio de destino y muestra sus errores dentro del
submodal. Cancelar regresa a la lista; guardar cierra el submodal y recarga las
asignaciones. Mientras se guarda se bloquean el cierre y los envíos duplicados.

La lista de asignaciones permite buscar por nombre y limita la altura de la tabla
a 45vh, con desplazamiento interno. Abrir o cancelar el formulario conserva la
búsqueda. Las búsquedas remotas de profesionales ignoran respuestas antiguas y
muestran los errores de red dentro del formulario.

No se cambiaron endpoints, permisos, criterios de especialidad ni reglas de
vigencia. No se crearon ni modificaron asignaciones reales durante esta revisión.

Verificación:

- 11 pruebas de Consultorios: alta y edición, asignar, cerrar asignación, lista
  vacía, búsqueda en 80 asignaciones, cancelar sin perder el filtro, conservar el
  formulario ante un rechazo y evitar duplicados o cierres mientras guarda.
- TypeScript, ESLint, compilación Vite y revisión del detector de diseño.
- Navegador real como administrador: lista de Medicina de C.S. ALTO SELVA ALEGRE,
  apertura del submodal, cancelación y búsqueda de ELSA GUILLEN TOCCAS.

Captura: `docs/audits/consultorios-asignar-submodal-20261021.png`.
