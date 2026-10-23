# Gestión de consultorios — 22/10/2026

La vista extiende la configuración administrativa existente en Vue 3 y Element Plus. El directorio y el detalle reutilizan las APIs de consultorios y el permiso `CONSULTORIO_GESTIONAR`; esta vista no requiere migraciones de base de datos.

## Flujo implementado

- `/configuracion/consultorios` muestra los consultorios principales con nombre, código, establecimiento, área y servicios visibles. La búsqueda local compara nombre, código, nombre del área y nombres de servicios; los filtros de establecimiento e inclusión de inactivos se envían a la API.
- Abrir el nombre o pulsar **Gestionar servicios** navega a `/configuracion/consultorios/:officeId`. El botón está en **Acciones**, tanto en la tabla de escritorio como en la lista móvil. El detalle muestra el contexto del consultorio, sus servicios habilitados y sus subconsultorios, con regreso al directorio. Conserva alta, edición, baja lógica y gestión de asignaciones profesionales.
- Un consultorio principal permite agregar un servicio existente del catálogo de su área o crear uno nuevo. El nuevo servicio queda en el catálogo y habilitado en ese consultorio.
- Quitar un servicio requiere confirmación y envía un `PATCH` únicamente con `servicios_codigos`. Quita la habilitación del consultorio; conserva el servicio en el catálogo global y las atenciones anteriores.
- En un consultorio hijo, la selección de servicios heredados se hace mediante **Editar consultorio**. La creación de servicios nuevos corresponde al consultorio principal y la selección queda acotada a los servicios permitidos por la jerarquía.

## Integración y mantenimiento

`ConsultoriosView.vue` recibe la prop opcional `officeId` y delega en `ConsultoriosPanel.vue`, que coordina directorio, detalle, catálogos y asignaciones. `OfficeServicesPanel.vue` gestiona los servicios del consultorio; `AddOfficeServiceForm.vue`, `OfficeFormDialog.vue` y `OfficesTable.vue` reutilizan formularios y presentación entre los flujos.

Las llamadas están centralizadas en `frontend/src/services/consultorios.ts`. Bajo el prefijo `/api/v1` se reutilizan:

| Recurso | Operaciones usadas |
| --- | --- |
| `/configuracion/consultorios` | `GET` de directorio y `POST` de alta. |
| `/configuracion/consultorios/{id}` | `PATCH` de edición y `DELETE` de baja lógica. |
| `/configuracion/consultorios/{id}/servicios` | `GET` de catálogo disponible y `POST` para agregar un servicio existente o nuevo. |
| `/configuracion/consultorios/{id}/profesionales` | Consulta y alta de asignaciones; cierre mediante la ruta existente de profesional, fecha de inicio y `/cierre`. |

Ambas rutas de la SPA declaran `CONSULTORIO_GESTIONAR`. La API mantiene sus comprobaciones de permisos y reglas de dominio.

## Continuidad visual

Se contrastaron `frontend/src/assets/main.css`, `AppLayout.vue` y los componentes de configuración existentes. La pantalla conserva la tipografía Inter/Segoe UI del proyecto, los fondos claros, los controles Element Plus y sus variables de texto, bordes y color primario. No se aprobó un sistema visual ni una familia de tokens nueva; no se crean ni modifican `PRODUCT.md` o `DESIGN.md` para esta extensión.

El directorio usa tabla en escritorio y lista en móvil. Los enlaces de nombre oscurecen el primario mediante `color-mix` con los tokens existentes. El diálogo de consultorio limita su altura al viewport, desplaza solo el cuerpo y conserva cabecera y pie visibles. La presentación móvil apila el contexto y permite envolver acciones y textos largos.

## Verificación y límites

Pasaron 34 pruebas de la vista, 13 de rutas y 59 pruebas de backend sobre servicios, jerarquía y catálogo de consultorios, además de comprobación de tipos, compilación y ESLint del alcance modificado. Las pruebas HTTP de backend usaron SQLite en memoria. La ejecución aislada se detuvo al llegar a estas pruebas y se completó correctamente fuera del aislamiento.

La revisión visual examinó las nueve capturas locales `.impeccable/review/consultorios-*.png`, incluidas vistas de directorio, detalle, formulario y agregado de servicio. Se revisaron escritorio de 1440 × 1000, móvil de 390 × 844 y el directorio a 320 × 844. El veredicto fue apto para entrega dentro del alcance inspeccionado.

Las capturas son evidencia local de revisión. El revisor no realizó una comprobación independiente de navegación por teclado, foco, mutaciones reales ni medición de contraste; la revisión visual no sustituye esas verificaciones.
