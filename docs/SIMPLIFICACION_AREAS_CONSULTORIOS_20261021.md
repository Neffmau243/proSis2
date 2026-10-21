# Áreas nuevas y asignación de profesionales

## Objetivo y plan

Conservar los consultorios, servicios, profesionales y asignaciones de la semilla.
Facilitar el mismo recorrido para las áreas nuevas:

1. Registrar un área de atención, sin elegir una clasificación profesional.
2. Crear su consultorio en un establecimiento y, si corresponde, subconsultorios.
3. Asignar profesionales nuevos o existentes desde el consultorio. Completar el
   vínculo con el área en esa misma operación, sin volver a Personal.
4. Conservar los requisitos específicos anteriores y verificar regresiones,
   transacciones, permisos y el recorrido hasta Admisión.

## Componentes y responsabilidades

- `ConsultoriosPanel`: coordina catálogos, consultorios y asignaciones. Pasa datos
  a sus componentes y procesa sus eventos; `createChild` abre el alta con sede,
  área y padre seleccionados.
- `StaffCatalogsPanel` / `StaffCatalogSection`: ofrecen el modo de áreas, con
  búsqueda y acceso secundario a las especialidades anteriores. No reclasifican datos.
- `StaffCatalogForm`: en ese modo crea áreas directamente; al editar conserva
  el tipo anterior y envía `nombre` y `es_area`.
- `OfficeFormDialog`: muestra los datos de organización y agrupa los servicios
  en Servicios de atención. No ofrece el selector Especialidad requerida; los
  requisitos anteriores se conservan e informan en texto cuando corresponden.
- `OfficeAssignmentDialog`: recoge profesional, fechas y responsabilidad; explica
  el vínculo con el área o el requisito específico que sigue siendo obligatorio.
- `OfficeAssignmentService` / `OfficeRepository`: validan y guardan el vínculo,
  su auditoría y la asignación en una sola transacción.

## Comportamiento implementado

La pestaña habitual se llama **Áreas de atención** y el botón **Nueva área**.
No pide tipo de registro ni muestra la columna Tipo en la lista habitual. La
opción Mostrar también especialidades anteriores permite consultar y editar
sus nombres conservando su clasificación y referencias.

El alta habitual de consultorios solo necesita sede, código, nombre y área; el
padre es opcional. Nuevo subconsultorio preselecciona sede, área y padre. Los
servicios conservan sus valores predeterminados o heredados y pueden limitarse
desde Servicios de atención. Se retiró el selector Especialidad requerida y su
lista de opciones: aparecía por conservar un flujo de requisitos específicos
usado en la prueba de Cardiología, ajeno al alta habitual de áreas. Las
referencias anteriores se conservan al editar otros campos.

La petición de asignación puede enviar `vincular_area: true`. Requiere también
permiso `PROFESIONAL_GESTIONAR`. Si falta el área en la ficha del profesional y
no hay un requisito profesional distinto, se agrega el vínculo. La primera
calificación queda como principal solo si no existía otra principal. El vínculo
se audita y se revierte junto con la asignación si algo falla. No concede una
especialidad profesional adicional ni elude requisitos existentes.

Los clientes que omiten el nuevo campo conservan la validación anterior.
Las asignaciones y la herencia existentes conservan su funcionamiento. No hay
migraciones nuevas, reclasificaciones, eliminaciones ni cambios de la semilla.

## Prueba manual

1. Abrir `/configuracion/consultorios` con una cuenta ADMIN.
2. En Áreas de atención, crear un área con un nombre nuevo.
3. En Consultorios, crear un consultorio con esa área y un establecimiento.
4. Usar Nuevo subconsultorio, completar código y nombre, y guardar.
5. En Asignaciones del subconsultorio, asignar un profesional activo, con fecha
   de inicio vigente. Puede ser nuevo o ya tener otras áreas.
6. Revisar en Personal que el área se agregó sin reemplazar la principal previa.
7. En Admisión, seleccionar sede, subconsultorio y profesional.

Las especialidades de prueba anteriores se conservan con sus vínculos. No se
convierten automáticamente en áreas.

## Verificación realizada

- 89 pruebas de backend: oficinas, herencia, asignaciones, catálogos y permisos.
- 49 pruebas de interfaz: catálogos, alta de subconsultorios, asignaciones y Personal.
- 5 pruebas de integración en una base MySQL temporal: incluye área nueva,
  subconsultorio, profesionales con y sin área anterior, vínculo sin duplicados,
  conservación de la principal, Admisión y reversión real ante fallo de auditoría.
  La base temporal fue eliminada al terminar; no se utilizaron pacientes nuevos
  en la base de la aplicación.
- Compilación Vite y TypeScript, ESLint y Ruff correctos. La compilación conserva
  el aviso existente de tamaño de algunos paquetes.
- Comprobación visual del formulario de área y del subconsultorio en escritorio
  y a 390 × 844. Sin altas en la base de la aplicación durante esta inspección.
- Servidor local en el puerto 8000: `/health` devuelve 200 y OpenAPI contiene
  `vincular_area` en el contrato de asignación.

Evidencia en `docs/audits/areas-simplificadas-20261021.jpg`,
`nueva-area-simple-20261021.jpg`, `nueva-area-simple-movil-20261021.jpg`,
`subconsultorio-preseleccionado-20261021.jpg` y
`subconsultorio-preseleccionado-movil-20261021.jpg`.
